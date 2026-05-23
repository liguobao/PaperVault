"""OpenReview (ICLR / NeurIPS) 自动发现"""

from typing import List, Dict, Any, Set
from urllib.parse import quote
from .base import BaseDiscovery


class OpenReviewDiscovery(BaseDiscovery):
    """
    通过 OpenReview API 自动发现 ICLR 和 NeurIPS 的 venue 配置。
    每个 venue 可能需要多条 URL（分页，每页 limit=1000）。
    """

    def __init__(self, existing_conf: List[Dict[str, Any]] = None):
        super().__init__("openreview", existing_conf)

    def _fetch_venues(self, invitation_tpl: str, year: int) -> List[str]:
        """返回该年份下所有 distinct 的 venue 字符串"""
        invitation = invitation_tpl.format(year=year)
        url = (
            f"https://api.openreview.net/notes?"
            f"invitation={quote(invitation, safe='')}&"
            f"details=replyCount&offset=0&limit=1000"
        )
        try:
            data = self._get_json(url, timeout=30, retries=3)
        except Exception:
            return []
        venues: Set[str] = set()
        for note in data.get("notes", []):
            v = note.get("content", {}).get("venue")
            if v:
                venues.add(v)
        return sorted(venues)

    def _count_for_venue(self, venue: str, invitation: str) -> int:
        """估算某个 venue 的论文数量，用于决定需要几条 URL"""
        url = (
            f"https://api.openreview.net/notes?"
            f"content.venue={quote(venue, safe='')}&"
            f"invitation={quote(invitation, safe='')}&"
            f"offset=0&limit=1"
        )
        try:
            data = self._get_json(url, timeout=30, retries=2)
            return data.get("count", 0)
        except Exception:
            return 0

    def _generate_urls(self, name: str, venue: str, invitation: str, count: int) -> List[Dict[str, Any]]:
        limit = 1000
        pages = (count // limit) + 1
        results = []
        for i in range(pages):
            offset = i * limit
            url = (
                f"https://api.openreview.net/notes?"
                f"content.venue={quote(venue, safe='')}&"
                f"details=replyCount&"
                f"offset={offset}&limit={limit}&"
                f"invitation={quote(invitation, safe='')}"
            )
            results.append({"name": name, "url": url})
        return results

    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        results = []
        sources = [
            ("ICLR", "ICLR.cc/{year}/Conference/-/Blind_Submission"),
            ("NIPS", "NeurIPS.cc/{year}/Conference/-/Blind_Submission"),
        ]
        for prefix, invitation_tpl in sources:
            for year in range(start_year, end_year + 1):
                name = f"{prefix}{year}"
                if name in self.existing_names:
                    continue
                invitation = invitation_tpl.format(year=year)
                venues = self._fetch_venues(invitation_tpl, year)
                if not venues:
                    # OpenReview API 可能因权限或结构变更返回空；提示用户检查
                    print(f"    [!] OpenReview returned no venues for {name} (invitation={invitation})")
                    continue
                for venue in venues:
                    count = self._count_for_venue(venue, invitation)
                    if count == 0:
                        continue
                    results.extend(self._generate_urls(name, venue, invitation, count))
        return results
