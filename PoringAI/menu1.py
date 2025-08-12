from flask import Blueprint, render_template, request, url_for
import os, json, requests
from .api.available_bikes import fetch_available_bikes

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
            "description": "허브의 정확한 이름(예: '정문 앞')"
          }
        },
        "required": ["hub_name"]
      }
    }
  }
]

@bp.route('/', methods=["GET", "POST"])
def menu1():
  answer = None
  question = None
  structured = None

  if request.method == "POST":
    question = (request.form.get("question") or "").strip()
    if question:
      if USE_MOCK or client is None:
        # MOCK 모드: 허브 이름 고정 예시
        structured = {"hub_name": "정문 앞", "found": True, "available_bikes": 5}
        answer = f"[MOCK] '{structured['hub_name']}' 허브 이용가능 대수: {structured['available_bikes']}대"
      else:
        try:
          # GPT에게 질문 보내고 tool 호출 유도
          resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": question}],
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
            except Exception:
              name, args = None, {}

            if name == "get_available_bikes" and "hub_name" in args:
              structured = fetch_available_bikes(args["hub_name"])
              if structured.get("found"):
                answer = f"'{structured['hub_name']}' 허브 이용가능 대수: {structured['available_bikes']}대"
              else:
                msg = structured.get("error")
                answer = f"'{structured['hub_name']}' 허브를 찾을 수 없어요." + (f"\n[API ERROR] {msg}" if msg else "")
            else:
              answer = "(허브 이름을 추출하지 못했습니다)"
          else:
              # 함수 호출이 없으면 일반 텍스트 응답 출력
              answer = resp.choices[0].message.content or "(응답이 없습니다)"
        except Exception as e:
          answer = f"[ERROR] {type(e).__name__}: {e}"

  return render_template("menu1.html", question=question, answer=answer, structured=structured)
