from datetime import datetime

from fastapi import HTTPException


def validate_month_key(
    value: int,
    field_name: str,
) -> int:
    text = str(value)

    try:
        parsed = datetime.strptime(text, "%Y%m%d")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} phải có dạng YYYYMM01.",
        )

    if parsed.day != 1:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} phải là ngày đầu tháng YYYYMM01.",
        )

    if not 1900 <= parsed.year <= 2100:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} nằm ngoài khoảng cho phép.",
        )

    return value