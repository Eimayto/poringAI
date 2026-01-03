from flask import Blueprint, render_template, request, url_for, session, redirect
from collections import deque
import time
import os, json, requests
from .api import (
    fetch_available_bikes, 
    fetch_available_nearby_bikes, 
    fetch_rent_bike_normal, 
    fetch_rent_recommand, 
    fetch_bike_return_zone,
    fetch_bike_return_station,
    fetch_mission_prepare,
)
from datetime import datetime
from .classify_intent import (
  classify_return_intent,
  classify_yes_no,
  classify_rent_intent
)
from .config import Config

# 캐시 세팅
HIST_KEY = Config.HIST_KEY
MAX_MSGS = Config.MAX_MSGS
TTL_SEC = Config.TTL_SEC
WAITING_RENT_CONFORM = Config.WAITING_RENT_CONFORM
RECOMMAND_DISTANCE = Config.RECOMMAND_DISTANCE
RETURN_DISTANCE = Config.RETURN_DISTANCE
WAITING_RETURN_TYPE = Config.WAITING_RETURN_TYPE
RETURN_CTX_KEY = Config.RETURN_CTX_KEY
HUB_DESCRIPTION = Config.HUB_DESCRIPTION
WAITING_MISSION_CONFIRM = Config.WAITING_MISSION_CONFIRM
PENDING_MISSION = Config.PENDING_MISSION

bp = Blueprint('menu1', __name__, url_prefix='/menu1')

USE_MOCK = os.environ.get("OPENAI_MOCK", "0") == "1"

client = None
if not USE_MOCK:
  try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
  except Exception:
    client = None

# OpenAI tools 정의
tools = [
  {
    "type": "function",
    "function": {
      "name": "get_available_bikes",
      "description": "허브 이름으로 이용가능 자전거 수를 조회한다.",
      "parameters": {
        "type": "object",
        "properties": {
          "hub_name": {
            "type": "string",
            "description": f"허브의 정확한 이름을 추출해줘. {HUB_DESCRIPTION}" # 자동으로 db에서 허브 이름 가져오는 시스템이 필요할듯
          }
        },
        "required": ["hub_name"]
      }
    }
  }, {
    "type": "function",
    "function": {
      "name": "get_available_nearby_bikes",
      "description": "이 함수는 반드시 사용자의 '현재 위치'를 기준으로 가까운 허브의 자전거 대수를 알고 싶을 때만 호출된다. 즉 질문 안에 '내', '나', '지금', '현재', '여기', 'near me', 'around me', 'nearby here'처럼 사용자의 현재 위치를 직접 가리키는 표현이 포함되어 있어야 한다. 예: '내 근처 자전거 몇 대 있어?', '지금 여기 주변 허브 알려줘', 'near me bikes'. 이러한 표현이 있을 때만 이 함수를 사용한다. 반대로 특정 지역이나 장소 이름을 기준으로 한 표현일 때는 절대 이 함수를 호출하지 않는다. 예: '생활관 근처 자전거 대수 알려줘', '무은재기념관 근처 허브 알려줘', '환경공학동 주변 자전거 알려줘'처럼 특정 건물/지역을 기준으로 말하는 경우는 get_available_bikes를 사용해야 한다. 정리: '나 / 내 / 지금 / 여기' = get_available_nearby_bikes, '특정 장소 이름 / 지역 이름' = get_available_bikes."
    }
  },
  #  {
  #   "type": "function",
  #   "function": {
  #     "name": "rent_bike_normal_with_id",
  #     "description": "bike_id를 갖고 자전거를 대여한다! 꼭 bike_id를 알려줘야된다",
  #     "parameters": {
  #       "type": "object",
  #       "properties": {
  #         "bike_id": {
  #           "type": "string",
  #           "description": "bike_id 혹은 자전거 번호를 가져온다"
  #         }
  #       },
  #       "required": ["bike_id"]
  #     }
  #   }
  # }
]

@bp.app_template_filter('hm')
def hm(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%H:%M')
    except Exception:
        return ''

@bp.route('/', methods=["GET", "POST"])
def menu1():
  answer = None
  question = None
  structured = None

  if request.method == "POST":
    question = (request.form.get("question") or "").strip()
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    if session.get(WAITING_MISSION_CONFIRM):
      intent = classify_yes_no(question, client)

      mission = session.get(PENDING_MISSION)

      if intent == "YES" and mission:
        res, status = fetch_mission_prepare(mission)

        if status >= 400 or not res.get("success"):
          answer = res.get('error') or "미션을 등록하지 못했어요. 잠시 후 다시 시도해 주세요."
        elif res.get("created") is False:
          answer = "이미 진행 중인 미션이 있어요. 기존 미션을 완료해 주세요!"
        else:
          answer = (
            "미션을 수락했어요!\n"
            "해당 자전거를 Station에 꽂으면 자동으로 보상이 지급돼요 🚲"
          )

      else:
        answer = "미션을 진행하지 않을게요. 필요하면 다음에 다시 제안할게요!"

      session.pop(WAITING_MISSION_CONFIRM, None)
      session.pop(PENDING_MISSION, None)
      session.modified = True

      _append("user", question)
      _append("system", answer)
      return redirect(url_for("menu1.menu1"))

    if session.get(WAITING_RENT_CONFORM):
      intent = classify_yes_no(question, client)
      if intent == 'YES':
          rec, _ = fetch_rent_recommand(session.get('last_nearby_hub_name'))

          if not rec or rec.get("success") is False:
            answer = (rec.get("error") if isinstance(rec, dict) else None) or \
                     "추천 정보를 가져오지 못했어요. 잠시 후 다시 시도해주세요."
          else:
            bike_id = rec.get("rent_bike_id", [])
            if not bike_id:
              answer = rec.get('error') or (
                "지금 이 허브에는 바로 대여할 수 있는 자전거가 없어요.\n"
                "조금 뒤 다시 시도하거나 다른 허브를 이용해 주세요."
              )

            else:
              structured = fetch_rent_bike_normal(bike_id)[0]
              answer = structured.get('content') or structured.get('error') or "대여 처리 결과를 확인할 수 없어요."

              # 3) 미션 안내 + 세션 저장
              mission = rec.get("mission") or {}
              if mission and mission.get("enabled"):
                session[PENDING_MISSION] = mission
                session[WAITING_MISSION_CONFIRM] = True
                session.modified = True

                answer += (
                  f"\n\n💡 추가 미션 제안!\n"
                  f"존에 있는 저배터리 자전거({mission['low_battery_bike_id']})를\n"
                  f"Station({mission['target_station_id']})에 꽂으면 "
                  f"{mission['incentive']['amount']}P 적립!\n"
                  f"미션을 수락할까요? (네 / 아니요)"
                )

          # 상태 종료
          session.pop(WAITING_RENT_CONFORM, None)
          session.modified = True

          _append("user", question)
          _append("system", answer)
          return redirect(url_for("menu1.menu1"))

      elif intent == 'NO':
          answer = "알겠습니다. 필요하시면 다시 말씀해주세요."

          session.pop(WAITING_RENT_CONFORM, None)
          session.modified = True

          _append("user", question)
          _append("system", answer)
          return redirect(url_for("menu1.menu1"))

      else:
        print('둘 중 아무것도 아닙니다')
        session.pop(WAITING_RENT_CONFORM, None)
        session.modified = True

    if question:
      if USE_MOCK or client is None:
        # MOCK 모드: 허브 이름 고정 예시
        structured = {"hub_name": "정문 앞", "found": True, "available_bikes": 5}
        answer = f"[MOCK] '{structured['hub_name']}' 허브 이용가능 대수: {structured['available_bikes']}대"
      else:
        try:
          # 반납의도 확인
          ret = classify_return_intent(question, client)

          if ret.get("is_return"):
            rtype = ret.get("return_type", "UNKNOWN")
            hub_name = ret.get("hub_name")
            _append("user", question)

            if not latitude or not longitude:
              answer = "반납하려면 현재 위치 정보가 필요해요."
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))

            # 허브를 지정한 경우
            if hub_name:
              check = fetch_available_bikes(hub_name, latitude, longitude)[0]
              dist = check.get("distance")

              if dist is None:
                answer = "반납 위치를 확인할 수 없어요."
                _append("system", answer)
                return redirect(url_for("menu1.menu1"))

              if dist > RETURN_DISTANCE:
                answer = (
                  f"'{hub_name}' 허브까지 거리가 약 {dist}m예요.\n"
                  "허브 근처로 이동한 뒤 다시 반납해주세요."
                )
                _append("system", answer)
                return redirect(url_for("menu1.menu1"))

            # 허브가 없으면 위치 기반 탐색
            else:
              nearby = fetch_available_nearby_bikes(latitude, longitude)[0]
              dist = nearby.get("distance")
              hub_name = nearby.get("hub_name")

              if dist is None or dist > RETURN_DISTANCE or not hub_name:
                answer = "근처에 반납 가능한 허브가 없어요."
                _append("system", answer)
                return redirect(url_for("menu1.menu1"))

            # Zone / Station 선택 안 했으면 질문
            if rtype == "UNKNOWN":
              session[WAITING_RETURN_TYPE] = True
              session[RETURN_CTX_KEY] = {
                "hub_name": hub_name,
                "lat": latitude,
                "lon": longitude
              }
              session.modified = True

              answer = (
                f"'{hub_name}' 허브로 반납할 수 있어요.\n"
                "Zone으로 반납할까요, Station으로 반납할까요?"
              )
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))

            # Zone 반납
            if rtype == "ZONE":
              structured = fetch_bike_return_zone(
                hub_name=hub_name,
                lat=latitude,
                lon=longitude
              )[0]
              answer = structured.get("content") or structured.get("error")
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))

            # Station 반납 (TODO)
            if rtype == "STATION":
              print('STATION - 196line')
              structured, _ = fetch_bike_return_station(
                hub_name=hub_name,
                lat=latitude,
                lon=longitude
              )
              answer = structured.get("content") or structured.get("error") or "Station 반납 처리 결과를 확인할 수 없어요."
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))
            
          # 대여의도 확인
          rent = classify_rent_intent(question, client)
          if rent.get("is_rent"):
            _append("user", question)

            hub_name = rent.get("hub_name")

            # 허브 이름이 명시된 경우
            if hub_name:
              structured = fetch_available_bikes(hub_name, latitude, longitude)[0]

            # 허브 이름이 없으면 -> nearby
            else:
                if not latitude or not longitude:
                  answer = "현재 위치 정보가 필요해요. 위치 권한을 켜고 다시 말해주세요."
                  _append("system", answer)
                  return redirect(url_for("menu1.menu1"))

                structured = fetch_available_nearby_bikes(latitude, longitude)[0]

            if structured.get("error"):
              answer = structured.get("error") or "자전거 정보를 가져오지 못했어요."
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))

            # nearby인 경우만 거리 체크
            distance = structured.get("distance")
            if not hub_name and (distance is None or distance > RECOMMAND_DISTANCE):
              answer = structured.get("content") or "근처에 바로 대여할 수 있는 허브가 없어요."
              answer += "\n조금 더 가까운 곳으로 이동한 뒤 다시 말해주세요."
              _append("system", answer)
              return redirect(url_for("menu1.menu1"))

            # 대여 확인
            answer = structured.get("content") or "대여 가능한 자전거를 찾았어요."
            answer += "\n대여하시겠습니까? (네 / 아니요)"

            session["last_nearby_hub_name"] = structured.get("hub_name")
            session[WAITING_RENT_CONFORM] = True
            session.modified = True

            _append("system", answer)
            return redirect(url_for("menu1.menu1"))

          hist = _get_history()
          messages_for_model = hist + [{"role" : "user", "content":question}]
          
          # GPT에게 질문 보내고 tool 호출 유도
          resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_for_model,
            tools=tools,
            tool_choice="auto"
          )

          # tool call 추출
          tool_call = None
          tool_calls = resp.choices[0].message.tool_calls
          if tool_calls:
            tool_call = tool_calls[0]

          if tool_call:
            try:
              name = tool_call.function.name
              args = json.loads(tool_call.function.arguments)

              print(f'function : {name}')

            except Exception:
              name, args = None, {}

            if name == "get_available_bikes" and "hub_name" in args:
              # 0번째 : 실질적인 정보, 1번째 : status 코드
              structured = fetch_available_bikes(args["hub_name"])[0]
              
              # For Log
              print(structured)
              
              if not structured.get("error"):
                # answer = f"'{structured['hub_name']}' 허브 이용가능 대수: {structured['available_bikes']}대"
                answer = structured['content']
              else:
                msg = structured.get("error")
                answer = f"'{structured['hub_name']}' 허브를 찾을 수 없어요." + (f"\n[API ERROR] {msg}" if msg else "")

            elif name == "get_available_nearby_bikes":
                structured = fetch_available_nearby_bikes(latitude, longitude)[0]

                print(structured)

                if not structured.get("error"):
                  answer = structured['content']

                  distance = structured.get("distance")  # recommend API에서 내려준다고 가정

                  if distance is not None and distance <= RECOMMAND_DISTANCE:
                      answer += "\n대여하시겠습니까? (네 / 아니요)"

                      # 상태 저장
                      session["last_nearby_hub_name"] = structured.get('hub_name')
                      session[WAITING_RENT_CONFORM] = True
                      session.modified = True
                else:
                  msg = structured.get("error")
                  answer = f"'{structured['hub_name']}' 허브를 찾을 수 없어요." + (f"\n[API ERROR] {msg}" if msg else "")

            # elif name == "rent_bike_normal_with_id" and "bike_id" in args:
            #   print(args["bike_id"])
            #   structured = fetch_rent_bike_normal(args["bike_id"])[0]

            #   print(structured)

            #   if not structured.get("error"):
            #     answer = structured['content']
              
            #   else:
            #     msg = structured.get("error")
            #     answer = f"\n[API ERROR] {msg}" if msg else ""
            
            else:
              answer = "(허브 이름을 추출하지 못했습니다)"
          else:
              # 함수 호출이 없으면 일반 텍스트 응답 출력
              answer = resp.choices[0].message.content or "(응답이 없습니다)"
              
          
          
          # For Log
          _append("user", question)
          _append("system", answer)
          print(_get_history())
          
        except Exception as e:
          answer = f"[ERROR] {type(e).__name__}: {e}"

        return redirect(url_for('menu1.menu1'))

  # return render_template("menu1.html", question=question, answer=answer, structured=structured)
  history = _get_history()
  return render_template(
      "menu1.html",
      structured=structured,
      history=history,
  )
  

# 현재 시간 반환
def _now_ts():
  return int(time.time())

def _prune(hist_list):
  if not hist_list:
    return []
  if TTL_SEC > 0:
    cut_off = _now_ts() - TTL_SEC
    hist_list = [m for m in hist_list if (m.get("ts", 0) >= cut_off)]
  # 최근 MAX_MSGS만 유지
  if len(hist_list) > MAX_MSGS:
    hist_list = hist_list[-MAX_MSGS : ]
  return hist_list

def _get_history():
  hist = session.get(HIST_KEY, [])
  hist = _prune(hist)
  session[HIST_KEY] = hist
  session.modified = True
  return hist

def _append(role, content):
  content = (content or "").strip()
  hist = _get_history()
  hist.append({"role":role, "content":content, "ts" : _now_ts()})
  session[HIST_KEY] = _prune(hist)
  session.modified = True 
  
def _clear_history():
  session[HIST_KEY] = []
  session.modified = True