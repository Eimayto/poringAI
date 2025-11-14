from flask import(
  Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort
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

    -- 1) bikes 테이블에서 실제 주차된(반납된) 자전거 수
    (
      SELECT COUNT(*)
      FROM bikes b
      WHERE b.assigned_hub_id = h.hub_id
        AND b.is_active       = 1
        AND b.is_under_repair = 0
        AND b.is_retired      = 0
        AND b.status          = 'Returned'
    ) AS parked_sum,

    -- 2) 기존처럼 허브의 총 슬롯 수
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

  return render_template("menu2.html", hubs=hubs);