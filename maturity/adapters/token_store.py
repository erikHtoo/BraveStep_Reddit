"""Encrypted token store — AES-256-GCM when keyring set; lab plaintext opt-in only."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from maturity.config import ALLOW_PLAINTEXT_TOKENS, CHANNEL_TOKEN_ENCRYPTION_KEYS, DATA_DIR


@dataclass
class StoredConnection:
    case_id: str
    username: str
    access_token: str
    refresh_token: str | None
    scope: str


class TokenStoreError(RuntimeError):
    pass


def _parse_keyring(raw: str) -> list[bytes]:
    """CHANNEL_TOKEN_ENCRYPTION_KEYS=v1:<b64-32B>[,v2:...] — first key encrypts."""
    keys: list[bytes] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise TokenStoreError("keyring entries must be version:base64")
        _, b64 = part.split(":", 1)
        key = base64.b64decode(b64)
        if len(key) != 32:
            raise TokenStoreError("each AES key must be 32 bytes")
        keys.append(key)
    return keys


def _store_path(case_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in case_id)
    return DATA_DIR / f"connection_{safe}.json"


def save_connection(conn: StoredConnection) -> Path:
    path = _store_path(conn.case_id)
    payload = asdict(conn)
    if CHANNEL_TOKEN_ENCRYPTION_KEYS:
        keys = _parse_keyring(CHANNEL_TOKEN_ENCRYPTION_KEYS)
        aes = AESGCM(keys[0])
        nonce = os.urandom(12)
        pt = json.dumps(payload).encode("utf-8")
        ct = aes.encrypt(nonce, pt, None)
        blob = {
            "v": 1,
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ct).decode(),
        }
        path.write_text(json.dumps(blob), encoding="utf-8")
        return path

    if not ALLOW_PLAINTEXT_TOKENS:
        raise TokenStoreError(
            "Set CHANNEL_TOKEN_ENCRYPTION_KEYS (prod) or MATURITY_ALLOW_PLAINTEXT_TOKENS=1 (lab only)"
        )
    path.write_text(json.dumps({"v": 0, "plaintext": payload}), encoding="utf-8")
    return path


def load_connection(case_id: str) -> StoredConnection:
    path = _store_path(case_id)
    if not path.exists():
        raise TokenStoreError(f"no connection for case_id={case_id}")
    blob = json.loads(path.read_text(encoding="utf-8"))
    if blob.get("v") == 0:
        if not ALLOW_PLAINTEXT_TOKENS:
            raise TokenStoreError("plaintext store forbidden without lab flag")
        p = blob["plaintext"]
        return StoredConnection(**p)

    if not CHANNEL_TOKEN_ENCRYPTION_KEYS:
        raise TokenStoreError("encrypted blob requires CHANNEL_TOKEN_ENCRYPTION_KEYS")
    keys = _parse_keyring(CHANNEL_TOKEN_ENCRYPTION_KEYS)
    nonce = base64.b64decode(blob["nonce"])
    ct = base64.b64decode(blob["ciphertext"])
    last_err: Exception | None = None
    for key in keys:
        try:
            pt = AESGCM(key).decrypt(nonce, ct, None)
            p = json.loads(pt.decode("utf-8"))
            return StoredConnection(**p)
        except Exception as e:  # try next key (rotation)
            last_err = e
            continue
    raise TokenStoreError(f"decrypt failed: {last_err}")
