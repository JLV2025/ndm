"""
密码加密/解密模块测试
遵循 TDD 原则：先写测试，再实现代码
"""
import pytest
from utils.password import PasswordManager


class TestPasswordManager:
    """密码管理器测试类"""

    def test_encrypt_decrypt_roundtrip(self, test_password_manager):
        """测试加密后再解密应该得到原始值"""
        plaintext = "test_password_123"
        encrypted = test_password_manager.encrypt(plaintext)
        decrypted = test_password_manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_different_passwords(self, test_password_manager):
        """测试相同的密码应该产生不同的加密结果（因为随机 IV）"""
        password = "same_password"
        encrypted1 = test_password_manager.encrypt(password)
        encrypted2 = test_password_manager.encrypt(password)
        assert encrypted1 != encrypted2

    def test_encrypt_unicode_password(self, test_password_manager):
        """测试包含特殊字符的密码"""
        passwords = [
            "p@ssw0rd!",
            "密码 123",
            "密码 test@#$",
            "müller-straße",
        ]
        for password in passwords:
            encrypted = test_password_manager.encrypt(password)
            decrypted = test_password_manager.decrypt(encrypted)
            assert decrypted == password

    def test_encrypt_empty_password(self, test_password_manager):
        """测试空密码"""
        encrypted = test_password_manager.encrypt("")
        decrypted = test_password_manager.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_special_characters(self, test_password_manager):
        """测试特殊字符"""
        special_chars = ['"', "'", "<", ">", "&", "\n", "\t"]
        test_string = "".join(special_chars)
        encrypted = test_password_manager.encrypt(test_string)
        decrypted = test_password_manager.decrypt(encrypted)
        assert decrypted == test_string

    def test_decrypt_invalid_format(self, test_password_manager):
        """测试解密格式错误的密文应该失败"""
        with pytest.raises(Exception):
            test_password_manager.decrypt("invalid_format")

    def test_encrypt_long_password(self, test_password_manager):
        """测试较长的密码"""
        long_password = "a" * 1000
        encrypted = test_password_manager.encrypt(long_password)
        decrypted = test_password_manager.decrypt(encrypted)
        assert decrypted == long_password
