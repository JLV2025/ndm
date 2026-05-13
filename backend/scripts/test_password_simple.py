"""
简单的密码加密测试脚本
"""
import sys
sys.path.insert(0, '.')

from utils.password import PasswordManager

def test_password():
    pm = PasswordManager()

    # 测试 1：基本加密解密
    plaintext = "test_password_123"
    encrypted = pm.encrypt(plaintext)
    decrypted = pm.decrypt(encrypted)

    if decrypted == plaintext:
        print("✓ 测试 1 通过：基本加密解密")
    else:
        print(f"✗ 测试 1 失败：解密结果 '{decrypted}' != 原始值 '{plaintext}'")
        return False

    # 测试 2：相同密码产生不同加密
    encrypted1 = pm.encrypt("same_password")
    encrypted2 = pm.encrypt("same_password")
    if encrypted1 != encrypted2:
        print("✓ 测试 2 通过：相同密码产生不同加密")
    else:
        print("✗ 测试 2 失败：相同密码产生相同加密")
        return False

    # 测试 3：特殊字符
    special = 'p@ssw0rd!#$%'
    encrypted = pm.encrypt(special)
    decrypted = pm.decrypt(encrypted)
    if decrypted == special:
        print("✓ 测试 3 通过：特殊字符处理")
    else:
        print(f"✗ 测试 3 失败：特殊字符处理失败")
        return False

    # 测试 4：中文密码
    chinese = "密码 test@123"
    encrypted = pm.encrypt(chinese)
    decrypted = pm.decrypt(encrypted)
    if decrypted == chinese:
        print("✓ 测试 4 通过：中文密码处理")
    else:
        print(f"✗ 测试 4 失败：中文密码处理失败")
        return False

    print("\n所有测试通过！")
    return True

if __name__ == "__main__":
    success = test_password()
    sys.exit(0 if success else 1)
