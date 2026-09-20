"""AI 专家简报测试 —— prompt 构建（纯函数）+ 调用链 + 数据装配。

三条要点：
  1. prompt 里**必须有**判定条目、统计、例外说明；**必须没有**配置原文与凭据值（打码）
  2. LLM 不可用 → 可读中文错误；审计本身不受影响
  3. 全网数据装配：豁免不计入建议数、集体性条目的台数从标题提出、指纹变化标记
"""
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import storage.database as db  # noqa: E402
from services import audit_briefing as briefing  # noqa: E402


def make_env(**kw):
    env = {
        "device": "SHAD1SWI01", "location": "SHA", "platform": "cisco_ios",
        "model": "C9500-24Y4C", "week": "2026-38", "collected_at": "2026-09-20T08:00:00",
        "usable": True, "reason": "", "exempt_count": 1,
        "counts": {"风险提示": 1, "需人工判断": 1},
        "findings": [
            {"rule_id": "hq_cs_no_snmp_community", "title": "不得配置明文团体字",
             "level": "风险提示", "source": "公司总部",
             "current": "snmp-server community QorvoRW RO",
             "fix": "no snmp-server community QorvoRW",
             "why": "总部第 8 章要求", "detail": ""},
            {"rule_id": "ops_lifecycle_unknown", "title": "生命周期信息待查",
             "level": "需人工判断", "source": "组织规范", "current": "尚未登记：型号 EoL",
             "fix": "", "why": "", "detail": ""},
        ],
    }
    env.update(kw)
    return env


# ---------------------------------------------------------------- 单台 prompt

def test_单台prompt含条目统计例外但不含配置原文():
    env = make_env(findings=[{**make_env()["findings"][0],
                              "exempt": {"exception_id": "exc-001", "approved_by": "张工",
                                         "expires_at": "2027-03-19", "status": "active",
                                         "reason": "改造前无法满足"}}],
                   config="CONFIDENTIAL-SWITCH-CONFIG-BODY")
    prompt = briefing.build_device_prompt(env)
    assert "不得配置明文团体字" in prompt and "风险提示" in prompt
    assert "exc-001" in prompt and "张工" in prompt and "已批准例外" in prompt
    assert "CONFIDENTIAL-SWITCH-CONFIG-BODY" not in prompt      # 不喂配置原文
    assert "不得新增" in prompt                                  # 反幻觉硬约束在


def test_单台prompt对凭据打码():
    prompt = briefing.build_device_prompt(make_env())
    assert "QorvoRW" not in prompt
    assert "snmp-server community <REDACTED> RO" in prompt


def test_没有命中时明示不要凭空找问题():
    prompt = briefing.build_device_prompt(make_env(findings=[]))
    assert "没有命中任何规则" in prompt and "不要凭空找问题" in prompt


# ---------------------------------------------------------------- 全网 prompt

def test_全网prompt含统计榜与数据说明():
    data = {
        "run_id": 7, "started_at": "2026-09-20T13:00:00", "trigger": "manual",
        "device_count": 36, "finding_count": 487, "exempt_count": 3,
        "counts": {"强烈建议": 240, "风险提示": 12}, "by_source": {"公司总部": 260},
        "top_rules": [{"rule_id": "hq_cs_mgmt_acl", "title": "缺少 MGMT_ACL",
                       "level": "强烈建议", "devices": 18}],
        "collective": [{"title": "生命周期信息待查（型号 EoL 与保修期）（36 台）", "device_count": 36}],
        "lifecycle_unknown": 36, "ruleset_changed": True, "exceptions_changed": False,
        "diff": {"from": {"week": "2026-37"}, "to": {"week": "2026-38"},
                 "rules": [{"rule_id": "r1", "title": "旧问题", "delta": -3},
                           {"rule_id": "r2", "title": "新问题", "delta": 2}],
                 "converged": 1, "worsened": 1},
    }
    prompt = briefing.build_network_prompt(data)
    assert "缺少 MGMT_ACL" in prompt and "命中 18 台" in prompt
    assert "36 台" in prompt and "生命周期" in prompt
    assert "收敛 3 台" in prompt and "恶化 2 台" in prompt
    assert "标准" in prompt and "发生了变化" in prompt            # 指纹变化提示
    assert "数据可信度" in prompt


# ---------------------------------------------------------------- 调用链

def test_无provider给可读错误(monkeypatch):
    monkeypatch.setattr(briefing, "_providers", lambda: [])
    with pytest.raises(briefing.BriefingError) as ei:
        briefing._call_llm("x")
    assert "LLM 设置" in str(ei.value)


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_provider降级链(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        if "bad" in url:
            return FakeResp(None, status=500)
        return FakeResp({"choices": [{"message": {"content": "简报正文"}}]})

    monkeypatch.setattr(briefing.requests, "post", fake_post)
    monkeypatch.setattr(briefing, "_providers", lambda: [
        {"name": "坏", "base_url": "https://bad.example/v1", "api_key": "k",
         "model": "m", "timeout": 5},
        {"name": "好", "base_url": "https://good.example/v1", "api_key": "k",
         "model": "m", "timeout": 5},
    ])
    text, provider = briefing._call_llm("prompt")
    assert text == "简报正文" and provider.startswith("好")
    assert len(calls) == 2                                   # 第一个失败后降级到第二个


def test_全部失败时列出原因(monkeypatch):
    monkeypatch.setattr(briefing.requests, "post",
                        lambda url, **kw: FakeResp(None, status=500))
    monkeypatch.setattr(briefing, "_providers", lambda: [
        {"name": "A", "base_url": "https://a/v1", "api_key": "k", "model": "m", "timeout": 5}])
    with pytest.raises(briefing.BriefingError) as ei:
        briefing._call_llm("x")
    assert "都调用失败" in str(ei.value) and "A" in str(ei.value)


def test_不可用设备拒绝生成(monkeypatch):
    with pytest.raises(briefing.BriefingError) as ei:
        briefing.generate_device_briefing(make_env(usable=False, reason="配置已被清理"))
    assert "配置已被清理" in str(ei.value)


def test_生成单台简报(monkeypatch):
    monkeypatch.setattr(briefing, "_call_llm", lambda p, max_tokens=1200: ("整体印象……", "DeepSeek(x)"))
    res = briefing.generate_device_briefing(make_env())
    assert res["briefing"] == "整体印象……" and res["scope"] == "device"
    assert res["provider"] and res["generated_at"]


# ---------------------------------------------------------------- 全网数据装配

def test_装配全网数据(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    conn = db.get_connection()
    conn.execute("INSERT INTO audit_runs (id, started_at, finished_at, trigger, ruleset_hash, "
                 "exceptions_hash, device_count, finding_count, exempt_count, status) "
                 "VALUES (1, '2026-09-14T08:00:00', '2026-09-14T08:01:00', 'manual', 'R1', 'E1', 2, 0, 0, 'done')")
    conn.execute("INSERT INTO audit_runs (id, started_at, finished_at, trigger, ruleset_hash, "
                 "exceptions_hash, device_count, finding_count, exempt_count, status) "
                 "VALUES (2, '2026-09-20T08:00:00', '2026-09-20T08:01:00', 'manual', 'R2', 'E1', 2, 0, 1, 'done')")
    rows = [
        # 普通建议 ×2（同一条规则命中两台）
        (2, "A", "hq_cs_mgmt_acl", "缺少 MGMT_ACL", "强烈建议", "公司总部", None, None),
        (2, "B", "hq_cs_mgmt_acl", "缺少 MGMT_ACL", "强烈建议", "公司总部", None, None),
        # 生效中豁免 → 不计入建议数
        (2, "A", "cs_bpduguard", "接入口应配 BPDU Guard", "强烈建议", "公司总部",
         "exc-001", json.dumps({"status": "active"}, ensure_ascii=False)),
        # 集体性条目（折叠）：device_name = 全网
        (2, "全网", "ops_lifecycle_unknown", "生命周期信息待查（型号 EoL 与保修期）（2 台）",
         "需人工判断", "组织规范", None, None),
    ]
    for r in rows:
        conn.execute("INSERT INTO audit_findings (run_id, device_name, rule_id, title, level, "
                     "source, exempt_by, exempt_json) VALUES (?,?,?,?,?,?,?,?)", r)
    conn.commit()
    try:
        data = briefing.collect_network_data(conn)
        assert data["run_id"] == 2 and data["exempt_count"] == 1
        assert data["counts"] == {"强烈建议": 2, "需人工判断": 1}      # 豁免被排除
        assert data["top_rules"][0]["rule_id"] == "hq_cs_mgmt_acl"
        assert data["top_rules"][0]["devices"] == 2
        assert data["collective"][0]["device_count"] == 2             # 台数从标题提取
        assert data["lifecycle_unknown"] == 2
    finally:
        db.close_connection()
        db._db_path = original


def test_没有运行记录时可读错误(tmp_path):
    original = db._db_path
    db.close_connection()
    db.init_db(str(tmp_path))
    try:
        with pytest.raises(briefing.BriefingError) as ei:
            briefing.collect_network_data(db.get_connection())
        assert "全网审计" in str(ei.value)
    finally:
        db.close_connection()
        db._db_path = original
