from flask import request, jsonify, url_for
import os, json, requests
from ..db import get_db
from . import bp

@bp.route("/available-nearby-bikes", methods=["GET"])
def available_nearby_bikes():
  """
  사용자의 현재 위치(lat, lon)를 받아, 내부 /api/available-nearby-bikes를 호출하고
  가장 가까운 허브의 이용가능 자전거 대수만 요약해서 반환한다.

  예:
    GET /api/closest-available-bikes?lat=36.0123&lon=129.3210&r_km=1.0&limit=10
  응답 형태:
  {
    "query": {...},
    "closest": {
      "hub_id": ...,
      "hub_name": "...",
      "distance_km": 0.123,
      "available_bikes": 7
    },
    "count_examined": 5
  }
  """
  # 필수 파라미터
  lat_raw = request.args.get("lat")
  lon_raw = request.args.get("lon")
  if lat_raw is None or lon_raw is None:
      return jsonify({"error": "lat, lon 쿼리 파라미터가 필요합니다 (float)"}), 400

  try:
      lat = float(lat_raw)
      lon = float(lon_raw)
  except ValueError:
      return jsonify({"error": "lat, lon은 float로 전달되어야 합니다"}), 400

  # 선택 파라미터
  r_km_raw = request.args.get("r_km")
  limit_raw = request.args.get("limit")
  radius_km = None
  limit = None
  try:
      if r_km_raw is not None:
          radius_km = float(r_km_raw)
  except ValueError:
      pass
  try:
      if limit_raw is not None:
          limit = int(limit_raw)
  except ValueError:
      pass

  try:
      data, status = _fetch_available_nearby_bikes(lat, lon, radius_km, limit)
  except Exception as e:
      return jsonify({"error": f"internal call failed: {type(e).__name__}: {e}"}), 502

  if status != 200:
      # 내부 API 에러를 투명하게 전달
      return jsonify({"error": "available-nearby-bikes upstream error", "upstream": data}), status

  # 기대 형식: {"hubs":[ {...}, ... ], "count": N, ...}
  hubs = (data or {}).get("hubs", [])
  if not hubs:
      return jsonify({
          "query": {"lat": lat, "lon": lon, "r_km": radius_km, "limit": limit},
          "closest": None,
          "count_examined": 0,
          "message": "근처 허브가 없습니다."
      }), 200

  # 첫 번째가 '가장 가까운' 허브라고 가정(정렬은 내부 API가 수행)
  top = hubs[0]
  # 내부 API가 내려주는 키 이름에 맞춰 안전하게 꺼내기
  closest = {
      "hub_id": top.get("hub_id"),
      "hub_name": top.get("hub_name"),
      "distance_km": top.get("distance_km"),     # 내부 API가 제공한다고 가정
      "available_bikes": top.get("available_bikes")
  }

  return jsonify({
      "query": {"lat": lat, "lon": lon, "r_km": radius_km, "limit": limit},
      "closest": closest,
      "count_examined": len(hubs)
  }), 200