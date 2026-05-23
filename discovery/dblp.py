"""DBLP 自动发现（会议 + 期刊）"""

from typing import List, Dict, Any
from .base import BaseDiscovery


# 会议缩写 → 起始年份
CONFERENCES = {
    "icassp": 2019,
    "www": 2019,
    "iclr": 2019,
    "icml": 2019,
    "aaai": 2019,
    "ijcai": 2019,
    "cvpr": 2019,
    "iccv": 2019,
    "mm": 2019,
    "kdd": 2019,
    "cikm": 2019,
    "sigir": 2019,
    "wsdm": 2019,
    "ecir": 2019,
    "eccv": 2020,  # 偶数年，多卷
    "colt": 2019,
    "aistats": 2019,
    "interspeech": 2019,
    "iswc": 2019,
    "recsys": 2019,
    "icme": 2019,
    "bmvc": 2019,
    "miccai": 2019,  # 多卷
    "fast": 2019,
    "sigmod": 2019,
    "icdm": 2019,
}

# 特殊 DBLP path（与缩写不同）
DBLP_PATH_OVERRIDE = {
    "iswc": "conf/semweb/iswc",
    "icme": "conf/icmcs/icme",
}

# 多卷会议（需要尝试 -1, -2, -3 …）
MULTI_VOLUME = {"eccv", "miccai", "ecir"}

# 期刊：DBLP path + 卷号计算公式（vol = f(year)）
# name_map 用于将 DBLP 缩写映射为配置中的会议名前缀
JOURNALS: Dict[str, Dict[str, Any]] = {
    "jmlr":  {
        "path": "journals/jmlr/jmlr",
        "volume_for": lambda y: y % 100,
        "name": "JMLR",
        "start_year": 2019,
    },
    "pvldb": {
        "path": "journals/pvldb/pvldb",
        "volume_for": lambda y: y - 2006,
        "name": "VLDB",
        "start_year": 2019,
    },
    "tip":   {
        "path": "journals/tip/tip",
        "volume_for": lambda y: y - 1991,
        "name": "TIP",
        "start_year": 2019,
    },
    "pami":  {
        "path": "journals/pami/pami",
        "volume_for": lambda y: y - 1978,
        "name": "TPAMI",
        "start_year": 2019,
    },
    "tkde":  {
        "path": "journals/tkde/tkde",
        "volume_for": lambda y: y - 1988 + 1,
        "name": "TKDE",
        "start_year": 2019,
    },
    "tois":  {
        "path": "journals/tois/tois",
        "volume_for": lambda y: y - 1982 + 1,
        "name": "TOIS",
        "start_year": 2019,
    },
    "taslp": {
        "path": "journals/taslp/taslp",
        "volume_for": lambda y: y - 1992,
        "name": "TASLP",
        "start_year": 2019,
    },
    "ijcv":  {
        "path": "journals/ijcv/ijcv",
        "volume_for": lambda y: y - 1892,
        "name": "IJCV",
        "start_year": 2019,
    },
    "tnn":   {
        "path": "journals/tnn/tnn",
        "volume_for": lambda y: y - 1989 + 1,
        "name": "TNNLS",
        "start_year": 2019,
    },
}


class DBLPDiscovery(BaseDiscovery):
    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        results = []

        # ---------- 会议 ----------
        for abbrev, conf_start in CONFERENCES.items():
            for year in range(max(start_year, conf_start), end_year + 1):
                name = f"{abbrev.upper()}{year}"
                if name in self.existing_names:
                    continue

                path = DBLP_PATH_OVERRIDE.get(abbrev, f"conf/{abbrev}/{abbrev}")
                base_url = f"https://dblp.org/db/{path}{year}.html"

                if abbrev in MULTI_VOLUME:
                    vol = 1
                    found_any = False
                    while vol <= 40:
                        url = f"https://dblp.org/db/{path}{year}-{vol}.html"
                        if self._head_ok(url):
                            results.append({"name": name, "url": url})
                            found_any = True
                            vol += 1
                        else:
                            break
                    if not found_any and self._head_ok(base_url):
                        results.append({"name": name, "url": base_url})
                else:
                    if self._head_ok(base_url):
                        results.append({"name": name, "url": base_url})

        # ---------- 期刊 ----------
        for abbrev, meta in JOURNALS.items():
            for year in range(max(start_year, meta["start_year"]), end_year + 1):
                name = f"{meta['name']}{year}"
                if name in self.existing_names:
                    continue

                vol = meta["volume_for"](year)
                url = f"https://dblp.org/db/{meta['path']}{vol}.html"
                if self._head_ok(url):
                    results.append({"name": name, "url": url})

        return results
