# menu3.py
from flask import Blueprint, render_template, session, redirect, url_for
from .db import get_db

bp = Blueprint('menu3', __name__, url_prefix='/menu3')


@bp.route('/')
def menu3():
    # 로그인 안 했으면 로그인 페이지로
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login.login'))

    db = get_db()

    # 1) 내 기본 정보(users)
    user = db.execute(
        """
        SELECT
            user_id,
            total_usage_count,
            avg_usage_minutes,
            final_paid_amount,
            points,
            user_type,
            nationality_type,
            position_type,
            division,
            join_date,
            verify_date
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    # user 테이블에 없으면 세션 꼬임 가능 -> 로그아웃 처리
    if user is None:
        session.clear()
        return redirect(url_for('login.login'))

    # 2) 요약 통계(rentals 기반)
    # - 총 대여 횟수, 총 이용시간(분), 총 결제(최종), 결제 성공 횟수 등
    summary = db.execute(
        """
        SELECT
            COUNT(*) AS rental_count,
            COALESCE(SUM(duration_minutes), 0) AS total_minutes,
            COALESCE(SUM(final_paid_amount), 0) AS total_paid,
            COALESCE(SUM(earned_point), 0) AS total_earned_point,
            COALESCE(SUM(used_point), 0) AS total_used_point,
            SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) AS paid_count,
            SUM(CASE WHEN payment_status = 'Failed' THEN 1 ELSE 0 END) AS failed_count
        FROM rentals
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()

    # 3) 최근 대여 내역 10개 (자전거/허브명까지 조인)
    # ERD상 hubs는 hub_id가 PK인데, rentals에는 start_hub_id/end_hub_id가 있음
    recent_rentals = db.execute(
        """
        SELECT
            r.rental_id,
            r.rental_code,
            r.rental_start_date,
            r.rental_end_date,
            r.duration_minutes,
            r.payment_status,
            r.payment_method,
            r.final_paid_amount,
            r.used_point,
            r.earned_point,

            b.serial_number AS bike_serial,

            hs.hub_name AS start_hub_name,
            he.hub_name AS end_hub_name
        FROM rentals r
        LEFT JOIN bikes b ON b.bike_id = r.bike_id
        LEFT JOIN hubs hs ON hs.hub_id = r.start_hub_id
        LEFT JOIN hubs he ON he.hub_id = r.end_hub_id
        WHERE r.user_id = ?
        ORDER BY r.rental_start_date DESC
        LIMIT 10
        """,
        (user_id,)
    ).fetchall()

    return render_template(
        "menu3.html",
        user=user,
        summary=summary,
        recent_rentals=recent_rentals
    )
