"""审批相关接口。

本模块只负责发送审批请求。审批前的业务 2FA 由
``VerificationService.execute`` 统一处理，避免 Action Token 泄漏或复用。
"""

from common.logger import logger
from requests_models.base import ApiService


class ApprovalService(ApiService):
    """订单审批 API，绑定一个角色独立的 HTTP 客户端。"""

    VALID_ACTIONS = {"APPROVE", "REJECT","APPROVED"}

    def __init__(self, http, base_url, role=None):
        super().__init__(http, base_url)
        self.role = role

    @classmethod
    def normalize_action(cls, action, *, lowercase=False):
        """校验审批动作，并按接口要求返回大小写格式。"""
        normalized = cls.required(action, "action").upper()
        if normalized not in cls.VALID_ACTIONS:
            raise ValueError("action 仅支持 APPROVE 或 REJECT")
        return normalized.lower() if lowercase else normalized

    def internal_approve(self, order_id, action, reason=None):
        """发送订单审批请求；调用方应在外层完成业务 2FA。

        Args:
            order_id: 待审批订单 ID。
            action: ``APPROVE`` 或 ``REJECT``，大小写均可。
            reason: 审批原因；拒绝且未填写时使用默认原因。
        """
        safe_order_id = self.encoded_id(order_id, "order_id")
        normalized_action = self.normalize_action(action)
        normalized_reason = reason.strip() if isinstance(reason, str) else ""
        if normalized_action == "REJECT" and not normalized_reason:
            normalized_reason = "拒绝审批"

        logger.info(
            "审批订单：%s，操作：%s，角色：%s",
            order_id,
            normalized_action,
            self.role,
        )
        return self.request_data(
            "POST",
            f"/transaction/{safe_order_id}/approve",
            payload={
                "action": normalized_action.lower(),
                "reason": normalized_reason,
            },
        )

    def wallet_approve(self, wallet_id, action, rejectionReason=None):
        """执行钱包地址企业审核。"""
        safe_wallet_id = self.encoded_id(wallet_id, "wallet_id")
        return self.request_data(
            "PATCH",
            f"/user-account/wallet-addresses/{safe_wallet_id}/enterprise-review",
            payload={
                "action": self.normalize_action(action),
                "rejectionReason": rejectionReason,
            },
        )

    def bank_approve(self, bank_id, action, rejectionReason=None):
        """执行银行账户企业审核。"""
        safe_bank_id = self.encoded_id(bank_id, "bank_id")
        return self.request_data(
            "PATCH",
            f"/user-account/bank-accounts/{safe_bank_id}/enterprise-review",
            payload={
                "action": self.normalize_action(action),
                "rejectionReason": rejectionReason,
            },
        )


    # 额度审批
    def limit_approve(self, limit_id, action, reviewNote=None):
        """执行额度申请企业审核。"""
        safe_limit_id = self.encoded_id(limit_id, "limit_id")
        return self.request_data(
            "POST",
            f"/enterprise-user/limit-increase-requests/{safe_limit_id}/review",
            payload={"status":self.normalize_action(action),
                     "reviewNote":reviewNote}
        )

if __name__ == "__main__":
    print("请通过 ApprovalWorkflow 调用审批接口，避免绕过业务 2FA。")
