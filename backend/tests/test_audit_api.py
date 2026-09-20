"""审计 API 端点测试 —— 临时库直接调端点函数（HTTP 层之下）。

重点覆盖三条契约（见计划 §三 C）：
  - envelope **必须带配置原文**：前端标红只认行号，而行号只对同一份文本有意义
  - **配置不可用不是错误**：采集失败 / 全文被清理 / 从未采集 → 200 + usable=false + 原因
  - 导出走**服务端渲染**（前端拼会在 i18n 与排序两处漂移）
"""
import asyncio
import json
from pathlib import Path

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


# ---------------------------------------------------------------- 全量审计入库

def test_run_audit_persists_run_and_findings(conn):
    res = call(audit_api.run_audit(trigger="manual"))
    assert res["device_count"] == 1 and res["finding_count"] > 0
    assert res["ruleset_hash"] and res["duration_ms"] >= 0
    # 不usable 的设备要单列原因，不能静默跳过
    assert [s["device"] for s in res["skipped"]] == ["DEZD1SWI01"]
    assert "采集失败" in res["skipped"][0]["reason"]

    run = conn.execute("SELECT status, device_count, finding_count, finished_at "
                       "FROM audit_runs WHERE id = ?", (res["run_id"],)).fetchone()
    assert run[0] == "done" and run[1] == 1 and run[2] == res["finding_count"] and run[3]
    # 证据自包含：库里存的是全文，不是引用
    rows = conn.execute("SELECT evidence_json, lines_json, config_hash, rule_id "
                        "FROM audit_findings").fetchall()
    assert rows and all(r[2] and r[3] for r in rows)     # 每条都有配置指纹与规则 id
    assert any(json.loads(r[1]) for r in rows)           # 至少有一条能定位到行
    assert all(json.loads(r[0]) is not None for r in rows)  # 证据必须是合法 JSON


def test_list_and_get_run(conn):
    res = call(audit_api.run_audit())
    runs = call(audit_api.list_runs(limit=5))["runs"]
    assert runs[0]["id"] == res["run_id"]

    detail = call(audit_api.get_run(res["run_id"]))
    assert detail["run"]["id"] == res["run_id"]
    assert len(detail["findings"]) == res["finding_count"]
    # lines / controls 必须是解析后的列表，前端不用再解字符串
    assert isinstance(detail["findings"][0]["lines"], list)
    assert isinstance(detail["findings"][0]["controls"], list)

    only_strong = call(audit_api.get_run(res["run_id"], level="强烈建议"))
    assert all(f["level"] == "强烈建议" for f in only_strong["findings"])

    with pytest.raises(HTTPException) as ei:
        call(audit_api.get_run(99999))
    assert ei.value.status_code == 404


# ---------------------------------------------------------------- 规则编辑

@pytest.fixture
def rules_dir(tmp_path, monkeypatch):
    """把真实规则文件拷到临时目录，并让 loader 指向它 —— 测试绝不改动项目里的规则。"""
    import shutil
    from analyzers.compliance import loader
    src = Path(__file__).resolve().parents[2] / "config" / "audit"
    dst = tmp_path / "audit"
    dst.mkdir()
    for f in src.glob("*.yaml"):
        shutil.copy2(f, dst / f.name)
    monkeypatch.setattr(loader, "DEFAULT_DIR", dst)
    loader.clear_cache()
    yield dst
    loader.clear_cache()


def test_update_rule_toggles_and_preserves_comments(rules_dir):
    f = rules_dir / "vendor-baseline.yaml"
    before = f.read_text(encoding="utf-8")
    comments_before = [ln for ln in before.splitlines() if ln.strip().startswith("#")]

    res = call(audit_api.update_rule("cx_telnet_disabled", audit_api.RuleUpdate(
        enabled=False, disabled_reason="测试停用", base_hash=audit_api._file_hash(f))))
    assert res["ok"] and res["backup"]

    after = f.read_text(encoding="utf-8")
    comments_after = [ln for ln in after.splitlines() if ln.strip().startswith("#")]
    assert comments_after == comments_before, "注释必须原样保留（ruamel 往返编辑）"
    assert "enabled: false" in after and "disabled_reason: 测试停用" in after

    # 停用后不再参与判定，但仍在规则库里
    from analyzers.compliance import loader
    std = loader.load_standard(use_cache=False)
    rule = next(r for r in std["rules"] if r["id"] == "cx_telnet_disabled")
    assert rule["enabled"] is False
    assert "cx_telnet_disabled" not in [r["id"] for r in audit_api.engine.active_rules(std)]

    # 备份文件留在 .backups/
    assert (rules_dir / ".backups").exists()
    assert list((rules_dir / ".backups").glob("vendor-baseline.yaml.*"))


def test_update_rule_minimizes_diff(rules_dir):
    """只改一个字段时，文件其余部分必须**逐字不变**。

    ruamel 默认会把整个文件重排（列表缩进改成 0、长行按 80 列折行）——
    改一个字段看起来像全文重写，git 历史直接报废。这个测试就是那道闸门：
    行数必须不变、差异行数必须只有 1。
    """
    f = rules_dir / "vendor-baseline.yaml"
    before = f.read_text(encoding="utf-8").splitlines()

    call(audit_api.update_rule("cx_telnet_disabled", audit_api.RuleUpdate(title="新标题")))

    after = f.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after), "文件被重排（行数变了）——检查 ruamel 的 indent/width 参数"
    diff = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert len(diff) == 1, f"应只改 1 行，实际改了 {len(diff)} 行：{[before[i] for i in diff][:4]}"
    assert "新标题" in after[diff[0]]


def test_all_rule_files_are_roundtrip_stable(rules_dir):
    """所有规则文件必须"零改动往返后逐字节不变"。

    这是上面那条 diff 测试的**全文件版闸门**：只要有人在规则文件里写了跨行的
    普通标量（应写 `>-` 折叠块），这个测试立刻失败 —— 否则第一次通过界面编辑规则，
    整个文件就会被重排，git 历史报废。
    """
    from api.audit import _yaml_rt
    import io as _io
    for f in sorted(rules_dir.glob("*.yaml")):
        src = f.read_text(encoding="utf-8")
        buf = _io.StringIO()
        _yaml_rt().dump(_yaml_rt().load(_io.StringIO(src)), buf)
        assert src == buf.getvalue(), \
            f"{f.name} 往返不稳定（检查是否有跨行普通标量，应改用 '>-' 折叠块）"


def test_update_rule_rejects_disable_without_reason(rules_dir):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_rule("cx_telnet_disabled",
                                   audit_api.RuleUpdate(enabled=False)))
    assert ei.value.status_code == 400
    assert "superseded_by" in ei.value.detail


def test_update_rule_rolls_back_on_invalid_ruleset(rules_dir):
    """把档位改成非法值 → 校验不过 → 文件必须回滚成原样。"""
    f = rules_dir / "vendor-baseline.yaml"
    before = f.read_text(encoding="utf-8")
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_rule("cx_telnet_disabled",
                                   audit_api.RuleUpdate(level="不存在的档位")))
    assert ei.value.status_code == 400
    assert "已回滚" in ei.value.detail
    assert f.read_text(encoding="utf-8") == before


def test_update_rule_optimistic_lock(rules_dir):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_rule("cx_telnet_disabled",
                                   audit_api.RuleUpdate(title="x", base_hash="deadbeef")))
    assert ei.value.status_code == 409


def test_update_rule_unknown_rule_404(rules_dir):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_rule("no_such_rule", audit_api.RuleUpdate(title="x")))
    assert ei.value.status_code == 404


def test_update_rule_empty_body_400(rules_dir):
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_rule("cx_telnet_disabled", audit_api.RuleUpdate()))
    assert ei.value.status_code == 400


# ---------------------------------------------------------------- 例外登记 API

def make_exception(**kw):
    base = dict(rule_id="cx_telnet_disabled", scope_type="device", scope_value="BJQD1SWI01",
                reason="改造窗口前无法关闭 Telnet", compensating_control="已用 ACL 限制管理网段",
                approved_by="张工")
    base.update(kw)
    return audit_api.ExceptionCreate(**base)


def test_exception_create_list_update_revoke(rules_dir):
    """登记 → 列表 → 续期 → 撤销 的完整链路（含状态推导与默认到期日）。"""
    import datetime
    f = rules_dir / "_exceptions.yaml"
    res = call(audit_api.create_exception(make_exception()))
    e = res["exception"]
    assert res["ok"] and e["id"] == "exc-001" and e["status"] == "active"
    assert e["rule_title"]                                # 列表要显示规则标题
    today = datetime.date.today()
    assert e["expires_at"] == (today + datetime.timedelta(days=180)).isoformat()

    lst = call(audit_api.list_exceptions())
    assert [x["id"] for x in lst["exceptions"]] == ["exc-001"]
    assert lst["counts"]["active"] == 1 and lst["base_hash"]

    # 续期（乐观锁用列表返回的 base_hash）
    upd = call(audit_api.update_exception("exc-001", audit_api.ExceptionUpdate(
        expires_at=(today + datetime.timedelta(days=365)).isoformat(),
        base_hash=lst["base_hash"])))
    assert upd["changed"] == ["expires_at"] and upd["exception"]["days_left"] == 365

    # 撤销 = 软删除：条目保留，状态为 revoked
    rev = call(audit_api.revoke_exception("exc-001", audit_api.ExceptionRevoke(
        by="李工", reason="设备已下线", base_hash=upd["base_hash"])))
    assert rev["exception"]["status"] == "revoked"
    assert call(audit_api.list_exceptions(state="active"))["exceptions"] == []
    assert call(audit_api.list_exceptions(state="revoked"))["counts"]["revoked"] == 1

    text = f.read_text(encoding="utf-8")
    assert "revoked:" in text and "exc-001" in text
    assert "# NDM 配置审计 —— 例外登记表" in text          # 文件头注释没被 ruamel 丢掉


def test_exception_create_rejects_unknown_rule_and_rolls_back(rules_dir):
    f = rules_dir / "_exceptions.yaml"
    before = f.read_text(encoding="utf-8")
    with pytest.raises(HTTPException) as ei:
        call(audit_api.create_exception(make_exception(rule_id="no_such_rule")))
    assert ei.value.status_code == 400 and "不在规则库" in ei.value.detail
    assert f.read_text(encoding="utf-8") == before         # 校验失败 → 回滚


def test_exception_duplicate_scope_rejected(rules_dir):
    call(audit_api.create_exception(make_exception()))
    with pytest.raises(HTTPException) as ei:
        call(audit_api.create_exception(make_exception()))
    assert ei.value.status_code == 400 and "重复登记" in ei.value.detail


def test_exception_revoke_requires_operator_and_reason(rules_dir):
    call(audit_api.create_exception(make_exception()))
    with pytest.raises(HTTPException) as ei:
        call(audit_api.revoke_exception("exc-001", audit_api.ExceptionRevoke(by="", reason="")))
    assert ei.value.status_code == 400
    call(audit_api.revoke_exception("exc-001", audit_api.ExceptionRevoke(by="李工", reason="下线")))
    with pytest.raises(HTTPException) as ei2:
        call(audit_api.revoke_exception("exc-001", audit_api.ExceptionRevoke(by="李工", reason="再撤")))
    assert ei2.value.status_code == 400


def test_exception_update_optimistic_lock_and_404(rules_dir):
    call(audit_api.create_exception(make_exception()))
    with pytest.raises(HTTPException) as ei:
        call(audit_api.update_exception("exc-001",
                                        audit_api.ExceptionUpdate(reason="x", base_hash="deadbeef")))
    assert ei.value.status_code == 409
    with pytest.raises(HTTPException) as ei2:
        call(audit_api.update_exception("no_such", audit_api.ExceptionUpdate(reason="x")))
    assert ei2.value.status_code == 404


def test_exempted_finding_in_envelope_and_run(conn, rules_dir):
    """端到端：登记例外后，单台审计里该条进「已批准例外」，全量审计落库带豁免快照。"""
    env0 = call(audit_api.audit_device("BJQD1SWI01"))
    hit = env0["findings"][0]
    before = env0["counts"][hit["level"]]

    call(audit_api.create_exception(make_exception(rule_id=hit["rule_id"])))

    env = call(audit_api.audit_device("BJQD1SWI01"))
    f = next(x for x in env["findings"] if x["rule_id"] == hit["rule_id"])
    assert f["exempt"]["status"] == "active" and f["exempt"]["exception_id"] == "exc-001"
    assert env["counts"][hit["level"]] == before - 1
    assert env["exempt_count"] == 1

    run = call(audit_api.run_audit())
    assert run["exempt_count"] == 1 and run["exceptions_hash"]

    detail = call(audit_api.get_run(run["run_id"]))
    fr = next(x for x in detail["findings"] if x["rule_id"] == hit["rule_id"])
    assert fr["exempt_by"] == "exc-001" and fr["exempt"]["status"] == "active"
