from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
MAX_EPOCH = 4_102_444_800  # 2100-01-01T00:00:00Z


def parse_time(value, label="时间"):
    """Accept epoch seconds or ISO 8601; naive values use China Standard Time."""
    if type(value) is int:
        stamp = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{label}不能为空")
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        except ValueError as exc:
            raise ValueError(f"{label}须为 epoch 秒或 ISO 8601 时间") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=CST)
        stamp = int(parsed.timestamp())
    else:
        raise ValueError(f"{label}须为 epoch 秒或 ISO 8601 时间")
    if not 0 <= stamp <= MAX_EPOCH:
        raise ValueError(f"{label}超出可登记范围")
    return stamp


def display_time(stamp):
    return datetime.fromtimestamp(stamp, CST).strftime("%Y-%m-%d %H:%M")
