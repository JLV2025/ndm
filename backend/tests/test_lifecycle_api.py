"""生命周期 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）。

重点：
  · 手工登记是主路径，必须简单可靠（保存/导入/型号 EoL 三个入口）
  · 批量导入**未匹配的序列号原样回显**（不猜、不静默丢）
  · 未配 Cisco 凭据时刷新给可读 400，而不是 500 或静默失败
"""
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from api import lifecycle as lc  # noqa: E402

# 相对"今天"生成日期，避免测试随时间腐化（阈值是日历月：+30 天必在 2 个月内，
# +170 天必在 6 个月内，+400 天必超两个阈值）
FAR = (date.today() + timedelta(days=400)).isoformat()
SOON = (date.today() + timedelta(days=30)).isoformat()
EOL_SOON = (date.today() + timedelta(days=170)).isoformat()
PAST = (date.today() - timedelta(days=10)).isoformat()


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (id, name, ip, type, model) "
              "VALUES (1, 'BJQD1SWI01', '10.0.0.1', 'aruba_aoscx', 'JL659A')")
    c.execute("INSERT INTO devices (id, name, ip, type, model) "
              "VALUES (2, 'SHAD1SWI01', '10.0.0.2', 'cisco_ios', 'C9500-48Y4C')")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, serial_number) "
              "VALUES (10, 1, '2026-38', '2026-09-20T08:00:00', 'SG30LMQ17K, SG30LMQ108')")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, serial_number) "
              "VALUES (11, 2, '2026-38', '2026-09-20T08:00:00', 'CAT2322L0L4')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def call(coro):
    return asyncio.run(coro)


def test_取设备生命周期_含序列号与刷新状态(conn):
    info = call(lc.get_device_lifecycle("BJQD1SWI01"))
    assert info["models"] == ["JL659A"]
    assert [s["serial"] for s in info["serials"]] == ["SG30LMQ17K", "SG30LMQ108"]
    assert "available" in info["refresh"]                    # 前端据此提示"未配凭据"

    with pytest.raises(HTTPException) as ei:
        call(lc.get_device_lifecycle("NOSUCH"))
    assert ei.value.status_code == 404


def test_保存保修期逐序列号(conn):
    res = call(lc.save_device_lifecycle("BJQD1SWI01", lc.DeviceLifecycleUpdate(
        rows=[lc.WarrantyRow(serial="SG30LMQ17K", warranty_end="2028-05-01", note="Smart Net"),
              lc.WarrantyRow(serial="SG30LMQ108", warranty_end="2026-10-01")],
        verified_by="张工")))
    assert res["ok"] is True and res["saved"] == ["SG30LMQ17K", "SG30LMQ108"]
    rows = {s["serial"]: s for s in res["lifecycle"]["serials"]}
    assert rows["SG30LMQ17K"]["warranty_end"] == "2028-05-01"
    assert rows["SG30LMQ17K"]["verified_by"] == "张工"
    assert rows["SG30LMQ17K"]["source"] == "manual"


def test_保存坏日期给可读400(conn):
    with pytest.raises(HTTPException) as ei:
        call(lc.save_device_lifecycle("BJQD1SWI01", lc.DeviceLifecycleUpdate(
            rows=[lc.WarrantyRow(serial="SG30LMQ17K", warranty_end="2028/05/01")])))
    assert ei.value.status_code == 400 and "YYYY-MM-DD" in str(ei.value.detail)


def test_批量导入_匹配与未匹配都报给用户(conn):
    res = call(lc.import_warranty(lc.ImportRequest(
        text="sg30lmq17k,2028-05-01,Smart Net\nCAT2322L0L4 2027-12-31\nNOSUCHX,2028-01-01\n乱写的行\n",
        verified_by="张工")))
    assert {m["device_name"] for m in res["matched"]} == {"BJQD1SWI01", "SHAD1SWI01"}
    assert res["unmatched"] == ["NOSUCHX"]
    assert res["invalid"] == ["乱写的行"]
    # 未匹配的不许写库：只有匹配上的 2 条
    assert conn.execute("SELECT COUNT(*) FROM device_lifecycle").fetchone()[0] == 2


def test_导入行数上限(conn):
    with pytest.raises(HTTPException) as ei:
        call(lc.import_warranty(lc.ImportRequest(
            text="\n".join(f"SN{i},2028-01-01" for i in range(lc.MAX_IMPORT_LINES + 1)))))
    assert ei.value.status_code == 400 and "最多" in str(ei.value.detail)


def test_导入空文本400(conn):
    with pytest.raises(HTTPException) as ei:
        call(lc.import_warranty(lc.ImportRequest(text="   \n# 只有注释\n")))
    assert ei.value.status_code == 400


def test_手工登记型号EoL可覆盖(conn):
    call(lc.save_model_eol("JL659A", lc.ModelEolUpdate(
        end_of_sale="2025-01-31", end_of_support="2030-01-31", updated_by="张工")))
    row = call(lc.save_model_eol("JL659A", lc.ModelEolUpdate(
        end_of_sale="2025-03-31", updated_by="李工")))["model"]
    assert row["end_of_sale"] == "2025-03-31" and row["source"] == "manual"
    assert row["updated_by"] == "李工"

    with pytest.raises(HTTPException) as ei:
        call(lc.save_model_eol("JL659A", lc.ModelEolUpdate(end_of_sale="2025/01/01")))
    assert ei.value.status_code == 400


def test_刷新未配凭据给可读400(conn, monkeypatch):
    monkeypatch.delenv("CISCO_API_CLIENT_ID", raising=False)
    monkeypatch.delenv("CISCO_API_CLIENT_SECRET", raising=False)
    with pytest.raises(HTTPException) as ei:
        call(lc.refresh_eox())
    assert ei.value.status_code == 400 and "环境变量" in str(ei.value.detail)


def test_概况给出待查清单所需字段(conn):
    call(lc.save_device_lifecycle("BJQD1SWI01", lc.DeviceLifecycleUpdate(
        rows=[lc.WarrantyRow(serial="SG30LMQ17K", warranty_end="2028-05-01")],
        verified_by="张工")))
    devices = {d["device_name"]: d for d in call(lc.lifecycle_overview())["devices"]}
    assert devices["BJQD1SWI01"]["registered"] == 1
    assert devices["SHAD1SWI01"]["registered"] == 0 and devices["SHAD1SWI01"]["warranty_end"] == ""


# ------------------------------------------------ Plan 2：物理清单（生命周期页数据源）

@pytest.fixture
def phys_conn(tmp_path):
    """物理清单数据集：双成员堆叠 + 单成员堆叠 + 两台单机，覆盖 绿/橙/红/未登记 四态"""
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.executemany(
        "INSERT INTO devices (name, ip, type, model, kind, stack_name, member_no, "
        "serial_number, location) VALUES (?,?,?,?,?,?,?,?,?)", [
            ("SZXD1SWI01", "10.0.0.3", "cisco_ios", "C9500-24Y4C", "stack", "", None, "", "SZX"),
            ("SZXD1SWI01-1", "", "cisco_ios", "C9500-24Y4C", "member", "SZXD1SWI01", 1,
             "FCW2129B3TR", "SZX"),
            ("SZXD1SWI01-2", "", "cisco_ios", "C9500-24Y4C", "member", "SZXD1SWI01", 2,
             "FCW2129B3TS", "SZX"),
            ("SZXD1SWI03", "10.0.0.6", "aruba_aoscx", "JL659A", "stack", "", None, "", "SZX"),
            ("SZXD1SWI03-1", "", "aruba_aoscx", "JL659A", "member", "SZXD1SWI03", 1,
             "CN12345678", "SZX"),
            ("UCDD1SWI01", "10.0.0.4", "aruba_aoscx", "JL659A", "standalone", "", None,
             "SG30LMQ17K", "UCD"),
            ("SHAD1SWI02", "10.0.0.5", "cisco_ios", "C9500-48Y4C", "standalone", "", None,
             "CAT2322L0L4", "SHAD"),
        ])
    c.executemany(
        "INSERT INTO device_lifecycle (device_name, serial, warranty_end, note, source, "
        "verified_at, updated_at) VALUES (?,?,?,?,?,?,'2026-09-22T00:00:00')", [
            ("SZXD1SWI01", "FCW2129B3TR", FAR, "", "manual", "2026-09-01"),
            ("SZXD1SWI01", "FCW2129B3TS", "", "Unavailable", "manual", "2026-09-01"),
            ("SHAD1SWI02", "cat2322l0l4", SOON, "", "api", ""),   # 小写：靠宽容比对命中
        ])
    c.executemany(
        "INSERT INTO eol_models (model, end_of_sale, end_of_support, source) VALUES (?,?,?,'manual')", [
            ("C9500-24Y4C", FAR, FAR),
            ("JL659A", PAST, ""),
            ("C9500-48Y4C", EOL_SOON, ""),
        ])
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def test_物理清单_每行带三色状态(phys_conn):
    rows = {r["name"]: r for r in call(lc.lifecycle_physical())["devices"]}
    assert set(rows) == {"SZXD1SWI01-1", "SZXD1SWI01-2", "SZXD1SWI03-1",
                         "UCDD1SWI01", "SHAD1SWI02"}

    r1 = rows["SZXD1SWI01-1"]                     # 双成员堆叠：物理名带后缀，编辑归堆叠
    assert r1["display_name"] == "SZXD1SWI01-1"
    assert r1["device"] == "SZXD1SWI01" and r1["kind"] == "member"
    assert r1["serial"] == "FCW2129B3TR" and r1["model"] == "C9500-24Y4C"
    assert r1["location"] == "SZX"
    assert r1["warranty_status"] == "ok"
    assert (r1["source"], r1["verified_at"]) == ("manual", "2026-09-01")
    assert r1["eol"]["status"] == "ok"

    # 未填写日期且备注 Unavailable → 按出保（红）
    assert rows["SZXD1SWI01-2"]["warranty_status"] == "expired"

    # 单成员堆叠：展示名回基础名；没登记保修 → 橙
    assert rows["SZXD1SWI03-1"]["display_name"] == "SZXD1SWI03"
    assert rows["SZXD1SWI03-1"]["warranty_status"] == "missing"

    u = rows["UCDD1SWI01"]                        # 单机：展示名 = 存储名，EoS 已过 → 红
    assert u["display_name"] == "UCDD1SWI01" and u["device"] == "UCDD1SWI01"
    assert u["warranty_status"] == "missing"
    assert u["eol"] == {"end_of_sale": PAST, "end_of_support": "", "status": "expired"}

    s = rows["SHAD1SWI02"]                        # ≤2 月橙；EoS 在 6 个月内橙
    assert s["warranty_status"] == "soon"
    assert s["eol"]["status"] == "soon"
    assert s["warranty_end"] == SOON              # 登记串是小写，靠宽容比对命中


def test_详情接口_成员名归到堆叠记账(phys_conn):
    """成员详情页看到的保修 = 写在堆叠名下的那行；兄弟成员不算「离线登记」"""
    info = call(lc.get_device_lifecycle("SZXD1SWI01-1"))
    assert [s["serial"] for s in info["serials"]] == ["FCW2129B3TR"]
    assert info["serials"][0]["warranty_status"] == "ok"
    assert info["serials"][0]["physical_name"] == "SZXD1SWI01-1"
    assert info["extra_rows"] == []
    assert info["model_eol"][0]["status"] == "ok"


def test_保存保修返回带状态字段(phys_conn):
    res = call(lc.save_device_lifecycle("UCDD1SWI01", lc.DeviceLifecycleUpdate(
        rows=[lc.WarrantyRow(serial="SG30LMQ17K", warranty_end=FAR)],
        verified_by="张工")))
    assert res["lifecycle"]["serials"][0]["warranty_status"] == "ok"
