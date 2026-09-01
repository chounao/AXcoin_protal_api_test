"""业务敏感操作的二次认证入口。"""

from contextlib import contextmanager

from common.second_verification import SecondVerification
from requests_models.base import ApiService


class VerificationService(ApiService):
    """组合 challenge/verify-action 两步业务 2FA。"""

    def __init__(self, http, base_url, verifier=None):
        super().__init__(http, base_url)
        self.verifier = verifier or SecondVerification()

    def verify(self, code=None, action_type="TRANSACTION_SUBMIT"):
        """完成二次认证并返回 actionToken。"""
        return self.verifier.verify_action(
            self.http,
            self.base_url,
            action_type=action_type,
            code=code,
        )

    @contextmanager
    def authorized(self, code=None, action_type="TRANSACTION_SUBMIT"):
        """创建一次性 Action Token 上下文，供复杂流程手动使用。"""
        action_token = self.verify(code=code, action_type=action_type)
        with self.http.use_action_token(action_token):
            yield action_token

    def execute(self, operation, *args, code=None,
                action_type="TRANSACTION_SUBMIT", **kwargs):
        """二次校验后执行目标方法，自动注入并清除 Action Token。"""
        if not callable(operation):
            raise TypeError("operation 必须是可调用的方法")
        with self.authorized(code=code, action_type=action_type):
            return operation(*args, **kwargs)



