# Axcoin Portal 多角色接口测试框架

## 本地安装

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp common/test_config.example.ini common/test_config.ini
```

编辑本地的 `common/test_config.ini` 填写测试账号邮箱，并按示例中的
`password_env`、`two_factor_code_env` 设置环境变量。真实配置、Token 缓存、日志、
虚拟环境和 IDE 配置均已加入 `.gitignore`，不要强制提交这些文件。

## 设计原则

每次 HTTP 请求只能携带一个 `Authorization`，所以一个 `PortalApi` 实例固定
绑定一个角色。跨用户操作由 Workflow 协调，不在业务方法内部修改 headers。

```text
TokenCache        按 ROLE 保存 access/refresh Token 对及各自 JWT 有效期
Login             缓存有效时复用；支持 refresh，必要时才执行完整登录
HttpRequest       每次请求按角色生成 Authorization；401 刷新后重试一次
PortalApi         单个角色的业务域服务聚合入口
RoleClients       按角色创建、保存和复用 PortalApi
MintOrderWorkflow 负责决定每一步由哪个角色执行
```

## 多角色客户端

```python
from common.role_clients import RoleClients

clients = RoleClients()

submitter = clients.submitter
operator = clients.operator
approver = clients.approver

order = submitter.transactions.create(amount="100.00")
operator.receipts.submit(order["id"], "receipts/example.jpg")
detail = approver.transactions.get_detail(order["id"])
```

每个属性返回独立角色客户端。无需调用 `update_headers()`，也不要手工填写
`Authorization`。

## 按业务域调用

`PortalApi` 不再把所有接口逻辑堆在一个大类中，而是提供七个业务域：

```python
api.user.get_info()
api.fees.get_config("ETH")
api.fees.get_quota("USD", "ETH", "mint")
api.assets.get_id("USD", "ETHEREUM")
api.accounts.get_bank_account_number("ETHEREUM")
api.accounts.get_wallet_address("ETHEREUM")
api.transactions.create(amount="100.00")
api.verification.verify(code="当前验证码")
api.receipts.submit("order-id", "receipts/example.jpg")
```

每个服务只维护自己的接口。以后新增钱包接口只修改 `AccountService`，新增交易
接口只修改 `TransactionService`，不会继续扩大 `PortalApi`。

## Workflow：由其他用户提交凭证

默认角色映射：

- 创建订单：`ROLE_Submitter`
- 提交凭证：`ROLE_operator`

```python
from workflows.order_workflow import MintOrderWorkflow

workflow = MintOrderWorkflow()

result = workflow.run(
    amount="100.00",
    currency="USD",
    chain="ETHEREUM",
    receipt_url="receipts/example.jpg",
    create_2fa_code="111111",
    receipt_2fa_code="111111",
)

print(result["order_id"])
print(result["status"])
print(result["receipt"])
```

完整流程严格按以下顺序执行：

1. 查询资产、银行账户、钱包地址并生成订单参数；
2. 第一次业务 2FA，创建订单请求临时携带 ``x-action-token``；
3. 创建请求结束后自动清除该 Token，并查询订单最新状态；
4. 第二次业务 2FA；
5. 提交凭证请求临时携带新的 ``x-action-token``，结束后再次自动清除。

如果两个操作对应不同的后端 actionType，可额外传入
``create_action_type`` 和 ``receipt_action_type``。

如果实际提交凭证的是 Compliance，只修改角色映射：

```python
from workflows.order_workflow import MintOrderWorkflow, MintWorkflowRoles

workflow = MintOrderWorkflow(
    roles=MintWorkflowRoles(
        creator="ROLE_Submitter",
        receipt_submitter="ROLE_compliance",
    )
)
```

不需要修改 `submit_receipt()`，也不需要更新 headers。

## 分步骤执行

业务流程可能需要等待链上状态或人工审批，所以 Workflow 支持分步骤调用：

```python
workflow = MintOrderWorkflow()

order_id = workflow.create_order(amount="100.00", code="111111")

# 创建订单的 Action Token 已清除，可以安全查询最新状态。
status = workflow.get_latest_status(order_id)

# 等待实际凭证生成后，由配置的 receipt_submitter 再次完成 2FA 并操作。
receipt = workflow.submit_receipt(
    order_id,
    "receipts/example.jpg",
    code="111111",
)

```

## 提前登录多个用户

默认采用懒登录：角色第一次请求时才准备 Token。需要流程开始前准备参与者时：

```python
workflow = MintOrderWorkflow()
workflow.prepare_users()
```

多个角色会并行准备 Token。每个角色的 access token 和 refresh token 以角色
section 为键独立缓存到：

```text
.axcoin-token-cache.json
```

缓存文件权限为 `600`。access token 仍有效时直接复用。业务接口收到 401 后：

1. 读取当前角色缓存的 refresh token；
2. 调用 `POST /user/refresh-token`；
3. 原子更新响应中的新 access token 和新 refresh token；
4. 使用新 access token 重试原业务请求一次；
5. refresh token 缺失、过期或刷新接口失败时，才执行完整登录和登录 2FA。

刷新只影响当前请求角色，不会清除其他用户的 Token。同一角色的刷新和登录使用
角色锁保护，避免并发请求同时覆盖缓存；不同角色仍可独立操作。

登录验证码优先读取角色配置中的 `two_factor_code_env`，其次读取
`AXCOIN_2FA_CODE`。开发环境未配置时兼容固定验证码 `111111`；非开发环境建议
始终使用环境变量。

原 `test_config.ini` 中仍有效的旧 `access_token` 会在首次使用时迁移到独立缓存，
方便平滑升级。旧 Token 没有配套 refresh token，因此它失效后会完整登录一次，
之后缓存中就会同时拥有两个 Token。新 Token 不再写回 INI。

## 业务 2FA

登录 2FA 和业务操作 2FA 是两套流程。业务操作验证码可以直接传入：

```python
clients.submitter.verification.verify(code="当前验证码")
```

也可以设置环境变量：

```sh
export AXCOIN_ACTION_2FA_CODE='当前验证码'
```

## 兼容旧代码

以下旧接口继续可用：

- `Requests`（等同于 `PortalApi`）
- `get_fee_cofig()`
- `get_assets_id()`
- `get_bank_data()`
- `get_bank_accountNumber()`
- `get_wallet_account()`
- `get_wallet_accountNumber()`
- `get_transaction()`
- `upload_image()`

旧方法通过兼容层转发到对应业务域。新代码推荐直接使用业务域服务。

## 测试

```sh
python3 -m unittest discover -s tests -v
```

单元测试使用模拟响应，不访问真实 API。
