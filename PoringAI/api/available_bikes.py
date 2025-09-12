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

  data = {
    "hub_name" : hub_name,
    "found" : True,
    "available_bikes" : int(row["cnt"])
  }
  print(data)
  return generate_sentence(data)
  # return jsonify({
  #   "hub_name" : hub_name,
  #   "found" : True,
  #   "available_bikes" : int(row["cnt"])
  # }), 200

def fetch_available_bikes(hub_name: str):
  """내부 API(/available-bikes) 호출"""
  api_url = url_for("api.available_bikes", _external=True)
  try:
    res = requests.get(api_url, params={"hub_name": hub_name}, timeout=5)
    return res.json()
  except Exception as e:
    return {"hub_name": hub_name, "found": False, "available_bikes": 0, "error": str(e)}
  
def generate_sentence(data):
  try:
    messages_for_model = [
      {"role": "system", "content":"You are Poring-AI, a chatbot for a bike rental service. You will engage in natural conversation with the user to tell them the number of available bikes at a specified location. If there are no bikes at that location, recommend the nearest alternative station. Rules: 1) Always maintain a friendly and warm tone. 2) Keep answers concise, limited to 1-2 sentences. 3) Do not provide unnecessary explanations, background information, or verbose descriptions. 4) Avoid an overly humorous or casual tone. 5) Always respond in short, clear Korean sentences."},
      {"role":"user", "content": f"다음 값을 자연스럽게 한문장으로 바꿔줘 허브이름 : {data['hub_name']}, 자전거 개수 : {data['available_bikes']}"}
    ]
    
    ## TODO : MOCK 넣기 
    from openai import OpenAI   
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # GPT에게 질문 보내기
    resp = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=messages_for_model,
      temperature=0.1
    )


    # output 추출
    output = resp.choices[0].message.content

    data["message"] = output
    
    return jsonify(data), 200
              
  except Exception as e:
    data["found"] = False
    print(e)
    return jsonify(data), 400
    