"""DBLP 自动发现（会议 + 期刊）"""

import json
import time
from pathlib import Path
from typing import List, Dict, Any
from .base import BaseDiscovery

CACHE_FILE = Path("cache/dblp_discovery_cache.json")
CACHE_TTL_EXIST = 30 * 86400      # 已确认存在的 URL 缓存 30 天
CACHE_TTL_NOT_EXIST = 7 * 86400   # 已确认不存在的 URL 缓存 7 天


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


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
    # --- 新增（来自 FL-paper-update-tracker） ---
    "alt": 2019,
    "uai": 2019,
    "osdi": 2019,    # 双年（奇数年）
    "sosp": 2019,    # 双年（奇数年）
    "isca": 2019,
    "eurosys": 2019,
    "sigcomm": 2019,
    "infocom": 2019,
    "mobicom": 2019,
    "nsdi": 2019,
    "dac": 2019,
    "ndss": 2019,
    "sp": 2019,      # IEEE S&P
    "uss": 2019,     # USENIX Security
    "icse": 2019,
    "stoc": 2019,
    "focs": 2019,    # IEEE FOCS (会议，非期刊)
}

# 特殊 DBLP path（与缩写不同）
DBLP_PATH_OVERRIDE = {
    "iswc": "conf/semweb/iswc",
    "icme": "conf/icmcs/icme",
}

# 双年会议（仅在奇数年举办）
BIENNIAL_ODD = {"osdi", "sosp"}

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
    # --- 新增（来自 FL-paper-update-tracker） ---
    "ai":    {
        "path": "journals/ai/ai",
        "volume_for": lambda y: y - 1970,
        "name": "AI",
        "start_year": 2019,
    },
    "ml":    {
        "path": "journals/ml/ml",
        "volume_for": lambda y: y - 1986,
        "name": "MLJ",
        "start_year": 2019,
    },
    "tocs":  {
        "path": "journals/tocs/tocs",
        "volume_for": lambda y: y - 1972,
        "name": "TOCS",
        "start_year": 2019,
    },
    "tos":   {
        "path": "journals/tos/tos",
        "volume_for": lambda y: y - 2005,
        "name": "TOS",
        "start_year": 2019,
    },
    "tpds":  {
        "path": "journals/tpds/tpds",
        "volume_for": lambda y: y - 1991,
        "name": "TPDS",
        "start_year": 2019,
    },
    "tcad":  {
        "path": "journals/tcad/tcad",
        "volume_for": lambda y: y - 1981,
        "name": "TCAD",
        "start_year": 2019,
    },
    "tc":    {
        "path": "journals/tc/tc",
        "volume_for": lambda y: y - 1951,
        "name": "TC",
        "start_year": 2019,
    },
}


class DBLPDiscovery(BaseDiscovery):
    def __init__(self, name: str = "", existing_conf: List[Dict[str, Any]] = None):
        super().__init__(name, existing_conf)
        self._cache = _load_cache()
        self._cache_dirty = False

    def _head_ok_cached(self, url: str, timeout: int = 10) -> bool:
        """带缓存的 HEAD 检查，避免对相同 URL 重复请求。"""
        now = time.time()
        entry = self._cache.get(url)
        if entry:
            ts = entry.get("ts", 0)
            ttl = CACHE_TTL_EXIST if entry.get("exists") else CACHE_TTL_NOT_EXIST
            if now - ts < ttl:
                return entry["exists"]

        result = self._head_ok(url, timeout)
        self._cache[url] = {"exists": result, "ts": now}
        self._cache_dirty = True
        return result

    def discover(self, start_year: int, end_year: int) -> List[Dict[str, Any]]:
        results = []
        existing_urls = {item.get("url") for item in self.existing}

        try:
            # ---------- 会议 ----------
            for abbrev, conf_start in CONFERENCES.items():
                for year in range(max(start_year, conf_start), end_year + 1):
                    name = f"{abbrev.upper()}{year}"
                    path = DBLP_PATH_OVERRIDE.get(abbrev, f"conf/{abbrev}/{abbrev}")
                    base_url = f"https://dblp.org/db/{path}{year}.html"

                    # 跳过双年会议的非举办年份
                    if abbrev in BIENNIAL_ODD and year % 2 == 0:
                        continue

                    if abbrev in MULTI_VOLUME:
                        # 多卷会议：尝试所有卷号，连续 3 次失败才停止，避免网络抖动导致漏卷
                        consecutive_fail = 0
                        for vol in range(1, 41):
                            url = f"https://dblp.org/db/{path}{year}-{vol}.html"
                            if url in existing_urls:
                                consecutive_fail = 0
                                continue
                            if self._head_ok_cached(url):
                                results.append({"name": name, "url": url})
                                consecutive_fail = 0
                            else:
                                consecutive_fail += 1
                                if consecutive_fail >= 3:
                                    break
                            time.sleep(0.5)
                        # 没有任何卷时回退到 base_url
                        if not any(r["name"] == name for r in results):
                            if base_url not in existing_urls and self._head_ok_cached(base_url):
                                results.append({"name": name, "url": base_url})
                                time.sleep(0.5)
                    else:
                        # 非多卷会议：若 name 已存在则直接跳过，减少无效请求
                        if name in self.existing_names:
                            continue
                        if self._head_ok_cached(base_url):
                            results.append({"name": name, "url": base_url})
                        time.sleep(0.5)

            # ---------- 期刊 ----------
            for abbrev, meta in JOURNALS.items():
                for year in range(max(start_year, meta["start_year"]), end_year + 1):
                    name = f"{meta['name']}{year}"
                    if name in self.existing_names:
                        continue
                    vol = meta["volume_for"](year)
                    url = f"https://dblp.org/db/{meta['path']}{vol}.html"
                    if url not in existing_urls and self._head_ok_cached(url):
                        results.append({"name": name, "url": url})
                    time.sleep(0.5)

        finally:
            if self._cache_dirty:
                _save_cache(self._cache)

        return results
