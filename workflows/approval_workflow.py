"""订单、钱包及银行账户审批工作流。"""

from workflows.base import BaseWorkflow, WorkflowRoles


ApprovalWorkflowRoles = WorkflowRoles


class ApprovalWorkflow(BaseWorkflow):
    """由 Approver 或指定角色执行审批。"""

    DEFAULT_ACTOR_FIELD = "Approver"
    DEFAULT_PREPARE_FIELDS = ("Approver",)
    ORDER_ACTION_TYPE = "TRANSACTION_CONFIRM"

    def approve_order(
        self,
        user_role=None,
        order_id=None,
        action=None,
        reason=None,
        code=None,
        action_type=ORDER_ACTION_TYPE,
    ):
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.approval_model.internal_approve,
            self.required_id(order_id, "order_id"),
            action,
            reason=reason,
            code=code,
            action_type=action_type,
        )

    def approve_wallet_address(
        self,
        user_role=None,
        wallet_id=None,
        action=None,
        rejectionReason=None,
    ):
        """钱包企业审核接口不执行业务 2FA。"""
        actor = self.actor(user_role)
        return actor.approval_model.wallet_approve(
            self.required_id(wallet_id, "wallet_id"),
            action,
            rejectionReason=rejectionReason,
        )

    def approve_bank_account(
        self,
        user_role=None,
        bank_account_id=None,
        action=None,
        rejectionReason=None,
    ):
        """银行账户企业审核接口不执行业务 2FA。"""
        actor = self.actor(user_role)
        return actor.approval_model.bank_approve(
            self.required_id(bank_account_id, "bank_account_id"),
            action,
            rejectionReason=rejectionReason,
        )

    def approve_limit(
        self,
        user_role=None,
        limit_id=None,
        action=None,
        reviewNote=None,
    ):
        """额度企业审核接口不执行业务 2FA。"""
        actor = self.actor(user_role)
        return actor.approval_model.limit_approve(
            self.required_id(limit_id, "limit_id"),
            action,
            reviewNote=reviewNote,
        )
if __name__ == "__main__":
    print("请实例化 ApprovalWorkflow 并显式调用；直接运行不会执行真实审批。")
    from wallet_workflow import WalletWorkflow
    import time
    wallet = WalletWorkflow()

    approval = ApprovalWorkflow()
    # wallet_id =  wallet.create_wallet(
    #     user_role = wallet.roles.Submitter,
    #     wallet_info={
    #          "name": "TEST003",
    #         "chainName": "ETHEREUM",
    #         "isDefault": bool(False),
    #         "walletAddress": "0x27B9685450447802993145014243308746194708",
    #     },
    #     code="123456",
    # )
    # print(wallet_id)
    # time.sleep(5)
    # result = approval.approve_wallet_address(
    #     user_role="ROLE_admin",
    #     wallet_id=wallet_id,
    #     action="REJECT",
    #     rejectionReason="test",
    # )
    #
    # wallet.delete_wallet(
    #     wallet_id=wallet_id,
    #     user_role=wallet.roles.Submitter,
    #     code="123456",
    # )


    # from bank_workflow import BankWorkflow
    # bank = BankWorkflow()
    #
    # bank_id = bank.create_bank_account(
    #     bank_account_info={"name": "yangbailao",
    #                        "bankName": "Ahli United Bank Bahrain",
    #                        "iban": "GB29NWBK60161331926819",
    #                        "accountNumber": "123456789077",
    #                        "routingNumber": "00098761",
    #                        "swiftCode": "AUBBBHBMXXX",
    #                        "currency": ["USD", "BHD"],
    #                        "isDefault": bool(False)},
    #     code="123456",
    # )
    #
    # print(bank_id)
    # time.sleep(5)
    # result = approval.approve_bank_account(
    #     user_role="ROLE_approver",
    #     bank_account_id=bank_id,
    #     action="REJECT",
    #     rejectionReason="test",
    # )
    #
    # bank.delete_bank_account(
    #     bank_account_id=bank_id,
    #     code="123456",
    # )


    id = "30cd5261-8500-459d-912c-a8a3e55ddbf8"
    approval.approve_limit(
        user_role="ROLE_admin",
        limit_id=id,
        action="APPROVED",
        reviewNote="test",
    )