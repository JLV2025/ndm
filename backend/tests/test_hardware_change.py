"""硬件变更检测测试（spec 第六节）：指纹 diff 各情形 + 事件落库 + 调拨。

只做确定性集合比较（"什么变了"）；整机级变化只记录、只提示（意图不自动化）。
"""
import pytest

import storage.database as db
from analyzers.hardware_change import compute_fingerprint, diff_fingerprints, record_event
from services.collector_service import _save_to_sqlite


def fp(platform, models, serials, kind="stack"):
    return compute_fingerprint(platform, ",".join(models), ",".join(serials), kind)


# ============================================================
# 指纹 diff 各情形
# ============================================================

def test_无变化():
    a = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    assert diff_fingerprints(a, a) is None


def test_首次采集无事件():
    assert diff_fingerprints(None, fp("aruba_aoscx", ["JL727B"], ["SN1"])) is None


def test_成员新增():
    prev = fp("aruba_aoscx", ["JL727B"], ["SN1"])
    cur = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "member_added" and "SN2" in ev["detail"]


def test_新增成员型号不同不是整机更换():
    """混型号堆叠是常态（ITMD1SWI01 = JL728B + JL727B）——不能因为型号集合
    变化就误判成整机更换（整机更换的判据只有平台变化或 SN 零交集）。"""
    prev = fp("aruba_aoscx", ["JL727B"], ["SN1"])
    cur = fp("aruba_aoscx", ["JL727B", "JL728B"], ["SN1", "SN2"])
    assert diff_fingerprints(prev, cur)["kind"] == "member_added"


def test_成员减少():
    prev = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    cur = fp("aruba_aoscx", ["JL727B"], ["SN1"])
    assert diff_fingerprints(prev, cur)["kind"] == "member_removed"


def test_成员更换_部分交集同槽位新SN():
    prev = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN2"])
    cur = fp("aruba_aoscx", ["JL727B", "JL727B"], ["SN1", "SN3"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "member_replaced" and "SN3" in ev["detail"] and "SN2" in ev["detail"]


def test_整机更换_零交集():
    """Cisco 单机 → Aruba VSF 双机：平台/型号全变、SN 零交集"""
    prev = fp("cisco_ios", ["WS-C2960X-48FPD-L"], ["FCW1"], kind="standalone")
    cur = fp("aruba_aoscx", ["JL726B", "JL727B"], ["SG1", "CN2"])
    ev = diff_fingerprints(prev, cur)
    assert ev["kind"] == "full_replacement"
    assert "cisco_ios" in ev["detail"] and "aruba_aoscx" in ev["detail"]


def test_形态变化_standalone到一成员stack():
    prev = fp("aruba_aoscx", ["JL659A"], ["SN1"], kind="standalone")
    cur = fp("aruba_aoscx", ["JL659A"], ["SN1"], kind="stack")
    assert diff_fingerprints(prev, cur)["kind"] == "form_change"


def test_成员重编号():
    """集合相同、槽位绑定变化（成员 2 → 3）→ member_reordered（成员行是槽位身份，
    重编号会让旧行离线、新行建立，必须有事件解释）"""
    prev = compute_fingerprint("aruba_aoscx", "JL727B, JL727B", "SN1, SN2", "stack", "1, 2")
    cur = compute_fingerprint("aruba_aoscx", "JL727B, JL727B", "SN1, SN2", "stack", "1, 3")
    assert diff_fingerprints(prev, cur)["kind"] == "member_reordered"


# ============================================================
# 事件落库与调拨
# ============================================================

@pytest.fixture
def restore_db_path():
    original = db._db_path
    db.close_connection()
    yield
    db.close_connection()
    db._db_path = original


def save(tmp_path, **overrides):
    """以 Aruba VSF 双成员为默认场景写一次采集"""
    params = dict(
        device_name="SZXD1SWI01", device_ip="10.0.0.1",
        device_type="aruba_aoscx", device_platform="aruba_aoscx",
        week="2026-38", collected_at="2026-09-17T09:00:00",
        running_config="vsf member 1\n type jl726b\nvsf member 2\n type jl726b\n",
        logs_raw="",
        performance_results="{}", validation_results="{}", change_results="{}",
        software_version="ML.10.16.1020", serial_number="SN1, SN2",
        device_model="JL726B, JL726B",
        system_uptime_seconds=1000,
        port_details=[], port_errors={}, neighbors_data=[], boot_history="",
        member_ids="1, 2",
    )
    params.update(overrides)
    db.init_db(str(tmp_path))
    _save_to_sqlite(**params)
    return db.get_connection()


def test_记录事件与调拨(tmp_path, restore_db_path):
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    conn.execute("INSERT INTO devices (name, ip, type, platform) "
                 "VALUES ('SZXD1SWI01', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx')")
    did = conn.execute("SELECT id FROM devices WHERE name='SZXD1SWI01'").fetchone()["id"]

    record_event(conn, did, {"kind": "member_replaced", "detail": '{"in":["SN3"]}'},
                 "2026-09-22T10:00:00",
                 movements=[{"serial": "SN3", "from_device": "BJQD1SWI01"}])
    conn.commit()

    row = conn.execute("SELECT kind, detail FROM device_change_events").fetchone()
    assert row["kind"] == "member_replaced"
    assert "BJQD1SWI01" in row["detail"]              # 调拨来源进了 detail


def test_采集后写变更事件(tmp_path, restore_db_path):
    save(tmp_path)                                     # 首次采集 → 无事件（没有上次指纹）
    conn = db.get_connection()
    assert conn.execute("SELECT COUNT(*) FROM device_change_events").fetchone()[0] == 0

    save(tmp_path, collected_at="2026-09-18T09:00:00",
         serial_number="SN1, SN2, SN3", device_model="JL726B, JL726B, JL726B",
         member_ids="1, 2, 3")
    row = conn.execute("SELECT kind, detail FROM device_change_events").fetchone()
    assert row["kind"] == "member_added" and "SN3" in row["detail"]


def test_成员更换带调拨记录(tmp_path, restore_db_path):
    """SN2 上一轮在 BJQD1SWI01 名下，本轮出现在 SZXD1SWI01 → 事件 detail 记来源"""
    save(tmp_path, serial_number="SN1, SN4", device_model="JL726B, JL726B")
    save(tmp_path, device_name="BJQD1SWI01", collected_at="2026-09-18T09:00:00",
         serial_number="SN2, SN5", device_model="JL726B, JL726B")
    conn = save(tmp_path, collected_at="2026-09-19T09:00:00",
                serial_number="SN4, SN2", device_model="JL726B, JL726B")

    row = conn.execute(
        "SELECT kind, detail FROM device_change_events WHERE device_id="
        "(SELECT id FROM devices WHERE name='SZXD1SWI01')").fetchone()
    assert row["kind"] == "member_replaced"
    assert "BJQD1SWI01" in row["detail"] and "SN2" in row["detail"]
