# menu2.py
from flask import(
  Blueprint, redirect, render_template, request, url_for, session
)
from .db import get_db

bp = Blueprint('menu2', __name__, url_prefix='/menu2')

@bp.route('/')
def menu2():
  db = get_db()

  sql = '''
  SELECT
    h.hub_id,
    h.hub_name,
    h.latitude,
    h.longitude,

    (
      SELECT COUNT(*)
      FROM bikes b
      WHERE b.assigned_hub_id = h.hub_id
        AND b.is_active       = 1
        AND b.is_under_repair = 0
        AND b.is_retired      = 0
        AND b.status          = 'Returned'
    ) AS parked_sum,

    (
      SELECT COALESCE(SUM(s.total_slots), 0)
      FROM stations s
      WHERE s.hub_id = h.hub_id
    ) AS total_sum

  FROM hubs h
  ORDER BY h.hub_id;
  '''
  rows = db.execute(sql).fetchall()
  hubs = [dict(row) for row in rows]

  # 완충 기준
  from .config import Config
  FULL_BATTERY = Config.FULL_BATTERY

  # 허브마다 top5 추천 자전거 붙이기
  for h in hubs:
    top = db.execute(
      """
      SELECT
        b.bike_id,
        b.serial_number,
        b.where_parked,
        b.battery_level_int,
        CASE
          WHEN b.where_parked='Station' AND b.battery_level_int >= ? THEN 1
          WHEN b.where_parked='Zone'    AND b.battery_level_int >= ? THEN 3
          WHEN b.where_parked='Station' AND b.battery_level_int <  ? THEN 2
          ELSE 4
        END AS category
      FROM bikes b
      WHERE b.assigned_hub_id = ?
        AND b.status = 'Returned'
        AND b.is_active = 1
        AND b.is_under_repair = 0
        AND b.is_retired = 0
      ORDER BY
        CASE
          WHEN b.where_parked='Station' AND b.battery_level_int >= ? THEN 1
          WHEN b.where_parked='Zone'    AND b.battery_level_int >= ? THEN 2
          WHEN b.where_parked='Station' AND b.battery_level_int <  ? THEN 3
          ELSE 4
        END ASC,
        b.battery_level_int DESC,
        (b.last_rental_time IS NOT NULL) ASC,
        b.last_rental_time ASC,
        b.bike_id ASC
      LIMIT 5
      """,
      (FULL_BATTERY, FULL_BATTERY, FULL_BATTERY,
       h["hub_id"],
       FULL_BATTERY, FULL_BATTERY, FULL_BATTERY)
    ).fetchall()

    h["top_bikes"] = [dict(r) for r in top]
    h["full_battery_threshold"] = FULL_BATTERY

  flash_msg = session.pop("menu2_flash", None)
  return render_template("menu2.html", hubs=hubs, flash_msg=flash_msg)


@bp.post("/rent")
def menu2_rent():
  user_id = session.get("user_id")
  if not user_id:
    return redirect(url_for("login.login"))

  bike_id = request.form.get("bike_id")
  next_hub_id = request.form.get("hub_id")  # 다시 그 허브로 포커싱할 때 쓰려고

  if not bike_id:
    session["menu2_flash"] = {"type": "danger", "text": "bike_id가 없습니다."}
    return redirect(url_for("menu2.menu2"))

  from .api import fetch_rent_bike_normal
  rent_json, status = fetch_rent_bike_normal(bike_id=bike_id)
  content_msg = None

  if isinstance(rent_json, dict):
      # generate_sentence 응답 구조 대응
      if "content" in rent_json:
          content_msg = rent_json["content"]
      elif "message" in rent_json:
          content_msg = rent_json["message"]
      elif "error" in rent_json:
          content_msg = rent_json["error"]

  if status < 400:
      session["menu2_flash"] = {
          "type": "success",
          "text": content_msg or "대여가 완료되었습니다."
      }
  else:
      session["menu2_flash"] = {
          "type": "danger",
          "text": content_msg or "대여 중 오류가 발생했습니다."
      }

  return redirect(url_for("menu2.menu2"))

