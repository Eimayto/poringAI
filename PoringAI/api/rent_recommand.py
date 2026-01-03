# api/rent_recommand.py
from flask import jsonify, session, request
from . import bp
from ..db import get_db
from ..config import Config

FULL_BATTERY = Config.FULL_BATTERY

@bp.get("/rent-recommand")
def rent_recommand():
    hub_name = request.args.get('hub_name')
    if not hub_name:
        return jsonify({
            "success": False,
            "error": "최근 추천된 허브가 없습니다."
        }), 400

    db = get_db()

    hub = db.execute(
        "SELECT hub_id FROM hubs WHERE hub_name = ?",
        (hub_name,)
    ).fetchone()

    if not hub:
        return jsonify({
            "success": False,
            "error": "허브 정보를 찾을 수 없습니다."
        }), 404

    rows = db.execute(
        """
        SELECT bike_id
        FROM bikes
        WHERE assigned_hub_id = ?
          AND status = 'Returned'
          AND is_active = 1
          AND is_under_repair = 0
          AND is_retired = 0
        ORDER BY
          CASE
            WHEN where_parked = 'Station' AND battery_level >= ? THEN 1
            WHEN where_parked = 'Zone'    AND battery_level >= ? THEN 2
            WHEN where_parked = 'Station' AND battery_level <  ? THEN 3
            ELSE 4
          END ASC,
          battery_level DESC,
          (last_rental_time IS NOT NULL) ASC,  -- NULL 먼저
          last_rental_time ASC,
          bike_id ASC
        LIMIT 5
        """,
        (hub["hub_id"], FULL_BATTERY, FULL_BATTERY, FULL_BATTERY)
    ).fetchall()

    bike_ids = [r["bike_id"] for r in rows]

    return jsonify({
        "success": True,
        "hub_name": hub_name,
        "full_battery_threshold": FULL_BATTERY,
        "bike_ids": bike_ids
    }), 200
