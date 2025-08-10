PRAGMA foreign_keys = ON;

-- 1) 사용자
CREATE TABLE user (
  user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL,
  student_no     TEXT,
  phone          TEXT,
  grade          TEXT,                -- 등급(일반/관리자/…)
  joined_at      TEXT NOT NULL DEFAULT (datetime('now'))  -- ISO8601
);

CREATE UNIQUE INDEX idx_user_student_no ON user(student_no);
CREATE UNIQUE INDEX idx_user_phone ON user(phone);

-- 2) 허브
CREATE TABLE hub (
  hub_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name           TEXT NOT NULL,
  lat            REAL NOT NULL,
  lng            REAL NOT NULL,
  capacity       INTEGER NOT NULL CHECK (capacity >= 0),
  current_bikes  INTEGER NOT NULL DEFAULT 0 CHECK (current_bikes >= 0)
);

CREATE INDEX idx_hub_coord ON hub(lat, lng);

-- 3) 자전거
CREATE TABLE bike (
  bike_id            INTEGER PRIMARY KEY AUTOINCREMENT,
  current_hub_id     INTEGER,          -- 허브 밖(거리)에 있을 수 있어 NULL 허용
  lock_state         TEXT NOT NULL DEFAULT 'locked',  -- 'locked' | 'unlocked' | 'fault'
  battery_percent    INTEGER NOT NULL DEFAULT 100 CHECK (battery_percent BETWEEN 0 AND 100),
  is_available       INTEGER NOT NULL DEFAULT 1,      -- 1/0 (TRUE/FALSE)
  FOREIGN KEY (current_hub_id) REFERENCES hub(hub_id) ON UPDATE CASCADE
);

CREATE INDEX idx_bike_hub ON bike(current_hub_id);
CREATE INDEX idx_bike_available ON bike(is_available);

-- 4) 대여 기록
CREATE TABLE ride (
  ride_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER NOT NULL,
  bike_id        INTEGER NOT NULL,
  start_hub_id   INTEGER,                 -- 허브 밖에서 시작하면 NULL
  end_hub_id     INTEGER,                 -- 허브 밖 반납이면 NULL
  start_at       TEXT NOT NULL,           -- datetime ISO8601
  end_at         TEXT,                    -- 진행중이면 NULL
  duration_min   INTEGER,                 -- 종료 시 계산 저장(분)
  fare_amount    INTEGER DEFAULT 0,       -- 최종 요금(원)
  incentive_applied INTEGER NOT NULL DEFAULT 0,  -- 1/0
  FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE RESTRICT,
  FOREIGN KEY (bike_id) REFERENCES bike(bike_id) ON DELETE RESTRICT,
  FOREIGN KEY (start_hub_id) REFERENCES hub(hub_id),
  FOREIGN KEY (end_hub_id)   REFERENCES hub(hub_id)
);

CREATE INDEX idx_ride_user_time ON ride(user_id, start_at);
CREATE INDEX idx_ride_bike_time ON ride(bike_id, start_at);
CREATE INDEX idx_ride_end_at ON ride(end_at);

-- 5) 잠금 상태(일시잠금/중간대여 베이스 로그)
CREATE TABLE lock_status (
  lock_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  bike_id        INTEGER NOT NULL,
  user_id        INTEGER NOT NULL,
  locked_at      TEXT NOT NULL,        -- 잠근 시각
  lat            REAL,                 -- 잠근 위치
  lng            REAL,
  transferable   INTEGER NOT NULL DEFAULT 0,  -- 양도 가능 여부 1/0
  is_active      INTEGER NOT NULL DEFAULT 1,  -- 현재 잠금 상태(해제 시 0)
  FOREIGN KEY (bike_id) REFERENCES bike(bike_id),
  FOREIGN KEY (user_id) REFERENCES user(user_id)
);

CREATE INDEX idx_lock_active ON lock_status(is_active, transferable);

-- 6) 양도 의사
CREATE TABLE transfer_intent (
  transfer_id    INTEGER PRIMARY KEY AUTOINCREMENT,
  lock_id        INTEGER NOT NULL,
  registered_at  TEXT NOT NULL,
  is_matched     INTEGER NOT NULL DEFAULT 0,
  matched_user_id INTEGER,                 -- 양도 받은 사용자
  FOREIGN KEY (lock_id) REFERENCES lock_status(lock_id) ON DELETE CASCADE,
  FOREIGN KEY (matched_user_id) REFERENCES user(user_id)
);

CREATE INDEX idx_transfer_match ON transfer_intent(is_matched);

-- 7) 인센티브 정책 (허브 혼잡 해소 등)
CREATE TABLE incentive_policy (
  policy_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  target_hub_id  INTEGER NOT NULL,
  start_date     TEXT NOT NULL,        -- 'YYYY-MM-DD'
  end_date       TEXT,                  -- 종료 없으면 NULL
  time_start     TEXT NOT NULL,        -- 'HH:MM:SS'
  time_end       TEXT NOT NULL,
  amount         INTEGER NOT NULL,     -- 금액(+ 인센티브)
  policy_type    TEXT NOT NULL,        -- 예: 'rebalancing','peak','event'
  FOREIGN KEY (target_hub_id) REFERENCES hub(hub_id)
);

CREATE INDEX idx_incentive_range ON incentive_policy(target_hub_id, start_date, end_date);

-- 8) 요금 정책 (존/시간대별 가감 요금)
CREATE TABLE fare_policy (
  fare_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  origin_zone    TEXT NOT NULL,
  dest_zone      TEXT NOT NULL,
  time_start     TEXT NOT NULL,        -- 'HH:MM:SS'
  time_end       TEXT NOT NULL,
  base_per_min   INTEGER NOT NULL,     -- 분당 기본 요금(원)
  adj_type       TEXT,                  -- 'discount' | 'surcharge' 등
  adj_amount     INTEGER DEFAULT 0
);

CREATE INDEX idx_fare_zone ON fare_policy(origin_zone, dest_zone);

-- 9) 자전거 상태 로그
CREATE TABLE bike_status_log (
  log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  bike_id        INTEGER NOT NULL,
  status         TEXT NOT NULL,        -- 'ok','low_battery','repair_needed',…
  logged_at      TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (bike_id) REFERENCES bike(bike_id)
);

CREATE INDEX idx_bike_status_time ON bike_status_log(bike_id, logged_at);

-- 10) 자전거 위치 로그
CREATE TABLE bike_location_log (
  log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
  bike_id        INTEGER NOT NULL,
  lat            REAL NOT NULL,
  lng            REAL NOT NULL,
  logged_at      TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (bike_id) REFERENCES bike(bike_id)
);

CREATE INDEX idx_bike_loc_time ON bike_location_log(bike_id, logged_at);
CREATE INDEX idx_bike_loc_geo ON bike_location_log(lat, lng);

-- 11) 챗봇 상호작용 로그
CREATE TABLE chat_log (
  chat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id        INTEGER,
  user_question  TEXT NOT NULL,
  gpt_answer     TEXT NOT NULL,
  inferred_intent TEXT,
  function_called INTEGER NOT NULL DEFAULT 0,
  logged_at      TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES user(user_id)
);

CREATE INDEX idx_chat_user_time ON chat_log(user_id, logged_at);
