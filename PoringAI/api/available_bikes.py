from flask import request, jsonify, url_for
import os, json, requests
from ..db import get_db
from . import bp

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

def fetch_available_bikes(hub_name: str):
  """내부 API(/available-bikes) 호출"""
  api_url = url_for("api.available_bikes", _external=True)
  try:
    res = requests.get(api_url, params={"hub_name": hub_name}, timeout=5)
    return res.json()
  except Exception as e:
    return {"hub_name": hub_name, "found": False, "available_bikes": 0, "error": str(e)}