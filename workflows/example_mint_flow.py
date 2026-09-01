"""多角色 Mint 流程使用示例。

此文件只展示调用方式。请确认测试数据和用户权限后再取消实际调用代码的注释。
"""

from workflows.order_workflow import MintOrderWorkflow, MintWorkflowRoles


def build_workflow():
    """在此处集中定义流程中的用户分工。"""
    return MintOrderWorkflow(
        roles=MintWorkflowRoles(
            creator="ROLE_Submitter",
            receipt_submitter="ROLE_operator",
        )
    )


if __name__ == "__main__":
    workflow = build_workflow()

    # 可选：流程开始前并行准备两个用户的 Token。
    # workflow.prepare_users()

    # 完整流程会创建真实订单，请确认数据后再执行：
    # result = workflow.run(
    #     amount="100.00",
    #     currency="USD",
    #     chain="ETHEREUM",
    #     receipt_url="receipts/example.jpg",
    #     create_2fa_code="111111",   # 创建订单前的第一次 2FA
    #     receipt_2fa_code="111111",  # 提交凭证前的第二次 2FA
    # )
    # print(result)

    print("Workflow 已创建；示例中的真实接口调用默认保持注释状态。")
