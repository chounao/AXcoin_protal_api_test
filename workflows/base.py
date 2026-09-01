"""所有跨角色 Workflow 共用的轻量基础能力。"""

from dataclasses import dataclass

from common.role_clients import RoleClients


@dataclass(frozen=True)
class WorkflowRoles:
    """项目统一角色映射。

    ``creator`` 和 ``receipt_submitter`` 保留给旧 Mint 流程自定义分工；
    未设置时分别回退到 Submitter 和 Operator。
    """

    Admin: str = "ROLE_admin"
    Submitter: str = "ROLE_Submitter"
    Approver: str = "ROLE_approver"
    Root_admin: str = "ROLE_root_admin"
    Sales: str = "ROLE_sales"
    Operator: str = "ROLE_operator"
    Compliance: str = "ROLE_compliance"
    creator: str | None = None
    receipt_submitter: str | None = None


class BaseWorkflow:
    """集中处理角色客户端、Token 预热、ID 校验和敏感操作。"""

    DEFAULT_ACTOR_FIELD = "Admin"
    DEFAULT_PREPARE_FIELDS = ("Admin",)

    def __init__(self, clients=None, roles=None):
        self.clients = clients or RoleClients()
        self.roles = roles or WorkflowRoles()

    def role(self, field_name):
        """按字段名取得角色配置。"""
        value = getattr(self.roles, field_name, None)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"流程角色 {field_name} 未配置")
        return value.strip()

    def actor(self, user_role=None, *, default_role=None):
        """取得角色独立客户端，不修改其他角色 headers。"""
        selected_role = user_role or default_role or self.role(
            self.DEFAULT_ACTOR_FIELD
        )
        if not isinstance(selected_role, str) or not selected_role.strip():
            raise ValueError("user_role 必须是非空字符串")
        return self.clients[selected_role.strip()]

    def prepare_users(self, user_roles=None, *, force=False):
        """提前并行准备参与角色登录 Token。"""
        selected_roles = user_roles or [
            self.role(field_name) for field_name in self.DEFAULT_PREPARE_FIELDS
        ]
        return self.clients.prepare(selected_roles, force=force)

    @staticmethod
    def required_id(value, name):
        """在发起 2FA 前校验资源 ID，避免浪费一次性验证码。"""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} 不能为空")
        return value.strip()

    @staticmethod
    def execute_sensitive(
        actor,
        operation,
        *args,
        code=None,
        action_type,
        **kwargs,
    ):
        """完成业务 2FA 后执行一次写操作并自动清除 Action Token。"""
        return actor.verification.execute(
            operation,
            *args,
            code=code,
            action_type=action_type,
            **kwargs,
        )


if __name__ == '__main__':
    a = BaseWorkflow()
    print( a.actor(user_role ='ROLE_admin' ))