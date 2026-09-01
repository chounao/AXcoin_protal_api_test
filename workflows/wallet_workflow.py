"""钱包地址跨角色操作流程。"""

from workflows.base import BaseWorkflow, WorkflowRoles


WalletWorkflowRoles = WorkflowRoles


class WalletWorkflow(BaseWorkflow):
    """查询钱包，并在业务 2FA 后执行增删改。"""

    CREATE_ACTION_TYPE = "WALLET_ADDRESS_CREATE"
    UPDATE_ACTION_TYPE = "WALLET_ADDRESS_UPDATE"
    DELETE_ACTION_TYPE = "WALLET_ADDRESS_DELETE"

    def list_wallets(self, user_role=None, chain=None):
        return self.actor(user_role).wallets.list(chain)

    def get_wallet(self, wallet_id, user_role=None):
        selected_id = self.required_id(wallet_id, "wallet_id")
        return self.actor(user_role).wallets.get_wallet(selected_id)

    def create_wallet(
        self,
        code=None,
        action_type=CREATE_ACTION_TYPE,
        user_role=None,
        wallet_info=None,
        **overrides,
    ):
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.wallets.create_wallet,
            wallet_info,
            code=code,
            action_type=action_type,
            **overrides,
        )

    def update_wallet(
        self,
        wallet_id,
        code=None,
        action_type=UPDATE_ACTION_TYPE,
        user_role=None,
        wallet_info=None,
        **overrides,
    ):
        selected_id = self.required_id(wallet_id, "wallet_id")
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.wallets.update_wallet_account,
            selected_id,
            wallet_info,
            code=code,
            action_type=action_type,
            **overrides,
        )

    def delete_wallet(
        self,
        wallet_id,
        code=None,
        action_type=DELETE_ACTION_TYPE,
        user_role=None,
    ):
        selected_id = self.required_id(wallet_id, "wallet_id")
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.wallets.delete_wallet_account,
            selected_id,
            code=code,
            action_type=action_type,
        )


if __name__ == "__main__":
    print("请实例化 WalletWorkflow 并显式调用；直接运行不会修改真实钱包。")
    workflow = WalletWorkflow()
    id = workflow.create_wallet(
        user_role=workflow.roles.Submitter,
        wallet_info={
            "name": "TEST003",
            "chainName": "ETHEREUM",
            "isDefault": bool(False),
            "walletAddress": "0x27B9685450447802993145014243308746194708",
        },
        code="123456",
    )
    print(id)
    # id = 'd1cf7876-8172-4333-9aae-e34fef19cad9'
    workflow.update_wallet(
        wallet_id=id,
        user_role=workflow.roles.Admin,
        **{
            "name": "TEST005",

        },
    )

    workflow.delete_wallet(
        wallet_id=id,
        user_role=workflow.roles.Admin,
        code="123456",
    )
