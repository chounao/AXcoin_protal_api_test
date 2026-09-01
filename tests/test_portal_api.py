"""PortalApi 的离线测试。"""

import unittest
from unittest.mock import Mock

from requests_models.requests_tools import PortalApi, Requests


def make_api(http=None, role="ROLE_Submitter"):
    config = Mock()
    config.get_url_data.return_value = "https://example.test/api/v1/"
    return PortalApi(http_request=http or Mock(), config=config, role=role)


class PortalApiTests(unittest.TestCase):
    def test_old_class_name_is_compatible(self):
        self.assertIs(Requests, PortalApi)

    def test_asset_bank_wallet_and_payload(self):
        http = Mock()
        http.requests.side_effect = [
            [{"assetId": "asset-1", "settlementCurrency": "USD", "chainName": "ETHEREUM"}],
            [{"id": "bank-1", "isDefault": True}],
            [{"walletAddress": "wallet-1", "chainName": "ETHEREUM", "isDefault": "true"}],
        ]
        payload = make_api(http).build_order_payload(amount="100.00")
        self.assertEqual(payload["assetId"], "asset-1")
        self.assertEqual(payload["bankAccountId"], "bank-1")
        self.assertEqual(payload["destinationAddress"], "wallet-1")

    def test_create_order_submits_and_returns_id(self):
        http = Mock()
        http.requests.return_value = {"id": "order-1"}
        result = make_api(http).create_order(
            asset_id="asset-1",
            bank_account_id="bank-1",
            destination_address="wallet-1",
        )
        self.assertEqual(result, "order-1")
        self.assertEqual(http.requests.call_args.args[0], "POST")

    def test_submit_receipt_as_does_not_switch_current_client(self):
        current_http = Mock()
        actor_http = Mock()
        actor_http.requests.return_value = {"saved": True}
        current = make_api(current_http)
        actor = make_api(actor_http, role="ROLE_operator")
        self.assertEqual(
            current.submit_receipt_as(actor, "order-1", "receipts/a.jpg"),
            {"saved": True},
        )
        current_http.requests.assert_not_called()
        self.assertEqual(actor_http.requests.call_count, 1)


if __name__ == "__main__":
    unittest.main()
