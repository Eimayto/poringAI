import sqlite3
from flask import request, jsonify, g, session
from ..db import get_db
from . import bp
from datetime import datetime

@bp.route('/rent-normal', methods=['POST'])
def rent_bike_normal():
    """
    자전거 대여를 처리하는 API 엔드포인트. (ERD v_image_fbd067 기준)
    Request Body (JSON): { "bike_id": 123, "user_id": 1 }
    """
    
    # 1. 요청 본문(JSON)에서 user_id와 bike_id를 받습니다.
    # (ERD에서 bikes.bike_id, users.user_id, rentals.bike_id, rentals.user_id가 혼용되나,
    #  요청의 편의를 위해 bike_id, user_id로 통일합니다.)
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "JSON 요청이 필요합니다."}), 400

    user_id = data.get('user_id')
    bike_id = data.get('bike_id') # 이 ID가 ERD의 bikes.bike_id 라고 가정

    if not user_id:
        return jsonify({"success": False, "error": "user_id가 필요합니다."}), 400
    if not bike_id:
        return jsonify({"success": False, "error": "bike_id가 필요합니다."}), 400

    db = get_db()
    
    try:
        # 2. user_id가 DB(users 테이블)에 실재하는지 확인
        user = db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            return jsonify({"success": False, "error": "존재하지 않는 사용자입니다."}), 404

        # 3. rentals 에서 이 user 가 아직 반납 안 한 대여가 있는지 확인
        #    기준: rental_end_date IS NULL 이면 아직 진행 중
        active_rental = db.execute(
            """
            SELECT rental_id, rental_start_date
              FROM rentals
             WHERE user_id = ?
               AND rental_end_date IS NULL
             ORDER BY rental_start_date DESC
             LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        if active_rental:
            # 아직 진행 중인 대여가 있다면 새로 빌릴 수 없음
            return jsonify({
                "success": False,
                "error": "아직 반납하지 않은 대여가 있습니다.",
                "active_rental_id": active_rental["rental_id"]
            }), 409
        
        # 4. 자전거의 현재 상태, 주차 위치, 할당 ID 확인 (bikes 테이블)
        bike = db.execute(
            """
            SELECT assigned_hub_id, assigned_sz_id, where_parked, status 
            FROM bikes 
            WHERE bike_id = ?
            """,
            (bike_id,)
        ).fetchone()

        if not bike:
            return jsonify({"success": False, "error": "존재하지 않는 자전거입니다."}), 404

        # ERD의 status ('Using', 'Returned', 'Returning') 기준
        if bike['status'] != 'Returned':
            return jsonify({"success": False, "error": "이미 대여 중이거나 이용 불가능한 자전거입니다."}), 409

        # 5. 대여 기록(rentals)에 사용할 변수 준비
        where_parked = bike['where_parked'] # 'Station' 또는 'Zone'
        parked_location_id = bike['assigned_hub_id'] # hub_id 가져오기
        parked_sz_id = bike['assigned_sz_id']   # station/zone id 가져오기
        start_at_iso = datetime.now().isoformat()
        start_hub_id = parked_location_id

        if not parked_sz_id:
            return jsonify({"success": False, "error": "parked_sz_id가 존재하지 않는 자전거입니다."}), 404

        # 6. 주차 위치(station/zone)의 parked_slots 감소 + hub_id 조회
        if where_parked == "Station":
            if not parked_location_id:
                raise Exception("Station 대여인데 assigned_hub_id(hub_id)가 없습니다.")

            db.execute(
                """
                UPDATE stations
                   SET parked_slots = parked_slots - 1
                 WHERE station_id = ?
                   AND parked_slots > 0
                """,
                (parked_sz_id,)
            )
            print(parked_sz_id)

        elif where_parked == "Zone":
            if not parked_location_id:
                raise Exception("Zone 대여인데 assigned_hub_id(zone_id)가 없습니다.")

            db.execute(
                """
                UPDATE zones
                   SET parked_slots = parked_slots - 1
                 WHERE zone_id = ?
                   AND parked_slots > 0
                """,
                (parked_sz_id,)
            )

        else:
            return jsonify({
                "success": False,
                "error": "자전거가 허브나 존에 주차된 상태가 아닙니다."
            }), 409

        if start_hub_id is None:
            raise Exception(f"{where_parked} (ID: {parked_location_id})에 해당하는 hub_id를 찾을 수 없습니다.")

        # 7. bikes 상태 업데이트 (대여 중으로 변경)
        db.execute(
            """
            UPDATE bikes
               SET status = 'Using',
                   assigned_hub_id = NULL,
                   where_parked = NULL,
                   assigned_sz_id = NULL,
                   is_active = 0,
                   last_rental_time = ?
             WHERE bike_id = ?
            """,
            (start_at_iso, bike_id)
        )

        # 8. rentals 에 새 대여 로그 추가
        #    NOT NULL 컬럼: bike_id, user_id, rental_start_date, payment_status
        #    payment_status 는 초기값을 'Pending' 으로 가정
        cursor = db.execute(
            """
            INSERT INTO rentals (
                bike_id,
                user_id,
                rental_start_date,
                start_hub_id,
                payment_status
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (bike_id, user_id, start_at_iso, start_hub_id, "Pending")
        )

        new_rental_id = cursor.lastrowid

        # 9. 커밋
        db.commit()

        return jsonify({
            "success": True,
            "message": "대여가 시작되었습니다.",
            "rental_id": new_rental_id,
            "start_at": start_at_iso,
            "user_id": user_id,
            "bike_id": bike_id
        }), 201

    except sqlite3.Error as e:
        db.rollback()
        return jsonify({"success": False, "error": f"데이터베이스 오류: {e}"}), 500
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": f"작업 중 오류 발생: {e}"}), 500