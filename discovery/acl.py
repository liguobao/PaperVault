"""ACL Anthology 自动发现"""

from typing import List, Dict, Any
from .base import BaseDiscovery


VENUES = ["acl", "emnlp", "naacl", "eacl", "coling"]

# 年份 → tag 前缀映射（ACL Anthology 在 2020 年后改用年份前缀）
def _tag_for(venue: str, year: int) -> str:
    if year >= 2020:
        return f"^{year}.{venue}*"
    # 2019 及以前使用经典 P/C/N/D 前缀，需要按 venue 映射
    prefix_map = {
        "acl": "P",
        "emnlp": "D",
        "naacl": "N",
        "eacl": "E",
        "coling": "C",
    }
    prefix = prefix_map.get(venue, "P")
    # 例如 2019 对应 P19-*, 2018 对应 P18-*
    yy = str(year)[2:]
    return f"^{prefix}{yy}-*"


class ACLDiscovery(BaseDiscovery):
    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        results = []
        for venue in VENUES:
            for year in range(start_year, end_year + 1):
                name = f"{venue.upper()}{year}"
                if name in self.existing_names:
                    continue

                url = f"https://aclanthology.org/events/{venue}-{year}/"
                if self._head_ok(url):
                    results.append({
                        "name": name,
                        "tag": _tag_for(venue, year),
                        "url": url,
                    })

                # Findings
                findings_url = f"https://aclanthology.org/volumes/{year}.findings-{venue}/"
                if self._head_ok(findings_url):
                    findings_name = f"Findings{name}"
                    # 如果 Findings 名字不存在，或者名字相同但 url 不同
                    # 当前系统里 Findings 通常合并到同名会议中（如 EMNLP2021 包含 findings）
                    # 为了与现有行为保持一致，使用同名
                    findings_entry = {
                        "name": name,
                        "tag": f"^{year}.findings*",
                        "url": findings_url,
                    }
                    results.append(findings_entry)
        return results
