from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def get_cipher() -> Fernet:
    """Return a Fernet cipher using the key defined in settings."""
    key = settings.CHAT_ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_message(plaintext: str) -> str:
    """
    Encrypt a plaintext string and return the encrypted token as a string.
    Returns an empty string if plaintext is empty/None.
    """
    if not plaintext:
        return plaintext
    cipher = get_cipher()
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_message(ciphertext: str) -> str:
    """
    Decrypt a Fernet-encrypted string back to plaintext.
    Falls back to returning the original value if decryption fails
    (e.g. legacy unencrypted rows in the database).
    """
    if not ciphertext:
        return ciphertext
    try:
        cipher = get_cipher()
        return cipher.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        print(f"[decrypt_message ERROR] type={type(e).__name__} | value='{e}' | ciphertext_preview={ciphertext[:30]}")
        return ciphertext