"""collector_service 型号/序列号/成员ID提取测试 — 重点：Aruba CX VSF 堆叠"""
import pytest

from services.collector_service import extract_model, extract_serial_number, extract_member_ids

# Aruba CX show vsf detail 输出（VSF 堆叠，真实成员顺序：member 1=JL726B 原，member 2=JL725A 新加）
# 注意：成员 2 的 Model 刻意用不同系列(6300M) — 用于验证 SKU↔系列名的 1:1 配对不错位
VSF_DETAIL_TWO_MEMBERS = """VSF Stack
MAC Address               : ec:eb:b8:d0:80:40
Secondary                 : 2
Topology                  : Chain
Status                    : No Split
Uptime                    : 0d 0h 23m
Software Version          : ML.10.13.1161
Member ID                 : 1
MAC Address               : 70:5a:0f:11:22:33
Type                      : JL726B
Model                     : Aruba 6200F 48G CL4 PoE+ 4SFP56 Switch
Status                    : Conductor
Serial Number             : TW48LZ61MR
Uptime                    : 0d 0h 23m
VSF link 1                : Up, connected to peer member 2, link 1
Member ID                 : 2
MAC Address               : 70:5a:0f:44:55:66
Type                      : JL725A
Model                     : Aruba 6300M 48SR5 CL6 PoE 4SFP56 Switch
Status                    : Standby
Serial Number             : SG19KW50MR
Uptime                    : 0d 0h 23m
VSF link 1                : Up, connected to peer member 1, link 1
"""

# R 前缀 SKU（6300M 新款等）堆叠
VSF_DETAIL_R_SKU = """VSF Stack
Member ID                 : 1
Type                      : R8S89A
Model                     : Aruba 6300M 48SR5 CL6 PoE 4SFP56 Switch
Status                    : Conductor
Serial Number             : CN7ZK90012
Member ID                 : 2
Type                      : R8S91A
Model                     : Aruba 6300M 48SR5 CL6 PoE 4SFP56 Switch
Status                    : Standby
Serial Number             : CN7ZK90013
"""

# Model 行缺失的 VSF 输出（防御路径：应退化纯 SKU）
VSF_DETAIL_NO_MODEL = """VSF Stack
Member ID                 : 1
Type                      : JL726B
Status                    : Conductor
Serial Number             : TW48LZ61MR
Member ID                 : 2
Type                      : JL725A
Status                    : Standby
Serial Number             : SG19KW50MR
"""

# 单机（非 VSF）show vsf detail 输出：无成员 Type
VSF_DETAIL_SINGLE = """VSF is not enabled
"""

SHOW_SYSTEM_SINGLE = """System Name        : UCDD1SWI01
System Description : Aruba JL726B 6200F 48G CL4 PoE+ 4SFP56 Switch
Product Name       : JL726B 6200F 48G CL4 PoE+ 4SFP56 Swch
Software Version   : ML.10.13.1161
"""


# ---- extract_model：Aruba VSF 成员型号 ----

def test_extract_model_vsf_members_distinct():
    """VSF 堆叠两台不同型号 → 按成员顺序逗号拼接（SKU + 系列名，配对不错位）"""
    result = extract_model("", "", "aruba_aoscx", VSF_DETAIL_TWO_MEMBERS)
    assert result == "JL726B 6200F, JL725A 6300M"


def test_extract_model_vsf_serial_alignment():
    """型号与序列号逐成员 1:1 对应（成员顺序一致）"""
    model = extract_model("", "", "aruba_aoscx", VSF_DETAIL_TWO_MEMBERS)
    serial = extract_serial_number("", "aruba_aoscx", vsf_output=VSF_DETAIL_TWO_MEMBERS)
    model_list = model.split(", ")
    serial_list = serial.split(", ")
    assert len(model_list) == len(serial_list) == 2
    assert model_list[0] == "JL726B 6200F" and serial_list[0] == "TW48LZ61MR"
    assert model_list[1] == "JL725A 6300M" and serial_list[1] == "SG19KW50MR"


def test_extract_model_vsf_r_prefix_sku():
    """R 前缀 SKU（6300M 新款）同样按成员提取"""
    result = extract_model("", "", "aruba_aoscx", VSF_DETAIL_R_SKU)
    assert result == "R8S89A 6300M, R8S91A 6300M"


def test_extract_model_vsf_missing_model_falls_back_to_sku():
    """Model 行缺失 → 退化为纯 SKU 拼接，数量与序列号一致"""
    result = extract_model("", "", "aruba_aoscx", VSF_DETAIL_NO_MODEL)
    assert result == "JL726B, JL725A"


def test_extract_model_vsf_lowercase_lines():
    """小写 type/model 行（re.IGNORECASE）同样匹配"""
    vsf = VSF_DETAIL_TWO_MEMBERS.replace("Type", "type").replace("Model", "model")
    result = extract_model("", "", "aruba_aoscx", vsf)
    assert result == "JL726B 6200F, JL725A 6300M"


def test_extract_model_non_vsf_fallback_to_system():
    """非 VSF（无成员 Type）→ 回退 show system Product Name"""
    result = extract_model(SHOW_SYSTEM_SINGLE, "", "aruba_aoscx", VSF_DETAIL_SINGLE)
    assert result == "JL726B 6200F"


def test_extract_model_no_vsf_output_system_only():
    """无 vsf 输出 → show system Product Name"""
    result = extract_model(SHOW_SYSTEM_SINGLE, "", "aruba_aoscx")
    assert result == "JL726B 6200F"


# ---- extract_member_ids：VSF 成员 ID ----

def test_extract_member_ids_two_members():
    """双成员 VSF → 逗号拼接 "1, 2"（与序列号同序）"""
    result = extract_member_ids(VSF_DETAIL_TWO_MEMBERS)
    assert result == "1, 2"


def test_extract_member_ids_jump_ids():
    """跳号成员（删掉 2 号）→ 保留真实 ID "1, 3"（无空格冒号变体也匹配）"""
    vsf = """VSF Stack
Member ID                 : 1
Serial Number             : AAA1111111
Member ID: 3
Serial Number             : BBB2222222
"""
    assert extract_member_ids(vsf) == "1, 3"


def test_extract_member_ids_not_enabled():
    """非 VSF 输出 / 空输入 → 空字符串"""
    assert extract_member_ids(VSF_DETAIL_SINGLE) == ""
    assert extract_member_ids("") == ""
    assert extract_member_ids(None) == ""


def test_extract_member_ids_serial_alignment():
    """成员 ID 与序列号逐位 1:1 对应（对齐核心不变量）"""
    ids = extract_member_ids(VSF_DETAIL_TWO_MEMBERS)
    serial = extract_serial_number("", "aruba_aoscx", vsf_output=VSF_DETAIL_TWO_MEMBERS)
    id_list = ids.split(", ")
    serial_list = serial.split(", ")
    assert len(id_list) == len(serial_list) == 2
    assert id_list[0] == "1" and serial_list[0] == "TW48LZ61MR"
    assert id_list[1] == "2" and serial_list[1] == "SG19KW50MR"


def test_extract_member_ids_lowercase():
    """小写 member id 行（re.IGNORECASE）同样匹配"""
    vsf = VSF_DETAIL_TWO_MEMBERS.replace("Member ID", "member id")
    assert extract_member_ids(vsf) == "1, 2"
