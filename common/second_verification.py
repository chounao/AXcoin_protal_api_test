"""业务敏感操作的二次校验。

流程固定为：创建 challenge -> 提交 challengeToken 与验证码 -> 返回 actionToken。
登录阶段的 2FA 仍由 common.login.Login 负责，两者不要混用。
"""

import os

from common.logger import logger
from common.simple_request import HttpRequest


class SecondVerification:
    """封装业务操作的 challenge/verify 两步校验。"""

    CHALLENGE_PATH = "/user/2fa/challenge"
    VERIFY_ACTION_PATH = "/user/2fa/verify-action"

    @staticmethod
    def _base_url(url):
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url 必须是非空字符串")
        return url.rstrip("/")

    def get_challenge(
        self,
        http_request: HttpRequest,
        url: str,
        action_type: str = "TRANSACTION_SUBMIT",
    ):
        """申请一次 challengeToken。"""
        if not action_type:
            raise ValueError("action_type 不能为空")
        token = http_request.requests(
            "POST",
            f"{self._base_url(url)}{self.CHALLENGE_PATH}",
            data={"actionType": action_type},
            nested_keys=["data", "challengeToken"],
        )
        if not token:
            raise RuntimeError(f"未取得 challengeToken（actionType={action_type}）")
        logger.debug("业务 2FA challenge 创建成功: %s", action_type)
        return token

    def verify_action(
        self,
        http_request: HttpRequest,
        url: str,
        action_type: str = "TRANSACTION_SUBMIT",
        code: str | None = None,
    ):
        """校验业务验证码并返回包含 actionToken/expireAt 的 data。"""
        verification_code = (
            code
            or os.getenv("AXCOIN_ACTION_2FA_CODE")
            or os.getenv("AXCOIN_2FA_CODE")
        )
        if not verification_code:
            raise ValueError(
                "缺少业务 2FA 验证码；请传入 code 或设置 AXCOIN_ACTION_2FA_CODE"
            )
        challenge_token = self.get_challenge(http_request, url, action_type)
        action_token = http_request.requests(
            "POST",
            f"{self._base_url(url)}{self.VERIFY_ACTION_PATH}",
            data={
                "actionType": action_type,
                "challengeToken": challenge_token,
                "code": verification_code,
            },
            nested_keys=["data", "actionToken"],
        )
        if not isinstance(action_token, str) or not action_token.strip():
            raise RuntimeError(f"未取得 actionToken（actionType={action_type}）")
        logger.debug("业务 2FA 验证成功: %s", action_type)
        return action_token.strip()
