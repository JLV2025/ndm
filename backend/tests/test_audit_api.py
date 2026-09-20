"""审计 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）。

重点覆盖三条契约（见计划 §三 C）：
  - envelope **必须带配置原文**：前端标红只认行号，而行号只对同一份文本有意义
  - **配置不可用不是错误**：采集失败 / 全文被清理 / 从未采集 → 200 + usable=false + 原因
  - 导出走**服务端渲染**（前端拼会在 i18n 与排序两处漂移）
"""
import asyncio
import json

import pytest
from fastapi import HTTPException

import storage.database as db
from api import audit as audit_api
from analyzers.compliance import source

# 一份能触发多条规则的最小 CX 配置（要超过 source.MIN_CONFIG_LEN）
CX_CONFIG = """Current configuration:
!
!Version ArubaOS-CX FL.10.10.1070
hostname BJQD1SWI01
clock timezone asia/shanghai
ntp server 10.8.26.10
vlan 1
vlan 16
    name 10.1.16.0_Data
interface 1/1/1
    no shutdown
    vlan access 16
    spanning-tree bpdu-guard
""" + "!\n" * 600


@pytest.fixture
def conn(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    c = db.get_connection()
    c.execute("INSERT INTO devices (id, name, ip, type, platform, location, model, uplink_ports) "
              "VALUES (1, 'BJQD1SWI01', '10.0.0.1', 'aruba_aoscx', 'aruba_aoscx', 'BJQ', 'JL659A', NULL)")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, running_config) "
              "VALUES (10, 1, '2026-38', '2026-09-20T08:00:00', ?)", (CX_CONFIG,))
    c.execute("INSERT INTO devices (id, name, ip, type, platform, location) "
              "VALUES (2, 'DEZD1SWI01', '10.0.0.2', 'aruba_aoscx', 'aruba_aoscx', 'DEZ')")
    c.execute("INSERT INTO collections (id, device_id, week, collected_at, running_config) "
              "VALUES (11, 2, '2026-38', '2026-09-20T08:00:00', '% 收集失败: 认证失败')")
    c.execute("INSERT INTO neighbors (collection_id, device_id, local_port, neighbor_name, "
              "neighbor_type) VALUES (10, 1, '1/1/1', 'PC-001', 'server')")
    c.commit()
    yield c
    db.close_connection()
    db._db_path = original


def call(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- 单台审计

def test_audit_device_returns_full_envelope(conn):
    env = call(audit_api.audit_device("BJQD1SWI01"))
    assert env["device"] == "BJQD1SWI01" and env["usable"] is True
    # 配置原文必须带 —— 前端要渲染这一份做行号对齐
    assert env["config"] == CX_CONFIG
    assert env["config_hash"] and len(env["config_hash"]) == 16
    assert env["ruleset_hash"] and env["generated_at"]
    assert env["location"] == "BJQ"
    assert env["port_roles"].get("1/1/1", {}).get("role") == "access"
    assert isinstance(env["findings"], list) and isinstance(env["counts"], dict)
    # 排序契约：档位 → 层优先级 → 规则 id，前端不再自行排序
    assert env["findings"], "这份配置应当命中若干条"


def test_findings_carry_line_numbers_and_locatable(conn):
    """标红契约：每条发现带 lines；不可定位的 locatable=False。"""
    env = call(audit_api.audit_device("BJQD1SWI01"))
    for f in env["findings"]:
        assert "lines" in f and "locatable" in f
        assert f["locatable"] == bool(f["lines"])
        for ln in f["lines"]:
            assert isinstance(ln, int) and 1 <= ln <= len(CX_CONFIG.split("\n"))


def test_include_config_false_omits_large_payload(conn):
    env = call(audit_api.audit_device("BJQD1SWI01", include_config=False))
    assert "config" not in env
    assert env["config_hash"]          # 指纹仍要保留，否则前端无法判断渲染的是哪一份


def test_unknown_device_404(conn):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.audit_device("NOT_A_DEVICE"))
    assert ei.value.status_code == 404


def test_unusable_device_returns_200_with_reason(conn):
    """采集失败**不是错误**：照样 200，把原因说清楚，让界面能解释"为什么没结果"。"""
    env = call(audit_api.audit_device("DEZD1SWI01"))
    assert env["usable"] is False
    assert "采集失败" in env["reason"]
    assert env["findings"] == [] and env["config"] == ""


# ---------------------------------------------------------------- 规则库与导出

def test_ruleset_lists_all_rules_including_disabled(conn):
    rs = call(audit_api.get_ruleset())
    assert len(rs["rules"]) >= 50
    assert rs["ruleset_hash"] and rs["levels"] and rs["platforms"] == ["all", "cisco", "cx"]
    assert rs["layer_priority"]["公司总部"] < rs["layer_priority"]["厂商基线"]
    for r in rs["rules"]:
        assert {"id", "title", "level", "source", "check", "enabled", "source_file"} <= set(r)


def test_export_markdown_contains_key_sections(conn):
    resp = call(audit_api.export_audit("BJQD1SWI01", format="md"))
    body = resp.body.decode("utf-8")
    assert "# 配置审计报告 —— BJQD1SWI01" in body
    assert "配置指纹" in body and "规则集指纹" in body
    assert "建议统计" in body
    assert "建议**，非强制" in body          # 语义不能走样成"违规清单"
    assert "attachment" in resp.headers["content-disposition"]


def test_export_json_is_valid_and_complete(conn):
    resp = call(audit_api.export_audit("BJQD1SWI01", format="json"))
    data = json.loads(resp.body.decode("utf-8"))
    assert data["device"] == "BJQD1SWI01" and data["config"] == CX_CONFIG


def test_export_unusable_device_renders_reason(conn):
    body = call(audit_api.export_audit("DEZD1SWI01", format="md")).body.decode("utf-8")
    assert "本次未能审计" in body and "采集失败" in body


def test_export_unknown_device_404(conn):
    with pytest.raises(HTTPException):
        call(audit_api.export_audit("NOT_A_DEVICE", format="md"))
