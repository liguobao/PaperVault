"""Discovery 基类与通用工具"""

import abc
import time
from typing import List, Dict, Any

import requests
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36 "
        "PaperVault/1.0 (+https://github.com/youngfish42/PaperVault; "
        "contact: im.young@foxmail.com)"
    )
}


def _create_session() -> requests.Session:
    """创建一个新的 Session，禁用系统代理，避免 Windows 自动代理问题"""
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", HTTPAdapter(max_retries=2))
    session.mount("http://", HTTPAdapter(max_retries=2))
    return session


class BaseDiscovery(abc.ABC):
    """自动发现会议配置的抽象基类"""

    def __init__(self, name: str = "", existing_conf: List[Dict[str, Any]] = None):
        self.name = name
        self.existing = existing_conf or []
        self.existing_names = {item["name"] for item in self.existing}

    @abc.abstractmethod
    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        """返回新发现的配置列表，每条为 dict(name=..., url=..., [tag=...])"""
        ...

    def _head_ok(self, url: str, timeout: int = 15) -> bool:
        try:
            with _create_session() as session:
                resp = session.head(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
                return resp.status_code == 200
        except Exception:
            return False

    def _get_json(self, url: str, timeout: int = 30, retries: int = 3) -> Any:
        for attempt in range(retries):
            try:
                with _create_session() as session:
                    resp = session.get(url, headers=HEADERS, timeout=timeout)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None

    def _get_text(self, url: str, timeout: int = 15, retries: int = 2) -> str:
        for attempt in range(retries):
            try:
                with _create_session() as session:
                    resp = session.get(url, headers=HEADERS, timeout=timeout)
                    resp.raise_for_status()
                    return resp.text
            except Exception:
                if attempt == retries - 1:
                    return ""
                time.sleep(2 ** attempt)
        return ""
