# api/missions.py
import sqlite3
from flask import request, jsonify
from . import bp
from ..db import get_db


@bp.post("/missions/prepare")
def missions_prepare():
    """
    대여 완료 직후, 추천된 미션을 DB에 저장(생성)한다.
    - menu1.py는 DB 직접 접근 X
    - rent_recommand.py는 READ ONLY 유지

    요청 JSON:
    {
      "user_id": 1,
      "low_battery_bike_id": 205,
      "target_station_id": 3,      # optional
      "reward": 300
    }

    응답:
    {
      "success": true,
      "mission_id": 10,
      "created": true|false
    }
    """

    data = request.get_json() or {}

    user_id = data.get("user_id")
    low_bike_id = data.get("low_battery_bike_id")
    target_station_id = data.get("target_station_id")  # None 가능
    reward = data.get("reward")

    if not user_id or not low_bike_id or reward is None:
        return jsonify({
            "success": False,
            "error": "user_id, low_battery_bike_id, reward가 필요합니다."
        }), 400

    db = get_db()

    try:
        # (1) 사용자 존재 확인
        user = db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return jsonify({"success": False, "error": "존재하지 않는 사용자입니다."}), 404

        # (2) 이미 진행 중인 미션이 있으면 새로 만들지 않음
        existing = db.execute(
            """
            SELECT mission_id
            FROM missions
            WHERE user_id = ?
              AND status = 'ACTIVE'
            """,
            (user_id,)
        ).fetchone()

        if existing:
            return jsonify({
                "success": True,
                "mission_id": existing["mission_id"],
                "created": False
            }), 200
        
        # (2-1) 해당 자전거로 이미 ACTIVE 미션이 있는지 확인
        dup = db.execute(
            """
            SELECT mission_id
            FROM missions
            WHERE low_battery_bike_id = ?
            AND status = 'ACTIVE'
            """,
            (low_bike_id,)
        ).fetchone()

        if dup:
            return jsonify({
                "success": False,
                "error": "이미 다른 사용자가 이 자전거에 대한 미션을 진행 중입니다."
            }), 409

        # (3) 미션 생성
        cur = db.execute(
            """
            INSERT INTO missions (user_id, low_battery_bike_id, target_station_id, reward, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
            """,
            (user_id, low_bike_id, target_station_id, reward)
        )
        db.commit()

        return jsonify({
            "success": True,
            "mission_id": cur.lastrowid,
            "created": True
        }), 201

    except sqlite3.Error as e:
        db.rollback()
        return jsonify({"success": False, "error": f"DB 오류: {e}"}), 500
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": f"오류 발생: {e}"}), 500
