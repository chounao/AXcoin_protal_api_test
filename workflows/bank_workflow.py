"""银行账户跨角色操作流程。"""

from workflows.base import BaseWorkflow, WorkflowRoles


BankWorkflowRoles = WorkflowRoles


class BankWorkflow(BaseWorkflow):
    """查询银行账户，并在业务 2FA 后执行增删改。"""

    CREATE_ACTION_TYPE = "BANK_ACCOUNT_CREATE"
    UPDATE_ACTION_TYPE = "BANK_ACCOUNT_UPDATE"
    DELETE_ACTION_TYPE = "BANK_ACCOUNT_DELETE"

    def list_accounts(self, user_role=None, chain=None):
        return self.actor(user_role).banks.list(chain)

    def get_account(self, bank_account_id, user_role=None):
        account_id = self.required_id(bank_account_id, "bank_account_id")
        return self.actor(user_role).banks.get_bank_account(account_id)

    def create_bank_account(
        self,
        code=None,
        action_type=CREATE_ACTION_TYPE,
        user_role=None,
        bank_account_info=None,
        **overrides,
    ):
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.banks.create_bank_account,
            bank_account_info,
            code=code,
            action_type=action_type,
            **overrides,
        )

    def update_bank_account(
        self,
        bank_account_id,
        code=None,
        action_type=UPDATE_ACTION_TYPE,
        user_role=None,
        bank_account_info=None,
        **overrides,
    ):
        account_id = self.required_id(bank_account_id, "bank_account_id")
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.banks.update_bank_account,
            account_id,
            bank_account_info,
            code=code,
            action_type=action_type,
            **overrides,
        )

    def delete_bank_account(
        self,
        bank_account_id,
        code=None,
        action_type=DELETE_ACTION_TYPE,
        user_role=None,
    ):
        account_id = self.required_id(bank_account_id, "bank_account_id")
        actor = self.actor(user_role)
        return self.execute_sensitive(
            actor,
            actor.banks.delete_bank_account,
            account_id,
            code=code,
            action_type=action_type,
        )


if __name__ == "__main__":

    workflow = BankWorkflow()
    id = workflow.create_bank_account(
        bank_account_info={"name":"yangbailao",
                           "bankName":"Ahli United Bank Bahrain",
                           "iban":"GB29NWBK60161331926819",
                           "accountNumber":"123456789077",
                           "routingNumber":"00098761",
                           "swiftCode":"AUBBBHBMXXX",
                           "currency":["USD","BHD"],
                           "isDefault":bool(False)},
        code="123456",
    )
    print(id)
    # id = 'f60a5dd1-b0e0-4697-aeec-b95b537c1f8a'

    workflow.update_bank_account(
        bank_account_id=id,
        code="123456",
        bank_account_info={"name":"yangbailao",
                           "bankName":"Ahli United Bank Bahrain",
                           "iban":"GB29NWBK60161331926819",
                           "accountNumber":"123456789077",
                           "routingNumber":"00098761",
                           "swiftCode":"AUBBBHBMXXX",
                           "currency":["USD"],
                           "isDefault":bool(False)},
    )



    workflow.delete_bank_account(
        bank_account_id=id,
        code="123456",
    )

