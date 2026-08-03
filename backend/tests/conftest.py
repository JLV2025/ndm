"""
测试配置和共享 fixture
"""
import pytest


@pytest.fixture
def test_password_manager():
    """创建密码管理器的测试实例 - 使用固定 key 以便测试可重复"""
    from utils.password import PasswordManager
    # 使用固定 key 以便测试可重复，而不是随机生成
    return PasswordManager(key=b'0123456789abcdef0123456789abcdef')
