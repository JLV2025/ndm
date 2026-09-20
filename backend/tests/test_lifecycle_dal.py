"""设备生命周期数据层测试。

三条语义钉死：
  1. **手工值不被自动刷新覆盖**（api 写入遇到 manual 行要跳过）
  2. 序列号匹配容忍现实输入（大小写/空格/堆叠成员串），命中多台报 ambiguous 不猜
  3. 坏日期报错而不是静默丢弃（否则页面显示空白，分不清"没填"和"填错"）
"""
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from storage import lifecycle_dal as dal  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    # 一台堆叠（两个成员序列号）+ 一台单机
    c.execute("INSERT INTO devices (id, name, ip, type, model, serial_number) "
              "VALUES (1, 'BJQD1SWI01', '10.0.0.1', 'aruba_aoscx', 'JL659A', NULL)")
    c.execute("INSERT INTO devices (id, name, ip, type, model, serial_number) "
              "VALUES (2, 'SHAD1SWI01', '10.0.0.2', 'cisco_ios', 'C9500-48Y4C', 'CAT2322L0L4')")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, serial_number) "
              "VALUES (10, 1, '2026-38', '2026-09-20T08:00:00', 'SG30LMQ17K, SG30LMQ108')")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, serial_number) "
              "VALUES (11, 2, '2026-38', '2026-09-20T08:00:00', 'CAT2322L0L4')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


# ---------------------------------------------------------------- 基础工具

def test_split_serials_容忍分隔与重复():
    assert dal.split_serials("SG30LMQ17K, SG30LMQ108") == ["SG30LMQ17K", "SG30LMQ108"]
    assert dal.split_serials("A,B;A") == ["A", "B"]
    assert dal.split_serials(None) == [] and dal.split_serials("  ") == []


def test_norm_date_坏格式报错而不是静默丢弃():
    assert dal.norm_date("2028-05-01") == "2028-05-01"
    assert dal.norm_date("") == ""
    with pytest.raises(ValueError) as ei:
        dal.norm_date("2028/05/01")
    assert "YYYY-MM-DD" in str(ei.value)


def test_list_device_serials_拆堆叠成员(conn):
    assert dal.list_device_serials(conn, "BJQD1SWI01") == ["SG30LMQ17K", "SG30LMQ108"]
    assert dal.list_device_serials(conn, "SHAD1SWI01") == ["CAT2322L0L4"]


# ---------------------------------------------------------------- 读写

def test_upsert_warranty_插入与更新(conn):
    assert dal.upsert_warranty(conn, "SHAD1SWI01", "CAT2322L0L4", "2028-05-01",
                               note="Smart Net", verified_by="张工") is True
    row = conn.execute("SELECT warranty_end, source, verified_by, note FROM device_lifecycle").fetchone()
    assert tuple(row) == ("2028-05-01", "manual", "张工", "Smart Net")

    dal.upsert_warranty(conn, "SHAD1SWI01", "CAT2322L0L4", "2029-01-01", verified_by="李工")
    rows = conn.execute("SELECT COUNT(*), warranty_end FROM device_lifecycle").fetchall()
    assert rows[0][0] == 1 and rows[0][1] == "2029-01-01"     # 同一 (设备,序列号) 是更新不是新增


def test_api写入不覆盖手工值(conn):
    """人工核实过的数据不该被一次外部查询悄悄改掉 —— 除非 force。"""
    dal.upsert_warranty(conn, "SHAD1SWI01", "CAT2322L0L4", "2028-05-01", verified_by="张工")
    assert dal.upsert_warranty(conn, "SHAD1SWI01", "CAT2322L0L4", "2027-01-01",
                               source="api") is False
    assert tuple(conn.execute("SELECT warranty_end, source FROM device_lifecycle").fetchone()) == \
        ("2028-05-01", "manual")
    # force 可以覆盖（显式的"以外部数据为准"）
    assert dal.upsert_warranty(conn, "SHAD1SWI01", "CAT2322L0L4", "2027-01-01",
                               source="api", force=True) is True
    assert tuple(conn.execute("SELECT warranty_end, source FROM device_lifecycle").fetchone()) == \
        ("2027-01-01", "api")


def test_model_eol_读写与手工保护(conn):
    dal.upsert_model_eol(conn, "JL659A", end_of_sale="2025-01-31",
                         end_of_support="2030-01-31", bulletin="EOL123", source="manual")
    eol = dal.get_model_eol(conn, "JL659A")
    assert eol["end_of_sale"] == "2025-01-31" and eol["source"] == "manual"

    assert dal.upsert_model_eol(conn, "JL659A", end_of_sale="2024-01-01", source="api") is False
    assert dal.get_model_eol(conn, "JL659A")["end_of_sale"] == "2025-01-31"


def test_设备生命周期全景(conn):
    dal.upsert_warranty(conn, "BJQD1SWI01", "SG30LMQ17K", "2028-05-01")
    dal.upsert_model_eol(conn, "JL659A", end_of_sale="2025-01-31")
    info = dal.get_device_lifecycle(conn, "BJQD1SWI01")
    assert info["models"] == ["JL659A"]
    assert info["model_eol"][0]["end_of_sale"] == "2025-01-31"
    by_serial = {s["serial"]: s for s in info["serials"]}
    assert by_serial["SG30LMQ17K"]["warranty_end"] == "2028-05-01"
    assert by_serial["SG30LMQ108"] == {"serial": "SG30LMQ108"}   # 未登记的第二成员也在清单里


# ---------------------------------------------------------------- 批量导入

def test_parse_import_text_容忍常见粘贴格式():
    text = """# 从 HPE 网页抄下来的
FOC1234X5AB,2028-05-01,Smart Net 到期
CN41LM90H4\t2027-12-31
SG30LMQ17K 2029-06-30
坏行没有日期
"""
    rows, bad = dal.parse_import_text(text)
    assert rows == [("FOC1234X5AB", "2028-05-01", "Smart Net 到期"),
                    ("CN41LM90H4", "2027-12-31", ""),
                    ("SG30LMQ17K", "2029-06-30", "")]
    assert bad == ["坏行没有日期"]


def test_批量导入按序列号匹配设备(conn):
    rows = [("sg30lmq17k", "2028-05-01", ""),          # 小写也能匹配
            ("CAT2322L0L4", "2027-01-01", ""),
            ("NOSUCHSERIAL", "2028-01-01", "")]
    res = dal.bulk_import_warranty(conn, rows, verified_by="张工")
    assert [m["device_name"] for m in res["matched"]] == ["BJQD1SWI01", "SHAD1SWI01"]
    assert res["unmatched"] == ["NOSUCHSERIAL"] and res["ambiguous"] == []
    # 未匹配的序列号不得写入任何数据
    assert conn.execute("SELECT COUNT(*) FROM device_lifecycle").fetchone()[0] == 2


def test_同序列号命中多台报_ambiguous_不猜(conn):
    conn.execute("INSERT INTO devices (id, name, ip, type) VALUES (3, 'DUPD1SWI01', '10.0.0.3', 'cisco_ios')")
    conn.execute("INSERT INTO collections (id, device_id, week, collected_at, serial_number) "
                 "VALUES (12, 3, '2026-38', '2026-09-20T08:00:00', 'CAT2322L0L4')")
    conn.commit()
    res = dal.bulk_import_warranty(conn, [("CAT2322L0L4", "2027-01-01", "")], verified_by="张工")
    assert len(res["matched"]) == 2 and len(res["ambiguous"]) == 1
    assert set(res["ambiguous"][0]["devices"]) == {"SHAD1SWI01", "DUPD1SWI01"}


# ---------------------------------------------------------------- 概况

def test_概况给出待查所需字段(conn):
    dal.upsert_warranty(conn, "BJQD1SWI01", "SG30LMQ17K", "2028-05-01", verified_by="张工")
    dal.upsert_warranty(conn, "BJQD1SWI01", "SG30LMQ108", "2026-10-01", verified_by="张工")
    dal.upsert_model_eol(conn, "JL659A", end_of_sale="2025-01-31")
    rows = {r["device_name"]: r for r in dal.overview(conn)}
    bjq = rows["BJQD1SWI01"]
    assert bjq["registered"] == 2 and bjq["warranty_end"] == "2026-10-01"   # 最早到期最该关注
    assert bjq["eol_announced"] is True and bjq["verified_at"]
    shad = rows["SHAD1SWI01"]
    assert shad["registered"] == 0 and shad["warranty_end"] == "" and shad["eol_announced"] is False
