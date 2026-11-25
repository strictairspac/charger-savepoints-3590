from .intake import validate
from .transaction import receive

CONFIG = {
    "title": "桐驿充电·换站批次验收",
    "team": "桐驿公共充电运维组（14 人）",
    "description": "逐站登记枪口，隔离编号冲突以及检测未过的站点，同批其他站点仍可交接；校准撤销单迟到时按仪表号与失效时段追查原检测记录，涉及枪口复测合格才恢复送电。",
    "direction": "事务与锁 / 保存点 / 撤销追溯",
    "mechanism": "PostgreSQL 对站点和枪口写入建立真实 SAVEPOINT，站内原子回退、批内继续；撤销单与签核共用行锁。",
    "modules": ["换站交接", "站点与枪口", "分站验收", "送电核对单"],
    "unit": "验收批次",
    "max_parameter": 100000,
    "parameter_label": "绝缘读数下限（kΩ）",
    "default_parameter": 1000,
    "facts": ["通过站点", "搁置站点", "已登记枪口", "撤销追溯"],
    "palette": 3,
    "fixture": "TY-1124-站批",
    "meter_label": "仪表号",
    "tested_label": "检测时间",
    "revocation_label": "校准撤销单",
    "clearance_states": {
        "放行": "可送电",
        "恢复送电": "复测后恢复送电",
        "停送": "停送待复测",
        "读数失效": "读数失效",
        "搁置": "搁置不送电",
        "复测合格": "复测合格",
        "不合格": "不合格",
        "停送待复测": "停送待复测",
        "无可送电站点": "无可送电站点",
        "无检测台账": "无检测台账",
    },
}


def port(serial, insulation, meter, tested_at, interlock=True):
    return {"serial": serial, "insulation": insulation, "interlock": interlock, "meter": meter, "tested_at": tested_at}


def station(code, district, *ports):
    return {"station": code, "district": district, "ports": list(ports)}


FIXTURES = [
    {
        "code": "TY-1124-AC", "title": "TY-1124-站批", "description": "含跨站序列号重复及低绝缘读数；送检时记下仪表号与检测时间。",
        "payload": {"stations": [
            station("TY-S11", "口袋公园", port("TY-P01", 1840, "M-2201", "2026-11-24 08:40")),
            station("TY-S12", "东客站", port("TY-P02", 1280, "M-2202", "2026-11-24 08:41"),
                    port("TY-P01", 1450, "M-2201", "2026-11-24 08:42")),
            station("TY-S13", "体育场", port("TY-P03", 620, "M-2203", "2026-11-24 08:44")),
            station("TY-S14", "竹园路", port("TY-P02", 1000, "M-2202", "2026-11-24 08:45"),
                    port("TY-P03", 1610, "M-2203", "2026-11-24 08:46")),
        ]},
    },
    {
        "code": "TY-1125-SV", "title": "二次送检·重验联锁", "description": "联锁失败后，站号可用于同批的复测记录；复测沿用仪表号与检测时间。",
        "payload": {"stations": [
            station("TY-S21", "老集镇", port("TY-P21", 1800, "M-2301", "2026-11-25 09:10", False)),
            station("TY-S21", "老集镇", port("TY-P21", 1800, "M-2301", "2026-11-25 09:15")),
        ]},
    },
    {
        "code": "TY-1125-RT", "title": "复测批次·撤销后重测", "description": "撤销单迟到后按涉及枪口复测；复测合格的枪口恢复送电。",
        "payload": {"stations": [
            station("TY-S11", "口袋公园", port("TY-P01", 1520, "M-2402", "2026-11-25 10:20")),
            station("TY-S15", "新城大道", port("TY-P04", 1720, "M-2402", "2026-11-25 10:24")),
        ]},
    },
]

# Demonstration revocations: the meter M-2201 was later found drifting between
# 08:39 and 08:43, so TY-S11/TY-S12 readings from it are invalidated.
FIXTURE_REVOCATIONS = [
    {"code": "RV-1124-01", "meter": "M-2201",
     "invalid_from": "2026-11-24 08:39", "invalid_to": "2026-11-24 08:43",
     "registered_at": "2026-11-24 09:20",
     "note": "计量室补发：M-2201 期间读数漂移，涉及读数一律失效。"},
]


def run(payload, parameter, db, run_id):
    if type(parameter) is not int or not 1 <= parameter <= 100000:
        raise ValueError("验收下限须为 1–100000 kΩ 整数")
    validate(payload)
    rows, accepted, ports = receive(db, run_id, payload["stations"], parameter)
    held = len(rows) - accepted
    return {
        "summary": f"{len(rows)} 次分站送检，{accepted} 站通过、{held} 次搁置，登记 {ports} 个枪口。",
        "metrics": {"通过站点": accepted, "搁置站点": held, "已登记枪口": ports},
        "rows": rows,
    }
