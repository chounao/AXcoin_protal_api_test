"""交易订单流程和凭证提交接口。"""

from decimal import Decimal, InvalidOperation

from requests_models.base import ApiService


class TransactionService(ApiService):
    """订单参数构建、创建、列表、状态和详情。"""

    def __init__(
        self,
        http,
        base_url,
        assets,
        accounts=None,
        *,
        banks=None,
        wallets=None,
    ):
        """组合订单依赖。

        ``accounts`` 为旧版兼容入口；新代码分别传入 ``banks`` 和
        ``wallets``，使银行及钱包逻辑各自归属对应模块。
        """
        super().__init__(http, base_url)
        self.assets = assets
        self.accounts = accounts
        self.banks = banks or accounts
        self.wallets = wallets or accounts
        if self.banks is None or self.wallets is None:
            raise ValueError("TransactionService 缺少 banks 或 wallets 服务")

    def list(
        self,
        operation_type="MINT",
        sort_by="createdAt",
        sort_order="desc",
        page=1,
        limit=20,
    ):
        if not isinstance(page, int) or page < 1:
            raise ValueError("page 必须是大于 0 的整数")
        if not isinstance(limit, int) or limit < 1:
            raise ValueError("limit 必须是大于 0 的整数")
        return self.request_data(
            "GET",
            "/transaction",
            query={
                "operationType": self.required(
                    operation_type, "operation_type"
                ).upper(),
                "sortBy": self.required(sort_by, "sort_by"),
                "sortOrder": self.required(sort_order, "sort_order").lower(),
                "page": page,
                "limit": limit,
            },
        )

    def build_payload(
        self,
        operation_type="MINT",
        amount="100.00",
        currency="USD",
        chain="ETHEREUM",
        *,
        asset_id=None,
        bank_account_id=None,
        bank_account_number=None,
        destination_address=None,
    ):
        """获取缺失的资产/账户数据并构建订单参数，不发送请求。

        ``bank_account_number`` 仅用于兼容旧测试代码，现在后端请求字段为
        ``bankAccountId``，新代码请使用 ``bank_account_id``。
        """
        try:
            if Decimal(str(amount)) <= 0:
                raise ValueError
        except (InvalidOperation, ValueError) as error:
            raise ValueError("amount 必须是大于 0 的数字") from error

        values = {
            "assetId": asset_id or self.assets.get_id(currency, chain),
            "bankAccountId": bank_account_id
            or bank_account_number
            or self.banks.get_bank_account_id(chain),
            "destinationAddress": destination_address
            or self.wallets.get_wallet_address(chain),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f"创建订单缺少必要数据: {', '.join(missing)}")

        return {
            **values,
            "operationType": self.required(
                operation_type, "operation_type"
            ).upper(),
            "network": self.required(chain, "chain").upper(),
            "amount": str(amount),
        }

    def create(
        self,
        operation_type="MINT",
        amount="100.00",
        currency="USD",
        chain="ETHEREUM",
        **overrides,
    ):
        payload = self.build_payload(
            operation_type,
            amount,
            currency,
            chain,
            **overrides,
        )
        return self.create_prepared(payload)

    def create_prepared(self, payload):
        """发送已构建的订单 payload，并返回后端响应中的订单 ID。

        ``operationType`` 属于订单业务数据，已经由 ``build_payload`` 写入
        payload，不应作为额外参数继续传给 HTTP 请求封装。
        """
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload 必须是非空字典")
        res = self.http.requests(
            "POST",
            self.url("/transaction"),
            data=payload,
            jsonpath_expr="$.data",
        )
        if res is None:
            raise RuntimeError(
                "创建订单响应中 $.data 为空；订单可能已创建，"
                "请结合响应 meta.requestId 从交易列表恢复，或与后端确认接口返回结构"
            )
        return self.extract_id(res)


    @staticmethod
    def extract_id(order_data):
        """从订单响应中提取 ID，兼容常见字段名。"""
        if isinstance(order_data, str) and order_data.strip():
            return order_data.strip()
        if not isinstance(order_data, dict):
            raise TypeError("order_data 必须是字典或非空字符串")
        order_id = (
            order_data.get("id")
            or order_data.get("orderId")
            or order_data.get("transactionId")
        )
        if not order_id:
            raise RuntimeError("创建订单失败：响应中没有订单 ID")
        return str(order_id)

    def create_id(self, *args, **kwargs):
        """创建订单并只返回订单 ID。"""
        return self.extract_id(self.create(*args, **kwargs))

    def get_status(self, order_id):
        """查询并返回订单当前状态。

        兼容后端返回单个历史对象或历史列表。列表默认最后一项是最新记录；
        如果响应含时间字段，则优先按时间选择最新记录。
        """
        data = self.request_data(
            "GET",
            f"/transaction/{self.encoded_id(order_id, 'order_id')}/history",
            query={"fieldName": "status"},
        )
        return self.extract_status(data)

    @staticmethod
    def extract_status(data):
        """从不同格式的状态历史响应中提取最新状态。

        支持以下后端响应：单个状态对象、直接列表，以及 ``{"list": [...]}``。
        包含时间字段时按时间取最新；没有时间字段时保持后端顺序取最后一项。
        """
        if isinstance(data, dict) and isinstance(data.get("list"), list):
            records = data["list"]
        elif isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        else:
            records = []

        records = [item for item in records if isinstance(item, dict)]
        if records:
            time_fields = ("createdAt", "updatedAt", "timestamp")

            def record_time(item):
                return next(
                    (str(item.get(key)) for key in time_fields if item.get(key)),
                    "",
                )

            latest = max(records, key=record_time) if any(
                record_time(item) for item in records
            ) else records[-1]
            status = latest.get("newStatus") or latest.get("status")
        else:
            status = None

        if not isinstance(status, str) or not status.strip():
            raise RuntimeError("订单状态响应中没有 newStatus/status")
        return status.strip().upper()

    def get_detail(self, order_id):
        return self.request_data(
            "GET",
            f"/transaction/{self.encoded_id(order_id, 'order_id')}",
        )

    # 取消订单
    def cancel(self, order_id):
        """取消订单。"""
        return self.request_data(
            "POST",
            f"/transaction/{self.encoded_id(order_id, 'order_id')}/cancel",
        )



class ReceiptService(ApiService):
    """将已上传的 receiptUrl 关联到订单。"""

    def __init__(self, http, base_url, transactions, role=None):
        super().__init__(http, base_url)
        self.transactions = transactions
        self.role = role

    def submit(self, order_id, receipt_url):
        """直接提交凭证；状态查询由 Workflow 在第二次 2FA 前完成。"""
        return self.submit_prechecked(order_id, receipt_url)

    def submit_prechecked(self, order_id, receipt_url):
        """发送凭证提交请求，不执行额外状态判断。"""
        normalized_order_id = self.required(order_id, "order_id")
        return self.request_data(
            "POST",
            f"/transaction/{self.encoded_id(normalized_order_id, 'order_id')}/perfectProof",
            payload={"receiptUrl": self.required(receipt_url, "receipt_url")},
        )



if __name__ == "__main__":
    print("请通过 PortalApi 或 Workflow 调用交易服务；直接运行不会访问真实接口。")
