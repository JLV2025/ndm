"""Cisco EoX 客户端测试 —— mock HTTP（凭据到位前无法实盘验证，如实标注）。

覆盖四件事：
  1. 未配凭据 → **可读原因**（手工登记永远是可用路径，不能让刷新把功能带崩）
  2. 解析：日期在 {"value": …} 里；同一 PID 多条迁移路径记录
  3. 分片（每次 ≤20 个型号）与 404（该批没记录，不是错误）
  4. 写库：命中写 source='api'；**未公告不写库**（保持"未登记"语义）；手工登记默认不被覆盖
"""
import sys
from pathlib import Path

import pytest
import requests

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from services import eox_client  # noqa: E402
from storage import lifecycle_dal as dal  # noqa: E402

EOX_JSON = {
    "EOXRecord": [{
        "EOLProductID": "C9500-48Y4C",
        "ProductIDDescription": "Cisco Catalyst 9500 48-Port",
        "ProductBulletinNumber": "EOL12345",
        "LinkToProductBulletinURL": "https://cisco.example/bulletin/EOL12345",
        "EOXExternalAnnouncementDate": {"value": "2025-01-15"},
        "EndOfSaleDate": {"value": "2025-07-15"},
        "LastDateOfSupport": {"value": "2030-07-31"},
        "EOXInputType": "ShowEOXByPids",
        "EOXInputValue": "C9500-48Y4C",
    }]
}


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """按 URL 里的型号清单决定返回什么（默认全部命中 EOX_JSON，含 404 批次的模拟）。"""

    def __init__(self, payload=EOX_JSON, missing=()):
        self.payload, self.missing, self.get_calls = payload, set(missing), []

    def post(self, url, data=None, auth=None, timeout=None):
        return FakeResp({"access_token": "tok"})

    def get(self, url, headers=None, params=None, timeout=None):
        self.get_calls.append(url)
        pids = url.rsplit("/", 1)[-1].split(",")
        if any(p in self.missing for p in pids):
            return FakeResp(None, status=404)
        return FakeResp(self.payload)


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    yield c
    db.close_connection()
    db._db_path = original


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("CISCO_API_CLIENT_ID", "cid")
    monkeypatch.setenv("CISCO_API_CLIENT_SECRET", "secret")


# ---------------------------------------------------------------- 凭据与状态

def test_未配凭据给可读原因(monkeypatch, conn):
    monkeypatch.delenv("CISCO_API_CLIENT_ID", raising=False)
    monkeypatch.delenv("CISCO_API_CLIENT_SECRET", raising=False)
    st = eox_client.status()
    assert st["available"] is False and "环境变量" in st["reason"]
    with pytest.raises(RuntimeError) as ei:
        eox_client.refresh_models(conn, ["C9500-48Y4C"])
    assert "环境变量" in str(ei.value)


def test_配了凭据则可用(creds):
    assert eox_client.status()["available"] is True
    assert eox_client.credentials_configured() is True


# ---------------------------------------------------------------- 解析与分片

def test_解析拍平value字段():
    rec = eox_client._parse_record(EOX_JSON["EOXRecord"][0])
    assert rec["end_of_sale"] == "2025-07-15" and rec["end_of_support"] == "2030-07-31"
    assert rec["bulletin"] == "EOL12345" and rec["description"].startswith("Cisco Catalyst")


def test_按型号查询并归位(creds):
    session = FakeSession()
    out = eox_client.lookup_product_ids(["C9500-48Y4C"], session=session)
    assert out["C9500-48Y4C"][0]["end_of_support"] == "2030-07-31"


def test_超过20个型号分两批(creds):
    session = FakeSession()
    models = [f"MODEL-{i:02d}" for i in range(25)]
    eox_client.lookup_product_ids(models, session=session)
    assert len(session.get_calls) == 2
    assert "MODEL-24" in session.get_calls[1]           # 第 21~25 个在第二批


def test_404视为未公告而不是错误(creds):
    # 整批都没有记录 → Cisco 返回 404：结果为空列表、不抛异常
    out = eox_client.lookup_product_ids(["NOPE-1"], session=FakeSession(missing={"NOPE-1"}))
    assert out["NOPE-1"] == []
    # 混合批次（同一批里既有存在的也有不存在的）正常返回命中的那些
    out2 = eox_client.lookup_product_ids(["NOPE-1", "C9500-48Y4C"], session=FakeSession())
    assert out2["C9500-48Y4C"][0]["bulletin"] == "EOL12345"


# ---------------------------------------------------------------- 写库

def test_刷新写库且未公告不写(creds, conn, monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(eox_client.requests, "Session", lambda: fake)
    res = eox_client.refresh_models(conn, ["C9500-48Y4C", "JL659A"])
    # FakeSession 对所有批次都返回同一条记录，归位逻辑会把记录挂到 EOXInputValue 上
    assert res["updated"] == ["C9500-48Y4C"] and res["not_announced"] == ["JL659A"]
    row = dal.get_model_eol(conn, "C9500-48Y4C")
    assert row["source"] == "api" and row["end_of_support"] == "2030-07-31"
    assert dal.get_model_eol(conn, "JL659A") is None      # 未公告 = 不写（保持"未登记"语义）


def test_刷新不覆盖手工登记(creds, conn, monkeypatch):
    dal.upsert_model_eol(conn, "C9500-48Y4C", end_of_sale="2024-01-01", source="manual")
    monkeypatch.setattr(eox_client.requests, "Session", lambda: FakeSession())
    res = eox_client.refresh_models(conn, ["C9500-48Y4C"])
    assert res["updated"] == [] and res["skipped_manual"] == ["C9500-48Y4C"]
    assert dal.get_model_eol(conn, "C9500-48Y4C")["end_of_sale"] == "2024-01-01"
    # force 可覆盖（显式的"以外部数据为准"）
    res2 = eox_client.refresh_models(conn, ["C9500-48Y4C"], force=True)
    assert res2["updated"] == ["C9500-48Y4C"]
    assert dal.get_model_eol(conn, "C9500-48Y4C")["end_of_sale"] == "2025-07-15"
