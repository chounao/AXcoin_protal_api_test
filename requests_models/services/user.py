"""用户信息、手续费和额度接口。"""

from requests_models.base import ApiService


class UserService(ApiService):
    """当前登录用户相关接口。"""

    def get_info(self):
        return self.request_data("GET", "/user/info")


class FeeService(ApiService):
    """手续费配置和用户额度接口。"""

    def get_config(self, chain="ETH"):
        """获取手续费配置。"""
        expected = self.required(chain, "chain").upper()
        data = self.request_data("GET", "/fee-config") or {}
        schedules = data.get("schedules", []) if isinstance(data, dict) else []
        return [
            item
            for item in schedules
            if isinstance(item, dict)
            and str(item.get("chain", "")).upper() == expected
        ]

    def get_quota(self, currency="USD", chain="ETH", request_type="mint"):
        """获取用户额度。"""
        operation = self.required(request_type, "request_type")
        data = self.request_data(
            "GET",
            "/limits",
            query={
                "settlementCurrency": self.required(currency, "currency").upper(),
                "feeChainType": self.required(chain, "chain").upper(),
            },
        )
        return data.get(operation) if isinstance(data, dict) else None
