"""银行账户查询与维护接口。"""

from copy import deepcopy

from common.logger import logger
from requests_models.base import ApiService


class BankService(ApiService):
    """银行账户 API，绑定一个角色独立的 HTTP 客户端。"""

    DEFAULT_PAYLOAD = {
        "name": "Xiajun",
        "bankName": "超杰",
        "iban": "BH67BMAG00001299123456",
        "accountNumber": "00012345678901",
        "routingNumber": "00012345",
        "swiftCode": "AUBBBHBM",
        "currency": ["BHD", "USD"],
        "isDefault": False,
        "bankAddress": {
            "street": "Al Seef District, Building 42",
            "city": "Manama",
            "state": "",
            "postalCode": "1001",
            "country": "BH",
        },
    }

    def __init__(self, http, base_url, role=None):
        super().__init__(http, base_url)
        self.role = role

    def build_payload(self, bank_account_info=None, **overrides):
        """构建银行账户请求数据。

        未提供 ``bank_account_info`` 时使用测试默认数据；传入字典时以该
        字典为基础，并允许通过关键字参数覆盖字段。
        """
        if bank_account_info is not None and not isinstance(bank_account_info, dict):
            raise TypeError("bank_account_info 必须是字典或 None")
        payload = deepcopy(
            self.DEFAULT_PAYLOAD if bank_account_info is None else bank_account_info
        )
        if "is_default" in overrides:
            overrides["isDefault"] = overrides.pop("is_default")
        payload.update(overrides)
        return payload

    def mock_bank_account(self, is_default=False):
        """兼容旧方法：返回一份相互独立的测试银行账户数据。"""
        return self.build_payload(is_default=is_default)

    def list(self, chain=None):
        """查询银行账户列表，可按 chainName 过滤。"""
        data = self.request_data("GET", "/user-account/bank-accounts") or []
        accounts = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )
        if chain is None or not any("chainName" in item for item in accounts):
            return accounts
        expected = self.required(chain, "chain").upper()
        return [
            item
            for item in accounts
            if str(item.get("chainName", "")).upper() == expected
        ]

    def get_default(self, chain=None):
        """返回状态为 VERIFIED 的默认银行账户。"""
        accounts = self.list(chain)
        verified = [
            item
            for item in accounts
            if self.is_status(item.get("status"))
        ]
        # 兼容部分旧响应不返回 status；只要响应明确带有状态，就坚持只选
        # VERIFIED，绝不回退到 PENDING/REJECTED。
        has_explicit_status = any(item.get("status") for item in accounts)
        eligible = verified if has_explicit_status else accounts
        defaults = [
            item for item in eligible if self.is_default(item.get("isDefault"))
        ]
        description = f"{chain + ' ' if chain else ''}已验证默认银行账户"
        return self.select_one(defaults or eligible, description)

    def get_id(self, chain=None):
        """返回已验证默认银行账户 ID。"""
        account = self.get_default(chain)
        if account is None:
            return None
        return self.required(account.get("id"), "银行账户 id")

    # 与旧 AccountService 方法名保持兼容。
    list_bank_accounts = list
    get_default_bank_account = get_default
    get_bank_account_id = get_id

    def create_bank_account(self, bank_account_info=None, **overrides):
        """创建银行账户。"""
        payload = self.build_payload(bank_account_info, **overrides)
        logger.info("创建银行账户，角色：%s", self.role)
        return self.request_data(
            "POST",
            "/user-account/bank-accounts",
            payload=payload,
            jsonpath_expr="$.data.id",
        )

    def get_bank_account(self, account_id):
        """按 ID 获取银行账户详情。"""
        safe_id = self.encoded_id(account_id, "account_id")
        return self.request_data("GET", f"/user-account/bank-accounts/{safe_id}")

    def update_bank_account(self, account_id, bank_account_info=None, **overrides):
        """按 ID 更新银行账户。"""
        safe_id = self.encoded_id(account_id, "account_id")
        payload = self.build_payload(bank_account_info, **overrides)
        logger.info("更新银行账户：%s", account_id)
        return self.request_data(
            "PATCH",
            f"/user-account/bank-accounts/{safe_id}",
            payload=payload,
        )

    def delete_bank_account(self, account_id):
        """按 ID 删除银行账户。"""
        safe_id = self.encoded_id(account_id, "account_id")
        logger.info("删除银行账户：%s", account_id)
        return self.request_data("DELETE", f"/user-account/bank-accounts/{safe_id}")
