"""项目统一 HTTP 请求封装。

两种调用方式：
1. requests(method, url, ...)：直接请求完整 URL。
2. send_request(api_name=..., ...)：从 INI 的 API_DATA 解析接口。

所有公开快捷方法最终都进入 _send()，避免重复代码和行为不一致。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Optional

import requests

from common import logger, read_and_save_tool
from common.execute import get_config_section
from common.login import get_login_manager

try:
    from jsonpath_ng.ext import parse
except ImportError:  # 只有使用 JSONPath 时才要求安装该可选依赖。
    parse = None


SENSITIVE_KEYS = {
    "password",
    "code",
    "token",
    "temptoken",
    "access_token",
    "accesstoken",
    "authorization",
    "x-action-token",
}


class HttpRequest:
    """可选绑定到一个角色 section 的请求客户端。

    section=None 用于登录和 2FA 等匿名接口；传入 ROLE_xxx 时自动读取该角色
    的 access_token，并规范为 ``Authorization: Bearer ...``。
    """

    def __init__(
        self,
        section: Optional[str] = None,
        *,
        session: Optional[requests.Session] = None,
        config: Optional[read_and_save_tool.ConfigTools] = None,
        auth_manager=None,
    ):
        self.section = section
        self.user_type = section  # 兼容旧属性名。
        self.config_section = get_config_section()
        self.logger = logger.logger
        self.session = session or requests.Session()
        self.config = config or read_and_save_tool.ConfigTools()
        self.auth_manager = (
            auth_manager if auth_manager is not None
            else get_login_manager() if section else None
        )
        self.timeout = float(
            self.config.get_value(self.config_section, "timeout") or 30
        )

        # 这里只保存公共头；不会修改 Session 的全局 headers。
        self.headers = {
            "Content-Type": "application/json",
            "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6",
            "Accept": "application/json",
        }
        self._action_token = ContextVar(
            f"axcoin_action_token_{id(self)}", default=None
        )

    @contextmanager
    def use_action_token(self, action_token: str):
        """临时提供一次性 Action Token，退出代码块时自动清除。"""
        if not isinstance(action_token, str) or not action_token.strip():
            raise ValueError("action_token 必须是非空字符串")
        context_state = self._action_token.set(action_token.strip())
        try:
            yield
        finally:
            self._action_token.reset(context_state)

    @staticmethod
    def _bearer(token: str) -> str:
        """统一 Bearer 格式，并兼容 INI 中已经包含前缀的旧数据。"""
        value = token.strip()
        return value if value.lower().startswith("bearer ") else f"Bearer {value}"

    @staticmethod
    def _redact(value: Any) -> Any:
        """递归遮盖日志中的密码、验证码及各种 Token。"""
        if isinstance(value, dict):
            return {
                key: "***" if key.lower() in SENSITIVE_KEYS else HttpRequest._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [HttpRequest._redact(item) for item in value]
        return value

    def _build_headers(
        self,
        extra_headers: Optional[dict] = None,
        force_login: bool = False,
    ) -> dict:
        """为每次请求新建 headers，避免多账号共享 Session 时互相覆盖。"""
        headers = dict(self.headers)
        if extra_headers:
            if not isinstance(extra_headers, dict):
                raise TypeError("headers 必须是字典")
            if any(key.lower() == "authorization" for key in extra_headers):
                raise ValueError("请通过 section 选择账号，不要手动覆盖 Authorization")
            headers.update(extra_headers)
        if self.section:
            headers["Authorization"] = self.auth_manager.get_authorization(
                self.section, force=force_login
            )
        return headers

    def update_headers(self, headers: dict):
        """更新后续请求使用的公共头；禁止手动设置 Authorization。"""
        if not isinstance(headers, dict):
            raise TypeError("Headers must be a dictionary")
        if any(key.lower() == "authorization" for key in headers):
            raise ValueError("请通过 section 选择账号，不要手动覆盖 Authorization")
        self.headers.update(headers)
        self.session.headers.update(headers)

    def get_current_headers(self) -> dict:
        """返回公共请求头；Authorization 会在每次请求时按角色动态生成。"""
        return dict(self.headers)

    def get_authorized_headers(self) -> dict:
        """返回包含当前角色 Token 的请求头副本，通常只用于调试。"""
        return self._build_headers()

    def get_nested_value(self, data: Any, keys: list) -> Any:
        """按字典键或列表下标逐层读取，例如 ['data', 'accessToken']。"""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
                current = current[key]
            else:
                self.logger.warning("响应中不存在路径 %s，断点位于 %r", keys, key)
                return None
        return current

    def extract_by_jsonpath(self, json_data: dict, jsonpath_expr: str) -> list:
        """通过 JSONPath 提取值，例如 ``$.meta.requestId``。"""
        if not isinstance(jsonpath_expr, str):
            raise TypeError(
                "jsonpath_expr 必须是字符串，例如 '$.meta.requestId'；"
                "列表路径请使用 nested_keys=['meta', 'requestId']"
            )
        if parse is None:
            raise RuntimeError("使用 jsonpath_expr 前请安装 jsonpath-ng")
        try:
            return [match.value for match in parse(jsonpath_expr).find(json_data)]
        except Exception as error:
            self.logger.error("JSONPath 解析失败: %s", error)
            return []

    @staticmethod
    def format_response_content(content: str, max_length: int = 500) -> str:
        """格式化并截断错误响应，避免日志过长。"""
        if not content:
            return "Empty response"
        try:
            formatted = json.dumps(json.loads(content), indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            formatted = str(content)
        return formatted if len(formatted) <= max_length else formatted[:max_length] + "..."

    def _extract_response(
        self,
        response: requests.Response,
        nested_keys: Optional[list],
        jsonpath_expr: Optional[str],
    ) -> Any:
        """根据提取参数返回值；未指定时返回原始 Response。"""
        if not nested_keys and not jsonpath_expr:
            return response
        try:
            payload = response.json()
        except ValueError:
            self.logger.error("Response is not valid JSON")
            return None

        if jsonpath_expr:
            values = self.extract_by_jsonpath(payload, jsonpath_expr)
            if len(values) == 1:
                return values[0]
            return values or None
        return self.get_nested_value(payload, nested_keys)

    def _send(
        self,
        method: str,
        url: str,
        *,
        data: Any = None,
        nested_keys: Optional[list] = None,
        jsonpath_expr: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """唯一的底层发送方法：记录、发送、校验并提取响应。"""
        normalized_method = method.upper()
        if normalized_method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError(f"Invalid method: {method}")
        if not isinstance(url, str) or not url:
            raise ValueError("url 必须是非空字符串")


        if data is not None:
            safe_data = self._redact(data)
            self.logger.info(
                "Request data: %s",
                json.dumps(safe_data, indent=2, ensure_ascii=False),
            )

        # GET 不消费 Token；首个写请求消费，401 重试仍复用同一 Token。
        action_token = None
        if normalized_method in {"POST", "PUT", "PATCH", "DELETE"}:
            action_token = self._action_token.get()
            if action_token:
                self._action_token.set(None)

        retry_authorization = None
        for attempt in range(2):
            try:
                request_headers = self._build_headers(headers)
                if action_token:
                    request_headers["x-action-token"] = action_token
                if retry_authorization:
                    request_headers["Authorization"] = retry_authorization
                response = self.session.request(
                    normalized_method,
                    url,
                    json=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                self.logger.info("method:%s；url:%s；status_code:%s", normalized_method, url, response.status_code)
                self.logger.debug(
                    "Response content: %s",
                    self.format_response_content(response.text),
                )
                # print(response.text)
                # Access Token 失效时只刷新当前角色，并使用同一个 Action Token
                # 重试原请求。第二次仍为 401 时再按普通 HTTP 错误处理。
                if response.status_code == 401 and self.section and attempt == 0:
                    self.logger.warning(
                        "%s access token 无效，尝试 refresh token 后重试",
                        self.section,
                    )
                    retry_authorization = self.auth_manager.recover_authorization(
                        self.section
                    )
                    continue

                # 后端大多数响应是对象，但错误响应也可能是 JSON 字符串、
                # 数组、纯文本或空内容。只有字典才能读取 success 字段。
                try:
                    response_payload = response.json()
                except (ValueError, TypeError):
                    response_payload = None

                api_failed = False
                if isinstance(response_payload, dict) and "success" in response_payload:
                    success = response_payload["success"]
                    api_failed = not (
                        success is True
                        or (
                            isinstance(success, str)
                            and success.strip().lower() == "true"
                        )
                    )

                if response.status_code >= 400 or api_failed:
                    self.logger.error(
                        "Response content: %s",
                        self.format_response_content(response.text),
                    )

                response.raise_for_status()
                return self._extract_response(response, nested_keys, jsonpath_expr)
            except requests.exceptions.RequestException as error:
                self.logger.error("Error occurred during request: %s", error)
                return None
        return None

    # ---------- 配置型接口调用 ----------

    def request(
        self,
        api_name: Optional[str] = None,
        ping_data: Optional[str] = None,
        replace_data=None,
        dict_data: Optional[dict] = None,
        data: Any = None,
        nested_keys: Optional[list] = None,
        jsonpath_expr: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """从 INI 的 API_DATA 根据 api_name 解析 method 和 URL 后发送。"""
        result = self.config.get_data_from_name(
            api_name=api_name,
            ping_data=ping_data,
            replace_data=replace_data,
            dict_data=dict_data,
        )
        if result is None:
            raise ValueError(f"API configuration not found for: {api_name}")
        method, url = result
        return self._send(
            method,
            url,
            data=data,
            nested_keys=nested_keys,
            jsonpath_expr=jsonpath_expr,
            headers=headers,
        )

    def send_request(self, *args, **kwargs):
        """request() 的兼容别名。"""
        return self.request(*args, **kwargs)

    # ---------- 完整 URL 调用 ----------

    def requests(
        self,
        method: str,
        url: str,
        data: Any = None,
        nested_keys: Optional[list] = None,
        jsonpath_expr: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """使用 method 和完整 URL 发送请求，保留原项目方法名。"""
        return self._send(
            method,
            url,
            data=data,
            nested_keys=nested_keys,
            jsonpath_expr=jsonpath_expr,
            headers=headers,
        )

    def send_requests(self, method: str, url: str, **kwargs):
        """requests() 的兼容别名。"""
        return self.requests(method, url, **kwargs)

    # 单数与复数快捷方法都按完整 URL 调用，避免原实现的位置参数错位。
    def get(self, url: str, **kwargs):
        return self.requests("GET", url, **kwargs)

    def post(self, url: str, data: Any = None, **kwargs):
        return self.requests("POST", url, data=data, **kwargs)

    def put(self, url: str, data: Any = None, **kwargs):
        return self.requests("PUT", url, data=data, **kwargs)

    def delete(self, url: str, data: Any = None, **kwargs):
        return self.requests("DELETE", url, data=data, **kwargs)

    def patch(self, url: str, data: Any = None, **kwargs):
        return self.requests("PATCH", url, data=data, **kwargs)

    gets = get
    posts = post
    puts = put
    deletes = delete
    patchs = patch

    def is_token_expired(self, response: requests.Response) -> bool:
        """兼容旧方法：401 表示 Token 无效或已过期。"""
        expired = response.status_code == 401
        if expired:
            self.logger.warning("Token expired or invalid")
        return expired
