from flask import Blueprint, render_template, request, url_for
import os, json
import requests
from typing import Optional, Dict, Any

from .db import get_db

bp = Blueprint('menu1', __name__, url_prefix='/menu1')

USE_MOCK = os.environ.get("OPENAI_MOCK", "0") == "1"
client = None
if not USE_MOCK:
  try:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
  except Exception:
    client = None

def extract_hub_name(text: str) -> Optional[str]:
  """Hub 테이블의 name들 중에서 질문에 포함된 것을 간단 매칭"""
  if not text:
    return None
  names = [r["name"] for r in get_db().execute("SELECT name FROM Hub").fetchall()]
  for name in names:
    if name and name in text:
      return name
  return None

def call_available_bikes_api(hub_name: str) -> Dict[str, Any]:
  """내부 API(/available-bikes)를 HTTP로 호출해 결과 JSON 리턴"""
  api_url = url_for("api.available_bikes", _external=True)
  try:
    res = requests.get(api_url, params={"hub_name": hub_name}, timeout=5)
    return res.json()
  except Exception as e:
    return {"hub_name": hub_name, "found": False, "available_bikes": 0, "error": str(e)}

@bp.route('/', methods=["GET", "POST"])
def menu1():
  answer = None
  question = None
  structured = None

  if request.method == "POST":
    question = (request.form.get("question") or "").strip()
    if question:
      hub_name = extract_hub_name(question)
      if hub_name:
        structured = call_available_bikes_api(hub_name)
        if structured.get("found"):
          answer = f"'{structured['hub_name']}' 허브 이용가능 대수: {structured['available_bikes']}대"
        else:
          msg = structured.get("error")
          answer = f"'{structured['hub_name']}' 허브를 찾을 수 없어요." + (f"\n[API ERROR] {msg}" if msg else "")
      else:
        if USE_MOCK or client is None:
          answer = (
            f"[MOCK] 너가 물은 내용: {question}\n"
            "(허브 이름이 문장에 포함되면 /available-bikes API를 자동으로 호출해요)"
          )
        else:
          try:
            resp = client.responses.create(
              model="gpt-4o-mini",
              input=[{"role": "user", "content": question}]
            )
            answer = getattr(resp, "output_text", None)
            if not answer:
              parts = []
              for out in getattr(resp, "output", []) or []:
                for c in getattr(out, "content", []) or []:
                  if getattr(c, "type", None) == "text":
                    parts.append(getattr(c, "text", ""))
              answer = "\n".join(p for p in parts if p).strip() or "(응답을 파싱하지 못했습니다)"
          except Exception as e:
            answer = f"[ERROR] {type(e).__name__}: {e}"

  return render_template("menu1.html", question=question, answer=answer, structured=structured)
