from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

_PREFIX = "enc:v1:"


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("utf-8"))


def is_encrypted_value(v: Any) -> bool:
    return isinstance(v, str) and v.startswith(_PREFIX)


# -----------------------------
# Windows DPAPI helpers
# -----------------------------
def _dpapi_encrypt(plaintext: str) -> str:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    raw = plaintext.encode("utf-8")
    in_buf = ctypes.create_string_buffer(raw, len(raw))
    in_blob = DATA_BLOB(len(raw), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return _PREFIX + "dpapi:" + _b64e(data)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def _dpapi_decrypt(ciphertext: str) -> str:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    enc = ciphertext[len(_PREFIX + "dpapi:"):]
    raw = _b64d(enc)
    in_buf = ctypes.create_string_buffer(raw, len(raw))
    in_blob = DATA_BLOB(len(raw), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return data.decode("utf-8")
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


# -----------------------------
# Portable fallback (best effort)
# -----------------------------
def _fallback_key_file(base_dir: Path) -> Path:
    return Path(base_dir) / ".panel_data_key"


def _get_fallback_key(base_dir: Path) -> bytes:
    p = _fallback_key_file(base_dir)
    if p.exists():
        data = p.read_text(encoding="utf-8").strip()
        if data:
            return hashlib.sha256(data.encode("utf-8")).digest()
    key_text = secrets.token_urlsafe(48)
    p.write_text(key_text, encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    return hashlib.sha256(key_text.encode("utf-8")).digest()


def _xor_stream(data: bytes, key: bytes) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hashlib.sha256(key + counter.to_bytes(8, "big")).digest()
        need = min(len(block), len(data) - len(out))
        start = len(out)
        for i in range(need):
            out.append(data[start + i] ^ block[i])
        counter += 1
    return bytes(out)


def _fallback_encrypt(plaintext: str, base_dir: Path) -> str:
    key = _get_fallback_key(base_dir)
    raw = plaintext.encode("utf-8")
    nonce = os.urandom(16)
    stream_key = hashlib.sha256(key + nonce).digest()
    cipher = _xor_stream(raw, stream_key)
    mac = hashlib.sha256(key + nonce + cipher).digest()
    payload = {"n": _b64e(nonce), "c": _b64e(cipher), "m": _b64e(mac)}
    return _PREFIX + "file:" + _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _fallback_decrypt(ciphertext: str, base_dir: Path) -> str:
    key = _get_fallback_key(base_dir)
    enc = ciphertext[len(_PREFIX + "file:"):]
    payload = json.loads(_b64d(enc).decode("utf-8"))
    nonce = _b64d(payload["n"])
    cipher = _b64d(payload["c"])
    mac = _b64d(payload["m"])
    expect = hashlib.sha256(key + nonce + cipher).digest()
    if expect != mac:
        raise ValueError("Secret integrity check failed")
    stream_key = hashlib.sha256(key + nonce).digest()
    raw = _xor_stream(cipher, stream_key)
    return raw.decode("utf-8")


def encrypt_value(value: Any, base_dir: Path | str) -> Any:
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        return value
    if is_encrypted_value(value):
        return value
    base_dir = Path(base_dir)
    if os.name == "nt":
        try:
            return _dpapi_encrypt(value)
        except Exception:
            pass
    return _fallback_encrypt(value, base_dir)


def decrypt_value(value: Any, base_dir: Path | str) -> Any:
    if not is_encrypted_value(value):
        return value
    base_dir = Path(base_dir)
    if value.startswith(_PREFIX + "dpapi:"):
        return _dpapi_decrypt(value)
    if value.startswith(_PREFIX + "file:"):
        return _fallback_decrypt(value, base_dir)
    raise ValueError("Unknown secret format")


def encrypt_fields(data: dict, fields: list[str], base_dir: Path | str) -> dict:
    out = dict(data or {})
    for f in fields:
        if f in out and isinstance(out.get(f), str) and out.get(f) != "":
            out[f] = encrypt_value(out.get(f), base_dir)
    return out


def decrypt_fields(data: dict, fields: list[str], base_dir: Path | str) -> dict:
    out = dict(data or {})
    for f in fields:
        if f in out and isinstance(out.get(f), str) and is_encrypted_value(out.get(f)):
            out[f] = decrypt_value(out.get(f), base_dir)
    return out
