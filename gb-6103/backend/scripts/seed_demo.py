import json
from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from migrations.v001_workbench import upgrade
from src.config.resources import engine
from src.config.settings import DEMO_PASSWORD
from src.constants.roles import Role
from src.domain.scenario import FIXTURES, FIXTURE_REVOCATIONS
from src.models.cases import cases
from src.models.revocations import revocations
from src.models.users import users
from src.utils.passwords import hash_password
from src.utils.timeparse import parse_time


def insert_new(db, table, key, values, refresh=()):
    if db.dialect.name == "postgresql":
        stmt = pg_insert(table).values(**values)
        if refresh:
            stmt = stmt.on_conflict_do_update(
                index_elements=[key], set_={column: stmt.excluded[column] for column in refresh}
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[key])
    else:
        update = {column: table.c[column] for column in refresh} if refresh else {key: table.c[key]}
        stmt = mysql_insert(table).values(**values).on_duplicate_key_update(**update)
    db.execute(stmt)


def setup_schema():
    with engine.begin() as db:
        upgrade(db)


def seed():
    with engine.begin() as db:
        existing = set(db.execute(select(users.c.username)).scalars())
        for role in Role:
            if role.value not in existing:
                insert_new(db, users, "username", {
                    "username": role.value, "role": role.value, "password_hash": hash_password(DEMO_PASSWORD),
                })
        for fixture in FIXTURES:
            insert_new(db, cases, "code", {**fixture, "created_by": "seed"}, refresh=("payload", "description", "title"))
        for item in FIXTURE_REVOCATIONS:
            insert_new(db, revocations, "code", {
                "code": item["code"], "meter": item["meter"],
                "invalid_from": parse_time(item["invalid_from"]),
                "invalid_to": parse_time(item["invalid_to"]),
                "note": item["note"], "actor": "seed", "created_at": parse_time(item["registered_at"]),
            })
        return {table.name: db.scalar(select(func.count()).select_from(table))
                for table in (users, cases, revocations)}


if __name__ == "__main__":
    setup_schema()
    print(json.dumps(seed(), sort_keys=True))
