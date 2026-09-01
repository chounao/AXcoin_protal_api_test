"""企业用户交易额度接口。"""

from decimal import Decimal, InvalidOperation

from requests_models.base import ApiService


class LimitsService(ApiService):
    """查询当前用户 ID，并配置指定企业用户的交易额度。"""

    DEFAULT_OPERATION_TYPES = ("MINT", "BURN")
    DEFAULT_CURRENCIES = ("USD", "BHD")
    DEFAULT_CHAINS = ("ETH", "SOL")
    CHAIN_ALIASES = {
        "ETH": "ETH",
        "ETHEREUM": "ETH",
        "SOL": "SOL",
        "SOLANA": "SOL",
    }

    def __init__(self, http, base_url, role=None):
        super().__init__(http, base_url)
        self.role = role

    @classmethod
    def _normalize_amount(cls, value):
        """允许 None 表示未限制；非空额度必须是非负数字。"""
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("limitAmount 必须是非负数字或 None")
        try:
            if Decimal(str(value)) < 0:
                raise ValueError
        except (InvalidOperation, ValueError) as error:
            raise ValueError("limitAmount 必须是非负数字或 None") from error
        return value

    @classmethod
    def build_limit(
        cls,
        operation_type,
        settlement_currency,
        fee_chain_type,
        limit_amount=None,
    ):
        """构建并校验一条额度配置。"""
        operation = cls.required(operation_type, "operation_type").upper()
        if operation not in cls.DEFAULT_OPERATION_TYPES:
            raise ValueError("operation_type 仅支持 MINT 或 BURN")

        currency = cls.required(
            settlement_currency, "settlement_currency"
        ).upper()
        chain_input = cls.required(fee_chain_type, "fee_chain_type").upper()
        if chain_input not in cls.CHAIN_ALIASES:
            raise ValueError("fee_chain_type 仅支持 ETH/ETHEREUM 或 SOL/SOLANA")

        return {
            "operationType": operation,
            "settlementCurrency": currency,
            "feeChainType": cls.CHAIN_ALIASES[chain_input],
            "limitAmount": cls._normalize_amount(limit_amount),
        }

    @classmethod
    def build_payload(cls, limits=None, default_limit_amount=None):
        """构建额度请求体。

        ``limits`` 为空时生成 MINT/BURN × USD/BHD × ETH/SOL 共 8 项；
        传入列表时只提交指定配置，字段支持 camelCase 和 snake_case。
        """
        if limits is None:
            items = [
                cls.build_limit(operation, currency, chain, default_limit_amount)
                for currency in cls.DEFAULT_CURRENCIES
                for chain in cls.DEFAULT_CHAINS
                for operation in cls.DEFAULT_OPERATION_TYPES
            ]
            return {"limits": items}

        if not isinstance(limits, list) or not limits:
            raise ValueError("limits 必须是非空列表或 None")

        items = []
        for index, item in enumerate(limits):
            if not isinstance(item, dict):
                raise TypeError(f"limits[{index}] 必须是字典")
            try:
                items.append(
                    cls.build_limit(
                        item.get("operationType") or item.get("operation_type"),
                        item.get("settlementCurrency")
                        or item.get("settlement_currency"),
                        item.get("feeChainType") or item.get("fee_chain_type"),
                        item.get("limitAmount", item.get("limit_amount")),
                    )
                )
            except (TypeError, ValueError) as error:
                raise type(error)(f"limits[{index}]: {error}") from error
        return {"limits": items}






    def get_limits_info(self):
        """兼容旧方法名；实际返回当前登录角色的 data。"""
        data = self.request_data(
            "GET",
            "/user/info",
            nested_keys=["data"],
        )
        if not isinstance(data, dict):
            raise RuntimeError("用户信息响应 data 不是对象")
        return data

    def get_current_user_id(self):
        """返回当前登录角色的 userId。"""
        data = self.get_limits_info()
        return self.required(data.get("userId") or data.get("id"), "userId")

    def get_assigned_by(self):
        """返回当前登录角色的 assignedBy。"""
        assigned_vault = self.get_limits_info().get("assignedVault")

        if not isinstance(assigned_vault, dict):
            raise RuntimeError("用户信息中没有 assignedVault")
        print("assignedBy", assigned_vault.get("assignedBy"))
        return self.required(assigned_vault.get("assignedBy"), "assignedBy")

    def get_assignedBy(self):
        """兼容旧驼峰方法名。"""
        return self.get_assigned_by()

    def get_enterprise_id(self):
        """返回当前登录角色的 enterpriseId。"""
        return self.required(
            self.get_limits_info().get("enterpriseId"),
            "enterpriseId",
        )

    def get_enterpriseId(self):
        """兼容旧驼峰方法名。"""
        return self.get_enterprise_id()



    def set_user_limits(
        self,
        user_id,
        limits=None,
        *,
        default_limit_amount=None,
    ):
        """为指定企业用户设置额度并返回响应 data。"""
        safe_user_id = self.encoded_id(user_id, "user_id")
        payload = self.build_payload(limits, default_limit_amount)
        return self.request_data(
            "PATCH",
            f"/enterprise-user/users/{safe_user_id}/limits",
            payload=payload,
        )

    def apply_for_burn_adn_mint_limit_increase(self):
        """提交企业 MINT/BURN 月度额度提升申请。"""
        payload = {
            "requestScope": "ENTITY",
            "periodType": "MONTHLY",
            "reason": "2222",
            "lines": [
                {
                    "targetOwnerType": "ENTERPRISE",
                    "operationType": "MINT",
                    "settlementCurrency": "USD",
                    "feeChainType": "ETH",
                    "requestedLimit": "8000"
                },
                {
                    "targetOwnerType": "ENTERPRISE",
                    "operationType": "BURN",
                    "settlementCurrency": "USD",
                    "feeChainType": "ETH",
                    "requestedLimit": "9000"
                }
            ]
        }
        return self.request_data(
            "POST",
            "/limit-increase-requests",
            payload=payload,
        )

    # 获取额度审批列表
    def get_limit_increase_requests(self):
        """获取额度审批列表。"""
        return self.request_data(
            "GET",
            "/enterprise-user/limit-increase-requests?page=1&limit=10",
        )


    # 根据审批列表返回的数据判断 如果有审批操作，获取第一个数据id，并进行接下来的审批操作，如果没有数据整个流程结束
    def get_limit_increase_request_id(self):
        """获取额度审批列表。"""
        data = self.get_limit_increase_requests()
        if not isinstance(data, list):
            raise RuntimeError("额度审批列表响应 data 不是数组")
        if not data:
            return None
        return data[0].get("id")


if __name__ == "__main__":
    print("请通过 PortalApi 或 LimitsWorkflow 调用额度服务；直接运行不会访问真实接口。")
