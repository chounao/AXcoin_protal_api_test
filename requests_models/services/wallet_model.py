"""钱包地址查询与维护接口。"""

import random

from common.logger import logger
from requests_models.base import ApiService


class WalletService(ApiService):
    """钱包 API，绑定一个角色独立的 HTTP 客户端。"""

    MOCK_ADDRESSES = {
        "ETHEREUM": "0x8f3Cf7ad23Cd3CaDbD9735AFf95823239c6A063",
        "SOLANA": "DRpbCBMxVnDK7maPM5tGv6MvQiR3oXBCL3mQqP8VHuTP",
    }

    def __init__(self, http, base_url, role=None):
        super().__init__(http, base_url)
        self.role = role

    def mock_wallet_deposit(self, chain_name="ETHEREUM", is_default=True):
        """构建测试钱包数据；不发送请求。"""
        normalized_chain = self.required(chain_name, "chain_name").upper()
        if normalized_chain not in self.MOCK_ADDRESSES:
            supported = ", ".join(self.MOCK_ADDRESSES)
            raise ValueError(f"不支持的 chain_name，可选值: {supported}")
        return {
            "name": f"TEST{random.randint(1, 100)}",
            "chainName": normalized_chain,
            "isDefault": bool(is_default),
            "walletAddress": self.MOCK_ADDRESSES[normalized_chain],
        }

    def build_payload(self, wallet_info=None, **overrides):
        """构建钱包请求数据，兼容完整字典和关键字参数。"""
        if wallet_info is not None and not isinstance(wallet_info, dict):
            raise TypeError("wallet_info 必须是字典或 None")
        if wallet_info is None:
            chain_name = overrides.pop("chain_name", "ETHEREUM")
            is_default = overrides.pop("is_default", True)
            payload = self.mock_wallet_deposit(chain_name, is_default)
        else:
            payload = dict(wallet_info)
            if "chain_name" in overrides:
                overrides["chainName"] = overrides.pop("chain_name")
            if "is_default" in overrides:
                overrides["isDefault"] = overrides.pop("is_default")
        payload.update(overrides)
        return payload

    def list(self, chain=None):
        """查询钱包列表，可按链过滤。"""
        data = self.request_data("GET", "/user-account/wallet-addresses") or []
        wallets = (
            [item for item in data if isinstance(item, dict)]
            if isinstance(data, list)
            else []
        )
        if chain is None:
            return wallets
        expected = self.required(chain, "chain").upper()
        return [
            item
            for item in wallets
            if str(item.get("chainName", "")).upper() == expected
        ]

    def get_default(self, chain="ETHEREUM"):
        """返回指定链的默认钱包。"""
        matches = [
            item for item in self.list(chain) if self.is_default(item.get("isDefault"))
        ]
        return self.select_one(matches, f"{chain} 默认钱包")

    def get_address(self, chain="ETHEREUM"):
        """返回指定链的默认钱包地址。"""
        wallet = self.get_default(chain)
        if wallet is None:
            return None
        return self.required(wallet.get("walletAddress"), "walletAddress")

    # 与旧 AccountService 方法名保持兼容。
    list_wallets = list
    get_default_wallet = get_default
    get_wallet_address = get_address

    def create_wallet(self, wallet_info=None, **overrides):
        """创建钱包。"""
        payload = self.build_payload(wallet_info, **overrides)
        logger.info("创建钱包，角色：%s", self.role)
        return self.request_data(
            "POST",
            "/user-account/wallet-addresses",
            payload=payload,
            jsonpath_expr="$.data.id",
        )

    def get_wallet(self, wallet_id):
        """按 ID 获取钱包详情。"""
        safe_id = self.encoded_id(wallet_id, "wallet_id")
        return self.request_data("GET", f"/user-account/wallet-addresses/{safe_id}")

    def update_wallet_account(self, wallet_id, wallet_info=None, **overrides):
        """按 ID 更新钱包；字符串参数兼容旧的 name 调用。"""
        safe_id = self.encoded_id(wallet_id, "wallet_id")
        if isinstance(wallet_info, str):
            payload = {"name": self.required(wallet_info, "name")}
            payload.update(overrides)
        else:
            if wallet_info is not None and not isinstance(wallet_info, dict):
                raise TypeError("wallet_info 必须是字典、字符串或 None")
            payload = dict(wallet_info or {})
            if "chain_name" in overrides:
                overrides["chainName"] = overrides.pop("chain_name")
            if "is_default" in overrides:
                overrides["isDefault"] = overrides.pop("is_default")
            payload.update(overrides)
        if not payload:
            raise ValueError("更新钱包至少需要一个字段")
        logger.info("更新钱包：%s", wallet_id)
        return self.request_data(
            "PATCH",
            f"/user-account/wallet-addresses/{safe_id}",
            payload=payload,
        )

    def delete_wallet_account(self, wallet_id):
        """按 ID 删除钱包。"""
        safe_id = self.encoded_id(wallet_id, "wallet_id")
        logger.info("删除钱包：%s", wallet_id)
        return self.request_data("DELETE", f"/user-account/wallet-addresses/{safe_id}")

    delete_wallet = delete_wallet_account
