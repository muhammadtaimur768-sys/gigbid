"""Encrypted per-user OAuth token storage (Fernet) for the Upwork MCP connection.

Implements the MCP SDK's `TokenStorage` protocol so it can back `OAuthClientProvider`
(discovery, dynamic client registration, PKCE, refresh) as well as a plain bearer lookup.
Key: env TOKEN_ENC_KEY (a urlsafe-base64 32-byte Fernet key). Files: <dir>/<user>.<kind>.enc
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from mcp.client.auth import TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from mcp_servers.common.settings import repo_path

_SAFE = re.compile(r"[^A-Za-z0-9_.-]")


class TokenStoreError(Exception):
    pass


class EncryptedTokenStore:
    def __init__(self, directory: str | Path | None = None, key: str | bytes | None = None):
        key = key or os.environ.get("TOKEN_ENC_KEY")
        if not key:
            raise TokenStoreError("TOKEN_ENC_KEY is not set; cannot store OAuth tokens")
        self.fernet = Fernet(key if isinstance(key, bytes) else key.encode())
        self.dir = Path(directory) if directory else repo_path("data/processed/oauth_tokens")

    def _path(self, user_id: str, kind: str) -> Path:
        return self.dir / f"{_SAFE.sub('_', user_id)}.{kind}.enc"

    def put(self, user_id: str, kind: str, data: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self._path(user_id, kind)
        p.write_bytes(self.fernet.encrypt(json.dumps(data).encode()))
        os.chmod(p, 0o600)

    def get(self, user_id: str, kind: str) -> dict | None:
        p = self._path(user_id, kind)
        if not p.exists():
            return None
        try:
            return json.loads(self.fernet.decrypt(p.read_bytes()))
        except InvalidToken as e:
            raise TokenStoreError("token file cannot be decrypted with the configured key") from e

    def delete(self, user_id: str) -> None:
        for kind in ("tokens", "client"):
            self._path(user_id, kind).unlink(missing_ok=True)


class UserTokenStorage(TokenStorage):
    """Per-user view implementing mcp.client.auth.TokenStorage."""

    def __init__(self, store: EncryptedTokenStore, user_id: str):
        self.store, self.user_id = store, user_id

    async def get_tokens(self) -> OAuthToken | None:
        d = self.store.get(self.user_id, "tokens")
        return OAuthToken(**d) if d else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self.store.put(self.user_id, "tokens", tokens.model_dump(mode="json", exclude_none=True))

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        d = self.store.get(self.user_id, "client")
        return OAuthClientInformationFull(**d) if d else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self.store.put(self.user_id, "client", client_info.model_dump(mode="json", exclude_none=True))
