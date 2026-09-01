"""多角色认证、客户端注册表及 Workflow 的离线测试。"""

import base64
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from common.login import Login
from common.role_clients import RoleClients
from common.simple_request import HttpRequest
from common.token_cache import TokenCache
from workflows.order_workflow import MintOrderWorkflow, MintWorkflowRoles


def fake_jwt(expires_at):
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": expires_at}).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"header.{payload}.signature"


def response(body=None, status=200):
    result = Mock(spec=requests.Response)
    result.status_code = status
    result.text = json.dumps(body or {})
    result.json.return_value = body or {}
    if status >= 400:
        result.raise_for_status.side_effect = requests.HTTPError(str(status))
    else:
        result.raise_for_status.return_value = None
    return result


class TokenCacheTests(unittest.TestCase):
    def test_legacy_bearer_token_is_imported_per_role(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = TokenCache(Path(directory) / "tokens.json")
            token = fake_jwt(int(time.time()) + 600)
            self.assertEqual(
                cache.import_legacy("ROLE_Submitter", "user@test", f"Bearer {token}"),
                token,
            )
            self.assertEqual(cache.get("ROLE_Submitter", "user@test"), token)

    def test_token_pair_is_saved_and_refresh_survives_expired_access(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = TokenCache(Path(directory) / "tokens.json")
            access = fake_jwt(int(time.time()) - 1)
            refresh = fake_jwt(int(time.time()) + 3600)
            cache.put_pair("ROLE_operator", "operator@test", access, refresh)
            self.assertIsNone(cache.get("ROLE_operator", "operator@test"))
            self.assertEqual(
                cache.get_refresh_token("ROLE_operator", "operator@test"), refresh
            )


class LoginRefreshTests(unittest.TestCase):
    def make_config(self, cache_path):
        config = Mock()
        config.get_url_data.return_value = "https://example.test/api/v1"
        config.get_timeout.return_value = 30
        config.get_token_cache_path.return_value = cache_path
        config.get_refresh_before_seconds.return_value = 60
        config.get_origin.return_value = "https://frontend.example.test"
        config.get_email.return_value = "operator@test"
        config.get_access_token.return_value = None
        return config

    def test_login_2fa_caches_access_and_refresh_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            access = fake_jwt(int(time.time()) + 600)
            refresh = fake_jwt(int(time.time()) + 3600)
            session = Mock()
            session.post.side_effect = [
                response({"data": {"tempToken": "temporary"}}),
                response({"data": {"accessToken": access, "refreshToken": refresh}}),
            ]
            config = self.make_config(Path(directory) / "tokens.json")
            config.get_login_data.return_value = ("operator@test", "secret")
            config.get_two_factor_code.return_value = "111111"
            login = Login(config=config, session=session)

            self.assertEqual(login.authenticate("ROLE_operator"), access)
            self.assertEqual(
                login.cache.get_refresh_token("ROLE_operator", "operator@test"),
                refresh,
            )

    def test_refresh_rotates_both_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            old_access = fake_jwt(int(time.time()) + 600)
            old_refresh = fake_jwt(int(time.time()) + 3600)
            new_access = fake_jwt(int(time.time()) + 700)
            new_refresh = fake_jwt(int(time.time()) + 7200)
            session = Mock()
            session.post.return_value = response(
                {"data": {"accessToken": new_access, "refreshToken": new_refresh}}
            )
            config = self.make_config(Path(directory) / "tokens.json")
            login = Login(config=config, session=session)
            login.cache.put_pair(
                "ROLE_operator", "operator@test", old_access, old_refresh
            )

            self.assertEqual(login.refresh("ROLE_operator"), new_access)
            self.assertEqual(
                session.post.call_args.kwargs["json"],
                {"refreshToken": old_refresh},
            )
            self.assertTrue(
                session.post.call_args.args[0].endswith("/user/refresh-token")
            )
            self.assertEqual(
                login.cache.get_refresh_token("ROLE_operator", "operator@test"),
                new_refresh,
            )

    def test_refresh_failure_falls_back_to_full_login(self):
        login = Mock()
        login.refresh.side_effect = requests.HTTPError("refresh expired")
        login.authenticate.return_value = "new-access"
        # 调用真实方法，同时让依赖保持为 Mock。
        result = Login.recover_authorization(login, "ROLE_operator")
        login.invalidate.assert_called_once_with("ROLE_operator")
        login.authenticate.assert_called_once_with("ROLE_operator", force=True)
        self.assertEqual(result, "Bearer new-access")


class HttpRequestTests(unittest.TestCase):
    def make_config(self):
        config = Mock()
        config.get_value.return_value = "30"
        return config

    def test_two_roles_build_independent_authorization_headers(self):
        auth = Mock()
        auth.get_authorization.side_effect = lambda role, force=False: f"Bearer {role}"
        first_session = Mock()
        second_session = Mock()
        first_session.request.return_value = response({"ok": True})
        second_session.request.return_value = response({"ok": True})

        HttpRequest(
            "ROLE_Submitter",
            session=first_session,
            config=self.make_config(),
            auth_manager=auth,
        ).get("https://example.test/submit")
        HttpRequest(
            "ROLE_operator",
            session=second_session,
            config=self.make_config(),
            auth_manager=auth,
        ).post("https://example.test/receipt", {"receiptUrl": "x"})

        self.assertEqual(
            first_session.request.call_args.kwargs["headers"]["Authorization"],
            "Bearer ROLE_Submitter",
        )
        self.assertEqual(
            second_session.request.call_args.kwargs["headers"]["Authorization"],
            "Bearer ROLE_operator",
        )

    def test_401_invalidates_only_current_role_and_retries(self):
        auth = Mock()
        auth.get_authorization.return_value = "Bearer old-ROLE_operator"
        auth.recover_authorization.return_value = "Bearer refreshed-ROLE_operator"
        session = Mock()
        session.request.side_effect = [response({}, 401), response({"ok": True})]
        client = HttpRequest(
            "ROLE_operator",
            session=session,
            config=self.make_config(),
            auth_manager=auth,
        )
        self.assertEqual(client.get("https://example.test/path").status_code, 200)
        auth.recover_authorization.assert_called_once_with("ROLE_operator")
        self.assertEqual(
            session.request.call_args_list[-1].kwargs["headers"]["Authorization"],
            "Bearer refreshed-ROLE_operator",
        )

    def test_action_token_skips_get_and_is_consumed_by_one_write_request(self):
        """状态 GET 不消费 Token；紧接着的 POST 使用，后续 POST 不再携带。"""
        auth = Mock()
        auth.get_authorization.return_value = "Bearer access-token"
        session = Mock()
        session.request.side_effect = [
            response({"data": {"newStatus": "CREATED"}}),
            response({"data": {"saved": True}}),
            response({"data": {"saved": True}}),
        ]
        client = HttpRequest(
            "ROLE_Submitter",
            session=session,
            config=self.make_config(),
            auth_manager=auth,
        )

        with client.use_action_token("action-token"):
            client.get("https://example.test/status")
            client.post("https://example.test/upload", {"receiptUrl": "a.jpg"})
            client.post("https://example.test/second", {"receiptUrl": "b.jpg"})

        first, second, third = session.request.call_args_list
        self.assertNotIn("x-action-token", first.kwargs["headers"])
        self.assertEqual(
            second.kwargs["headers"]["x-action-token"],
            "action-token",
        )
        self.assertNotIn("x-action-token", third.kwargs["headers"])
        self.assertNotIn("x-action-token", client.get_current_headers())

    def test_action_token_is_isolated_between_clients(self):
        """一个账号的临时 Token 不会进入另一个账号的请求头。"""
        auth = Mock()
        auth.get_authorization.side_effect = lambda role, force=False: f"Bearer {role}"
        first_session = Mock()
        second_session = Mock()
        first_session.request.return_value = response({"ok": True})
        second_session.request.return_value = response({"ok": True})
        first = HttpRequest(
            "ROLE_Submitter",
            session=first_session,
            config=self.make_config(),
            auth_manager=auth,
        )
        second = HttpRequest(
            "ROLE_operator",
            session=second_session,
            config=self.make_config(),
            auth_manager=auth,
        )

        with first.use_action_token("submitter-action-token"):
            second.post("https://example.test/operator", {})
            first.post("https://example.test/submitter", {})

        self.assertNotIn(
            "x-action-token",
            second_session.request.call_args.kwargs["headers"],
        )
        self.assertEqual(
            first_session.request.call_args.kwargs["headers"]["x-action-token"],
            "submitter-action-token",
        )


class RoleClientTests(unittest.TestCase):
    def test_same_role_reuses_client_but_other_role_is_separate(self):
        config = Mock()
        config.get_section_data.return_value = {"email": "x@test"}
        config.get_url_data.return_value = "https://example.test/api/v1"
        config.get_value.return_value = "30"
        auth = Mock()
        clients = RoleClients(config=config, login_manager=auth)
        self.assertIs(clients.get("ROLE_Submitter"), clients.get("ROLE_Submitter"))
        self.assertIsNot(clients.get("ROLE_Submitter"), clients.get("ROLE_operator"))

    def test_prepare_forwards_force_login(self):
        config = Mock()
        auth = Mock()
        auth.login_all.return_value = {"ROLE_Submitter": "token"}
        clients = RoleClients(config=config, login_manager=auth)
        result = clients.prepare(["ROLE_Submitter"], force=True)
        auth.login_all.assert_called_once_with(["ROLE_Submitter"], force=True)
        self.assertEqual(result["ROLE_Submitter"], "token")


class WorkflowTests(unittest.TestCase):
    @staticmethod
    def execute_operation(operation, *args, **kwargs):
        """模拟 VerificationService.execute，只把业务参数传给目标方法。"""
        kwargs.pop("code", None)
        kwargs.pop("action_type", None)
        return operation(*args, **kwargs)

    def test_run_uses_two_2fa_operations_in_required_order(self):
        events = []
        creator = Mock()
        operator = Mock()
        creator.transactions.build_payload.side_effect = lambda **kwargs: (
            events.append("prepare") or {"amount": kwargs["amount"]}
        )
        creator.transactions.create_prepared.side_effect = lambda payload: (
            events.append("create") or "order-1"
        )
        creator.transactions.get_status.side_effect = lambda order_id: (
            events.append("status") or "CREATED"
        )
        operator.receipts.submit_prechecked.side_effect = (
            lambda order_id, receipt_url: events.append("receipt")
            or {"saved": True}
        )
        creator.verification.execute.side_effect = self.execute_operation
        operator.verification.execute.side_effect = self.execute_operation

        clients = Mock()
        actors = {
            "ROLE_Submitter": creator,
            "ROLE_operator": operator,
        }
        clients.__getitem__ = Mock(side_effect=actors.__getitem__)
        workflow = MintOrderWorkflow(
            clients=clients,
            roles=MintWorkflowRoles(
                creator="ROLE_Submitter",
                receipt_submitter="ROLE_operator",
            ),
        )

        result = workflow.run(
            receipt_url="receipts/test.jpg",
            amount="100.00",
            create_2fa_code="111111",
            receipt_2fa_code="222222",
        )
        self.assertEqual(
            events,
            ["prepare", "create", "status", "receipt"],
        )
        creator.verification.execute.assert_called_once_with(
            creator.transactions.create_prepared,
            {"amount": "100.00"},
            code="111111",
            action_type="TRANSACTION_SUBMIT",
        )
        operator.verification.execute.assert_called_once_with(
            operator.receipts.submit_prechecked,
            "order-1",
            "receipts/test.jpg",
            code="222222",
            action_type="TRANSACTION_SUBMIT",
        )
        self.assertEqual(result["order_id"], "order-1")
        self.assertEqual(result["status"], "CREATED")

    def test_status_is_returned_without_extra_local_blocking(self):
        creator = Mock()
        operator = Mock()
        creator.transactions.build_payload.return_value = {"amount": "100.00"}
        creator.transactions.create_prepared.return_value = "order-1"
        creator.verification.execute.side_effect = self.execute_operation
        creator.transactions.get_status.return_value = "PENDING"
        operator.receipts.submit_prechecked.return_value = {"saved": True}
        operator.verification.execute.side_effect = self.execute_operation
        clients = Mock()
        clients.__getitem__ = Mock(
            side_effect={
                "ROLE_Submitter": creator,
                "ROLE_operator": operator,
            }.__getitem__
        )
        workflow = MintOrderWorkflow(clients=clients)

        result = workflow.run(
            receipt_url="receipts/test.jpg",
            amount="100.00",
            create_2fa_code="111111",
            receipt_2fa_code="222222",
        )
        self.assertEqual(result["status"], "PENDING")
        operator.verification.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
