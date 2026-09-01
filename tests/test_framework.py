"""业务接口封装的离线单元测试；不会调用真实环境。"""

import unittest
from contextlib import contextmanager
from unittest.mock import Mock

from common.second_verification import SecondVerification
from requests_models.requests_tools import PortalApi, Requests
from requests_models.services.verification import VerificationService


def make_api(http=None, verification=None):
    config = Mock()
    config.get_url_data.return_value = "https://example.test/api/v1/"
    return PortalApi(
        admin_http=http or Mock(),
        config=config,
        second_verification=verification,
    )


class PortalApiTests(unittest.TestCase):
    def test_old_class_name_is_compatible(self):
        self.assertIs(Requests, PortalApi)

    def test_get_user_info_extracts_data(self):
        http = Mock()
        http.requests.return_value = {"email": "user@example.test"}
        result = make_api(http).get_user_info()
        self.assertEqual(result["email"], "user@example.test")
        self.assertEqual(http.requests.call_args.kwargs["nested_keys"], ["data"])

    def test_fee_config_filters_chain_in_python(self):
        http = Mock()
        http.requests.return_value = {
            "schedules": [
                {"chain": "ETH", "fee": 1},
                {"chain": "SOL", "fee": 2},
            ]
        }
        self.assertEqual(make_api(http).get_fee_config("eth"), [{"chain": "ETH", "fee": 1}])

    def test_assets_are_filtered_in_python_and_id_is_returned(self):
        http = Mock()
        http.requests.return_value = [
            {
                "assetId": "AXUSD_ETH",
                "settlementCurrency": "USD",
                "chainName": "ETHEREUM",
            },
            {
                "assetId": "AXUSD_SOL",
                "settlementCurrency": "USD",
                "chainName": "SOLANA",
            },
        ]
        api = make_api(http)
        self.assertEqual(api.get_assets_id("usd", "ethereum"), "AXUSD_ETH")
        self.assertNotIn("jsonpath_expr", http.requests.call_args.kwargs)

    def test_assets_id_returns_none_when_no_match(self):
        http = Mock()
        http.requests.return_value = []
        self.assertIsNone(make_api(http).get_assets_id("USD", "ETHEREUM"))

    def test_assets_id_rejects_ambiguous_matches(self):
        http = Mock()
        http.requests.return_value = [
            {"id": "one", "settlementCurrency": "USD", "chainName": "ETHEREUM"},
            {"id": "two", "settlementCurrency": "USD", "chainName": "ETHEREUM"},
        ]
        with self.assertRaises(ValueError):
            make_api(http).get_assets_id()

    def test_transaction_list_uses_get_and_encoded_query(self):
        http = Mock()
        make_api(http).list_transactions(operation_type="MINT", page=2, limit=10)
        args = http.requests.call_args.args
        self.assertEqual(args[0], "GET")
        self.assertIn("operationType=MINT", args[1])
        self.assertIn("page=2", args[1])

    def test_create_order_returns_id_and_validates_amount(self):
        http = Mock()
        http.requests.return_value = {"id": "order-1"}
        api = make_api(http)
        self.assertEqual(
            api.create_order(
                asset_id="asset-1",
                bank_account_id="bank-1",
                destination_address="wallet-1",
            ),
            "order-1",
        )
        with self.assertRaises(ValueError):
            api.create_order(amount="0")

    def test_order_id_is_url_encoded(self):
        http = Mock()
        make_api(http).get_order_detail("order/with space")
        self.assertIn("order%2Fwith%20space", http.requests.call_args.args[1])


class SecondVerificationTests(unittest.TestCase):
    def test_challenge_then_verify_and_return_data(self):
        http = Mock()
        http.requests.side_effect = ["challenge-token", "action-token"]
        result = SecondVerification().verify_action(
            http,
            "https://example.test/api/v1/",
            action_type="TRANSACTION_SUBMIT",
            code="111111",
        )
        self.assertEqual(result, "action-token")
        self.assertTrue(
            http.requests.call_args_list[0].args[1].endswith(
                "/user/2fa/challenge"
            )
        )
        self.assertTrue(
            http.requests.call_args_list[1].args[1].endswith(
                "/user/2fa/verify-action"
            )
        )
        self.assertEqual(
            http.requests.call_args_list[1].kwargs["data"]["challengeToken"],
            "challenge-token",
        )

    def test_missing_code_fails_before_network_request(self):
        http = Mock()
        with self.assertRaises(ValueError):
            SecondVerification().verify_action(http, "https://example.test", code=None)
        http.requests.assert_not_called()

    def test_missing_action_token_raises_clear_error(self):
        http = Mock()
        http.requests.side_effect = ["challenge-token", None]
        with self.assertRaisesRegex(RuntimeError, "未取得 actionToken"):
            SecondVerification().verify_action(
                http,
                "https://example.test",
                code="111111",
            )

    def test_execute_verifies_runs_operation_and_cleans_context(self):
        events = []
        http = Mock()

        @contextmanager
        def action_context(token):
            events.append(("enter", token))
            try:
                yield
            finally:
                events.append(("exit", token))

        http.use_action_token = action_context
        verifier = Mock()
        verifier.verify_action.return_value = "action-token"
        service = VerificationService(http, "https://example.test", verifier)

        def operation(value):
            events.append(("operation", value))
            return "completed"

        result = service.execute(
            operation,
            "order-1",
            code="111111",
            action_type="TRANSACTION_SUBMIT",
        )
        self.assertEqual(result, "completed")
        self.assertEqual(
            events,
            [
                ("enter", "action-token"),
                ("operation", "order-1"),
                ("exit", "action-token"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
