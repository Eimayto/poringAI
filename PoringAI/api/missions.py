# api/missions.py
import sqlite3
from flask import request, jsonify
from . import bp
from ..db import get_db
from math import radians, sin, cos, atan2, sqrt
from ..config import Config

RETURN_DISTACNE = Config.RETURN_DISTANCE

def haversine_m(lat1, lon1, lat2, lon2):
    '''
    위도 차이를 meter로 바꿔주는 함수
    '''
    R = 6371000  # 지구 반지름 (meter)
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

@bp.post("/missions/prepare")
def missions_prepare():
    """
    대여 완료 직후, 추천된 미션을 DB에 저장(생성)한다.
    - menu1.py는 DB 직접 접근 X
    - rent_recommand.py는 READ ONLY 유지

    요청 JSON:
    {
      "user_id": 1,
      "low_battery_bike_id": 205,
      "target_station_id": 3,      # optional
      "reward": 300
    }

    응답:
    {
      "success": true,
      "mission_id": 10,
      "created": true|false
    }
    """

    data = request.get_json() or {}

    user_id = data.get("user_id")
    low_bike_id = data.get("low_battery_bike_id")
    target_station_id = data.get("target_station_id")  # None 가능
    reward = data.get("reward")

    if not user_id or not low_bike_id or reward is None:
        return jsonify({
            "success": False,
            "error": "user_id, low_battery_bike_id, reward가 필요합니다."
        }), 400

    db = get_db()

    try:
        # (1) 사용자 존재 확인
        user = db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"success": False, "error": "존재하지 않는 사용자입니다."}), 404

        # (2) 이미 진행 중인 미션이 있으면 새로 만들지 않음
        existing = db.execute(
            """
            SELECT mission_id
            FROM missions
            WHERE user_id = ?
              AND status = 'ACTIVE'
            """,
            (user_id,)
        ).fetchone()

        if existing:
            return jsonify({
                "success": True,
                "mission_id": existing["mission_id"],
                "created": False
            }), 200
        
        # (2-1) 해당 자전거로 이미 ACTIVE 미션이 있는지 확인
        dup = db.execute(
            """
            SELECT mission_id
            FROM missions
            WHERE low_battery_bike_id = ?
            AND status = 'ACTIVE'
            """,
            (low_bike_id,)
        ).fetchone()

        if dup:
            return jsonify({
                "success": False,
                "error": "이미 다른 사용자가 이 자전거에 대한 미션을 진행 중입니다."
            }), 409
        
        # (2-2) 저배터리 자전거가 실제로 Zone에 있는지 + 어느 hub인지 확인
        bike = db.execute(
            """
            SELECT bike_id, assigned_hub_id, where_parked, status
            FROM bikes
            WHERE bike_id = ?
              AND is_active = 1
              AND is_under_repair = 0
              AND is_retired = 0
            """,
            (low_bike_id,)
        ).fetchone()

        if not bike:
            return jsonify({"success": False, "error": "자전거 정보를 찾을 수 없습니다."}), 404

        if bike["status"] != "Returned" or bike["where_parked"] != "Zone":
            return jsonify({
                "success": False,
                "error": "미션 대상 자전거가 현재 Zone에 있지 않습니다."
            }), 409

        hub_id = bike["assigned_hub_id"]

        # (2-3) Zone parked_slots 1 감소 (0 미만 방지)
        upd = db.execute(
            """
            UPDATE zones
            SET parked_slots = parked_slots - 1
            WHERE hub_id = ?
              AND is_active = 1
              AND parked_slots > 0
            """,
            (hub_id,)
        )

        if upd.rowcount == 0:
            # zone row가 없거나 parked_slots가 0인 상태
            return jsonify({
                "success": False,
                "error": "Zone 수량을 감소시킬 수 없습니다(Zone 없음 또는 수량 0)."
            }), 409

        # (3) 미션 생성
        cur = db.execute(
            """
            INSERT INTO missions (user_id, low_battery_bike_id, target_station_id, reward, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
            """,
            (user_id, low_bike_id, target_station_id, reward)
        )
        db.commit()

        return jsonify({
            "success": True,
            "mission_id": cur.lastrowid,
            "created": True
        }), 201

    except sqlite3.Error as e:
        db.rollback()
        return jsonify({"success": False, "error": f"DB 오류: {e}"}), 500
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": f"오류 발생: {e}"}), 500

@bp.post("/missions/plug")
def missions_plug():
    data = request.get_json() or {}

    user_id = data.get("user_id")
    bike_id = data.get("bike_id")
    station_id = data.get("station_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not user_id or not bike_id or not station_id:
        return jsonify({"success": False, "error": "필수 값 누락"}), 400

    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "필수 값 누락(latitude, longitude)"}), 400

    try:
        user_id = int(user_id)
        bike_id = int(bike_id)
        station_id = int(station_id)
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "파라미터 타입이 올바르지 않습니다."}), 400

    db = get_db()

    try:
        # 1) ACTIVE 미션 확인
        mission = db.execute(
            """
            SELECT mission_id, reward, target_station_id
            FROM missions
            WHERE user_id = ?
              AND low_battery_bike_id = ?
              AND status = 'ACTIVE'
            """,
            (user_id, bike_id)
        ).fetchone()

        if not mission:
            return jsonify({
                "success": False,
                "error": "NO_ACTIVE_MISSION"
            }), 409

        if mission["target_station_id"] != station_id:
            return jsonify({"success": False, "error": "WRONG_STATION"}), 200
        
        # 2) station_id가 속한 hub의 위도/경도 가져오기
        hub_row = db.execute(
            """
            SELECT h.latitude AS hub_lat, h.longitude AS hub_lon
            FROM stations s
            JOIN hubs h ON h.hub_id = s.hub_id
            WHERE s.station_id = ?
              AND s.is_active = 1
            """,
            (station_id,)
        ).fetchone()

        if not hub_row or hub_row["hub_lat"] is None or hub_row["hub_lon"] is None:
            return jsonify({"success": False, "error": "STATION_HUB_LOCATION_NOT_FOUND"}), 404

        hub_lat = float(hub_row["hub_lat"])
        hub_lon = float(hub_row["hub_lon"])

        # 3) 거리 체크 (현재 위치 vs 허브 위치)
        dist_m = haversine_m(latitude, longitude, hub_lat, hub_lon)

        if dist_m > RETURN_DISTACNE:
            return jsonify({
                "success": False,
                "error": "자전거가 반납 위치에 있지 않습니다.",
                "distance_m": round(dist_m, 1),
                "limit_m": RETURN_DISTACNE
            }), 409

        # 4) 자전거 상태 변경
        db.execute(
            """
            UPDATE bikes
            SET where_parked = 'Station',
                assigned_sz_id = ?,
                status = 'Returned'
            WHERE bike_id = ?
            """,
            (station_id, bike_id)
        )

        # 5) station 적재 증가
        db.execute(
            """
            UPDATE stations
            SET parked_slots = parked_slots + 1
            WHERE station_id = ?
            """,
            (station_id,)
        )

        # 6) 미션 완료 + 보상
        db.execute(
            "UPDATE missions SET status='DONE' WHERE mission_id=?",
            (mission["mission_id"],)
        )

        db.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (mission["reward"], user_id)
        )

        db.commit()

        return jsonify({
            "success": True,
            "reward": mission["reward"]
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    
@bp.get("/missions/active")
def missions_active():
    """
    현재 사용자의 ACTIVE 미션 1개 조회
    """
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"success": False, "error": "user_id 필요"}), 400

    db = get_db()

    mission = db.execute(
        """
        SELECT mission_id,
               low_battery_bike_id,
               target_station_id,
               reward,
               status
        FROM missions
        WHERE user_id = ?
          AND status = 'ACTIVE'
        ORDER BY mission_id DESC
        LIMIT 1
        """,
        (user_id,)
    ).fetchone()

    if not mission:
        return jsonify({"success": True, "mission": None}), 200

    return jsonify({
        "success": True,
        "mission": dict(mission)
    }), 200