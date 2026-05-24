"""
为 cache/cache.jsonl 中的论文批量补充 abstract。

参考 FL-paper-update-tracker 的多源策略：
    Crossref (DOI) → Semantic Scholar (DOI) → arXiv (title) → OpenAlex (DOI)

用法:
    python scripts/fetch_abstracts.py              # 默认处理 DOI 论文 (Phase 1)
    python scripts/fetch_abstracts.py --phase all  # 处理所有空 abstract
    python scripts/fetch_abstracts.py --phase 2    # 处理核心会议非 DOI 论文
    python scripts/fetch_abstracts.py --phase 3    # 处理剩余非 DOI 论文
    python scripts/fetch_abstracts.py --conf AAAI2020 --chunk-size 500
    python scripts/fetch_abstracts.py --phase 1 --retry-failed
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
from urllib.parse import urlparse
from typing import Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter

# ---------- 配置 ----------
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "im.young@foxmail.com")

CROSSREF_AGENT = (
    f"PaperVault-AbstractBackfill/1.0 (mailto:{CONTACT_EMAIL})"
    if CONTACT_EMAIL
    else "PaperVault-AbstractBackfill/1.0"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36 " + CROSSREF_AGENT
    )
}

CACHE_DIR = Path("cache")
CACHE_FILE = CACHE_DIR / "cache.jsonl"
PROGRESS_FILE = CACHE_DIR / "abstract_backfill_progress.json"
BACKUP_FILE = CACHE_DIR / "cache.jsonl.bak"

# 核心会议（用于 Phase 2/3 划分）
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
        req_headers = kwargs.pop("headers", HEADERS)
        resp = session.get(url, timeout=timeout, headers=req_headers, **kwargs)
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
    parsed = urlparse(paper_url.strip())
    host = (parsed.netloc or "").lower()
    if host == "doi.org" or host.endswith(".doi.org"):
        doi = parsed.path.strip("/")
        return doi or None
    return None


def query_doi_by_title(title: str, last_time: float, min_interval: float = 2.0) -> Tuple[Optional[str], float]:
    """通过 Crossref 用标题查询 DOI（保守策略：严格限流，仅返回高置信度结果）。"""
    if not title or len(title) < 5:
        return None, last_time
    encoded = requests.utils.quote(title)
    url = f"https://api.crossref.org/works?query.title={encoded}&rows=1"
    headers = {"User-Agent": CROSSREF_AGENT}
    try:
        resp, last_time = _rate_limited_request(url, last_time, min_interval=min_interval, headers=headers)
        if resp.status_code != 200:
            return None, last_time
        data = resp.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            return None, last_time
        item = items[0]
        api_title = item.get("title", [""])[0] if isinstance(item.get("title"), list) else item.get("title", "")
        if not is_title_match(api_title, title, threshold=0.85):
            return None, last_time
        doi = item.get("DOI")
        return doi, last_time
    except Exception:
        return None, last_time


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
    paper: dict, last_time: dict, sleep_sec: float = 1.5, max_retries: int = 3,
    query_doi_by_title: bool = False,
) -> Tuple[Optional[str], dict, str]:
    """
    返回: (abstract, last_time, source)
    source 取值: "crossref", "semanticscholar", "arxiv", "openalex", ""
    """
    doi = extract_doi(paper.get("paper_url", ""))
    title = (paper.get("paper_name") or "").strip()
    abstract = None
    source = ""

    # 可选：对非 DOI 论文尝试用标题查询 DOI
    if not doi and query_doi_by_title and title:
        queried_doi, last_time["crossref"] = query_doi_by_title(title, last_time["crossref"])
        if queried_doi:
            doi = queried_doi

    if doi:
        abstract, api_title, last_time["crossref"] = fetch_crossref_abstract(
            doi, last_time["crossref"], min_interval=sleep_sec, max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            print(f"    [!] Title mismatch (crossref): api='{api_title[:80]}' vs local='{title[:80]}'")
            abstract = None
        if abstract:
            source = "crossref"
        if not abstract:
            abstract, api_title, last_time["semanticscholar"] = fetch_semantic_scholar_abstract(
                doi, last_time["semanticscholar"], min_interval=sleep_sec, max_retries=max_retries
            )
            if abstract and api_title and not is_title_match(api_title, title):
                print(f"    [!] Title mismatch (semanticscholar): api='{api_title[:80]}' vs local='{title[:80]}'")
                abstract = None
            if abstract:
                source = "semanticscholar"

    if not abstract and title:
        abstract, api_title, last_time["arxiv"] = fetch_arxiv_abstract(
            title, last_time["arxiv"], min_interval=max(sleep_sec, 3.0), max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            print(f"    [!] Title mismatch (arxiv): api='{api_title[:80]}' vs local='{title[:80]}'")
            abstract = None
        if abstract:
            source = "arxiv"

    if not abstract and doi:
        abstract, api_title, last_time["openalex"] = fetch_openalex_abstract(
            doi, last_time["openalex"], min_interval=sleep_sec, max_retries=max_retries
        )
        if abstract and api_title and not is_title_match(api_title, title):
            print(f"    [!] Title mismatch (openalex): api='{api_title[:80]}' vs local='{title[:80]}'")
            abstract = None
        if abstract:
            source = "openalex"

    return abstract, last_time, source


# ---------- 进度管理（v2 格式，兼容旧版） ----------
def load_progress() -> Dict[str, dict]:
    """加载进度文件，返回 {url: {"status": ..., ...}} 字典。"""
    if not PROGRESS_FILE.exists():
        return {}
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 兼容旧版格式 {"processed_urls": [...]}
    if "processed_urls" in data:
        old_urls = data["processed_urls"]
        return {url: {"status": "unknown", "ts": ""} for url in old_urls}
    # 新版格式 {"processed": {...}}
    return data.get("processed", {})


def save_progress(processed: Dict[str, dict]):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"version": 2, "processed": processed}, f, ensure_ascii=False, indent=2)


# ---------- 预检统计 ----------
def preflight_check(papers: List[dict]):
    """运行前统计，帮助用户确认目标和预期。"""
    total = len(papers)
    empty = [p for p in papers if not (p.get("paper_abstract") or "").strip()]
    empty_count = len(empty)

    doi_empty = 0
    non_doi_empty = 0
    host_counts = {}
    year_counts = {}
    conf_counts = {}

    for p in empty:
        url = p.get("paper_url", "")
        host = urlparse(url).netloc.lower()
        conf = p.get("conf", "UNKNOWN")
        year = conf[-4:] if len(conf) >= 4 else "UNKNOWN"

        host_counts[host] = host_counts.get(host, 0) + 1
        year_counts[year] = year_counts.get(year, 0) + 1
        conf_counts[conf] = conf_counts.get(conf, 0) + 1

        if host in ("doi.org",) or host.endswith(".doi.org"):
            doi_empty += 1
        else:
            non_doi_empty += 1

    print("=" * 60)
    print("[*] Preflight Check")
    print("=" * 60)
    print(f"    Total papers in cache      : {total}")
    print(f"    Papers with abstract       : {total - empty_count}")
    print(f"    Papers with EMPTY abstract : {empty_count} ({empty_count/total*100:.1f}%)")
    print(f"")
    print(f"    Empty abstract by URL type:")
    print(f"      DOI (doi.org)            : {doi_empty}")
    print(f"      Non-DOI                  : {non_doi_empty}")
    print(f"")
    print(f"    Empty abstract by year:")
    for y in sorted(year_counts.keys())[:10]:
        print(f"      {y}: {year_counts[y]}")
    print(f"")
    print(f"    Top 10 conferences with empty abstract:")
    for conf, n in sorted(conf_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"      {conf}: {n}")
    print("=" * 60)
    print("")


# ---------- Conf 粒度辅助函数 ----------
def list_pending_confs(papers: List[dict]) -> List[Tuple[str, dict]]:
    """扫描所有论文，返回按优先级排序的待处理 conf 列表（DOI 比例高的优先）。"""
    conf_stats: Dict[str, dict] = {}
    for p in papers:
        conf = p.get("conf", "UNKNOWN")
        has_abs = bool((p.get("paper_abstract") or "").strip())
        url = p.get("paper_url", "")
        host = urlparse(url).netloc.lower()
        is_doi = host == "doi.org" or host.endswith(".doi.org")

        if conf not in conf_stats:
            conf_stats[conf] = {"total": 0, "has": 0, "empty": 0, "doi_empty": 0}
        conf_stats[conf]["total"] += 1
        if has_abs:
            conf_stats[conf]["has"] += 1
        else:
            conf_stats[conf]["empty"] += 1
            if is_doi:
                conf_stats[conf]["doi_empty"] += 1

    empty_confs = {k: v for k, v in conf_stats.items() if v["empty"] > 0}
    return sorted(empty_confs.items(), key=lambda x: (x[1]["doi_empty"], x[1]["empty"]), reverse=True)


def update_conf_progress_md(conf: str, total: int, success: int, failed: int, elapsed_sec: float):
    """更新 docs/abstract_backfill_progress.md，将指定 conf 从'待处理'移到'已完成'。"""
    md_path = Path("docs/abstract_backfill_progress.md")
    if not md_path.exists():
        return

    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()
    new_lines = []
    found_pending = False

    for line in lines:
        if not found_pending and line.startswith("|") and conf in line and "待处理" in line:
            found_pending = True
            continue
        new_lines.append(line)

    if found_pending:
        done_header = "| Conf | 总数 | 成功 | 失败 | 完成时间 | 耗时 |"
        elapsed_str = "~{:.0f}min".format(elapsed_sec / 60) if elapsed_sec < 3600 else "~{:.1f}h".format(elapsed_sec / 3600)
        done_line = "| {} | {} | {} | {} | {} | {} |".format(
            conf, total, success, failed,
            time.strftime("%Y-%m-%d %H:%M"),
            elapsed_str
        )
        for i, line in enumerate(new_lines):
            if line.strip() == done_header:
                new_lines.insert(i + 2, done_line)
                break

        log_line = "- {}: 完成 {} (成功 {}/{}，耗时 {:.0f}s)".format(
            time.strftime("%Y-%m-%d %H:%M"), conf, success, total, elapsed_sec
        )
        for i, line in enumerate(new_lines):
            if line.startswith("## 执行日志"):
                new_lines.insert(i + 2, log_line)
                break

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")


def match_conf_pattern(pattern: str, confs: Set[str]) -> List[str]:
    """支持通配符匹配 conf 名称。pattern 如 'AAAI*'、'IC*2022'。"""
    if "*" not in pattern:
        return [pattern] if pattern in confs else []
    regex = pattern.replace("*", ".*")
    return sorted([c for c in confs if re.fullmatch(regex, c)])


# ---------- 主流程 ----------
def filter_papers_by_phase(papers: List[dict], phase: str) -> List[dict]:
    if phase == "all":
        return papers

    results = []
    for p in papers:
        url = p.get("paper_url", "")
        host = urlparse(url).netloc.lower()
        is_doi = host == "doi.org" or host.endswith(".doi.org")
        conf = p.get("conf", "")
        conf_name = re.sub(r"\d{4}$", "", conf)

        if phase == "1":
            if is_doi:
                results.append(p)
        elif phase == "2":
            if not is_doi and conf_name in CORE_CONFS:
                results.append(p)
        elif phase == "3":
            if not is_doi and conf_name not in CORE_CONFS:
                results.append(p)
    return results


def _process_targets(
    targets: List[dict],
    all_papers: List[dict],
    chunk_size: int,
    retry_failed: bool,
    retry_partial: bool,
    query_doi_by_title: bool,
) -> Tuple[int, int]:
    """处理一组目标论文，返回 (success_count, failed_count)。"""
    progress = load_progress()
    if not retry_failed and not retry_partial:
        targets = [p for p in targets if p.get("paper_url") not in progress]
    elif retry_partial:
        cache_has_abs = {p.get("paper_url", ""): (p.get("paper_abstract") or "").strip() for p in all_papers}
        partial_urls = {
            url for url, meta in progress.items()
            if meta.get("status") != "success" or not cache_has_abs.get(url, "")
        }
        targets = [p for p in targets if p.get("paper_url") in partial_urls]
        print(f"[*] Retry partial mode: {len(targets)} papers need retry")
    else:
        failed_urls = {url for url, meta in progress.items() if meta.get("status") == "failed"}
        targets = [p for p in targets if p.get("paper_url") in failed_urls]
        print(f"[*] Retry failed mode: {len(targets)} failed papers to retry")

    if not targets:
        print("[!] All target papers already processed. Exiting.")
        return 0, 0

    last_time = {"crossref": 0.0, "semanticscholar": 0.0, "arxiv": 0.0, "openalex": 0.0}
    success = 0
    failed = 0
    chunk_success = 0

    for i, paper in enumerate(targets, 1):
        title = (paper.get("paper_name") or "").strip()
        url = paper.get("paper_url", "")
        print(f"[{i}/{len(targets)}] {title[:60]}...")

        abstract, last_time, source = fetch_abstract_for_paper(
            paper, last_time, query_doi_by_title=query_doi_by_title
        )

        if abstract and len(abstract.strip()) >= 5:
            paper["paper_abstract"] = abstract
            success += 1
            chunk_success += 1
            print(f"  -> OK [{source}] ({len(abstract)} chars)")
            progress[url] = {
                "status": "success",
                "source": source,
                "chars": len(abstract),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        else:
            paper["paper_abstract"] = ""
            failed += 1
            print("  -> Failed")
            old_attempts = progress.get(url, {}).get("attempts", 0)
            progress[url] = {
                "status": "failed",
                "attempts": old_attempts + 1,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

        if i % chunk_size == 0 or i == len(targets):
            print(f"[*] Saving progress... (chunk success: {chunk_success}, total success: {success}, failed: {failed})")
            save_progress(progress)
            tmp_file = CACHE_FILE.with_suffix(".jsonl.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                for p in all_papers:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
            os.replace(str(tmp_file), str(CACHE_FILE))
            chunk_success = 0

    print(f"[*] Done. Success: {success}, Failed: {failed}")
    return success, failed


def run(
    phase: str = "1",
    target_conf: Optional[str] = None,
    chunk_size: int = 500,
    retry_failed: bool = False,
    retry_partial: bool = False,
    query_doi_by_title: bool = False,
    list_mode: bool = False,
    batch: bool = False,
    top_n: Optional[int] = None,
) -> None:
    print(f"[*] Phase: {phase}, conf: {target_conf or 'all'}, chunk_size: {chunk_size}")
    if query_doi_by_title:
        print("[*] DOI query by title: ENABLED (slower, use with caution)")

    # 1. 读取所有论文
    all_papers = []
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            all_papers.append(json.loads(line))
    print(f"[*] Total papers in cache: {len(all_papers)}")

    # 2. 预检统计
    preflight_check(all_papers)

    empty_papers = [p for p in all_papers if not (p.get("paper_abstract") or "").strip()]
    print(f"[*] Papers with empty abstract: {len(empty_papers)}")

    # --- list_mode: 只输出待处理 conf 列表 ---
    if list_mode:
        pending = list_pending_confs(all_papers)
        print("\n[*] Pending conferences (sorted by priority, DOI-first):")
        hdr = "{:<6} {:<20} {:>6} {:>6} {:>6} {:>8}".format("Rank", "Conf", "Total", "Empty", "DOI_E", "Pct")
        print(hdr)
        print("-" * 60)
        for i, (conf, s) in enumerate(pending, 1):
            pct = s["doi_empty"] / s["empty"] * 100 if s["empty"] > 0 else 0
            print("{:<6} {:<20} {:>6} {:>6} {:>6} {:>7.0f}%".format(
                i, conf, s["total"], s["empty"], s["doi_empty"], pct
            ))
        print(f"\n[*] Total: {len(pending)} conferences, {sum(s['empty'] for _, s in pending)} papers")
        return

    # --- 确定要处理的 conf 列表 ---
    all_empty_confs = sorted(set(p.get("conf") for p in empty_papers))

    if target_conf:
        matched = match_conf_pattern(target_conf, set(all_empty_confs))
        if not matched:
            print(f"[!] No conference matches pattern: {target_conf}")
            return
        target_confs = matched
        print(f"[*] Matched conferences: {', '.join(target_confs)}")
    elif batch:
        pending = list_pending_confs(all_papers)
        target_confs = [c for c, _ in pending]
        if top_n:
            target_confs = target_confs[:top_n]
        print(f"[*] Batch mode: will process {len(target_confs)} conferences")
    else:
        # phase 模式（原有逻辑）
        targets = filter_papers_by_phase(empty_papers, phase)
        print(f"[*] Targets after phase filter: {len(targets)}")
        if not targets:
            print("[!] No papers to process. Exiting.")
            return
        _process_targets(targets, all_papers, chunk_size, retry_failed, retry_partial, query_doi_by_title)
        return

    # --- 逐个 conf 处理 ---
    for conf in target_confs:
        conf_papers = [p for p in empty_papers if p.get("conf") == conf]
        if not conf_papers:
            continue
        print(f"\n{'='*60}")
        print(f"[*] Processing conf: {conf} ({len(conf_papers)} papers)")
        print(f"{'='*60}")
        start_ts = time.time()
        success, failed = _process_targets(
            conf_papers, all_papers, chunk_size, retry_failed, retry_partial, query_doi_by_title
        )
        elapsed = time.time() - start_ts
        if success > 0 or failed > 0:
            print(f"[*] Conf {conf} summary: Success={success}, Failed={failed}, Time={elapsed:.0f}s")
            update_conf_progress_md(conf, len(conf_papers), success, failed, elapsed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill paper abstracts from multiple APIs")
    parser.add_argument("--phase", type=str, default="1", choices=["1", "2", "3", "all"],
                        help="Phase: 1=DOI papers (high ROI), 2=core conf non-DOI, 3=remaining non-DOI, all=everything")
    parser.add_argument("--conf", type=str, default=None, help="Process conference(s), e.g. AAAI2020 or 'AAAI*'")
    parser.add_argument("--chunk-size", type=int, default=500, help="Save progress every N papers")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry only papers previously marked as failed")
    parser.add_argument("--retry-partial", action="store_true",
                        help="Retry papers that were interrupted (progress exists but cache not updated)")
    parser.add_argument("--query-doi-by-title", action="store_true",
                        help="Query Crossref for DOI using paper title (slower, optional)")
    parser.add_argument("--list", action="store_true", dest="list_mode",
                        help="List pending conferences sorted by priority and exit")
    parser.add_argument("--batch", action="store_true",
                        help="Batch process all pending conferences in priority order")
    parser.add_argument("--top", type=int, default=None, dest="top_n",
                        help="With --batch, only process top N conferences")
    args = parser.parse_args()
    run(
        phase=args.phase,
        target_conf=args.conf,
        chunk_size=args.chunk_size,
        retry_failed=args.retry_failed,
        retry_partial=args.retry_partial,
        query_doi_by_title=args.query_doi_by_title,
        list_mode=args.list_mode,
        batch=args.batch,
        top_n=args.top_n,
    )
