# api/rent_recommand.py
from flask import jsonify, session, request
from . import bp
from ..db import get_db
from ..config import Config

FULL_BATTERY = Config.FULL_BATTERY
LOW_BATTERY_INCENTIVE = Config.LOW_BATTERY_INCENTIVE

@bp.get("/rent-recommand")
def rent_recommand():
    '''
    아래와 같이 반환
    {
        "success": true,
        "hub_name": "정문 앞",
        "rent_bike_id": 101,                 // 지금 빌리라고 추천하는 1대
        "rent_category": 1,                  // 1/2/3/4 중 어디인지
        "mission": {
            "enabled": true,
            "low_battery_bike_id": 205,        // 4번(존+배터리부족)
            "target_station_id": 3,            // 꽂을 스테이션
            "incentive": { "type": "POINT", "amount": 300 }
        }
    }
    '''
    hub_name = request.args.get('hub_name')
    if not hub_name:
        return jsonify({"success": False, "error": "최근 추천된 허브가 없습니다."}), 400

    db = get_db()

    hub = db.execute(
        "SELECT hub_id FROM hubs WHERE hub_name = ?",
        (hub_name,)
    ).fetchone()
    if not hub:
        return jsonify({"success": False, "error": "허브 정보를 찾을 수 없습니다."}), 404

    hub_id = hub["hub_id"]

    # 1) 대여 추천 1대(1>3>>2>4)
    rent_row = db.execute(
        """
        SELECT bike_id,
               CASE
                 WHEN where_parked='Station' AND battery_level_int >= ? THEN 1
                 WHEN where_parked='Zone'    AND battery_level_int >= ? THEN 3
                 WHEN where_parked='Station' AND battery_level_int <  ? THEN 2
                 ELSE 4
               END AS category
        FROM bikes
        WHERE assigned_hub_id = ?
          AND status = 'Returned'
          AND is_active = 1
          AND is_under_repair = 0
          AND is_retired = 0
        ORDER BY
          CASE
            WHEN where_parked='Station' AND battery_level_int >= ? THEN 1
            WHEN where_parked='Zone'    AND battery_level_int >= ? THEN 2
            WHEN where_parked='Station' AND battery_level_int <  ? THEN 3
            ELSE 4
          END ASC,
          battery_level_int DESC,
          (last_rental_time IS NOT NULL) ASC,
          last_rental_time ASC,
          bike_id ASC
        LIMIT 1
        """,
        (FULL_BATTERY, FULL_BATTERY, FULL_BATTERY,
         hub_id,
         FULL_BATTERY, FULL_BATTERY, FULL_BATTERY)
    ).fetchone()

    if not rent_row:
        return jsonify({"success": False, "error": "대여 가능한 자전거가 없습니다."}), 200

    rent_bike_id = rent_row["bike_id"]
    rent_category = int(rent_row["category"])

    # 2) 미션: 4번(Zone+배터리부족) + 꽂을 빈 Station 하나
    station = db.execute(
        """
        SELECT station_id
        FROM stations
        WHERE hub_id = ?
          AND parked_slots < total_slots
        ORDER BY (total_slots - parked_slots) DESC, station_id ASC
        LIMIT 1
        """,
        (hub_id,)
    ).fetchone()

    mission = {"enabled": False}

    if station:
        low = db.execute(
            """
            SELECT bike_id
            FROM bikes
            WHERE assigned_hub_id = ?
              AND status = 'Returned'
              AND is_active = 1
              AND is_under_repair = 0
              AND is_retired = 0
              AND where_parked = 'Zone'
              AND battery_level_int < ?
            ORDER BY battery_level_int ASC, last_rental_time ASC, bike_id ASC
            LIMIT 1
            """,
            (hub_id, FULL_BATTERY)
        ).fetchone()

        if low and int(low["bike_id"]) != int(rent_bike_id):
            mission = {
                "enabled": True,
                "low_battery_bike_id": low["bike_id"],
                "target_station_id": station["station_id"],
                "incentive": {"type": "POINT", "amount": LOW_BATTERY_INCENTIVE}
            }

    return jsonify({
        "success": True,
        "hub_name": hub_name,
        "full_battery_threshold": FULL_BATTERY,
        "rent_bike_id": rent_bike_id,
        "rent_category": rent_category,
        "mission": mission
    }), 200