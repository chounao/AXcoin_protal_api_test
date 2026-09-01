"""Portal API 聚合入口及旧方法兼容层。

实际接口按用户信息、资产账户、交易流程、2FA 拆分在 ``services`` 目录。
新代码优先使用 ``api.assets.get_id()`` 等业务域调用；旧方法仍可继续使用。
"""
from common.read_and_save_tool import ConfigTools
from common.simple_request import HttpRequest
from requests_models.services import (
    AccountService,
    ApprovalService,
    AssetService,
    BankService,
    FeeService,
    LimitsService,
    ReceiptService,
    TransactionService,
    UserService,
    VerificationService,
    WalletService,
)


class PortalApi:
    """固定绑定一个角色，并组合该角色的全部业务域服务。"""

    def __init__(
        self,
        http_request=None,
        config=None,
        role="ROLE_Submitter",
        second_verification=None,
        admin_http=None,
    ):
        if http_request is not None and admin_http is not None:
            raise ValueError("http_request 和 admin_http 只能传入一个")

        self.config = config or ConfigTools()
        self.http = http_request or admin_http or HttpRequest(section=role)
        self.admin_http = self.http  # 兼容旧属性名。
        http_role = getattr(self.http, "section", None)
        self.role = (
            http_role.strip()
            if isinstance(http_role, str) and http_role.strip()
            else role
        )
        self.base_url = self.config.get_url_data().rstrip("/")
        self.url = self.base_url  # 兼容旧属性名。

        # 用户信息
        self.user = UserService(self.http, self.base_url)
        self.fees = FeeService(self.http, self.base_url)
        self.limits = LimitsService(self.http, self.base_url, role=self.role)

        # 兼容新增模块最初使用的属性名。
        self.limits_model = self.limits

        # 资产与账户查询。accounts 仅保留给旧代码兼容；新代码分别使用
        # banks 和 wallets，避免银行与钱包逻辑继续混在一个服务中。
        self.assets = AssetService(self.http, self.base_url)
        self.accounts = AccountService(self.http, self.base_url)
        self.banks = BankService(self.http, self.base_url, role=self.role)
        self.wallets = WalletService(self.http, self.base_url, role=self.role)

        # 兼容之前已经使用 api.bank_model / api.wallet_model 的代码。
        self.bank_model = self.banks
        self.wallet_model = self.wallets

        # 交易流程
        self.transactions = TransactionService(
            self.http,
            self.base_url,
            self.assets,
            self.accounts,
            banks=self.banks,
            wallets=self.wallets,
        )
        self.receipts = ReceiptService(
            self.http,
            self.base_url,
            self.transactions,
            role=self.role,
        )

        # 业务 2FA
        self.verification = VerificationService(
            self.http,
            self.base_url,
            second_verification,
        )
        self.second_verification = self.verification.verifier

        # 审批流程
        self.approval_model = ApprovalService(
            self.http, self.base_url, role=self.role
        )
    # -------------------- 用户信息兼容方法 --------------------

    def get_user_info(self):
        return self.user.get_info()

    def get_fee_config(self, chain="ETH"):
        return self.fees.get_config(chain)


    def get_quota(self, currency="USD", chain="ETH", request_type="mint"):
        return self.fees.get_quota(currency, chain, request_type)

    # -------------------- 企业用户额度兼容方法 --------------------

    def get_current_user_id(self):
        return self.limits.get_current_user_id()

    def get_limits_info(self):
        """兼容旧方法名；实际返回当前角色 userId。"""
        return self.get_current_user_id()

    def set_user_limits(
        self,
        user_id,
        limits=None,
        *,
        default_limit_amount=None,
    ):
        return self.limits.set_user_limits(
            user_id,
            limits,
            default_limit_amount=default_limit_amount,
        )
    def apply_for_burn_adn_mint_limit_increase(self):
        return self.limits.apply_for_burn_adn_mint_limit_increase()
    # -------------------- 资产账户兼容方法 --------------------

    def get_assets(self, currency="USD", chain="ETHEREUM"):
        return self.assets.list(currency, chain)

    def get_asset_id(self, currency="USD", chain="ETHEREUM"):
        return self.assets.get_id(currency, chain)

    def get_assets_id(self, currency="USD", chain="ETHEREUM"):
        """兼容旧方法名，新代码请使用 get_asset_id。"""
        return self.get_asset_id(currency, chain)

    def get_bank_accounts(self, chain=None):
        return self.banks.list(chain)

    def get_bank_data(self):
        return self.banks.list()

    def get_default_bank_account(self, chain=None):
        return self.banks.get_default(chain)

    def get_bank_account_id(self, chain=None):
        return self.banks.get_id(chain)

    def get_bank_account_number(self, chain=None):
        """兼容旧名称；后端当前实际使用银行账户 ID。"""
        return self.get_bank_account_id(chain)

    def get_bank_accountNumber(self, chainName=None):
        """兼容旧驼峰方法名；后端当前实际使用银行账户 ID。"""
        return self.get_bank_account_id(chainName)


    def get_wallets(self, chain=None):
        return self.wallets.list(chain)

    def get_default_wallet(self, chain="ETHEREUM"):
        return self.wallets.get_default(chain)

    def get_wallet_address(self, chain="ETHEREUM"):
        return self.wallets.get_address(chain)

    def get_wallet_account(self, chainName="ETHEREUM"):
        return self.wallets.get_default(chainName)

    def get_wallet_accountNumber(self, chainName="ETHEREUM"):
        """兼容旧方法名；实际返回钱包地址。"""
        return self.get_wallet_address(chainName)


    # -------------------- 交易流程兼容方法 --------------------

    def get_transactions(
        self,
        operation_type="MINT",
        sort_by="createdAt",
        sort_order="desc",
        page=1,
        limit=20,
    ):
        return self.transactions.list(
            operation_type,
            sort_by,
            sort_order,
            page,
            limit,
        )

    list_transactions = get_transactions

    def get_transaction(
        self,
        operationType="MINT",
        sortBy="createdAt",
        sortOrder="desc",
        page=1,
        limit=20,
    ):
        return self.transactions.list(
            operationType,
            sortBy,
            sortOrder,
            page,
            limit,
        )

    def create_mint_order(
        self,
        operationType="MINT",
        sortBy="createdAt",
        sortOrder="desc",
    ):
        """兼容历史误命名；该方法实际查询交易列表。"""
        return self.transactions.list(operationType, sortBy, sortOrder)

    def build_order_payload(
        self,
        operation_type="MINT",
        amount="100.00",
        currency="USD",
        chain="ETHEREUM",
        **overrides,
    ):
        return self.transactions.build_payload(
            operation_type,
            amount,
            currency,
            chain,
            **overrides,
        )

    def create_order(
        self,
        operation_type="MINT",
        amount="100.00",
        currency="USD",
        chain="ETHEREUM",
        **overrides,
    ):
        return self.transactions.create(
            operation_type,
            amount,
            currency,
            chain,
            **overrides,
        )

    def create_order_id(
        self,
        operation_type="MINT",
        amount="100.00",
        currency="USD",
        chain="ETHEREUM",
        **overrides,
    ):
        """创建订单并只返回订单 ID。"""
        return self.transactions.create_id(
            operation_type,
            amount,
            currency,
            chain,
            **overrides,
        )

    def get_order_status(self, order_id):
        return self.transactions.get_status(order_id)

    def get_order_detail(self, order_id):
        return self.transactions.get_detail(order_id)

    def submit_receipt(self, order_id, receipt_url):
        return self.receipts.submit(order_id, receipt_url)

    def upload_image(
        self,
        orderId,
        receiptUrl="receipts/1120f397-de5c-41e0-9237-4e8783b6de8d.JPG",
    ):
        return self.receipts.submit(orderId, receiptUrl)

    def submit_receipt_as(self, actor, order_id, receipt_url):
        """由另一个 PortalApi 角色提交凭证，不修改当前角色 headers。"""
        if not isinstance(actor, PortalApi):
            raise TypeError("actor 必须是 PortalApi 实例")
        return actor.receipts.submit(order_id, receipt_url)

    # -------------------- 业务 2FA 兼容方法 --------------------

    def verify_order_action(self, code=None, action_type="TRANSACTION_SUBMIT"):
        return self.verification.verify(code, action_type)

    def create_order_2fa_code(self, code=None):
        return self.verification.verify(code)

    def upload_2fa_code(self, code=None, action_type="TRANSACTION_SUBMIT"):
        return self.verification.verify(code, action_type)










    # -------------------- 审批操作 --------------------
    def approval_model_transaction(self, order_id, action, reason=None):
        return self.approval_model.internal_approve(order_id, action, reason=reason)

    def approval_model_bank_address_approve(self, order_id):
        return self.approval_model.bank_address_approve(order_id)

    def approval_model_wallet_approve(self, order_id):
        return self.approval_model.wallet_approve(order_id)

    def approval_limit_increase(self, order_id):
        return self.approval_model.limit_approve(order_id)

    # -------------------- 银行操作 --------------------

    def create_bank_account(self, bank_account_info=None, **overrides):
        return self.banks.create_bank_account(bank_account_info, **overrides)

    def get_bank_account(self, bank_account_id):
        return self.banks.get_bank_account(bank_account_id)

    def update_bank_account(
        self, bank_account_id, bank_account_info=None, **overrides
    ):
        return self.banks.update_bank_account(
            bank_account_id, bank_account_info, **overrides
        )

    def delete_bank_account(self, bank_account_id):
        return self.banks.delete_bank_account(bank_account_id)













    # -------------------- 钱包操作 --------------------

    def create_wallet(self, wallet_info=None, **overrides):
        return self.wallets.create_wallet(wallet_info, **overrides)

    def get_wallet(self, wallet_id):
        return self.wallets.get_wallet(wallet_id)

    def update_wallet(self, wallet_id, wallet_info=None, **overrides):
        return self.wallets.update_wallet_account(
            wallet_id, wallet_info, **overrides
        )

    def delete_wallet(self, wallet_id):
        return self.wallets.delete_wallet_account(wallet_id)

# 保留旧导入方式：from requests_models.requests_tools import Requests
Requests = PortalApi


if __name__ == "__main__":
    print("请通过 PortalApi 或 Workflow 调用；直接运行不会访问真实接口。")
