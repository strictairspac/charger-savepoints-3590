from fastapi import APIRouter, Depends

from src.config.resources import engine
from src.controllers.access import identity, operator
from src.schemas.revocations import RevocationEntry, RevocationInput
from src.services import revocations

router = APIRouter(prefix="/revocations", tags=["Revocations"])


@router.get("", response_model=list[RevocationEntry], dependencies=[Depends(identity)])
def list_revocations():
    with engine.connect() as db:
        return revocations.list_entries(db)


@router.post("", response_model=RevocationEntry, status_code=201)
def register(form: RevocationInput, user=Depends(operator)):
    with engine.begin() as db:
        return revocations.register(db, form, user["username"])
