"""跨角色业务流程的延迟导出。

使用延迟导入可避免仅导入 ``workflows`` 时初始化所有流程，也避免通过
``python -m workflows.xxx`` 运行单个流程产生重复导入警告。
"""

from importlib import import_module


_EXPORTS = {
    "WorkflowRoles": ("workflows.base", "WorkflowRoles"),
    "BaseWorkflow": ("workflows.base", "BaseWorkflow"),
    "ApprovalWorkflow": ("workflows.approval_workflow", "ApprovalWorkflow"),
    "ApprovalWorkflowRoles": (
        "workflows.approval_workflow",
        "ApprovalWorkflowRoles",
    ),
    "BankWorkflow": ("workflows.bank_workflow", "BankWorkflow"),
    "BankWorkflowRoles": ("workflows.bank_workflow", "BankWorkflowRoles"),
    "LimitsWorkflow": ("workflows.limits_workflow", "LimitsWorkflow"),
    "LimitsWorkflowRoles": (
        "workflows.limits_workflow",
        "LimitsWorkflowRoles",
    ),
    "OrderWorkflow": ("workflows.order_workflow", "OrderWorkflow"),
    "OrderWorkflowRoles": (
        "workflows.order_workflow",
        "OrderWorkflowRoles",
    ),
    "MintOrderWorkflow": ("workflows.order_workflow", "MintOrderWorkflow"),
    "MintWorkflowRoles": ("workflows.order_workflow", "MintWorkflowRoles"),
    "WalletWorkflow": ("workflows.wallet_workflow", "WalletWorkflow"),
    "WalletWorkflowRoles": ("workflows.wallet_workflow", "WalletWorkflowRoles"),
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    """首次访问流程类时再导入相应模块。"""
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
