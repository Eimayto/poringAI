from datetime import datetime
import math

# 하루치 전체 요금 (09~18: 9시간*30원 + 그 외: 15시간*5원)
FULL_DAY_FEE = 20700

def get_daily_accumulated_fee(target_dt: datetime) -> int:
    """
    해당 날짜의 00:00부터 target_dt(시:분)까지 누적 요금.
    - 기본: 전 구간 5원/분
    - 09:00~18:00 구간은 30원/분이므로, 이미 5원 깔린 상태에서 +25원/분을 추가
    """
    minutes_passed = target_dt.hour * 60 + target_dt.minute

    day_start = 9 * 60     # 540
    day_end   = 18 * 60    # 1080

    # 1) 전 구간 5원/분
    fee = minutes_passed * 5

    # 2) 09:00~18:00 겹치는 분만 +25원/분
    overlap_start = max(day_start, 0)
    overlap_end   = min(minutes_passed, day_end)

    if overlap_end > overlap_start:
        fee += (overlap_end - overlap_start) * 25

    return int(fee)


def calculate_bike_fee(start_dt: datetime, end_dt: datetime) -> dict:
    """
    start_dt ~ end_dt 총 요금과 이용시간(분)을 계산해서 반환.
    ERD rentals에 넣기 좋게 dict 형태로 리턴.

    return:
      {
        "duration_minutes": int,
        "charged_amount": int
      }
    """
    if end_dt < start_dt:
        raise ValueError("end_dt가 start_dt보다 빠릅니다.")

    duration_minutes = math.ceil(
        (end_dt - start_dt).total_seconds() / 60
    )

    start_date = start_dt.date()
    end_date = end_dt.date()
    date_diff = (end_date - start_date).days

    if date_diff == 0:
        # 같은 날: (자정~end) - (자정~start)
        total_fee = get_daily_accumulated_fee(end_dt) - get_daily_accumulated_fee(start_dt)
    else:
        # 여러 날:
        # 첫날: (start~24:00) = FULL - (자정~start)
        first_day_fee = FULL_DAY_FEE - get_daily_accumulated_fee(start_dt)

        # 중간 완전한 날들
        middle_days_fee = max(0, date_diff - 1) * FULL_DAY_FEE

        # 마지막날: (자정~end)
        last_day_fee = get_daily_accumulated_fee(end_dt)

        total_fee = first_day_fee + middle_days_fee + last_day_fee

    if total_fee < 0:
        # 이론상 나오면 안 되지만 방어
        total_fee = 0

    return {
        "duration_minutes": duration_minutes,
        "charged_amount": int(total_fee)
    }
