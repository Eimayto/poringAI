# api/rent_recommand.py
from flask import jsonify, session, request
from . import bp
from ..db import get_db

@bp.get("/rent-recommand")
def rent_recommand():
    hub_name = request.args.get('hub_name')
    if not hub_name:
        print(request.args)
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

    bikes = db.execute(
        """
        SELECT bike_id
        FROM bikes
        WHERE assigned_hub_id = ?
          AND status = 'Returned'
          AND is_active = 1
          AND is_under_repair = 0
          AND is_retired = 0
        LIMIT 5
        """,
        (hub["hub_id"],)
    ).fetchall()

    bike_ids = [b["bike_id"] for b in bikes]

    print(bike_ids, hub_name)

    return jsonify({
        "success": True,
        "hub_name": hub_name,
        "bike_ids": bike_ids
    }), 200
