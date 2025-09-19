import unittest

from app.services.security_service import AESCipher


class TestAESCipher(unittest.TestCase):
    def test_encrypt_and_decrypt_empty_bytes(self):
        encrypted = self.cipher.encrypt(b"")
        self.assertIsInstance(encrypted, bytes)
        decrypted = self.cipher.decrypt(encrypted)
        self.assertEqual(decrypted, b"")

    def test_encrypt_and_decrypt_large_data(self):
        large_data = b"A" * 1024 * 1024  # 1MB
        encrypted = self.cipher.encrypt(large_data)
        self.assertIsInstance(encrypted, bytes)
        decrypted = self.cipher.decrypt(encrypted)
        self.assertEqual(decrypted, large_data)

    def test_decrypt_with_wrong_key_fails(self):
        encrypted = self.cipher.encrypt(self.sample_bytes)
        wrong_cipher = AESCipher("wrong@example.com")
        with self.assertRaises(ValueError):
            wrong_cipher.decrypt(encrypted)

    def test_double_encryption(self):
        encrypted_once = self.cipher.encrypt(self.sample_bytes)
        encrypted_twice = self.cipher.encrypt(encrypted_once)
        # Should be able to decrypt twice to get original
        decrypted_once = self.cipher.decrypt(encrypted_twice)
        decrypted_twice = self.cipher.decrypt(decrypted_once)
        self.assertEqual(decrypted_twice, self.sample_bytes)

    def test_decrypt_truncated_ciphertext(self):
        encrypted = self.cipher.encrypt(self.sample_bytes)
        truncated = encrypted[:len(encrypted)//2]
        with self.assertRaises(ValueError):
            self.cipher.decrypt(truncated)

    def setUp(self):
        self.email = "test@example.com"
        self.cipher = AESCipher(self.email)
        self.sample_text = "Secret message"
        self.sample_bytes = self.sample_text.encode()

    def test_encrypt_and_decrypt(self):
        # Encrypt
        encrypted = self.cipher.encrypt(self.sample_bytes)
        self.assertIsInstance(encrypted, bytes)
        self.assertNotEqual(encrypted, self.sample_bytes)  # Should not match original

        # Decrypt
        decrypted = self.cipher.decrypt(encrypted)
        self.assertEqual(decrypted, self.sample_bytes)

    def test_different_email_key_produces_different_output(self):
        other_cipher = AESCipher("another@example.com")
        encrypted1 = self.cipher.encrypt(self.sample_bytes)
        encrypted2 = other_cipher.encrypt(self.sample_bytes)

        # Should not be the same due to different key/IV
        self.assertNotEqual(encrypted1, encrypted2)

    def test_decrypt_invalid_data_raises_error(self):
        with self.assertRaises(ValueError):
            self.cipher.decrypt(b"not_really_encrypted_data")


if __name__ == "__main__":
    unittest.main()
