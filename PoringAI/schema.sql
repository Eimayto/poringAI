DROP TABLE IF EXISTS User;
DROP TABLE IF EXISTS Bike;
DROP TABLE IF EXISTS Hub;
DROP TABLE IF EXISTS Ride;
DROP TABLE IF EXISTS LockStatus;
DROP TABLE IF EXISTS TransferIntent;
DROP TABLE IF EXISTS IncentivePolicy;
DROP TABLE IF EXISTS FarePolicy;
DROP TABLE IF EXISTS BikeLocationLog;
DROP TABLE IF EXISTS BikeStatusLog;
DROP TABLE IF EXISTS ChatLog;



-- 사용자
CREATE TABLE User (
    user_id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    student_id VARCHAR(20),
    phone_number VARCHAR(20),
    grade VARCHAR(20),
    join_date DATE
);

-- 자전거
CREATE TABLE Bike (
    bike_id INTEGER PRIMARY KEY,
    current_hub_id INTEGER,
    lock_status BOOLEAN,
    battery_level INTEGER,
    is_available BOOLEAN,
    FOREIGN KEY (current_hub_id) REFERENCES Hub(hub_id)
);

-- 허브
CREATE TABLE Hub (
    hub_id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    capacity INTEGER,
    current_bike_count INTEGER
);

-- 대여 기록
CREATE TABLE Ride (
    ride_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    bike_id INTEGER,
    start_hub_id INTEGER,
    end_hub_id INTEGER,
    start_time DATETIME,
    end_time DATETIME,
    duration_minutes INTEGER,
    fare INTEGER,
    incentive_applied BOOLEAN,
    FOREIGN KEY (user_id) REFERENCES User(user_id),
    FOREIGN KEY (bike_id) REFERENCES Bike(bike_id),
    FOREIGN KEY (start_hub_id) REFERENCES Hub(hub_id),
    FOREIGN KEY (end_hub_id) REFERENCES Hub(hub_id)
);

-- 잠금 상태
CREATE TABLE LockStatus (
    lock_id INTEGER PRIMARY KEY,
    bike_id INTEGER,
    user_id INTEGER,
    lock_time DATETIME,
    location_lat DECIMAL(9,6),
    location_lon DECIMAL(9,6),
    is_transferable BOOLEAN,
    is_locked BOOLEAN,
    FOREIGN KEY (bike_id) REFERENCES Bike(bike_id),
    FOREIGN KEY (user_id) REFERENCES User(user_id)
);

-- 양도 의사
CREATE TABLE TransferIntent (
    transfer_id INTEGER PRIMARY KEY,
    lock_id INTEGER,
    created_time DATETIME,
    is_matched BOOLEAN,
    matched_user_id INTEGER,
    FOREIGN KEY (lock_id) REFERENCES LockStatus(lock_id),
    FOREIGN KEY (matched_user_id) REFERENCES User(user_id)
);

-- 인센티브 정책
CREATE TABLE IncentivePolicy (
    policy_id INTEGER PRIMARY KEY,
    target_hub_id INTEGER,
    start_date DATE,
    end_date DATE,
    time_start TIME,
    time_end TIME,
    incentive_amount INTEGER,
    policy_type VARCHAR(50),
    FOREIGN KEY (target_hub_id) REFERENCES Hub(hub_id)
);

-- 요금 정책
CREATE TABLE FarePolicy (
    fare_id INTEGER PRIMARY KEY,
    start_zone VARCHAR(100),
    end_zone VARCHAR(100),
    time_start TIME,
    time_end TIME,
    base_fare_per_minute INTEGER,
    adjustment_type VARCHAR(50),  -- 예: 할인, 추가요금
    adjustment_amount INTEGER
);

-- 자전거 상태 로그
CREATE TABLE BikeStatusLog (
    log_id INTEGER PRIMARY KEY,
    bike_id INTEGER,
    status VARCHAR(50),
    timestamp DATETIME,
    FOREIGN KEY (bike_id) REFERENCES Bike(bike_id)
);

-- 자전거 위치 로그
CREATE TABLE BikeLocationLog (
    log_id INTEGER PRIMARY KEY,
    bike_id INTEGER,
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    timestamp DATETIME,
    FOREIGN KEY (bike_id) REFERENCES Bike(bike_id)
);

-- 챗봇 상호작용 로그
CREATE TABLE ChatLog (
    chat_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    user_question TEXT,
    gpt_response TEXT,
    inferred_intent TEXT,
    function_called BOOLEAN,
    timestamp DATETIME,
    FOREIGN KEY (user_id) REFERENCES User(user_id)
);
