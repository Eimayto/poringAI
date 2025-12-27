from datetime import datetime
from .fee import calculate_bike_fee

def finalize_rental_payment_in_db(db, rental_id: int, end_hub_id: int, payment_method: str = "Mobile") -> dict:
    """
    rentals에서 rental_id의 진행중 대여를 찾아서
    - end_time = now
    - duration_minutes, charged_amount 계산
    - rentals 업데이트
    - (여기서는 쿠폰/포인트 등은 일단 0으로 처리해서 final_paid_amount = charged_amount)

    반환: 업데이트된 요약 dict
    """
    rental = db.execute(
        """
        SELECT rental_id, rental_start_date, rental_end_date, payment_status
          FROM rentals
         WHERE rental_id = ?
        """,
        (rental_id,)
    ).fetchone()

    if not rental:
        raise Exception("존재하지 않는 rental_id 입니다.")

    if rental["rental_end_date"] is not None:
        raise Exception("이미 반납(종료) 처리된 대여입니다.")

    # start_dt 파싱
    start_dt = datetime.fromisoformat(rental["rental_start_date"])
    end_dt = datetime.now()

    calc = calculate_bike_fee(start_dt, end_dt)
    duration_minutes = calc["duration_minutes"]
    charged_amount = calc["charged_amount"]

    # 여기서는 할인 로직이 없다고 가정 (필요하면 여기서 차감)
    used_point = 0
    canceled_amount = 0
    final_paid_amount = max(0, charged_amount - used_point - canceled_amount)

    # 결제 상태는 일단 Paid로 처리 (실결제 연동이면 Pending->Paid 변경 시점을 조정)
    db.execute(
        """
        UPDATE rentals
           SET rental_end_date   = ?,
               duration_minutes  = ?,
               charged_amount    = ?,
               final_paid_amount = ?,
               canceled_amount   = ?,
               used_point        = ?,
               payment_status    = ?,
               payment_method    = ?
         WHERE rental_id = ?
        """,
        (
            end_dt.isoformat(),
            duration_minutes,
            charged_amount,
            final_paid_amount,
            canceled_amount,
            used_point,
            "Paid",
            payment_method,
            rental_id
        )
    )

    return {
        "rental_id": rental_id,
        "rental_start_date": start_dt.isoformat(),
        "rental_end_date": end_dt.isoformat(),
        "duration_minutes": duration_minutes,
        "charged_amount": charged_amount,
        "final_paid_amount": final_paid_amount,
        "payment_status": "Paid",
        "payment_method": payment_method
    }