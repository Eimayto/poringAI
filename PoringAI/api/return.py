from flask import request, jsonify
from ..db import get_db
from . import bp   # api/__init__.py 의 Blueprint("api", __name__) 재사용

# 선택: 내부 요약문 생성 훅을 쓰려면 주석 해제
# import os, requests

def _is_hub_full_by_id(db, hub_id: int) -> bool:
    """
    hub_id 기준으로 허브가 꽉 찼는지 여부를 반환.
    schema.sql 의 hub(capacity, current_bikes)를 사용.
    """
    row = db.execute(
        "SELECT capacity, current_bikes FROM hub WHERE hub_id = ?",
        (hub_id,),
    ).fetchone()

    if row is None:
        # 허브를 못 찾으면 일단 False 처리 (Zone 반납 허용 안 함)
        return False

    return row["current_bikes"] >= row["capacity"]


def _validate_lat_lng(lat, lng):
    """
    lat/lng가 전달되면 float 변환 및 범위 검증(-90~90, -180~180).
    미전달(None)은 허용(존 반납 좌표 로그 없이 진행).
    """
    if lat is None and lng is None:
        return None, None, None  # ok, no coords
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False, "invalid_params", "lat/lng 는 숫자여야 합니다."
    if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lng_f <= 180.0):
        return False, "invalid_params", "lat/lng 범위를 확인해 주세요."
    return True, lat_f, lng_f


@bp.route("/zone-return", methods=["POST"])
def zone_return():
    """
    Zone 반납 처리:
    - 허브가 꽉 찼을 때만 허용
    - ride(진행 중인 라이딩)를 종료
    - bike:
        current_hub_id = NULL (허브 밖, 존 위치)
        is_available   = 1   (다시 대여 가능)
        lock_state     = 'locked'
    - lock_status:
        is_active = 1 인 row 를 하나 남겨둔다
    - 모든 변경은 단일 트랜잭션으로 처리
    """
    payload = request.get_json(silent=True) or {}

    hub_id  = payload.get("hub_id")   # Zone 이 속한 허브 ID
    bike_id = payload.get("bike_id")
    user_id = payload.get("user_id")
    lat     = payload.get("lat")
    lng     = payload.get("lng")

    # 필수값 체크
    if hub_id is None or bike_id is None or user_id is None:
        return jsonify({
            "ok": False,
            "reason": "missing_params",
            "message": "hub_id, bike_id, user_id 는 필수입니다."
        }), 400

    # 타입 변환
    try:
        hub_id  = int(hub_id)
        bike_id = int(bike_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({
            "ok": False,
            "reason": "invalid_params",
            "message": "hub_id, bike_id, user_id 는 정수여야 합니다."
        }), 400

    # 좌표 검증(선택)
    coord_ok, lat_v, lng_v = _validate_lat_lng(lat, lng)
    if coord_ok is False:
        return jsonify({"ok": False, "reason": lat_v, "message": lng_v}), 400
    # coord_ok == None 또는 True 인 경우 정상 진행
    if coord_ok is None:
        lat_v = None
        lng_v = None

    db = get_db()

    # 허브 존재/상태 확인
    hub_row = db.execute(
        "SELECT hub_id, capacity, current_bikes FROM hub WHERE hub_id = ?",
        (hub_id,),
    ).fetchone()
    if hub_row is None:
        return jsonify({
            "ok": False,
            "reason": "hub_not_found",
            "message": "허브 정보를 찾을 수 없습니다."
        }), 404

    # 1) 허브가 꽉 찼는지 확인
    if not _is_hub_full_by_id(db, hub_id):
        return jsonify({
            "ok": False,
            "reason": "hub_not_full",
            "message": "허브에 아직 빈 자리가 있어서 Zone 반납이 불가능합니다."
        }), 409

    # 2) 진행 중인 ride 찾기 (user_id + bike_id + end_at IS NULL)
    ride = db.execute(
        """
        SELECT ride_id, start_at
        FROM ride
        WHERE user_id = ?
          AND bike_id = ?
          AND end_at IS NULL
        ORDER BY start_at DESC
        LIMIT 1
        """,
        (user_id, bike_id),
    ).fetchone()

    if ride is None:
        return jsonify({
            "ok": False,
            "reason": "no_active_ride",
            "message": "현재 진행 중인 라이딩을 찾을 수 없습니다."
        }), 404

    ride_id = ride["ride_id"]

    # 2-1) 자전거 존재 확인(추가 방어)
    bike_row = db.execute(
        "SELECT bike_id FROM bike WHERE bike_id = ?",
        (bike_id,),
    ).fetchone()
    if bike_row is None:
        return jsonify({
            "ok": False,
            "reason": "bike_not_found",
            "message": "자전거 정보를 찾을 수 없습니다."
        }), 404

    # 3~6) 트랜잭션으로 원자적 처리
    try:
        with db:  # sqlite3: 컨텍스트 블록 내 자동 COMMIT/ROLLBACK
            # 3) ride 종료 (Zone 반납 → end_hub_id 는 NULL)
            db.execute(
                """
                UPDATE ride
                SET end_hub_id   = NULL,               -- 허브가 아닌 존에서 끝났다는 의미
                    end_at       = datetime('now'),
                    duration_min = CAST(
                        (julianday(datetime('now')) - julianday(start_at)) * 24 * 60
                        AS INTEGER
                    )
                WHERE ride_id = ?
                """,
                (ride_id,),
            )

            # 4) 자전거 상태 업데이트
            #    - 허브 밖(존)에 있으므로 current_hub_id = NULL
            #    - is_available = 1 (누구나 새로 빌릴 수 있음)
            #    - lock_state   = 'locked' (물리적으로는 잠겨 있음)
            db.execute(
                """
                UPDATE bike
                SET current_hub_id = NULL,
                    is_available   = 1,
                    lock_state     = 'locked'
                WHERE bike_id = ?
                """,
                (bike_id,),
            )

            # 5) 기존 활성 lock_status 비활성화
            db.execute(
                """
                UPDATE lock_status
                SET is_active = 0
                WHERE bike_id = ?
                  AND user_id = ?
                  AND is_active = 1
                """,
                (bike_id, user_id),
            )

            # 6) Zone 반납용 lock_status row 삽입
            #    - transferable=1 → "누구나 가져가도 되는 상태"
            db.execute(
                """
                INSERT INTO lock_status (bike_id, user_id, locked_at, lat, lng, transferable, is_active)
                VALUES (?, ?, datetime('now'), ?, ?, 1, 1)
                """,
                (bike_id, user_id, lat_v, lng_v),
            )

            # 7) 위치 로그도 같이 남겨주기(좌표 있는 경우만)
            if lat_v is not None and lng_v is not None:
                db.execute(
                    """
                    INSERT INTO bike_location_log (bike_id, lat, lng, logged_at)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (bike_id, lat_v, lng_v),
                )

    except Exception as e:
        # 컨텍스트 블록에서 예외 발생 시 자동 롤백됨
        return jsonify({
            "ok": False,
            "reason": "db_error",
            "message": f"{type(e).__name__}: {e}"
        }), 500

    # 선택) 친절 메시지(content) 자동 생성 훅
    content = f"허브가 가득 차서 Zone 반납으로 종료했어요. 자전거는 잠금 상태로 대여 가능해요."
    # 요약문 생성 API가 있다면 주석 해제
    # try:
    #     base = os.environ.get("SELF_BASE", "http://127.0.0.1:5000")
    #     r = requests.post(
    #         f"{base}/api/generate-sentence",
    #         json={
    #             "messages_for_model": [
    #                 {"role": "system", "content": "한국어로 1–2문장, 친절하고 간결하게."},
    #                 {"role": "user", "content": f"허브ID {hub_id}가 꽉 차서 사용자 {user_id}가 자전거 {bike_id}를 Zone 반납했습니다."}
    #             ],
    #             "data": {}
    #         },
    #         timeout=4
    #     )
    #     jr = r.json()
    #     content = (jr.get("data") or {}).get("content") or content
    # except Exception:
    #     pass

    return jsonify({
        "ok": True,
        "zone_return": True,
        "ride_id": ride_id,
        "bike_id": bike_id,
        "user_id": user_id,
        "hub_id": hub_id,
        "content": content,
        "message": "허브가 꽉 차 있어 Zone 반납으로 라이딩을 종료했고, 자전거는 대여 가능 + 잠금 상태로 남겨두었습니다."
    }), 200
