"""
密码加密/解密模块
使用 AES-256 加密存储用户密码
"""

import os
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    """PKCS7 padding - 正确实现"""
    padding_len = block_size - (len(data) % block_size)
    if padding_len == 0:
        padding_len = block_size
    return data + bytes([padding_len] * padding_len)


def _pkcs7_unpad(data: bytes, block_size: int = 16) -> bytes:
    """PKCS7 unpadding - 正确实现"""
    if not data:
        raise ValueError('Empty data')
    padding_len = data[-1]
    if padding_len == 0 or padding_len > block_size:
        raise ValueError('Invalid padding')
    for i in range(1, padding_len + 1):
        if data[-i] != padding_len:
            raise ValueError('Invalid padding')
    return data[:-padding_len]


class PasswordManager:
    """密码管理器"""

    KEY_SIZE = 32  # 256 bits
    IV_SIZE = 16   # 128 bits

    def __init__(self, key: bytes = None):
        """初始化时生成密钥，或传入现有密钥"""
        if key is None:
            self._key = os.urandom(self.KEY_SIZE)
        else:
            self._key = key

    def encrypt(self, plaintext: str) -> str:
        """加密字符串 - 返回 base64 编码的 (iv + ciphertext)"""
        plaintext_bytes = plaintext.encode('utf-8')

        # 生成随机 IV
        iv = os.urandom(self.IV_SIZE)

        # 使用正确的 PKCS7 padding
        padded_data = _pkcs7_pad(plaintext_bytes, self.IV_SIZE)

        # AES-CBC 加密
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        # iv + ciphertext
        combined = iv + ciphertext
        return base64.b64encode(combined).decode('utf-8')

    def decrypt(self, ciphertext: str) -> str:
        """解密字符串"""
        encrypted_data = base64.b64decode(ciphertext.encode('utf-8'))

        # 提取 iv (前 16 字节)
        iv = encrypted_data[:self.IV_SIZE]
        ciphertext_bytes = encrypted_data[self.IV_SIZE:]

        # AES-CBC 解密
        cipher = Cipher(
            algorithms.AES(self._key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(ciphertext_bytes) + decryptor.finalize()

        # 移除填充
        plaintext = _pkcs7_unpad(padded_plaintext, self.IV_SIZE)

        return plaintext.decode('utf-8')


password_manager = PasswordManager()
