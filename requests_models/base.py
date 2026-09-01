"""业务 API 的公共基础能力。"""

from urllib.parse import quote, urlencode

from common.logger import logger


class ApiService:
    """所有业务域服务共享的 HTTP、URL 和校验能力。"""

    def __init__(self, http, base_url):
        self.http = http
        self.base_url = base_url.rstrip("/")

    def url(self, path, query=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        clean = {key: value for key, value in (query or {}).items() if value is not None}
        return f"{url}?{urlencode(clean, doseq=True)}" if clean else url

    def request_data(
        self,
        method,
        path,
        *,
        payload=None,
        query=None,
        nested_keys=None,
        jsonpath_expr=None,
        raw_response=False,
    ):
        """发送业务请求并提取响应数据。

        Axcoin 的标准响应结构为 ``{"success": ..., "data": ...}``，因此
        默认返回 ``data``。传入 ``jsonpath_expr`` 或 ``nested_keys`` 可
        覆盖提取方式；只有明确设置 ``raw_response=True`` 才返回原始
        ``requests.Response``。
        """
        if raw_response and (nested_keys is not None or jsonpath_expr is not None):
            raise ValueError(
                "raw_response 不能与 nested_keys 或 jsonpath_expr 同时使用"
            )
        effective_nested_keys = nested_keys
        if not raw_response and nested_keys is None and jsonpath_expr is None:
            effective_nested_keys = ["data"]

        request_options = {"data": payload}
        if effective_nested_keys is not None:
            request_options["nested_keys"] = effective_nested_keys
        if jsonpath_expr is not None:
            request_options["jsonpath_expr"] = jsonpath_expr

        result = self.http.requests(
            method,
            self.url(path, query),
            **request_options,
        )
        logger.debug("Portal API 完成: %s %s", method.upper(), path)
        return result

    @staticmethod
    def required(value, name):
        """校验值是否为非空字符串。"""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} 必须是非空字符串")
        return value.strip()

    @classmethod
    def encoded_id(cls, value, name="id"):
        """编码 ID 为 URL 安全的字符串。"""
        return quote(cls.required(value, name), safe="")

    @staticmethod
    def is_default(value):
        """校验值是否为默认值。"""
        return value is True or value == 1 or (
            isinstance(value, str) and value.strip().lower() in {"true", "1", "yes"}
        )

    @staticmethod
    def is_status(value):
        """状态是否是已经校验通过。"""
        return value is True or value == 1 or (
                isinstance(value, str) and value.strip().lower() in {"verified"}
        )
    @staticmethod
    def select_one(items, description):
        """从列表中选择一个元素。"""
        if not items:
            return None
        if len(items) > 1:
            raise ValueError(f"找到 {len(items)} 个{description}，请增加筛选条件")
        return items[0]

    @staticmethod
    def to_lower(value):
        """将字符串转换为小写。如果是小写则不变"""
        return value.lower() if isinstance(value, str) else value



if __name__ == '__main__':

    print(ApiService.to_lower("app"))
