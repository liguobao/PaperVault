"""
为 cache/cache.jsonl 中的论文批量补充 abstract。

参考 FL-paper-update-tracker 的多源策略：
    Crossref (DOI) → Semantic Scholar (DOI) → arXiv (title) → OpenAlex (DOI)

用法:
    python scripts/fetch_abstracts.py              # 默认处理 2024-2025 (Phase A)
    python scripts/fetch_abstracts.py --phase all  # 处理所有空 abstract
    python scripts/fetch_abstracts.py --phase b    # 处理核心会议 2020-2023
    python scripts/fetch_abstracts.py --phase c    # 处理剩余会议 2019-2023
    python scripts/fetch_abstracts.py --conf AAAI2024  # 只处理单个会议
"""

import argparse
import json
import os
import random
import re
import sys
import time
import difflib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter

# ---------- 配置 ----------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "")
CROSSREF_AGENT = (
    f"PaperVault-AbstractBackfill/1.0 (mailto:{CONTACT_EMAIL})"
    if CONTACT_EMAIL
    else "PaperVault-AbstractBackfill/1.0"
)

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "cache.jsonl"
PROGRESS_FILE = CACHE_DIR / "abstract_backfill_progress.json"
BACKUP_FILE = CACHE_DIR / "cache.jsonl.bak"

# 阶段定义
CORE_CONFS = {
    "NIPS", "ICML", "ICLR", "CVPR", "ICCV", "ECCV",
    "ACL", "EMNLP", "NAACL", "COLING",
    "AAAI", "IJCAI", "KDD", "SIGIR", "WWW", "MM",
}


def _create_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.mount("https://", HTTPAdapter(max_retries=2))
    return session


def _rate_limited_request(
    url: str,
    last_time: float,
    min_interval: float = 1.5,
    timeout: int = 15,
    **kwargs,
) -> Tuple[requests.Response, float]:
    wait = max(0.0, min_interval - (time.time() - last_time))
    if wait > 0:
        time.sleep(wait + random.uniform(0.0, 0.3))
    with _create_session() as session:
        resp = session.get(url, timeout=timeout, **kwargs)
    return resp, time.time()


# ---------- Abstract 清洗 ----------
def clean_abstract(text: str) -> str:
    if not text:
        return ""
    # 去除 XML 标签
    text = re.sub(r"<jats:p>(.*?)</jats:p>", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip()
    # 处理连字符换行
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"-\r\n\s*", "", text)
    # 合并句子内硬换行
    text = re.sub(r"\n\s*([a-z0-9])", r" \1", text)
    text = re.sub(r"\r\n\s*([a-z0-9])", r" \1", text)
    # 压缩空白
    text = re.sub(r"[\s\t]+", " ", text)
    return text.strip()


# ---------- 标题匹配 ----------
def is_title_match(api_title: str, paper_title: str, threshold: float = 0.70) -> bool:
    if not api_title or not paper_title:
        return False
    norm = lambda t: re.sub(r"[^\w]+", "", t.strip().lower(), flags=re.UNICODE)
    n_api = norm(api_title)
    n_paper = norm(paper_title)
    if not n_api or not n_paper:
        return False
    if n_api in n_paper or n_paper in n_api:
        return True
    ratio = difflib.SequenceMatcher(None, n_api, n_paper).ratio()
    return ratio >= threshold


# ---------- DOI 提取 ----------
def extract_doi(paper_url: str) -> Optional[str]:
    if "doi.org/" in paper_url:
        return paper_url.split("doi.org/")[-1].strip("/")
    return None


# ---------- API 查询 ----------
def fetch_crossref_abstract(
    doi: str, last_time: float, min_interval: float = 1.5, max_retries: int = 3
) -> Tuple[Optional[str], Optional[str], float]:
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": CROSSREF_AGENT}
    for attempt in range(1, max_retries + 1):
        try:
            resp, last_time = _rate_limited_request(
                url, last_time, min_interval=min_interval, headers=headers
            )
            if resp.status_code in (404, 403):
                return None, None, last_time
            if resp.status_code == 429:
                time.sleep(min(60, 2 ** attempt))
                continue
            resp.raise_for_status()
            data = resp.json()
            item = data.get("message", {})
            raw_title = item.get("title")
            if isinstance(raw_title, list) and raw_title:
                api_title = str(raw_title[0]).strip() or None
            elif raw_title:
                api_title = str(raw_title).strip() or None
            else:
                api_title = None
            abstract = item.get("abstract")
            if abstract and isinstance(abstract, str):
                cleaned = clean_abstract(abstract)
                if cleaned:
                    return cleaned, api_title, last_time
            return None, api_title, last_time
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return None, None, last_time


def fetch_semantic_scholar_abstract(
    doi: str, last_time: float, min_interval: float = 1.5, max_retries: int = 3
) -> Tuple[Optional[str], Optional[str], float]:
    url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
    params = {"fields": "abstract,title"}
    for attempt in range(1, max_retries + 1):
        try:
            resp, last_time = _rate_limited_request(
                url, last_time, min_interval=min_interval, params=params
            )
            if resp.status_code in (404, 403):
                return None, None, last_time
            if resp.status_code == 429:
                time.sleep(min(60, 2 ** attempt))
                continue
            resp.raise_for_status()
            data = resp.json()
            api_title = data.get("title")
            if api_title:
                api_title = str(api_title).strip() or None
            abstract = data.get("abstract")
            if abstract and abstract.strip():
                return clean_abstract(abstract), api_title, last_time
            return None, api_title, last_time
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return None, None, last_time


def fetch_arxiv_abstract(
    title: str, last_time: float, min_interval: float = 3.0, max_retries: int = 3
) -> Tuple[Optional[str], Optional[str], float]:
    import xml.etree.ElementTree as ET

    encoded_title = requests.utils.quote(title)
    url = f"http://export.arxiv.org/api/query?search_query=ti:{encoded_title}&max_results=1"
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for attempt in range(1, max_retries + 1):
        try:
            resp, last_time = _rate_limited_request(
                url, last_time, min_interval=min_interval
            )
            if resp.status_code in (404, 403):
                return None, None, last_time
            if resp.status_code == 429:
                time.sleep(min(60, 2 ** attempt))
                continue
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            entry = root.find("atom:entry", ns)
            if entry is None:
                return None, None, last_time
            title_elem = entry.find("atom:title", ns)
            api_title = title_elem.text.strip() if title_elem is not None and title_elem.text else None
            summary_elem = entry.find("atom:summary", ns)
            abstract = None
            if summary_elem is not None and summary_elem.text:
                cleaned = clean_abstract(summary_elem.text)
                if cleaned:
                    abstract = cleaned
            return abstract, api_title, last_time
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return None, None, last_time


def _reconstruct_openalex_abstract(inverted_index: dict) -> Optional[str]:
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    try:
        max_pos = max(max(positions) for positions in inverted_index.values() if positions)
        words = [""] * (max_pos + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                if 0 <= pos <= max_pos:
                    words[pos] = word
        abstract = " ".join(words)
        return abstract if abstract.strip() else None
    except Exception:
        return None


def fetch_openalex_abstract(
    doi: str, last_time: float, min_interval: float = 1.5, max_retries: int = 3
) -> Tuple[Optional[str], Optional[str], float]:
    mailto = f"&mailto={requests.utils.quote(CONTACT_EMAIL)}" if CONTACT_EMAIL else ""
    url = f"https://api.openalex.org/works/doi:{doi}?select=display_name,abstract_inverted_index{mailto}"
    for attempt in range(1, max_retries + 1):
        try:
            resp, last_time = _rate_limited_request(
                url, last_time, min_interval=min_interval
            )
            if resp.status_code in (404, 403):
                return None, None, last_time
            if resp.status_code == 429:
                time.sleep(min(60, 2 ** attempt))
                continue
            resp.raise_for_status()
            data = resp.json()
            api_title = data.get("display_name")
            if api_title:
                api_title = str(api_title).strip() or None
            inverted = data.get("abstract_inverted_index")
            abstract = None
            if inverted:
                reconstructed = _reconstruct_openalex_abstract(inverted)
                if reconstructed:
                    cleaned = clean_abstract(reconstructed)
                    if cleaned:
                        abstract = cleaned
            return abstract, api_title, last_time
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return None, None, last_time


def fetch_abstract_for_paper(
    paper: dict, last_time: dict, sleep_sec: float = 1.5, max_retries: int = 3
) -> Tuple[Optional[str], dict]:
    doi = extract_doi(paper.get("paper_url", ""))
    title = (paper.get("paper_name") or "").strip()
    abstract = None

    if doi:
        abstract, api_title, last_time["crossref"] = fetch_crossref_abstract(
            doi, last_time["crossref"], min_interval=sleep_sec, max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            abstract = None
        if not abstract:
            abstract, api_title, last_time["semanticscholar"] = fetch_semantic_scholar_abstract(
                doi, last_time["semanticscholar"], min_interval=sleep_sec, max_retries=max_retries
            )
            if abstract and api_title and not is_title_match(api_title, title):
                abstract = None

    if not abstract and title:
        abstract, api_title, last_time["arxiv"] = fetch_arxiv_abstract(
            title, last_time["arxiv"], min_interval=max(sleep_sec, 3.0), max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            abstract = None

    if not abstract and doi:
        abstract, api_title, last_time["openalex"] = fetch_openalex_abstract(
            doi, last_time["openalex"], min_interval=sleep_sec, max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            abstract = None

    return abstract, last_time


# ---------- 进度管理 ----------
def load_progress() -> Set[str]:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("processed_urls", []))
    return set()


def save_progress(urls: Set[str]):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed_urls": sorted(urls)}, f, ensure_ascii=False, indent=2)


# ---------- 主流程 ----------
def filter_papers_by_phase(papers: List[dict], phase: str, target_conf: Optional[str] = None) -> List[dict]:
    if target_conf:
        return [p for p in papers if p.get("conf") == target_conf]

    if phase == "all":
        return papers

    results = []
    for p in papers:
        year = p.get("conf", "")[-4:]
        try:
            year_int = int(year)
        except ValueError:
            continue
        conf_name = re.sub(r"\d{4}$", "", p.get("conf", ""))

        if phase == "a":
            if year_int >= 2024:
                results.append(p)
        elif phase == "b":
            if 2020 <= year_int <= 2023 and conf_name in CORE_CONFS:
                results.append(p)
        elif phase == "c":
            if year_int <= 2023 and not (conf_name in CORE_CONFS and year_int >= 2020):
                results.append(p)
    return results


def run(
    phase: str = "a",
    target_conf: Optional[str] = None,
    chunk_size: int = 500,
    retry_failed: bool = False,
) -> None:
    print(f"[*] Phase: {phase}, conf: {target_conf or 'all'}")

    # 1. 读取所有论文
    all_papers = []
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            all_papers.append(json.loads(line))
    print(f"[*] Total papers in cache: {len(all_papers)}")

    # 2. 筛选目标论文（空 abstract）
    empty_papers = [p for p in all_papers if not (p.get("paper_abstract") or "").strip()]
    print(f"[*] Papers with empty abstract: {len(empty_papers)}")

    targets = filter_papers_by_phase(empty_papers, phase, target_conf)
    print(f"[*] Targets after phase filter: {len(targets)}")
    if not targets:
        print("[!] No papers to process. Exiting.")
        return

    # 3. 加载进度
    processed = load_progress()
    if not retry_failed:
        targets = [p for p in targets if p.get("paper_url") not in processed]
    print(f"[*] Targets after skipping processed: {len(targets)}")
    if not targets:
        print("[!] All target papers already processed. Exiting.")
        return

    # 4. 处理
    last_time = {"crossref": 0.0, "semanticscholar": 0.0, "arxiv": 0.0, "openalex": 0.0}
    success = 0
    failed = 0
    chunk_success = 0

    for i, paper in enumerate(targets, 1):
        title = (paper.get("paper_name") or "").strip()
        url = paper.get("paper_url", "")
        print(f"[{i}/{len(targets)}] {title[:60]}...")

        abstract, last_time = fetch_abstract_for_paper(paper, last_time)

        if abstract and len(abstract.strip()) >= 5:
            paper["paper_abstract"] = abstract
            success += 1
            chunk_success += 1
            print(f"  -> OK ({len(abstract)} chars)")
        else:
            paper["paper_abstract"] = ""
            failed += 1
            print("  -> Failed")

        processed.add(url)

        # 每 chunk_size 条保存一次进度和缓存
        if i % chunk_size == 0 or i == len(targets):
            print(f"[*] Saving progress... (chunk success: {chunk_success})")
            save_progress(processed)
            # 写回 cache.jsonl
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                for p in all_papers:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
            chunk_success = 0

    print(f"[*] Done. Success: {success}, Failed: {failed}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill paper abstracts from multiple APIs")
    parser.add_argument("--phase", type=str, default="a", choices=["a", "b", "c", "all"],
                        help="Phase: a=2024-2025, b=core 2020-2023, c=remaining, all=everything")
    parser.add_argument("--conf", type=str, default=None, help="Process only one conference, e.g. AAAI2024")
    parser.add_argument("--chunk-size", type=int, default=500, help="Save progress every N papers")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry all targets including those already in progress file")
    args = parser.parse_args()
    run(phase=args.phase, target_conf=args.conf, chunk_size=args.chunk_size, retry_failed=args.retry_failed)
