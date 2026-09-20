"""凭据打码测试 —— 纪律项：发给 LLM 的文本里绝不带凭据值。

原则"宁可多打，不可漏打"：这里既测各类凭据形态都被打掉，
也测普通配置行**不被误伤**（误伤多了简报就读不出信息了）。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from utils.redact import redact_finding, redact_secrets  # noqa: E402


def test_snmp团体字被打掉但保留命令():
    assert redact_secrets("snmp-server community QorvoRW RO") == "snmp-server community <REDACTED> RO"
    assert redact_secrets(" snmp-server community public") == " snmp-server community <REDACTED>"


def test_snmpv3认证加密口令被打掉():
    out = redact_secrets("snmp-server user monitor GRP v3 auth sha Secret123 priv aes Enc456")
    assert "Secret123" not in out and "Enc456" not in out
    assert "snmp-server user monitor GRP v3 auth sha <REDACTED> priv aes <REDACTED>" == out


def test_enable与username口令被打掉():
    assert "pf9" not in redact_secrets("enable secret 5 $1$abcd$pf9xyz")
    # 加密类型数字**保留**（"用的哪种加密"是有用信息，值本身才是凭据）
    assert redact_secrets("enable password 7 08324D5D") == "enable password 7 <REDACTED>"
    assert redact_secrets("username admin privilege 15 secret 9 $9$xyzabc") == \
        "username admin privilege 15 secret 9 <REDACTED>"


def test_哈希与ciphertext被打掉():
    assert redact_secrets("key-string 7 030752180500") == "key-string 7 <REDACTED>"
    assert "$9$" not in redact_secrets("some blob $9$abc/def here")
    assert redact_secrets("ciphertext AQBapZ123") == "ciphertext <REDACTED>"


def test_radius_tacacs的key被打掉():
    out = redact_secrets("radius-server host 10.1.1.1 key MySharedSecret")
    assert "MySharedSecret" not in out and out.startswith("radius-server host 10.1.1.1 key <REDACTED>")


def test_修复命令里的凭据也要打掉():
    """fix 字段常以 no 开头（`no snmp-server community X`）——锚定行首会漏打。"""
    assert redact_secrets("no snmp-server community QorvoRW") == \
        "no snmp-server community <REDACTED>"
    assert redact_secrets("no username admin secret 9 $9$abc") == \
        "no username admin secret 9 <REDACTED>"


def test_普通配置行不被误伤():
    for line in ["interface GigabitEthernet1/0/1", " description Uplink to core",
                 " vlan 16", "    name PC-Data", "ntp server 10.1.1.1",
                 "spanning-tree bpduguard enable", "ip access-list extended MGMT_ACL"]:
        assert redact_secrets(line) == line


def test_多行与空值():
    text = "snmp-server community A RO\n!\nhostname SWI01"
    out = redact_secrets(text)
    assert "<REDACTED>" in out and "hostname SWI01" in out
    assert redact_secrets("") == "" and redact_secrets(None) == ""


def test_redact_finding只改可发送字段():
    f = {"rule_id": "r1", "current": "snmp-server community A RO", "fix": "no snmp-server community A",
         "detail": "说明", "evidence": [{"line": 3, "text": "snmp-server community A RO"}]}
    out = redact_finding(f)
    assert "community <REDACTED>" in out["current"] and "A RO" not in out["evidence"][0]["text"]
    assert out["detail"] == "说明" and out["rule_id"] == "r1"
    assert f["current"].endswith("A RO")          # 不改原字典
