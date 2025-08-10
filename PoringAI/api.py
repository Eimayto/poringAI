# api/api.py
from flask import (
  Blueprint, request, jsonify
)
from .db import get_db

bp = Blueprint("api", __name__)

@bp.route("/available-bikes", methods=["GET"])
def available_bikes():
  hub_name = request.args.get("hub_name")
  if not hub_name:
    return jsonify({"error": "hub_name 쿼리 파라미터가 필요합니다."}), 400

  db = get_db()
  hub = db.execute("SELECT hub_id FROM Hub WHERE name = ?", (hub_name,)).fetchone()
  if not hub:
    return jsonify({"hub_name" : hub_name, "found" : False, "available_bikes": 0}), 200

  row = db.execute(
    '''
    SELECT COUNT(*) AS cnt
    FROM Bike
    WHERE current_hub_id = ? AND (is_available = 1)
    ''',
    (hub["hub_id"], ),
  ).fetchone()

  return jsonify({
    "hub_name" : hub_name,
    "found" : True,
    "available_bikes" : int(row["cnt"])
  }), 200