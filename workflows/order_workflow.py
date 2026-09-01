"""Mint/Burn 订单的多角色流程协调器。"""

from workflows.base import BaseWorkflow, WorkflowRoles


OrderWorkflowRoles = WorkflowRoles
MintWorkflowRoles = WorkflowRoles


class OrderWorkflow(BaseWorkflow):
    """协调创建者与凭证提交者完成订单流程。"""

    CREATE_ACTION_TYPE = "TRANSACTION_SUBMIT"
    RECEIPT_ACTION_TYPE = "TRANSACTION_SUBMIT"

    @property
    def creator_role(self):
        return self.roles.creator or self.roles.Submitter

    @property
    def receipt_submitter_role(self):
        return self.roles.receipt_submitter or self.roles.Operator

    def prepare_users(self, user_roles=None, *, force=False):
        selected_roles = user_roles or [
            self.creator_role,
            self.receipt_submitter_role,
        ]
        return self.clients.prepare(selected_roles, force=force)

    def prepare_order(self, user_role=None, **order_data):
        creator = self.actor(user_role, default_role=self.creator_role)
        return creator.transactions.build_payload(**order_data)

    def create_order(
        self,
        *,
        user_role=None,
        code=None,
        action_type=None,
        operation_type="MINT",
        **order_data,
    ):
        creator = self.actor(user_role, default_role=self.creator_role)
        payload = creator.transactions.build_payload(
            operation_type=operation_type,
            **order_data,
        )
        return self.execute_sensitive(
            creator,
            creator.transactions.create_prepared,
            payload,
            code=code,
            action_type=action_type or self.CREATE_ACTION_TYPE,
        )

    def get_latest_status(self, order_id, user_role=None):
        actor = self.actor(user_role, default_role=self.creator_role)
        return actor.transactions.get_status(
            self.required_id(order_id, "order_id")
        )

    def cancel(self, order_id, user_role=None):
        actor = self.actor(user_role, default_role=self.creator_role)
        return actor.transactions.cancel(self.required_id(order_id, "order_id"))

    def receipt(
        self,
        order_id,
        receipt_url,
        *,
        code=None,
        action_type=None,
        user_role=None,
    ):
        actor = self.actor(
            user_role,
            default_role=self.receipt_submitter_role,
        )
        return self.execute_sensitive(
            actor,
            actor.receipts.submit_prechecked,
            self.required_id(order_id, "order_id"),
            receipt_url,
            code=code,
            action_type=action_type or self.RECEIPT_ACTION_TYPE,
        )

    def run_all(
        self,
        *,
        receipt_url,
        operation_type="MINT",
        create_2fa_code=None,
        receipt_2fa_code=None,
        create_action_type=None,
        receipt_action_type=None,
        **order_data,
    ):
        order_id = self.create_order(
            user_role=self.creator_role,
            code=create_2fa_code,
            operation_type=operation_type,
            action_type=create_action_type,
            **order_data,
        )
        status = self.get_latest_status(order_id, user_role=self.creator_role)
        receipt = self.receipt(
            order_id,
            receipt_url,
            user_role=self.receipt_submitter_role,
            code=receipt_2fa_code,
            action_type=receipt_action_type,
        )
        return {"order_id": order_id, "status": status, "receipt": receipt}

    # 兼容原 MintOrderWorkflow.run(...) 调用方式。
    run = run_all


    def create_order_run(
        self,
        *,
        create_2fa_code=None,
        operation_type="MINT",
        create_action_type=None,
        **order_data,
    ):
        return self.create_order(
            user_role=self.creator_role,
            code=create_2fa_code,
            action_type=create_action_type,
            operation_type=operation_type,
            **order_data,
        )

    def run_cancel(self, *, order_id):
        return self.cancel(order_id, user_role=self.creator_role)


MintOrderWorkflow = OrderWorkflow


if __name__ == "__main__":
    print("请实例化 OrderWorkflow 并显式调用；直接运行不会创建或取消真实订单。")
    workflow = OrderWorkflow()

    result = workflow.run_all(
        amount="101",
        currency="USD",
        chain="ETHEREUM",
        receipt_url="receipts/800aefd5-5b97-45b6-8eda-5d6a0a933588.JPG",
        create_2fa_code="111111",
        receipt_2fa_code="111111",
    )

    print(result["order_id"])
    print(result["status"])
    print(result["receipt"])

    # order_id = workflow.create_order_run(
    #     amount="101",
    #     currency="USD",
    #     chain="ETHEREUM",
    #     create_2fa_code="111111",
    #     operation_type="BURN",
    #     create_action_type="TRANSACTION_SUBMIT",
    # )
    # print(order_id)
    # result = workflow.run_cancel(
    #     order_id=order_id,
    # )

    print(result)
