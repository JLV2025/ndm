"""
设备管理 API 集成测试
测试 CRUD 操作、输入验证和错误处理
"""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import yaml
import os

from _main import app

# 创建测试专用的临时配置文件路径
TEST_CONFIG_PATH = __import__("pathlib").Path(__file__).parent / "config" / "test_devices.yaml"


def _get_client():
    """获取测试客户端"""
    return TestClient(app, raise_server_exceptions=False, follow_redirects=True)




@pytest.fixture(scope="function")
def test_config_file():
    """创建测试用的 YAML 配置文件，并设置环境变量让 API 使用它"""
    config_data = {
        "devices": [
            {
                "name": "switch-core-01",
                "ip": "192.168.1.1",
                "type": "cisco_ios",
                "platform": "cisco_ios",
                "location": "数据中心 A 区",
                "notes": "核心交换机",
                "username": "admin",
            }
        ]
    }
    # 创建目录
    TEST_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

    # 设置环境变量让 API 使用测试配置文件
    old_config_path = os.environ.get("DEVICES_CONFIG_PATH")
    os.environ["DEVICES_CONFIG_PATH"] = str(TEST_CONFIG_PATH)

    yield TEST_CONFIG_PATH

    # 恢复旧的环境变量
    if old_config_path:
        os.environ["DEVICES_CONFIG_PATH"] = old_config_path
    else:
        os.environ.pop("DEVICES_CONFIG_PATH", None)


def test_list_devices_empty(test_client, test_config_file):
    """测试获取空设备列表"""
    # 删除所有设备
    config_data = {"devices": []}
    with open(test_config_file, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

    response = test_client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_devices_with_data(test_client, test_config_file):
    """测试获取设备列表"""
    response = test_client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "switch-core-01"
    assert data[0]["ip"] == "192.168.1.1"
    assert data[0]["type"] == "cisco_ios"
    assert data[0]["location"] == "数据中心 A 区"
    assert data[0]["notes"] == "核心交换机"
    assert data[0]["username"] == "admin"


def test_get_device_success(test_client, test_config_file):
    """测试获取单个设备详情"""
    response = test_client.get("/api/devices/switch-core-01")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "switch-core-01"
    assert data["ip"] == "192.168.1.1"
    assert data["type"] == "cisco_ios"
    assert data["username"] == "admin"


def test_get_device_not_found(test_client, test_config_file):
    """测试获取不存在的设备返回 404"""
    response = test_client.get("/api/devices/nonexistent-device")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "不存在" in data["detail"]


def test_add_device_success(test_client, test_config_file):
    """测试成功添加设备"""
    new_device = {
        "name": "switch-access-01",
        "ip": "192.168.1.10",
        "type": "cisco_ios",
        "location": "办公区",
        "notes": "接入交换机",
    }
    response = test_client.post("/api/devices", json=new_device)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "设备添加成功"
    assert "device" in data


def test_add_device_duplicate_name(test_client, test_config_file):
    """测试添加重复设备名返回 400"""
    # 首先添加一个设备
    new_device = {
        "name": "switch-core-02",
        "ip": "192.168.1.2",
        "type": "cisco_ios",
    }
    response = test_client.post("/api/devices", json=new_device)
    assert response.status_code == 200

    # 尝试添加相同名称的设备
    duplicate_device = {
        "name": "switch-core-02",
        "ip": "192.168.1.3",
        "type": "cisco_ios",
    }
    response = test_client.post("/api/devices", json=duplicate_device)
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "存在" in data["detail"]


def test_add_device_invalid_name(test_client, test_config_file):
    """测试添加非法设备名"""
    # 测试包含非法字符的设备名
    invalid_names = [
        "switch/../etc/passwd",      # 路径遍历
        "switch\\etc\\passwd",        # 反斜杠
        "switch/test",                # 正斜杠
        "switch$name",                # 非法字符 $
        "switch#name",                # 非法字符 #
    ]

    for name in invalid_names:
        device = {
            "name": name,
            "ip": "192.168.1.100",
            "type": "cisco_ios",
        }
        response = test_client.post("/api/devices", json=device)
        assert response.status_code == 422, f"设备名 {name} 应该被拒绝"
        data = response.json()
        assert "detail" in data


def test_add_device_invalid_ip(test_client, test_config_file):
    """测试添加无效 IP 地址"""
    invalid_ips = [
        "999.999.999.999",   # 超出范围
        "256.256.256.256",   # 超出范围
        "192.168.1",         # 不完整
        "192.168.1.256",     # 最后一节超出范围
        "abc.def.ghi.jkl",   # 非数字
        "",                  # 空字符串
        None,                # None
    ]

    for ip in invalid_ips:
        device = {
            "name": f"switch-{ip or 'empty'}",
            "ip": ip,
            "type": "cisco_ios",
        }
        response = test_client.post("/api/devices", json=device)
        # 422 表示 Pydantic 验证失败，400 表示业务逻辑错误
        assert response.status_code in [400, 422], f"IP 地址 {ip} 应该被拒绝"


def test_add_device_invalid_type(test_client, test_config_file):
    """测试添加不支持的设备类型"""
    invalid_types = [
        "cisco_nxos",
        "aruba_os",
        "huawei",
        "juniper",
        "",
        None,
    ]

    for device_type in invalid_types:
        device = {
            "name": "switch-test",
            "ip": "192.168.1.1",
            "type": device_type,
        }
        response = test_client.post("/api/devices", json=device)
        assert response.status_code in [400, 422], f"设备类型 {device_type} 应该被拒绝"


def test_delete_device_success(test_client, test_config_file):
    """测试成功删除设备"""
    # 先添加一个设备
    new_device = {
        "name": "switch-temp-delete",
        "ip": "192.168.1.100",
        "type": "cisco_ios",
    }
    response = test_client.post("/api/devices", json=new_device)
    assert response.status_code == 200

    # 删除设备
    response = test_client.delete("/api/devices/switch-temp-delete")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "设备删除成功"

    # 验证设备已被删除
    response = test_client.get("/api/devices/switch-temp-delete")
    assert response.status_code == 404


def test_delete_device_not_found(test_client, test_config_file):
    """测试删除不存在的设备返回 404"""
    response = test_client.delete("/api/devices/nonexistent-device")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "不存在" in data["detail"]


def test_update_device_success(test_client, test_config_file):
    """测试成功更新设备"""
    # 先获取设备
    response = test_client.get("/api/devices/switch-core-01")
    assert response.status_code == 200
    device = response.json()

    # 更新设备
    update_data = {
        "location": "数据中心 B 区",
        "notes": "核心交换机 - 已更新",
        "version": "15.2(4)M",
    }
    response = test_client.patch("/api/devices/switch-core-01", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "设备更新成功"

    # 验证更新结果
    response = test_client.get("/api/devices/switch-core-01")
    updated_device = response.json()
    assert updated_device["location"] == "数据中心 B 区"
    assert updated_device["notes"] == "核心交换机 - 已更新"
    assert updated_device["version"] == "15.2(4)M"


def test_update_device_not_found(test_client, test_config_file):
    """测试更新不存在的设备返回 404"""
    update_data = {
        "location": "新位置",
        "notes": "新备注",
    }
    response = test_client.patch("/api/devices/nonexistent-device", json=update_data)
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "不存在" in data["detail"]


def test_update_device_partial_update(test_client, test_config_file):
    """测试部分更新设备（只更新部分字段）"""
    # 只更新 IP 地址
    update_data = {
        "ip": "192.168.1.200",
    }
    response = test_client.patch("/api/devices/switch-core-01", json=update_data)
    assert response.status_code == 200

    # 验证 IP 已更新，其他字段不变
    response = test_client.get("/api/devices/switch-core-01")
    device = response.json()
    assert device["ip"] == "192.168.1.200"
    assert device["location"] == "数据中心 A 区"  # 位置不变
    assert device["type"] == "cisco_ios"  # 类型不变


def test_update_device_invalid_ip(test_client, test_config_file):
    """测试更新时设置无效 IP"""
    update_data = {
        "ip": "999.999.999.999",  # 无效 IP
    }
    response = test_client.patch("/api/devices/switch-core-01", json=update_data)
    assert response.status_code in [400, 422], "无效 IP 应该被拒绝"


def test_update_device_invalid_name(test_client, test_config_file):
    """测试更新时设置非法设备名"""
    update_data = {
        "name": "switch/../path",  # 非法路径
    }
    response = test_client.patch("/api/devices/switch-core-01", json=update_data)
    assert response.status_code in [400, 422], "非法设备名应该被拒绝"


def test_add_device_with_all_fields(test_client, test_config_file):
    """测试添加包含所有字段的设备"""
    device = {
        "name": "switch-full-01",
        "ip": "192.168.2.1",
        "type": "cisco_ios",
        "platform": "cisco_ios",
        "location": "数据中心 A 区",
        "notes": "完整字段测试设备",
        "username": "test_user",
        "serial_number": "SN123456789",
        "version": "15.2(4)M",
    }
    response = test_client.post("/api/devices", json=device)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # 验证所有字段都被保存
    response = test_client.get("/api/devices/switch-full-01")
    saved_device = response.json()
    assert saved_device["name"] == device["name"]
    assert saved_device["ip"] == device["ip"]
    assert saved_device["platform"] == device["platform"]
    assert saved_device["location"] == device["location"]
    assert saved_device["notes"] == device["notes"]
    assert saved_device["serial_number"] == device["serial_number"]
    assert saved_device["version"] == device["version"]


def test_add_device_with_optional_fields(test_client, test_config_file):
    """测试添加仅包含必填字段的设备"""
    device = {
        "name": "switch-minimal-01",
        "ip": "192.168.2.2",
        "type": "aruba_osswitch",
    }
    response = test_client.post("/api/devices", json=device)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # 验证可选字段默认为 None
    response = test_client.get("/api/devices/switch-minimal-01")
    saved_device = response.json()
    assert saved_device["platform"] is None
    assert saved_device["location"] is None
    assert saved_device["notes"] is None


def test_delete_then_add_same_device(test_client, test_config_file):
    """测试删除设备后重新添加同名设备"""
    # 先添加设备
    device = {
        "name": "switch-temp-delete-01",
        "ip": "192.168.3.1",
        "type": "cisco_ios",
    }
    response = test_client.post("/api/devices", json=device)
    assert response.status_code == 200

    # 删除设备
    response = test_client.delete("/api/devices/switch-temp-delete-01")
    assert response.status_code == 200

    # 重新添加同名设备
    response = test_client.post("/api/devices", json=device)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_list_devices_after_operations(test_client, test_config_file):
    """测试在 CRUD 操作后设备列表的更新"""
    # 初始状态：1 个设备
    initial_response = test_client.get("/api/devices")
    assert initial_response.status_code == 200
    initial_count = len(initial_response.json())

    # 添加新设备
    new_device = {
        "name": "switch-test-count-01",
        "ip": "192.168.4.1",
        "type": "cisco_ios",
    }
    test_client.post("/api/devices", json=new_device)

    # 列表应该增加
    response = test_client.get("/api/devices")
    new_count = len(response.json())
    assert new_count == initial_count + 1

    # 删除新设备
    test_client.delete("/api/devices/switch-test-count-01")

    # 列表应该回到初始状态
    response = test_client.get("/api/devices")
    restored_count = len(response.json())
    assert restored_count == initial_count
