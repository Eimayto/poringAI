import json

HUB_DESCRIPTION = '''
허브 이름에는 무은재기념관, 학생회관, 환경공학동, 생활관21동, 생활관3동, 생활관12동, 생활관15동, 박태준학술정보관, 친환경소재대학원, 제1실험동, 기계실험동, 가속기IBS가 있어. 지역에는 교사지역, 생활관지역, 인화지역, 가속기&연구실험동이 있어. 교사지역에 있는 허브로는 무은재기념관, 학생회관, 환경공학동이 있어. 생활관지역에는 생활관21동, 생활관3동, 생활관12동, 생활관15동이 있어. 인화지역에 있는 허브는 박태준학술정보관, 친환경소재대학원이 있어. 가속기&연구실험동에 있는 허브는 제1실험동, 기계실험동, 가속기IBS가 있어.
'''

# 답변 긍정 / 부정 판단
def classify_yes_no(text, client):
  resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
      {
        "role": "system",
        "content": (
          "다음 사용자 발화를 보고 자전거 대여에 대한 응답 의도를 판단해라.\n\n"
          "다음 규칙을 반드시 따른다:\n"
          "- YES: 사용자가 대여에 동의하거나 진행 의사를 보임\n"
          "- NO: 사용자가 거절, 취소, 원하지 않음을 표현함\n"
          "- UNKNOWN: 위 두 경우가 명확하지 않음\n\n"
          "YES로 판단해야 하는 예시:\n"
          "네, 예, 응, ㅇㅇ, ㄱㄱ, 가자, 콜, 좋아, 진행해, 할게, 빌릴게\n\n"
          "NO로 판단해야 하는 예시:\n"
          "아니요, 아니, ㄴㄴ, 싫어, 안할래, 취소, 됐어\n\n"
          "반드시 다음 중 하나만 출력하라:\n"
          "YES\nNO\nUNKNOWN"
        )
      },
      {"role": "user", "content": text}
    ],
    temperature=0
  )
  return resp.choices[0].message.content.strip()

def classify_return_intent(text, client):
  resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
      {
        "role": "system",
        "content": (
          "사용자 발화를 보고 자전거 반납 의도를 JSON으로 판단해라.\n"
          "반드시 JSON만 출력.\n\n"
          "{\n"
          '  "is_return": true|false,\n'
          '  "return_type": "ZONE|STATION|UNKNOWN",\n'
          '  "hub_name": string|null\n'
          "}\n\n"
          "ZONE: 임시/바깥/정식아님/잠깐/존\n"
          "STATION: 정식/거치대/스테이션\n"
          f'{HUB_DESCRIPTION}'
        )
      },
      {"role": "user", "content": text}
    ],
    temperature=0
  )
  return json.loads(resp.choices[0].message.content)

def classify_rent_intent(text, client):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "사용자 발화를 보고 자전거 대여 의도를 판단하고, 허브 이름을 추출해라.\n"
                    "반드시 JSON만 출력한다.\n\n"
                    "{\n"
                    '  "is_rent": true|false,\n'
                    '  "hub_name": string|null\n'
                    "}\n\n"
                    "규칙:\n"
                    "- is_rent=true: 대여/빌리다/타다/렌트/자전거 대여/자전거 빌릴래/탈래 등\n"
                    "- hub_name은 아래 허브 목록 중 하나와 정확히 일치해야 한다.\n"
                    "- 허브가 언급되지 않았으면 hub_name은 null로 둔다.\n\n"
                    f"{HUB_DESCRIPTION}"
                )
            },
            {"role": "user", "content": text}
        ],
        temperature=0
    )
    return json.loads(resp.choices[0].message.content)