from time import time

from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from src.constants.job_state import JobState
from src.domain import clearance
from src.models.reviews import reviews
from . import audit, revocations, runs


def get(db, run_id):
    row = db.execute(select(reviews).where(reviews.c.run_id == run_id)).mappings().first()
    return dict(row) if row else None


def sign(db, run_id, data, actor):
    run = runs.get(db, run_id)
    if run["status"] != JobState.DONE:
        raise HTTPException(409, "批次执行成功后才能签核")
    if get(db, run_id) is not None:
        raise HTTPException(409, "该批次已经签核")
    # Hold the same row as revocation registration, then re-read the ledger
    # under READ COMMITTED so a concurrently registered revocation is seen.
    revocations.guard(db)
    snapshot = clearance.evaluate(db, run)
    if not snapshot["signable"]:
        detail = "；".join(snapshot["basis"]) or "无检测台账"
        raise HTTPException(409, f"送电核对未通过，不能签署：{detail}")
    try:
        db.execute(insert(reviews).values(
            run_id=run_id, note=data.note, actor=actor, created_at=int(time()),
            snapshot=snapshot, digest=clearance.digest(snapshot),
        ))
    except IntegrityError as exc:
        raise HTTPException(409, "该批次已经签核") from exc
    audit.record(db, "review", actor, "run", run_id)
    return get(db, run_id)
