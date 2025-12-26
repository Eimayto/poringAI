import sqlite3
from flask import request, jsonify
from datetime import datetime
from ..db import get_db
from . import bp


@bp.route("/bike-return-zone", methods=["POST"])
def bike_return_zone():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSON 요청이 필요합니다."}), 400

    user_id = data.get("user_id")
    hub_name = data.get("hub_name")
    lat = data.get("lat")
    lon = data.get("lon")

    if not user_id:
        return jsonify({"success": False, "error": "user_id가 필요합니다."}), 400
    if not hub_name:
        return jsonify({"success": False, "error": "hub_name이 필요합니다."}), 400

    db = get_db()

    try:
        # (1) user 검증
        user = db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"success": False, "error": "존재하지 않는 사용자입니다."}), 404

        # (2) hub 조회
        hub = db.execute(
            "SELECT hub_id, hub_name FROM hubs WHERE hub_name = ?",
            (hub_name,)
        ).fetchone()
        if not hub:
            return jsonify({"success": False, "error": f"'{hub_name}' 허브를 찾을 수 없습니다."}), 404

        hub_id = hub["hub_id"]
        print(hub_name, hub_id)

        # (2-1) hub 전체 station 기준 수용량 계산
        station_stats = db.execute(
            """
            SELECT
                COALESCE(SUM(total_slots), 0) AS capacity,
                COALESCE(SUM(parked_slots), 0) AS current_bikes
            FROM stations
            WHERE hub_id = ?
            """,
            (hub_id,)
        ).fetchone()

        capacity = station_stats["capacity"]
        current_bikes = station_stats["current_bikes"]

        print("hub capacity:", capacity, "current bikes:", current_bikes)

        # Zone 반납 조건 판단
        # 허브 station이 꽉 찼을 때만 Zone 반납 허용
        if current_bikes < capacity:
            return jsonify({
                "success": False,
                "error": f"{hub_name} 허브는 아직 Station 반납이 가능합니다.",
                "current_bikes": current_bikes,
                "capacity": capacity
            }), 409
        
        # (2-2) Zone 선택 (실제 반납 위치)
        zone = db.execute(
            """
            SELECT zone_id
            FROM zones
            WHERE hub_id = ?
            LIMIT 1
            """,
            (hub_id,)
        ).fetchone()


        # (3) 진행 중 ride 조회
        ride = db.execute(
            """
            SELECT rental_id, bike_id, rental_start_date
            FROM rentals
            WHERE user_id = ?
                AND rental_end_date IS NULL
            ORDER BY rental_start_date DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        print("RIDE RAW:", dict(ride))
        if not ride:
            return jsonify({"success": False, "error": "진행 중인 대여가 없습니다."}), 409

        rental_id = ride["rental_id"]
        bike_id = ride["bike_id"]

        # (4) ride 종료
        end_at = datetime.now().isoformat()

        duration = None
        try:
            start_dt = datetime.fromisoformat(ride["rental_start_date"])
            duration = int((datetime.now() - start_dt).total_seconds() / 60)
        except Exception:
            pass
        
        dbg = db.execute("""
            SELECT rental_id, rental_end_date, typeof(rental_end_date) AS t
            FROM rentals
            WHERE rental_id = ?
            """, (rental_id,)).fetchone()
        print("DBG rental:", dict(dbg) if dbg else None)
        print(rental_id)

        cur = db.execute(
            """
            UPDATE rentals
            SET rental_end_date = ?,
                duration_minutes = ?,
                end_hub_id = ?,
                payment_status = 'Paid'
            WHERE rental_id = ?
            """,
            (end_at, duration, hub_id, rental_id)
        )
        if cur.rowcount != 1:
            db.rollback()
            return jsonify({"success": False, "error": "반납 실패: rentals 종료 업데이트가 적용되지 않았습니다."}), 500

        # (5) bike 상태 업데이트 + assigned_sz_id 기록
        db.execute(
            """
            UPDATE bikes
            SET status = 'Returned',
                assigned_hub_id = ?,
                assigned_sz_id = ?,
                where_parked = 'Zone',
                is_active = 1,
                last_rental_time = ?
            WHERE bike_id = ?
            """,
            (hub_id, zone["zone_id"], end_at, bike_id)
        )

        # zone 적재 증가
        db.execute(
            """
            UPDATE zones
                SET parked_slots = parked_slots + 1
                WHERE zone_id = ?
            """,
            (zone["zone_id"],)
        )

        db.commit()

        return jsonify({
            "success": True,
            "message": "Zone 반납이 완료되었습니다.",
            "bike_id": bike_id,
            "hub_name": hub_name,
            "duration_minutes": duration
        }), 200

    except sqlite3.Error as e:
        db.rollback()
        return jsonify({"success": False, "error": f"DB 오류: {e}"}), 500
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": f"오류 발생: {e}"}), 500


