"""按角色独立缓存 access/refresh token，并根据 JWT exp 判断有效期。"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any


def read_jwt_exp(token: str) -> int | None:
    """读取 JWT 的 exp；无法解析时返回 None。此处不负责验证 JWT 签名。"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return int(decoded["exp"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


class TokenCache:
    """线程安全的 Token 对缓存，以 ROLE section 作为唯一键。"""

    def __init__(self, path: str | Path, refresh_before_seconds: int = 60):
        self.path = Path(path).expanduser()
        self.refresh_before_seconds = refresh_before_seconds
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as cache_file:
                data = json.load(cache_file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        """通过临时文件原子替换，避免中断后留下损坏 JSON。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)

    def get(self, section: str, email: str) -> str | None:
        """兼容旧调用：返回仍有效的 access token。"""
        pair = self.get_pair(section, email)
        return pair["access_token"] if pair else None

    def get_pair(self, section: str, email: str) -> dict[str, Any] | None:
        """返回角色的完整 Token 对；access token 即将过期时返回 None。"""
        with self._lock:
            item = self._read().get(section)
            if not isinstance(item, dict) or item.get("email") != email:
                return None
            token = item.get("access_token")
            expires_at = item.get("access_expires_at", item.get("expires_at"))
            if not isinstance(token, str) or not isinstance(expires_at, int):
                return None
            if expires_at <= int(time.time()) + self.refresh_before_seconds:
                return None
            return dict(item)

    def get_refresh_token(self, section: str, email: str) -> str | None:
        """返回仍有效的 refresh token，即使 access token 已经过期。"""
        with self._lock:
            item = self._read().get(section)
            if not isinstance(item, dict) or item.get("email") != email:
                return None
            token = item.get("refresh_token")
            expires_at = item.get("refresh_expires_at")
            if not isinstance(token, str) or not isinstance(expires_at, int):
                return None
            if expires_at <= int(time.time()) + self.refresh_before_seconds:
                return None
            return token

    def put(self, section: str, email: str, token: str) -> int:
        """兼容旧调用：只保存 access token。"""
        return self.put_pair(section, email, token, refresh_token=None)[0]

    def put_pair(
        self,
        section: str,
        email: str,
        access_token: str,
        refresh_token: str | None,
    ) -> tuple[int, int | None]:
        """原子保存一对新 Token，返回二者过期时间。"""
        access_expires_at = read_jwt_exp(access_token)
        if access_expires_at is None:
            raise ValueError("access token 不包含可读取的 JWT exp，无法可靠缓存")
        refresh_expires_at = read_jwt_exp(refresh_token) if refresh_token else None
        if refresh_token and refresh_expires_at is None:
            raise ValueError("refresh token 不包含可读取的 JWT exp，无法可靠缓存")
        with self._lock:
            data = self._read()
            data[section] = {
                "email": email,
                "access_token": access_token,
                "access_expires_at": access_expires_at,
                "refresh_token": refresh_token,
                "refresh_expires_at": refresh_expires_at,
            }
            self._write(data)
        return access_expires_at, refresh_expires_at

    def import_legacy(self, section: str, email: str, token: str | None) -> str | None:
        """把 INI 中仍有效的旧 Token 迁移到缓存。

        旧配置可能包含 ``Bearer`` 前缀；缓存始终只保存原始 Token。
        无效或即将过期的 Token 会被忽略，由登录流程重新获取。
        """
        if not isinstance(token, str) or not token.strip():
            return None
        raw_token = token.strip()
        if raw_token.lower().startswith("bearer "):
            raw_token = raw_token[7:].strip()
        expires_at = read_jwt_exp(raw_token)
        if expires_at is None or expires_at <= int(time.time()) + self.refresh_before_seconds:
            return None
        self.put(section, email, raw_token)
        return raw_token

    def remove(self, section: str) -> None:
        """只清除指定角色，不影响其他账号。"""
        with self._lock:
            data = self._read()
            if data.pop(section, None) is not None:
                self._write(data)
