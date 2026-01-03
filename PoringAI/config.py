class Config:
    FULL_BATTERY = 50 # 완충 기준
    HUB_DESCRIPTION = '''
    허브 이름에는 무은재기념관, 학생회관, 환경공학동, 생활관21동, 생활관3동, 생활관12동, 생활관15동, 박태준학술정보관, 친환경소재대학원, 제1실험동, 기계실험동, 가속기IBS가 있어. 지역에는 교사지역, 생활관지역, 인화지역, 가속기&연구실험동이 있어. 교사지역에 있는 허브로는 무은재기념관, 학생회관, 환경공학동이 있어. 생활관지역에는 생활관21동, 생활관3동, 생활관12동, 생활관15동이 있어. 인화지역에 있는 허브는 박태준학술정보관, 친환경소재대학원이 있어. 가속기&연구실험동에 있는 허브는 제1실험동, 기계실험동, 가속기IBS가 있어.
    '''
    HIST_KEY = "menu1_hist" # Flask session에 저장할 키
    MAX_MSGS = 16            # 최근 N개의 대화만 기억
    TTL_SEC = 60 * 30      # 30분 TTL, 0이면 비활성
    WAITING_RENT_CONFORM = 'waiting_rent_conform'
    RECOMMAND_DISTANCE = 100 # 근처 자전거 대여 허용 거리(m)
    RETURN_DISTANCE = 10     # 자전거 반납 허용 거리(m)
    WAITING_RETURN_TYPE = "waiting_return_type"
    RETURN_CTX_KEY = "return_ctx"
    LOW_BATTERY_INCENTIVE = 1000
    WAITING_MISSION_CONFIRM = "waiting_mission_confirm"
    PENDING_MISSION = "pending_mission"