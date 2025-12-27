from flask import request, jsonify, url_for
import os, json, requests
from ..db import get_db
from . import bp
from math import radians, sin, cos, sqrt, atan2


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

@bp.route("/available-bikes", methods=["GET"])
def available_bikes():
  hub_name = request.args.get("hub_name")
  lat = request.args.get("lat")
  lon = request.args.get("lon")
  
  if not hub_name:
    return jsonify({"error": "hub_name 쿼리 파라미터가 필요합니다."}), 400

  db = get_db()
  hub = db.execute(
      """
      SELECT hub_id, latitude, longitude
      FROM hubs
      WHERE hub_name = ?
      """,
      (hub_name,)
    ).fetchone()
  if not hub:
    return jsonify({"hub_name" : hub_name, "found" : False, "available_bikes": 0, "error" : f"{hub_name} 허브를 찾을 수 없습니다."}), 200

  row = db.execute(
    '''
    SELECT COUNT(*) AS cnt
    FROM bikes
    WHERE assigned_hub_id = ?
      AND is_active = 1
      AND is_under_repair = 0
      AND is_retired = 0
      AND status = 'Returned'
    ''',
    (hub["hub_id"], ),
  ).fetchone()

  data = {
    "hub_name" : hub_name,
    "found" : True,
    "available_bikes" : int(row["cnt"])
  }
  print(data)
  
  # 거리 계산 (lat/lon이 들어온 경우만)
  if lat is not None and lon is not None and hub["latitude"] and hub["longitude"]:
    try:
      dist = haversine_m(
          float(lat), float(lon),
          hub["latitude"], hub["longitude"]
      )
      data["distance"] = int(dist)  # meter
    except Exception:
      data["distance"] = None

  """내부 API(/available-bikes) 호출"""
  api_url = url_for("api.generate_sentence", _external=True)
  try:
    res = requests.post(api_url, 
                        json={"messages_for_model": [
                            {"role": "system", "content":"You are Poring-AI, a chatbot for a bike rental service. You will engage in natural conversation with the user to tell them the number of available bikes at a specified location. If there are no bikes at that location, recommend the nearest alternative station. Rules: 1) Always maintain a friendly and warm tone. 2) Keep answers concise, limited to 1-2 sentences. 3) Do not provide unnecessary explanations, background information, or verbose descriptions. 4) Avoid an overly humorous or casual tone. 5) Always respond in short, clear Korean sentences."},
                            {"role":"user", "content": f"다음 값을 자연스럽게 한문장으로 바꿔줘 허브이름 : {data['hub_name']}, 자전거 개수 : {data['available_bikes']}"}
                            ],
                            "data" : data},
                        timeout=5)
    return res.json()
  except Exception as e:
    data["error"] = str(e)
    return jsonify(data)