"""企业用户额度的多角色工作流。"""

from workflows.base import BaseWorkflow, WorkflowRoles


LimitsWorkflowRoles = WorkflowRoles


class LimitsWorkflow(BaseWorkflow):
    """由目标用户提供 userId，再由指定角色直接配置额度。

    设置用户额度不需要业务 2FA；申请提高额度需要先完成 2FA，
    临时写入 ``x-action-token``，请求结束后由认证服务自动清除。
    """

    DEFAULT_PREPARE_FIELDS = ("Submitter", "Admin")
    LIMIT_INCREASE_ACTION_TYPE = "LIMIT_INCREASE_APPLY"

    def get_user_id(self, user_role=None):
        return self.actor(
            user_role,
            default_role=user_role,
        ).limits.get_current_user_id()


    def set_limits(
        self,
        target_user_id,
        *,
        user_role=None,
        limits=None,
        default_limit_amount=None,
    ):
        manager = self.actor(user_role, default_role=user_role)
        return manager.limits.set_user_limits(
            self.required_id(target_user_id, "target_user_id"),
            limits,
            default_limit_amount=default_limit_amount,
        )

    def get_assignedby(self, user_role=None):

        return self.actor(
            user_role=user_role
        ).limits.get_assigned_by()

    def set_up_limits(
        self,
        target_user_id=None,
        *,
        user_role=None,
        id=None,
        limits=None,
        default_limit_amount=None,
    ):
        """兼容旧方法名和旧 ``id=`` 参数。"""
        selected_id = target_user_id if target_user_id is not None else id
        return self.set_limits(
            selected_id,
            user_role=user_role,
            limits=limits,
            default_limit_amount=default_limit_amount,
        )

    def run_set_up(
        self,
        *,
        user_role=None,
        limits=None,
        default_limit_amount=None,
    ):
        target_user_id = self.get_assignedby(user_role)
        result = self.set_limits(
            target_user_id,
            user_role=user_role,
            limits=limits,
            default_limit_amount=default_limit_amount,
        )
        return {"user_id": target_user_id, "limits": result}

    def limit_increase_requests(self, user_role=None):
        """直接提交提额申请；需要 2FA 的流程请调用 run_limit_increase_requests。"""
        manager = self.actor(user_role, default_role=user_role)
        return manager.limits.apply_for_burn_and_mint_limit_increase()

    def run_limit_increase_requests(
        self,
        user_role=None,
        code=None,
        action_type=None,
    ):
        """完成提额 2FA 后提交申请，并自动清除 x-action-token。"""
        manager = self.actor(user_role, default_role=user_role)
        return self.execute_sensitive(
            manager,
            manager.limits.apply_for_burn_adn_mint_limit_increase,
            code=code,
            action_type=action_type or self.LIMIT_INCREASE_ACTION_TYPE,
        )

if __name__ == "__main__":

    limits = LimitsWorkflow()
    print(limits.get_user_id(user_role = 'ROLE_admin'))

    limits.run_set_up(user_role='ROLE_admin')


    limits.run_limit_increase_requests(user_role='ROLE_admin', code='123456')
