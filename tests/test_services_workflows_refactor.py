"""Services 与 Workflows 公共化回归测试。"""

import unittest
from unittest.mock import Mock

from requests_models.services.Approval_model import ApprovalService
from requests_models.services.asset_account import AccountService
from requests_models.services.limits_model import LimitsService
from requests_models.services.wallet_model import WalletService
from workflows import (
    ApprovalWorkflowRoles,
    BankWorkflowRoles,
    LimitsWorkflow,
    LimitsWorkflowRoles,
    WalletWorkflowRoles,
    WorkflowRoles,
)
from workflows.bank_workflow import BankWorkflow
from workflows.wallet_workflow import WalletWorkflow


class WorkflowBaseTests(unittest.TestCase):
    def test_all_workflows_share_one_role_mapping(self):
        self.assertIs(BankWorkflowRoles, WorkflowRoles)
        self.assertIs(WalletWorkflowRoles, WorkflowRoles)
        self.assertIs(LimitsWorkflowRoles, WorkflowRoles)
        self.assertIs(ApprovalWorkflowRoles, WorkflowRoles)

    def test_bank_sensitive_operation_passes_callable_to_2fa(self):
        actor = Mock()
        actor.verification.execute.return_value = "bank-1"
        clients = Mock()
        clients.__getitem__ = Mock(return_value=actor)
        workflow = BankWorkflow(clients=clients)

        result = workflow.create_bank_account(
            code="111111",
            bank_account_info={"name": "A"},
        )

        actor.banks.create_bank_account.assert_not_called()
        actor.verification.execute.assert_called_once_with(
            actor.banks.create_bank_account,
            {"name": "A"},
            code="111111",
            action_type="BANK_ACCOUNT_CREATE",
        )
        self.assertEqual(result, "bank-1")

    def test_wallet_update_uses_2fa_and_keeps_code_out_of_payload(self):
        actor = Mock()
        clients = Mock()
        clients.__getitem__ = Mock(return_value=actor)
        workflow = WalletWorkflow(clients=clients)

        workflow.update_wallet(
            "wallet-1",
            code="111111",
            wallet_info={"name": "updated"},
        )

        actor.wallets.update_wallet_account.assert_not_called()
        actor.verification.execute.assert_called_once_with(
            actor.wallets.update_wallet_account,
            "wallet-1",
            {"name": "updated"},
            code="111111",
            action_type="WALLET_ADDRESS_UPDATE",
        )

    def test_limits_never_uses_2fa(self):
        actor = Mock()
        actor.limits.set_user_limits.return_value = {"updated": True}
        clients = Mock()
        clients.__getitem__ = Mock(return_value=actor)

        result = LimitsWorkflow(clients=clients).set_limits(
            "user-1",
            default_limit_amount="500",
        )

        actor.verification.execute.assert_not_called()
        actor.limits.set_user_limits.assert_called_once_with(
            "user-1",
            None,
            default_limit_amount="500",
        )
        self.assertEqual(result, {"updated": True})

    def test_limit_increase_uses_workflow_2fa_and_limits_service(self):
        actor = Mock()
        actor.verification.execute.return_value = {"submitted": True}
        clients = Mock()
        clients.__getitem__ = Mock(return_value=actor)

        result = LimitsWorkflow(clients=clients).run_limit_increase_requests(
            user_role="ROLE_admin",
            code="123456",
        )

        actor.verification.execute.assert_called_once_with(
            actor.limits.apply_for_burn_and_mint_limit_increase,
            code="123456",
            action_type="LIMIT_INCREASE_APPLY",
        )
        self.assertEqual(result, {"submitted": True})


class ServiceRefactorTests(unittest.TestCase):
    def test_order_reject_has_default_reason_and_encoded_id(self):
        http = Mock()
        http.requests.return_value = {"approved": True}
        service = ApprovalService(http, "https://example.test/api/v1")

        service.internal_approve("order/1", "reject")

        self.assertIn("order%2F1", http.requests.call_args.args[1])
        self.assertEqual(
            http.requests.call_args.kwargs["data"],
            {"action": "reject", "reason": "拒绝审批"},
        )

    def test_wallet_update_sends_only_changed_fields(self):
        http = Mock()
        http.requests.return_value = {"updated": True}
        service = WalletService(http, "https://example.test/api/v1")

        service.update_wallet_account("wallet/1", name="updated")

        self.assertIn("wallet%2F1", http.requests.call_args.args[1])
        self.assertEqual(http.requests.call_args.kwargs["data"], {"name": "updated"})

    def test_legacy_account_service_uses_bank_and_wallet_services(self):
        http = Mock()
        http.requests.side_effect = [
            [{"id": "bank-1", "isDefault": True}],
            [
                {
                    "walletAddress": "0xabc",
                    "chainName": "ETHEREUM",
                    "isDefault": True,
                }
            ],
        ]
        accounts = AccountService(http, "https://example.test/api/v1")
        self.assertEqual(accounts.get_bank_account_id(), "bank-1")
        self.assertEqual(accounts.get_wallet_address(), "0xabc")

    def test_limits_user_id_accepts_id_and_user_id_fields(self):
        first_http = Mock()
        first_http.requests.return_value = {"id": "legacy-id"}
        second_http = Mock()
        second_http.requests.return_value = {"userId": "new-id"}

        self.assertEqual(
            LimitsService(first_http, "https://example.test").get_current_user_id(),
            "legacy-id",
        )
        self.assertEqual(
            LimitsService(second_http, "https://example.test").get_current_user_id(),
            "new-id",
        )

    def test_limits_snake_case_and_legacy_assigned_by_methods_match(self):
        http = Mock()
        http.requests.return_value = {
            "assignedVault": {"assignedBy": "manager-1"}
        }
        service = LimitsService(http, "https://example.test")

        self.assertEqual(service.get_assigned_by(), "manager-1")
        self.assertEqual(service.get_assignedBy(), "manager-1")


if __name__ == "__main__":
    unittest.main()
