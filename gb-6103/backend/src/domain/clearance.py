from sqlalchemy import select

from src.models.port_tests import port_tests
from src.models.revocations import revocations
from src.utils.serial import content_digest
from src.utils.timeparse import display_time

RELEASED = ("放行", "恢复送电")


def matching(revocation_rows, meter, tested_at):
    return [row for row in revocation_rows if row["meter"] == meter and row["invalid_from"] <= tested_at <= row["invalid_to"]]


def _revocation_view(row):
    return {
        "code": row["code"], "meter": row["meter"],
        "invalid_from": row["invalid_from"], "invalid_to": row["invalid_to"],
        "invalid_text": f"{display_time(row['invalid_from'])} 至 {display_time(row['invalid_to'])}",
    }


def _retest(candidate_rows, revocation_rows, test, revoked_by):
    """Latest passing re-test for a port, recorded after the revocation arrived."""
    floor = max(row["created_at"] for row in revoked_by)
    window_end = max(row["invalid_to"] for row in revoked_by)
    options = [
        row for row in candidate_rows
        if row["station"] == test["station"] and row["port_serial"] == test["port_serial"]
        and row["run_id"] != test["run_id"] and row["port_ok"] and row["station_decision"] == "通过"
        and row["recorded_at"] >= floor and row["tested_at"] >= window_end
        and row["tested_at"] >= test["tested_at"]
        and not matching(revocation_rows, row["meter"], row["tested_at"])
    ]
    if not options:
        return None
    best = max(options, key=lambda row: (row["recorded_at"], row["id"]))
    return {
        "id": best["id"], "run_id": best["run_id"], "station": best["station"],
        "port_serial": best["port_serial"], "insulation": best["insulation"],
        "interlock": best["interlock"], "meter": best["meter"], "tested_at": best["tested_at"],
        "tested_text": display_time(best["tested_at"]),
    }


def evaluate(db, run):
    """Live energization judgment for a finished acceptance run."""
    tests = [dict(row) for row in db.execute(
        select(port_tests).where(port_tests.c.run_id == run["id"]).order_by(port_tests.c.id)
    ).mappings()]
    revoked = [dict(row) for row in db.execute(select(revocations).order_by(revocations.c.id)).mappings()]
    stations_involved = {test["station"] for test in tests}
    candidates = []
    if stations_involved:
        candidates = [dict(row) for row in db.execute(
            select(port_tests).where(
                port_tests.c.station.in_(stations_involved), port_tests.c.run_id != run["id"]
            ).order_by(port_tests.c.recorded_at, port_tests.c.id)
        ).mappings()]

    grouped = {}
    for test in tests:
        grouped.setdefault((test["position"], test["station"], test["district"]), []).append(test)

    stations = []
    revoked_codes = set()
    for (position, station, district), station_tests in grouped.items():
        ports = []
        missing = []
        involved = []
        energizable = station_tests[0]["station_decision"] == "通过"
        for test in station_tests:
            revoked_by = matching(revoked, test["meter"], test["tested_at"])
            codes = [row["code"] for row in revoked_by]
            revoked_codes.update(codes)
            retest = _retest(candidates, revoked, test, revoked_by) if revoked_by else None
            if revoked_by:
                involved.append(test["port_serial"])
                line = (f"{test['port_serial']} 由仪表 {test['meter']} 于 {display_time(test['tested_at'])} "
                        f"测得 {test['insulation']} kΩ，落入撤销单 {'、'.join(codes)} 的失效时段")
            else:
                line = f"{test['port_serial']} 读数 {test['insulation']} kΩ，联锁{'通过' if test['interlock'] else '未通过'}"
            if revoked_by and retest:
                state = "复测合格"
                line += (f"；已于 {retest['tested_text']} 用仪表 {retest['meter']} 复测 "
                         f"{retest['insulation']} kΩ、联锁{'通过' if retest['interlock'] else '未通过'}"
                         f"（批次 #{retest['run_id']}）")
            elif revoked_by:
                state = "停送" if energizable else "读数失效"
                line += "；尚未复测合格"
                if energizable:
                    missing.append(test["port_serial"])
            elif test["port_ok"]:
                state = "放行" if energizable else "搁置"
                line += "，判为可送电" if energizable else "，但所属站原分站验收未通过"
            else:
                state = "不合格"
                line += "，原判定未通过"
            ports.append({
                "port_serial": test["port_serial"], "insulation": test["insulation"],
                "interlock": test["interlock"], "meter": test["meter"], "tested_at": test["tested_at"],
                "port_ok": test["port_ok"], "invalid": bool(revoked_by), "revocations": codes,
                "retest": retest, "state": state, "basis": line,
            })

        original = station_tests[0]["station_decision"]
        reason = station_tests[0]["reason"]
        if original != "通过":
            state = "搁置"
            basis = f"原分站验收搁置：{reason}"
        elif missing:
            state = "停送"
            basis = f"撤销单涉及枪口 {'、'.join(missing)} 尚未复测合格，暂停送电；无关枪口照常"
        elif involved:
            state = "恢复送电"
            basis = f"撤销单涉及枪口 {'、'.join(involved)} 均已复测合格，恢复送电"
        else:
            state = "放行"
            basis = "本批次未涉及校准撤销单，按原分站验收结论送电"
        stations.append({
            "position": position, "station": station, "district": district, "original": original,
            "state": state, "involved": involved, "basis": basis, "ports": ports,
        })

    energized = [item for item in stations if item["original"] == "通过"]
    released = [item for item in energized if item["state"] in RELEASED]
    if not tests:
        # A run finished before meter/tested_at intake existed has nothing to trace.
        judgment = "无检测台账"
    elif not energized:
        judgment = "无可送电站点"
    elif len(released) == len(energized):
        judgment = "恢复送电" if any(item["state"] == "恢复送电" for item in energized) else "放行"
    else:
        judgment = "停送待复测"
    snapshot = {
        "parameter": run["parameter"],
        "judgment": judgment,
        "releasable": judgment in RELEASED or judgment == "无可送电站点",
        # A sheet may be signed while some stations are held, because unrelated
        # stations still hand over. It is refused only when nothing be traced or
        # no station at all can be released.
        "signable": judgment != "无检测台账" and (bool(released) or judgment == "无可送电站点"),
        "revocations": [_revocation_view(row) for row in revoked if row["code"] in revoked_codes],
        "stations": stations,
    }
    snapshot["basis"] = [
        f"{item['station']}：{item['basis']}" for item in stations if item["state"] in ("停送", "恢复送电")
    ]
    if not snapshot["basis"]:
        if judgment == "无检测台账":
            snapshot["basis"] = ["本批次在检测台账启用前完成，无法按仪表号与检测时间核对，请重新送检"]
        elif judgment == "无可送电站点":
            snapshot["basis"] = ["本批次没有通过站点，没有可送电对象"]
        elif judgment == "停送待复测":
            snapshot["basis"] = ["全部通过站点均停送待复测，暂无可放行站点"]
        else:
            snapshot["basis"] = ["全部通过站点均未涉及校准撤销单，照常送电"]
    return snapshot


def digest(snapshot):
    return content_digest(snapshot)
