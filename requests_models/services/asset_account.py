"""交易资产，以及旧账户查询兼容入口。"""

from common.logger import logger
from requests_models.base import ApiService
from requests_models.services.bank_model import BankService
from requests_models.services.wallet_model import WalletService


class AssetService(ApiService):
    """交易资产的查询和唯一资产选择。"""

    def list(self, currency="USD", chain="ETHEREUM"):
        expected_currency = self.required(currency, "currency").upper()
        expected_chain = self.required(chain, "chain").upper()
        assets = self.request_data("GET", "/transaction/assets") or []
        if not isinstance(assets, list):
            logger.warning("资产接口 data 不是列表: %s", type(assets).__name__)
            return []
        return [
            item
            for item in assets
            if isinstance(item, dict)
            and str(item.get("settlementCurrency", "")).upper()
            == expected_currency
            and str(item.get("chainName", "")).upper() == expected_chain
        ]

    def get(self, currency="USD", chain="ETHEREUM"):
        return self.select_one(
            self.list(currency, chain),
            f"{currency}/{chain} 资产",
        )

    def get_id(self, currency="USD", chain="ETHEREUM"):
        asset = self.get(currency, chain)
        if asset is None:
            return None
        asset_id = asset.get("assetId") or asset.get("id")
        if not asset_id:
            raise ValueError("匹配的资产中没有 assetId 或 id")
        return asset_id


class AccountService(ApiService):
    """旧版账户查询兼容层。

    新代码应直接使用 ``BankService`` 和 ``WalletService``。这里通过组合
    委托，确保旧入口与新模块始终使用同一套筛选规则。
    """

    def __init__(self, http, base_url):
        super().__init__(http, base_url)
        self.banks = BankService(http, base_url)
        self.wallets = WalletService(http, base_url)

    def list_bank_accounts(self, chain=None):
        return self.banks.list(chain)

    def get_default_bank_account(self, chain=None):
        return self.banks.get_default(chain)

    def get_bank_account_id(self, chain=None):
        return self.banks.get_id(chain)

    def list_wallets(self, chain=None):
        return self.wallets.list(chain)

    def get_default_wallet(self, chain="ETHEREUM"):
        return self.wallets.get_default(chain)

    def get_wallet_address(self, chain="ETHEREUM"):
        return self.wallets.get_address(chain)


if __name__ == "__main__":
    print("请通过 PortalApi 调用资产、银行和钱包服务；直接运行不会访问真实接口。")

