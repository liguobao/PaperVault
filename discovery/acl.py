"""ACL Anthology 自动发现

重构后逻辑：
1. 从 ACL Anthology 官网的 venues 页面获取目标 venues 列表。
2. 对每个 venue，访问其 venue 页面，提取所有年份的 events 链接。
3. 对每个 event 页面，自动检测实际使用的前缀（P, D, N, E, C, W, H, A 等）。
4. 生成对应的 tag 和配置条目。

当前关注的核心 venues：ACL, EMNLP, NAACL, EACL, COLING
"""

import re
from typing import List, Dict, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseDiscovery

# 核心 venues（与 PaperVault 主要关注的 NLP 顶级会议对应）
CORE_VENUES = {
    "acl": "ACL",
    "emnlp": "EMNLP",
    "naacl": "NAACL",
    "eacl": "EACL",
    "coling": "COLING",
}

_EVENTS_LINK_RE = re.compile(r"^/events/([a-z0-9]+)-(\d{4})/$")
_PAPER_LINK_RE = re.compile(r"^/[A-Za-z]\d{2}-\d+/$")
_PREFIX_RE = re.compile(r"^/([A-Za-z]\d{2})-\d+/$")


def _tag_for(prefix: str) -> str:
    return f"^{prefix}-*"


class ACLDiscovery(BaseDiscovery):
    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        results = []

        for venue_id, venue_name in CORE_VENUES.items():
            venue_url = f"https://aclanthology.org/venues/{venue_id}/"
            text = self._get_text(venue_url, timeout=20, retries=2)
            if not text:
                continue

            soup = BeautifulSoup(text, "html.parser")
            event_links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                m = _EVENTS_LINK_RE.match(href)
                if not m:
                    continue
                v_id, year_str = m.groups()
                if v_id != venue_id:
                    continue
                year = int(year_str)
                if year < start_year or year > end_year:
                    continue
                full_url = urljoin(venue_url, href)
                event_links.add((year, full_url))

            for year, event_url in sorted(event_links):
                name = f"{venue_name}{year}"
                if name in self.existing_names:
                    continue

                # 探测该 event 页面实际使用的前缀
                prefix = self._detect_event_prefix(event_url)
                if not prefix:
                    # fallback：按常见规则推断
                    prefix = self._fallback_prefix(venue_id, year)

                tag = _tag_for(prefix)
                results.append(
                    {
                        "name": name,
                        "tag": tag,
                        "url": event_url,
                    }
                )

                # Findings（2020 年后部分会议有 findings）
                findings_url = (
                    f"https://aclanthology.org/volumes/{year}.findings-{venue_id}/"
                )
                if self._head_ok(findings_url):
                    findings_name = f"Findings{name}"
                    # 与现有行为保持一致：findings 合并到同名会议
                    results.append(
                        {
                            "name": name,
                            "tag": f"^{year}.findings*",
                            "url": findings_url,
                        }
                    )

        return results

    def _detect_event_prefix(self, event_url: str) -> str:
        """访问 event 页面，检测论文编号前缀（如 P05, H05, W06, D10 等）。"""
        text = self._get_text(event_url, timeout=15, retries=2)
        if not text:
            return ""

        soup = BeautifulSoup(text, "html.parser")
        prefix_counts: Dict[str, int] = {}
        for strong in soup.find_all("strong"):
            a = strong.find("a", href=_PAPER_LINK_RE)
            if not a:
                continue
            m = _PREFIX_RE.match(a["href"])
            if m:
                prefix = m.group(1)
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1

        if not prefix_counts:
            return ""

        # 优先选择非 W 前缀（W 通常是 workshop）；如果全是 W 则选最多的
        non_w = {p: c for p, c in prefix_counts.items() if not p.startswith("W")}
        if non_w:
            return max(non_w, key=non_w.get)
        return max(prefix_counts, key=prefix_counts.get)

    def _fallback_prefix(self, venue_id: str, year: int) -> str:
        """当页面探测失败时，使用历史规则兜底。"""
        yy = str(year)[2:]
        prefix_map = {
            "acl": "P",
            "emnlp": "D",
            "naacl": "N",
            "eacl": "E",
            "coling": "C",
        }
        return f"{prefix_map.get(venue_id, 'P')}{yy}"
