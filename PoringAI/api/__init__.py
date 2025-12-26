from flask import Blueprint, render_template, request, url_for, session
import os, json, requests

bp = Blueprint("api", __name__)

from . import available_bikes
from . import generate_sentence
from . import available_nearby_bikes
from . import rent
from . import rent_recommand
from . import bike_return


def fetch_available_bikes(hub_name: str):
  """내부 API(/available-bikes) 호출"""
  api_url = url_for("api.available_bikes", _external=True)
  try:
    res = requests.get(api_url, params={"hub_name": hub_name}, timeout=5)
    return res.json(), res.status_code
  except Exception as e:
    return {"hub_name": hub_name, "found": False, "available_bikes": 0, "error": str(e)}, 500

    
def fetch_available_nearby_bikes(lat: float, lon: float):
  """
  내부 API /api/available-nearby-bikes를 호출해 가까운 허브 목록을 그대로 받아온다.
  서버 내부에서 거리 계산은 하지 않는다(요청만 전달).
  """
  api_url = url_for("api.available_nearby_bikes", _external=True)
  params = {"lat": lat, "lon": lon}

  try:
    res = requests.get(api_url, params=params, timeout=5)
    return res.json(), res.status_code
  except Exception as e:
    return {
        "hub_name" : None,
        "query": {"lat": lat, "lon": lon},
        "found": False,
        "available_bikes": 0,
        "error": str(e)
    }, 500

def fetch_rent_bike_normal(bike_id=None):
  if not bike_id:
    try:
      # 바이크 내가 고르기!
      return {
                "success": False,
                "error": "대여할 자전거(bike_id)가 선택되지 않았습니다."
            }, 400
    except Exception as e:
      return {
                "success": False,
                "error": f"bike_id 처리 중 오류: {e}"
            }, 500

  api_url = url_for("api.rent_bike_normal", _external=True)
  try:
    res = requests.post(api_url, json={"bike_id": bike_id, "user_id" : session.get('user_id')}, timeout=5)
    rent_json, rent_status = res.json(), res.status_code
  except Exception as e:
    return {
            "success": False,
            "error": f"rent-normal API 요청 중 오류가 발생했습니다: {e}"
        }, 500

  if rent_status >= 400:
    return rent_json, rent_status

  gen_url = url_for("api.generate_sentence", _external=True)

  try:
    gen_res = requests.post(gen_url,
                          json={
                              "messages_for_model": [{
                                "role": "system",
                                "content": (
                                    "너는 자전거 공유 서비스 안내 챗봇이야. "
                                    "주어진 API 응답(JSON)을 읽고, 사용자가 이해하기 쉬운 "
                                    "한국어 한두 문장으로 결과를 자연스럽게 설명해줘."
                                )
                                },
                                {
                                    "role": "user",
                                    "content": f"다음은 rent-normal API 응답이야:\n{json.dumps(rent_json, ensure_ascii=False)}"
                                }],
                              "data": {
                                "type": "rent_normal",
                                "api_response": rent_json
                              }
                          })  
    return gen_res.json(), gen_res.status_code
  except Exception as e:
    return {
            "success": False,
            "error": f"문장 생성 중 오류가 발생했습니다: {e}",
            "fallback": rent_json
        }, 500

def fetch_rent_recommand(hub_name=None):
    """
    내부 API /api/rent-recommand 호출
    추천 bike_id 목록을 받아온다.
    """
    api_url = url_for("api.rent_recommand", _external=True)

    params = {}
    if hub_name is not None:
        params['hub_name'] = hub_name
    

    try:
        res = requests.get(api_url, params=params, timeout=5)
        return res.json(), res.status_code
    except Exception as e:
        return {
            "success": False,
            "bike_ids": [],
            "error": f"rent_recommand API 요청 실패: {e}"
        }, 500

def fetch_bike_return_zone(hub_name=None, lat=None, lon=None):
    """
    hub_name만 받아서
    - bike-return-zone 호출
    - generate-sentence 호출
    """

    if not hub_name:
      return {"success": False, "error": "허브 이름이 필요합니다."}, 400

    api_url = url_for("api.bike_return_zone", _external=True)

    payload = {
      "user_id": session.get("user_id"),
      "hub_name": hub_name,
      "lat": lat,
      "lon": lon
    }

    try:
      res = requests.post(api_url, json=payload, timeout=5)
      ret_json, ret_status = res.json(), res.status_code
    except Exception as e:
      return {"success": False, "error": f"bike-return-zone 호출 실패: {e}"}, 500

    if ret_status >= 400:
      return ret_json, ret_status

    # 자연어 문장 생성
    gen_url = url_for("api.generate_sentence", _external=True)
    try:
      gen_res = requests.post(
        gen_url,
        json={
          "messages_for_model": [
            {
              "role": "system",
              "content": (
                "너는 자전거 공유 서비스 안내 챗봇이야. "
                "주어진 API 응답(JSON)을 읽고, "
                "사용자가 이해하기 쉬운 한국어 한두 문장으로 설명해."
              )
            },
            {
              "role": "user",
              "content": f"다음은 bike-return-zone API 응답이야:\n{json.dumps(ret_json, ensure_ascii=False)}"
            }
          ],
          "data": {
            "type": "bike_return_zone",
            "api_response": ret_json
          }
        },
        timeout=10
      )
      return gen_res.json(), gen_res.status_code

    except Exception as e:
      return {
        "success": False,
        "error": f"문장 생성 실패: {e}",
        "fallback": ret_json
      }, 500
    
def fetch_bike_return_station(hub_name=None, lat=None, lon=None):
  """
  hub_name만 받아서
  - bike-return-station 호출
  - generate-sentence 호출
  """

  if not hub_name:
    return {"success": False, "error": "허브 이름이 필요합니다."}, 400

  api_url = url_for("api.bike_return_station", _external=True)

  payload = {
    "user_id": session.get("user_id"),
    "hub_name": hub_name,
    "lat": lat,
    "lon": lon
  }

  try:
    res = requests.post(api_url, json=payload, timeout=5)
    ret_json, ret_status = res.json(), res.status_code
  except Exception as e:
    return {"success": False, "error": f"bike-return-station 호출 실패: {e}"}, 500

  if ret_status >= 400:
    return ret_json, ret_status

  # 자연어 문장 생성
  gen_url = url_for("api.generate_sentence", _external=True)
  try:
    gen_res = requests.post(
      gen_url,
      json={
        "messages_for_model": [
            {
              "role": "system",
              "content": (
                "너는 자전거 공유 서비스 안내 챗봇이야. "
                "주어진 API 응답(JSON)을 읽고, "
                "사용자가 이해하기 쉬운 한국어 한두 문장으로 설명해."
              )
            },
            {
              "role": "user",
              "content": f"다음은 bike-return-station API 응답이야:\n{json.dumps(ret_json, ensure_ascii=False)}"
            }
        ],
        "data": {
          "type": "bike_return_station",
          "api_response": ret_json
        }
      },
      timeout=10
    )
    return gen_res.json(), gen_res.status_code

  except Exception as e:
    return {
      "success": False,
      "error": f"문장 생성 실패: {e}",
      "fallback": ret_json
    }, 500
