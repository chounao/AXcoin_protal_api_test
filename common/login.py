"""登录、2FA、多账号并行认证和 Token 缓存。"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import requests

from common.logger import logger
from common.read_and_save_tool import ConfigTools
from common.token_cache import TokenCache


def _first_string(data, paths):
    """兼容 Token 位于顶层、data、meta 或 result 的常见响应结构。"""
    for path in paths:
        current = data
        for key in path.split("."):
            current = current.get(key) if isinstance(current, dict) else None
        if isinstance(current, str) and current:
            return current
    return None


class Login:
    """为每个 ROLE section 维护独立 Token。"""

    DEFAULT_SECTIONS = (
        "ROLE_admin",
        "ROLE_Submitter",
        "ROLE_approver",
        "ROLE_root_admin",
        # "ROLE_sales", # 销售用户暂时不支持
        "ROLE_operator",
        "ROLE_compliance",
    )

    def __init__(self, config=None, session=None):
        self.config = config or ConfigTools()
        # 测试可注入 Session；默认使用 requests.post，让并行账号不共享可变 Session。
        self.session = session
        self.url = self.config.get_url_data()
        self.timeout = self.config.get_timeout()
        self.cache = TokenCache(
            self.config.get_token_cache_path(),
            self.config.get_refresh_before_seconds(),
        )
        self._role_locks = {}
        self._role_locks_guard = threading.Lock()

    def _lock_for(self, config_section):
        with self._role_locks_guard:
            return self._role_locks.setdefault(config_section, threading.RLock())

    def _headers(self):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        origin = self.config.get_origin()
        if origin:
            headers.update({"Origin": origin, "Referer": f"{origin.rstrip('/')}/"})
        return headers

    def set_user_data(self, config_section):
        """兼容旧方法，返回 email/password。"""
        return self.config.get_login_data(config_section)

    def login(self, config_section):
        """第一步：账号密码换取短时 tempToken。"""
        email, password = self.set_user_data(config_section)
        post = self.session.post if self.session is not None else requests.post
        response = post(
            f"{self.url}/user/login",
            json={"email": email, "password": password},
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        token = _first_string(
            response.json(),
            ("tempToken", "data.tempToken", "result.tempToken"),
        )
        if not token:
            raise RuntimeError(f"{config_section} 登录响应中没有 tempToken")
        return token

    @staticmethod
    def _extract_token_pair(payload, config_section, source):
        """从登录或刷新响应中读取 accessToken 和 refreshToken。"""
        access_token = _first_string(
            payload,
            (
                "accessToken", "access_token", "token", "data.accessToken",
                "data.access_token", "data.token", "data.meta",
                "data.meta.accessToken", "result.accessToken",
            ),
        )
        refresh_token = _first_string(
            payload,
            (
                "refreshToken", "refresh_token", "data.refreshToken",
                "data.refresh_token", "result.refreshToken",
            ),
        )
        if not access_token:
            raise RuntimeError(f"{config_section} {source}响应中没有 accessToken")
        if not refresh_token:
            raise RuntimeError(f"{config_section} {source}响应中没有 refreshToken")
        return access_token, refresh_token

    def login_token_pair(self, config_section, code=None):
        """第二步：tempToken + 登录 2FA 换取完整 Token 对。"""
        temp_token = self.login(config_section)
        post = self.session.post if self.session is not None else requests.post
        response = post(
            f"{self.url}/user/login/2fa",
            json={
                "tempToken": temp_token,
                "code": code or self.config.get_two_factor_code(config_section),
            },
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._extract_token_pair(response.json(), config_section, "登录 2FA ")

    def FA2_login(self, config_section, code=None):
        """兼容旧方法：完成登录 2FA，仅返回 accessToken。"""
        return self.login_token_pair(config_section, code)[0]

    def authenticate(self, config_section, force=False):
        """优先复用缓存；无有效 Token 时才登录和 2FA。"""
        with self._lock_for(config_section):
            email = self.config.get_email(config_section)
            if not force:
                cached = self.cache.get(config_section, email)
                if cached:
                    logger.debug("复用 %s 的有效 Token", config_section)
                    return cached
                legacy = self.cache.import_legacy(
                    config_section,
                    email,
                    self.config.get_access_token(config_section),
                )
                if legacy:
                    logger.info("已把 %s 的旧 Token 迁移到独立缓存", config_section)
                    return legacy
                if self.cache.get_refresh_token(config_section, email):
                    try:
                        return self.refresh(config_section)
                    except (requests.exceptions.RequestException, RuntimeError, ValueError) as error:
                        logger.warning(
                            "%s 缓存 access token 已失效且刷新失败，将完整登录: %s",
                            config_section,
                            error,
                        )
            access_token, refresh_token = self.login_token_pair(config_section)
            self.cache.put_pair(config_section, email, access_token, refresh_token)
            logger.info("%s 登录成功，Token 对已缓存", config_section)
            return access_token

    def refresh(self, config_section):
        """使用该角色的 refreshToken 获取并缓存一对新 Token。

        刷新接口不携带旧 access token。刷新失败由调用方决定是否完整登录。
        """
        with self._lock_for(config_section):
            email = self.config.get_email(config_section)
            refresh_token = self.cache.get_refresh_token(config_section, email)
            if not refresh_token:
                raise RuntimeError(f"{config_section} 没有有效 refreshToken")

            post = self.session.post if self.session is not None else requests.post
            response = post(
                f"{self.url}/user/refresh-token",
                json={"refreshToken": refresh_token},
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            access_token, new_refresh_token = self._extract_token_pair(
                response.json(), config_section, "刷新 Token "
            )
            self.cache.put_pair(
                config_section,
                email,
                access_token,
                new_refresh_token,
            )
            logger.info("%s Token 刷新成功", config_section)
            return access_token

    def recover_authorization(self, config_section):
        """401 恢复：优先 refresh；失败后完整登录并返回 Authorization。"""
        try:
            access_token = self.refresh(config_section)
        except (requests.exceptions.RequestException, RuntimeError, ValueError) as error:
            logger.warning("%s 刷新失败，改为完整登录: %s", config_section, error)
            self.invalidate(config_section)
            access_token = self.authenticate(config_section, force=True)
        return f"Bearer {access_token}"

    def get_authorization(self, config_section, force=False):
        return f"Bearer {self.authenticate(config_section, force=force)}"

    def invalidate(self, config_section):
        self.cache.remove(config_section)

    def login_tools(self, config_section):
        return self.authenticate(config_section)

    def login_all(self, config_sections=None, force=False):
        """并行准备多个账号，返回 ``{section: token}``。"""
        sections = list(config_sections or self.DEFAULT_SECTIONS)
        with ThreadPoolExecutor(max_workers=len(sections)) as executor:
            tokens = list(
                executor.map(
                    lambda section: self.authenticate(section, force=force),
                    sections,
                )
            )
        return dict(zip(sections, tokens))


_manager = None
_manager_lock = threading.Lock()


def get_login_manager():
    """进程级认证管理器，供 HttpRequest 自动获取角色 Token。"""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = Login()
        return _manager


def reset_login_manager():
    """清除进程级认证管理器，主要用于切换环境和单元测试。"""
    global _manager
    with _manager_lock:
        _manager = None


if __name__ == "__main__":
    result = Login().login_all()
    print({section: "authenticated" for section in result})
