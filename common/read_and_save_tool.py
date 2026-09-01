"""INI 配置读取、接口 URL 组装和可选 Excel 导出。"""

from __future__ import annotations

import ast
import configparser
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlencode

from common.execute import get_config_section
from common.logger import logger


class ConfigTools:
    """读取项目配置；实例不在模块导入时自动创建，减少副作用。"""

    _write_lock = threading.RLock()

    def __init__(self, filepath=None):
        self.configpath = Path(filepath or Path(__file__).with_name("test_config.ini"))
        if not self.configpath.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.configpath}")
        self.config = configparser.RawConfigParser()
        if not self.config.read(self.configpath, encoding="utf-8"):
            raise RuntimeError(f"配置文件读取失败: {self.configpath}")
        self.config_section = get_config_section()
        self.api_section = "API_DATA"

    def reload(self):
        """重新读取磁盘配置，供外部修改配置后刷新。"""
        self.config.read(self.configpath, encoding="utf-8")
        return self

    def get_value(self, section, key, fallback=None):
        if self.config.has_option(section, key):
            return self.config.get(section, key)
        return fallback

    def save_value(self, section, key, value):
        """兼容普通配置写入；Token 应写入 TokenCache 而不是 INI。"""
        if str(key).lower() in {"access_token", "token", "temptoken"}:
            raise ValueError("Token 必须由 TokenCache 保存，不能写入 INI")
        with self._write_lock:
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, str(key), str(value))
            with self.configpath.open("w", encoding="utf-8") as config_file:
                self.config.write(config_file)

    def get_section_data(self, section):
        return dict(self.config.items(section)) if self.config.has_section(section) else None

    def get_url_data(self):
        url = self.get_value(self.config_section, "URL")
        if not url:
            raise ValueError(f"配置[{self.config_section}]缺少 URL")
        return url.rstrip("/")

    def get_origin(self):
        return self.get_value(self.config_section, "origin")

    def get_timeout(self):
        return float(self.get_value(self.config_section, "timeout", "30"))

    def get_refresh_before_seconds(self):
        return int(self.get_value(self.config_section, "refresh_before_seconds", "60"))

    def get_token_cache_path(self):
        configured = self.get_value(
            self.config_section, "token_cache_file", ".axcoin-token-cache.json"
        )
        path = Path(configured)
        return path if path.is_absolute() else self.configpath.parent.parent / path

    def get_email(self, config_section):
        email = self.get_value(config_section, "email")
        if not email:
            raise ValueError(f"配置[{config_section}]缺少 email")
        return email

    def get_login_data(self, config_section):
        """优先从 password_env 读取；兼容旧 INI 明文 password。"""
        email = self.get_email(config_section)
        env_name = self.get_value(config_section, "password_env")
        if env_name:
            password = os.getenv(env_name)
            if not password:
                raise ValueError(f"缺少环境变量 {env_name}（{config_section}）")
        else:
            password = self.get_value(config_section, "password")
            logger.warning("配置[%s]仍使用明文 password，建议迁移到 password_env", config_section)
        if not password:
            raise ValueError(f"配置[{config_section}]缺少 password/password_env")
        return email, password

    def get_two_factor_code(self, config_section):
        env_name = self.get_value(config_section, "two_factor_code_env")
        code = os.getenv(env_name) if env_name else None
        configured = self.get_value(config_section, "two_factor_code")
        return code or configured or os.getenv("AXCOIN_2FA_CODE", "111111")

    def get_access_token(self, config_section):
        """兼容旧调用；新代码通过 Login.authenticate() 获取 Token。"""
        return self.get_value(config_section, "access_token")

    @staticmethod
    def process_url_placeholder(url_template, replace_values):
        placeholders = re.findall(r"\{(.*?)\}", url_template)
        missing = [name for name in placeholders if name not in replace_values]
        if missing:
            raise ValueError(f"URL 缺少替换值: {', '.join(missing)}")
        return url_template.format(**replace_values)

    def get_url_method(self, api_name=None, ping_data=None, replace_data=None, dict_data=None):
        """从 API_DATA 读取 ``[method, path]`` 并生成完整 URL。"""
        raw = self.get_value(self.api_section, api_name) if api_name else None
        if not raw:
            return None
        try:
            parsed = ast.literal_eval(raw)
            if not isinstance(parsed, (list, tuple)) or len(parsed) < 2:
                raise ValueError("格式必须为 ['METHOD', '/path']")
            method, path = str(parsed[0]).upper(), str(parsed[1])
            url = f"{self.get_url_data()}/{path.lstrip('/')}"
            if replace_data:
                url = self.process_url_placeholder(url, replace_data)
            if ping_data:
                url = f"{url}?{ping_data}"
            elif dict_data:
                clean = {key: value for key, value in dict_data.items() if value is not None}
                url = f"{url}?{urlencode(clean, doseq=True)}"
            return method, url
        except (ValueError, SyntaxError, TypeError) as error:
            raise ValueError(f"API_DATA.{api_name} 配置无效: {error}") from error

    def get_data_from_name(self, **kwargs):
        return self.get_url_method(**kwargs)

    def get_api_data(self):
        result = []
        for name, value in (self.get_section_data(self.api_section) or {}).items():
            try:
                method, path = ast.literal_eval(value)[:2]
                result.append([name, str(method), str(path)])
            except (ValueError, SyntaxError, TypeError):
                logger.warning("跳过格式错误的 API 配置: %s=%s", name, value)
        return result

    def save_api_data_to_excel(self, output="api_data.xlsx"):
        """只有执行导出时才加载 pandas/openpyxl。"""
        import pandas as pd

        pd.DataFrame(
            self.get_api_data(), columns=["API名称", "请求方法", "URL路径"]
        ).to_excel(output, index=False, engine="openpyxl")
        return output


if __name__ == "__main__":
    print(ConfigTools().get_api_data())
