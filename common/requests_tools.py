"""兼容旧导入路径。

业务接口的唯一实现位于 requests_models.requests_tools。
旧代码仍可继续使用 ``from common.requests_tools import Requests``，
但请勿再在本文件重复编写接口方法。
"""

from requests_models.requests_tools import PortalApi, Requests

__all__ = ["PortalApi", "Requests"]
