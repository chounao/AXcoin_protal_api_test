"""多角色 API 客户端注册表。

一个角色只创建一个 PortalApi 实例；每个实例内部拥有独立 HttpRequest，
因此 Authorization 不会在用户之间相互覆盖。
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

from common.login import Login
from common.read_and_save_tool import ConfigTools
from common.simple_request import HttpRequest
from requests_models.requests_tools import PortalApi


class RoleClients:
    """按 ROLE section 懒加载并复用 PortalApi。"""

    DEFAULT_ROLES = (
        "ROLE_admin",
        "ROLE_Submitter",
        "ROLE_approver",
        "ROLE_root_admin",
        "ROLE_sales",
        "ROLE_operator",
        "ROLE_compliance",
    )

    def __init__(self, config=None, login_manager=None):
        self.config = config or ConfigTools()
        self.login_manager = login_manager or Login(config=self.config)
        self._clients = {}
        self._lock = threading.RLock()

    def get(self, role: str) -> PortalApi:
        """取得指定角色客户端；首次使用时才创建。"""
        if not isinstance(role, str) or not role.strip():
            raise ValueError("role 必须是非空字符串")
        role = role.strip()
        if not self.config.get_section_data(role):
            raise ValueError(f"配置中不存在角色 section: {role}")

        with self._lock:
            if role not in self._clients:
                http = HttpRequest(
                    section=role,
                    config=self.config,
                    auth_manager=self.login_manager,
                )
                self._clients[role] = PortalApi(
                    http_request=http,
                    config=self.config,
                    role=role,
                )
            return self._clients[role]

    def prepare(self, roles: Iterable[str], *, force=False):
        """提前并行准备多个角色 Token，返回 ``{role: token}``。"""
        role_list = list(dict.fromkeys(roles))
        return self.login_manager.login_all(role_list, force=force)

    def invalidate(self, role: str):
        """只清除指定角色 Token，不影响其他用户。"""
        self.login_manager.invalidate(role)

    def __getitem__(self, role: str) -> PortalApi:
        return self.get(role)

    @property
    def submitter(self):
        return self.get("ROLE_Submitter")

    @property
    def approver(self):
        return self.get("ROLE_approver")

    @property
    def operator(self):
        return self.get("ROLE_operator")

    @property
    def compliance(self):
        return self.get("ROLE_compliance")

    @property
    def admin(self):
        return self.get("ROLE_admin")

    @property
    def root_admin(self):
        return self.get("ROLE_root_admin")

    @property
    def sales(self):
        return self.get("ROLE_sales")
