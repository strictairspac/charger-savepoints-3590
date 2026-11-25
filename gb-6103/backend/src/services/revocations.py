from time import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src.models.revocations import clearance_guard, revocations
from src.utils.timeparse import parse_time
from . import audit


def guard(db):
    """Serialize revocation registration with clearance signing."""
    db.execute(select(clearance_guard.c.id).where(clearance_guard.c.id == 1).with_for_update())


def list_entries(db):
    query = select(revocations).order_by(revocations.c.invalid_from.desc(), revocations.c.id.desc()).limit(200)
    return [dict(row) for row in db.execute(query).mappings()]


def get(db, code):
    row = db.execute(select(revocations).where(revocations.c.code == code)).mappings().first()
    if row is None:
        raise HTTPException(404, "撤销单不存在")
    return dict(row)


def register(db, data, actor):
    guard(db)
    invalid_from = parse_time(data.invalid_from, "失效开始时间")
    invalid_to = parse_time(data.invalid_to, "失效结束时间")
    if invalid_to < invalid_from:
        raise HTTPException(422, "失效结束时间不能早于开始时间")
    row = {
        "code": data.code or f"RV-{uuid4().hex[:8].upper()}",
        "meter": data.meter, "invalid_from": invalid_from, "invalid_to": invalid_to,
        "note": (data.note or "").strip(), "actor": actor, "created_at": int(time()),
    }
    try:
        change = db.execute(insert(revocations).values(**row))
    except IntegrityError as exc:
        raise HTTPException(409, "撤销单编号已登记") from exc
    audit.record(db, "revocation", actor, "revocation", change.inserted_primary_key[0])
    return get(db, row["code"])
