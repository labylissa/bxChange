import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_NONCE_SIZE = 12  # 96-bit nonce for AES-GCM


def _get_key() -> bytes:
    try:
        key_bytes = bytes.fromhex(settings.encryption_key)
    except ValueError:
        raise ValueError(
            "ENCRYPTION_KEY must be a 64-character hex string (32 bytes). "
            "Generate with: openssl rand -hex 32"
        )
    if len(key_bytes) != 32:
        raise ValueError(
            f"ENCRYPTION_KEY must decode to exactly 32 bytes, got {len(key_bytes)}. "
            "Generate with: openssl rand -hex 32"
        )
    return key_bytes


def encrypt(data: dict) -> str:
    """Encrypt a dict to a base64-encoded AES-256-GCM ciphertext."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    plaintext = json.dumps(data, ensure_ascii=False).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode()


def decrypt(token: str) -> dict:
    """Decrypt a base64-encoded AES-256-GCM ciphertext back to a dict."""
    key = _get_key()
    aesgcm = AESGCM(key)
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        nonce, ciphertext = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())
    except Exception as exc:
        raise ValueError(f"Decryption failed: {exc}") from exc
