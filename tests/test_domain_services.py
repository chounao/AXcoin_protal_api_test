"""业务域服务入口的离线测试。"""

import unittest
from unittest.mock import Mock

from requests_models.requests_tools import PortalApi
from requests_models.services import (
    AccountService,
    AssetService,
    ReceiptService,
    TransactionService,
)
from requests_models.services.asset_account import AssetService as AssetModuleService
from requests_models.services.transaction import TransactionService as TransactionModuleService
from requests_models.services.user import UserService
from requests_models.services.verification import VerificationService


def api_with(http, role="ROLE_Submitter"):
    config = Mock()
    config.get_url_data.return_value = "https://example.test/api/v1"
    return PortalApi(http_request=http, config=config, role=role)


class DomainServiceTests(unittest.TestCase):
    def test_api_exposes_separate_domain_services(self):
        api = api_with(Mock())
        self.assertIsInstance(api.assets, AssetService)
        self.assertIsInstance(api.accounts, AccountService)
        self.assertIsInstance(api.transactions, TransactionService)
        self.assertIsInstance(api.receipts, ReceiptService)
        self.assertIsInstance(api.user, UserService)
        self.assertIsInstance(api.verification, VerificationService)
        self.assertIsInstance(api.assets, AssetModuleService)
        self.assertIsInstance(api.transactions, TransactionModuleService)

    def test_new_asset_api_and_old_method_are_equivalent(self):
        body = [
            {"assetId": "eth", "settlementCurrency": "USD", "chainName": "ETHEREUM"}
        ]
        first = Mock()
        first.requests.return_value = body
        second = Mock()
        second.requests.return_value = body
        self.assertEqual(api_with(first).assets.get_id(), "eth")
        self.assertEqual(api_with(second).get_assets_id(), "eth")

    def test_receipt_domain_submits_with_encoded_order_id(self):
        http = Mock()
        http.requests.return_value = {"saved": True}
        result = api_with(http).receipts.submit("order/1", "receipts/a.jpg")
        self.assertEqual(result, {"saved": True})
        self.assertEqual(http.requests.call_count, 1)
        self.assertIn("order%2F1", http.requests.call_args.args[1])

    def test_receipt_does_not_add_local_status_check(self):
        http = Mock()
        http.requests.return_value = {"saved": True}
        result = api_with(http).receipts.submit("order-1", "receipts/a.jpg")
        self.assertEqual(result, {"saved": True})
        self.assertEqual(http.requests.call_count, 1)
        self.assertIn("/perfectProof", http.requests.call_args.args[1])

    def test_status_uses_latest_history_record(self):
        http = Mock()
        http.requests.return_value = [
            {"newStatus": "PENDING", "createdAt": "2026-08-13T01:00:00Z"},
            {"newStatus": "CREATED", "createdAt": "2026-08-13T02:00:00Z"},
        ]
        self.assertEqual(
            api_with(http).transactions.get_status("order-1"),
            "CREATED",
        )

    def test_create_and_create_id_return_order_id(self):
        payload = {
            "asset_id": "asset-1",
            "bank_account_id": "bank-1",
            "destination_address": "wallet-1",
        }
        first = Mock()
        first.requests.return_value = {"id": "order-1", "status": "PENDING"}
        order_id = api_with(first).transactions.create(**payload)
        self.assertEqual(order_id, "order-1")

        second = Mock()
        second.requests.return_value = {"transactionId": "order-2"}
        self.assertEqual(
            api_with(second).transactions.create_id(**payload),
            "order-2",
        )

    def test_create_rejects_missing_order_id(self):
        http = Mock()
        http.requests.return_value = {"status": "PENDING"}
        with self.assertRaisesRegex(RuntimeError, "没有订单 ID"):
            api_with(http).transactions.create(
                asset_id="asset-1",
                bank_account_id="bank-1",
                destination_address="wallet-1",
            )

    def test_create_accepts_string_id_in_data(self):
        http = Mock()
        # request_data 已经提取响应中的 data，因此 Mock 直接返回 data 内容。
        http.requests.return_value = "order-string-id"
        result = api_with(http).transactions.create(
            asset_id="asset-1",
            bank_account_id="bank-1",
            destination_address="wallet-1",
        )
        self.assertEqual(result, "order-string-id")

    def test_direct_run_has_no_network_side_effect(self):
        # 模块入口只展示提示，业务实例不会在 import 时自动创建。
        http = Mock()
        api_with(http)
        http.requests.assert_not_called()


if __name__ == "__main__":
    unittest.main()
