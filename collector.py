import json
import os
import re
import warnings
from collections import Counter
import yaml
import requests
import time
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from tqdm import tqdm

# 忽略 ACL Anthology 某些 XML 页面被 HTML 解析器解析时的警告
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
}

def _is_openreview_accepted(venue: str) -> bool:
    """判断 OpenReview 论文的 venue 字段是否表示已接收。

    排除：Submitted / Reject / Withdrawn / Desk Rejected
    保留：Oral / Spotlight / Poster / Accept / Top
    """
    if not venue:
        return False
    venue_lower = venue.lower()
    # 严格排除未接收/撤回状态
    if any(k in venue_lower for k in ("submitted", "reject", "withdrawn", "desk rejected")):
        return False
    # 包含已接收状态（ oral, spotlight, poster, accept, top ）
    if any(k in venue_lower for k in ("oral", "spotlight", "poster", "accept", "top")):
        return True
    return False


def search_from_iclr_openreview(url, name, res):
    """通过 OpenReview API 获取 ICLR 论文，自动分页并过滤已接收论文。

    旧的按 venue 分类型查询（Oral/Poster/Spotlight 各自一条 URL）已废弃。
    改为统一查询 Blind_Submission，在代码内根据 venue 过滤，避免重复和遗漏。
    """
    if name not in res:
        res[name] = []

    # 清理 URL 中已有的 offset/limit，由本函数自行分页
    base_url = re.sub(r"&offset=\d+", "", url)
    base_url = re.sub(r"&limit=\d+", "", base_url)

    offset = 0
    limit = 1000

    while True:
        paginated_url = f"{base_url}&offset={offset}&limit={limit}"
        r = requests.get(paginated_url, headers=HEADERS)
        data = r.json()
        notes = data.get("notes", [])
        if not notes:
            break

        for item in notes:
            venue = item.get("content", {}).get("venue", "") or ""
            if not _is_openreview_accepted(venue):
                continue

            paper_authors = item["content"].get("authors", [])
            # authors 字段在部分旧数据中可能为 None，兜底处理
            if paper_authors is None:
                paper_authors = []

            res[name].append(
                {
                    "paper_name": item["content"]["title"],
                    "paper_url": "https://openreview.net/pdf?id=" + item["id"],
                    "paper_authors": paper_authors,
                    "paper_abstract": item["content"].get("abstract", ""),
                    "paper_code": "#",
                }
            )

        if len(notes) < limit:
            break
        offset += limit

    return res


def search_from_iclr_official(url, name, res):
    """通过 ICLR 官方 Schedule 页面获取论文（适用于 OpenReview API 不可用的年份，如 2024+）。

    页面结构：
        div.maincard (class 包含 poster / oral)
            div.maincardBody   -> 标题
            div.maincardFooter -> 作者（用 · 分隔）
            a[href*=openreview.net/forum?id=] -> OpenReview 链接
    """
    if name not in res:
        res[name] = []

    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    for card in soup.find_all("div", class_="maincard"):
        classes = card.get("class", [])
        # 只收集主会论文（poster / oral），排除 workshop / event / break 等
        if "poster" not in classes and "oral" not in classes:
            continue

        title_elem = card.find("div", class_="maincardBody")
        author_elem = card.find("div", class_="maincardFooter")
        or_link = card.find("a", href=lambda x: x and "openreview.net/forum?id=" in x)

        if not title_elem or not or_link:
            continue

        paper_name = title_elem.get_text(strip=True)
        paper_url = or_link.get("href", "")
        # 统一为 pdf 链接，与 OpenReview API 方式保持一致
        if "openreview.net/forum?id=" in paper_url:
            paper_url = paper_url.replace("openreview.net/forum?id=", "openreview.net/pdf?id=")

        # 解析作者：ICLR 官网用中间点 "·" 分隔
        authors = []
        if author_elem:
            author_text = author_elem.get_text(strip=True)
            authors = [a.strip() for a in author_text.split("·") if a.strip()]

        # 摘要留空：OpenReview API 对这些旧 forum 已不可用，
        # 后续由 scripts/fetch_abstracts.py 通过 Crossref / Semantic Scholar / arXiv 补充
        paper_abstract = ""

        res[name].append(
            {
                "paper_name": paper_name,
                "paper_url": paper_url,
                "paper_authors": authors,
                "paper_abstract": paper_abstract,
                "paper_code": "#",
            }
        )

    return res


def search_from_iclr(url, name, res):
    """ICLR 论文获取入口，自动根据 URL 类型选择解析策略。"""
    if "api.openreview.net" in url:
        return search_from_iclr_openreview(url, name, res)
    elif "iclr.cc" in url:
        return search_from_iclr_official(url, name, res)
    else:
        # fallback：默认当作 OpenReview API 处理
        return search_from_iclr_openreview(url, name, res)

def search_abs_from_nips(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    # 新结构：h2.section-label + p.paper-abstract
    h2 = soup.find('h2', class_='section-label')
    if h2 and 'Abstract' in h2.text:
        abstract_elem = h2.find_next_sibling()
        if abstract_elem:
            return abstract_elem.get_text(strip=True)
    # 旧结构 fallback
    h4 = soup.find(lambda tag: tag.name == "h4" and 'Abstract' in tag.text)
    if h4 and h4.next_sibling and h4.next_sibling.next_sibling:
        return h4.next_sibling.next_sibling.text.strip()
    return ""

def search_from_nips(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []
    url_prefix = "https://" + url[8:].split("/")[0]
    col = soup.find(class_="col")
    if not col or not col.ul:
        return res
    for paper_item in col.ul.find_all("li"):
        a_tag = paper_item.a
        if a_tag is None:
            continue
        href = a_tag.get("href")
        if not href:
            continue
        paper_url = url_prefix + href
        # 新结构：span class="paper-authors"
        authors_span = paper_item.find("span", class_="paper-authors")
        if authors_span:
            paper_author = [author.strip() for author in authors_span.get_text(strip=True).split(',')]
        # 旧结构 fallback：i 标签
        elif paper_item.i is not None and paper_item.i.string is not None:
            paper_author = [author.strip() for author in paper_item.i.string.split(',')]
        else:
            paper_author = []
        try:
            paper_abstract = search_abs_from_nips(paper_url)
        except Exception as e:
            print(f"Skip url:{paper_url}")
            paper_abstract = ""

        paper_name = a_tag.string if a_tag.string else a_tag.get_text(strip=True)
        res[name].append(
            {
                "paper_name": paper_name,
                "paper_url": paper_url,
                "paper_authors": paper_author,
                "paper_abstract": paper_abstract,
                "paper_code": "#",
            }
        )
    return res


def _parse_acl_volume(volume_url: str, tag: str, name: str, res: dict):
    """解析 ACL Anthology 单个 volume 页面"""
    if name not in res:
        res[name] = []
    r = requests.get(volume_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    # 新版页面：论文链接在 <strong> 下的 <a>，href 格式如 /2023.acl-long.1/
    strongs = soup.find_all("strong")
    for strong in strongs:
        a = strong.find("a", href=re.compile(r"^/\d{4}\.[a-zA-Z0-9-]+\.\d+/$"))
        if not a:
            continue
        paper = a.text.strip()
        if not paper:
            continue
        # 跳过 volume 封面页（Proceedings of ...）
        if paper.lower().startswith("proceedings of"):
            continue
        # tag 过滤：如 ^/2023.acl* 只匹配 acl 相关 volume
        href = a["href"]
        tag_pattern = tag.lstrip("^").rstrip("*")
        if tag_pattern not in href:
            continue

        paper_url = "https://aclanthology.org" + href

        # 作者：在 strong 的父容器中查找 people 链接
        container = strong.find_parent()
        paper_authors = []
        if container:
            for author in container.find_all("a", href=re.compile("people/")):
                author_text = author.string or author.text
                if author_text:
                    paper_authors.append(author_text.strip())

        # abstract：根据 href 构造 div id，如 /2023.acl-long.1/ -> abstract-2023--acl-long--1
        paper_id = href.strip("/").replace(".", "--")
        abstract_div = soup.find(id=f"abstract-{paper_id}")
        paper_abstract = abstract_div.text.strip() if abstract_div else ""

        res[name].append(
            {
                "paper_name": paper,
                "paper_url": paper_url,
                "paper_authors": paper_authors,
                "paper_abstract": paper_abstract,
                "paper_code": "#",
            }
        )
    return res


def search_from_acl(url, tag, name, res):
    """解析 ACL Anthology events 页面，自动跳转各 volume"""
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []

    # 提取所有 volume 链接（新版 events 页面结构）
    volume_links = set()
    for a in soup.find_all("a", href=re.compile(r"/volumes/")):
        href = a["href"]
        if not href.startswith("http"):
            href = "https://aclanthology.org" + href
        volume_links.add(href)

    if volume_links:
        # 新版：遍历各 volume 页面
        for volume_url in sorted(volume_links):
            res = _parse_acl_volume(volume_url, tag, name, res)
    else:
        # 旧版 fallback：直接解析当前页面（兼容早期年份）
        res = _parse_acl_volume(url, tag, name, res)

    return res


def search_abs_from_dblp(url):
    try:
        r = requests.get(url, headers=HEADERS)
    except Exception as e:
        msg = str(e)
        if "doesn't match either of 'aaai.org'" in msg:
            hostname = e.request.url.replace('//','/').split('/')[1]
            url = e.request.url.replace(hostname,'aaai.org')
        r = requests.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")

    abstract = ""
    if 'ieee' in r.url:
        script_tag = soup.find(lambda tag: tag.name == 'script' and 'xplGlobal.document.metadata' in tag.text)
        if script_tag:
            try:
                abstract = yaml.safe_load(script_tag.text.split('\n\t')[-1].strip()[28:-1])['abstract']
            except Exception:
                pass

    elif 'acm' in r.url:
        abstract_section = soup.find(class_="abstractSection")
        if abstract_section and abstract_section.p:
            abstract = abstract_section.p.get_text(strip=True)

    elif 'openreview' in r.url:
        try:
            api_url = 'https://api.openreview.net/notes?forum=' + r.url.split("=")[-1]
            r2 = requests.get(api_url, headers=HEADERS)
            abstract = r2.json()["notes"][-1]["content"]["abstract"]
        except Exception:
            pass

    elif 'mlr.press' in r.url:
        elem = soup.find(id="abstract")
        if elem:
            abstract = elem.get_text(strip=True)

    elif 'aaai' in r.url:
        abstract_elem = soup.find(class_="abstract")
        if abstract_elem and abstract_elem.p:
            abstract = abstract_elem.p.get_text(strip=True)

    elif 'ijcai' in r.url:
        proceedings = soup.find(class_="proceedings-detail")
        if proceedings:
            col = proceedings.find(class_="col-md-12")
            if col:
                abstract = col.get_text(strip=True)

    elif 'springer' in r.url:
        elem = soup.find(id="Abs1-content")
        if elem and elem.next_element:
            abstract = elem.next_element.get_text(strip=True)

    elif 'jmlr' in r.url:
        elem = soup.find(class_="abstract")
        if elem:
            abstract = elem.get_text(strip=True)

    return abstract


def search_from_dblp(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []

    for paper_item in soup.find_all("li", class_="entry"):
        drop_down = paper_item.find("li", class_="drop-down")
        if not drop_down or not drop_down.div or not drop_down.div.a:
            continue
        paper_url = drop_down.div.a.get("href", "")
        if not paper_url:
            continue

        paper_name = paper_item.find(class_="title", itemprop="name")
        if not paper_name:
            continue

        paper_authors = [
            re.sub(r"\d", "", author["title"]).strip()
            for author in paper_item.find_all(class_=None, itemprop="name") if author.has_attr("title")]

        items = [item.string if item.string else item for item in paper_name.contents]
        paper = "".join([item for item in items if isinstance(item, str)])
        try:
            # paper_abstract = search_abs_from_dblp(paper_url)
            paper_abstract = "" # due to limits
        except:
            print(f"Skip url:{paper_url}")
            paper_abstract = ""
        if paper and paper[-1] == ".":
            paper = paper[:-1]
        res[name].append(
            {
                "paper_name": paper, 
                "paper_url": paper_url,
                "paper_authors": paper_authors,
                "paper_abstract": paper_abstract,
                "paper_code": "#",
            }
        )
    return res


def search_abs_from_thecvf(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    abstract_elem = soup.find(id="abstract")
    if abstract_elem:
        return abstract_elem.get_text(strip=True)
    return ""

def search_from_thecvf(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []
        
    for paper_item in soup.find_all("dt", class_="ptitle"):
        a_tag = paper_item.a
        if a_tag is None:
            continue
        href = a_tag.get("href", "")
        if not href:
            continue
        url_postfix = href
        if url_postfix.startswith('/'):
            url_postfix = url_postfix[1:]
        paper_url = "https://openaccess.thecvf.com/" + href
        paper = a_tag.string if a_tag.string else a_tag.get_text(strip=True)
        
        authors = []
        ns = paper_item.next_sibling
        if ns:
            ns2 = ns.next_sibling
            if ns2:
                authors = [author.string for author in ns2.find_all('a', href='#') if author.string]
        
        try:
            paper_abstract = search_abs_from_thecvf(paper_url)
        except:
            print(f"Skip url:{paper_url}")
            paper_abstract = ""
        res[name].append(
            {
                "paper_name": paper, 
                "paper_url": paper_url,
                "paper_authors": authors,
                "paper_abstract": paper_abstract,
                "paper_code": "#",
            }
        )
    return res


# ---------- 代码链接提取（参考 FL-paper-update-tracker） ----------
import re as _re

_GITHUB_RE = _re.compile(
    r"https?://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:/[^\s\)\]\}>\"'`]*)?"
)


def extract_github_link(text: str) -> str:
    """从文本中提取第一个 GitHub 仓库链接，清理尾部标点。"""
    if not text:
        return ""
    matches = _GITHUB_RE.findall(text)
    if not matches:
        return ""
    url = matches[0]
    url = url.rstrip(".,;:'\")]}>")
    return url


def add_code_links(res):
    """扫描论文 abstract 中的 GitHub 链接，补充 code 字段。

    旧逻辑（爬取外部 Markdown 仓库）已废弃，改为直接从 abstract 中
    正则匹配 GitHub 链接。保留已有非 '#' 的 code_links 不变。
    """
    for conf_name, papers in res.items():
        for ii, item in enumerate(papers):
            existing = (item.get("paper_code") or "#").strip()
            if existing and existing != "#":
                continue
            abstract = (item.get("paper_abstract") or "").strip()
            if not abstract:
                continue
            link = extract_github_link(abstract)
            if link:
                papers[ii]["paper_code"] = link
    return res

def collect(cache_file=None, force=False):
    res = {}

    acl_conf = json.load(open("conf/acl_conf.json", "r"))
    dblp_conf = json.load(open("conf/dblp_conf.json", "r"))
    nips_conf = json.load(open("conf/nips_conf.json", "r"))
    iclr_conf = json.load(open("conf/iclr_conf.json", "r"))
    thecvf_conf = json.load(open("conf/thecvf_conf.json", "r"))

    cache_conf = []
    cache_res = {}
    if not force and cache_file is not None and os.path.exists(cache_file):
        # incremental update
        cache_res = load_cache(cache_file)
        cache_conf = [name for name in cache_res.keys()]

    dblp_name_counter = Counter(conf["name"] for conf in dblp_conf if conf.get("name"))
    multi_volume_dblp_names = {
        name for name, count in dblp_name_counter.items() if count > 1
    }

    for conf in tqdm(acl_conf, desc="[+] Collecting ACL", dynamic_ncols=True):
        assert conf.get("name") and conf.get("url") and conf.get("tag")
        url, tag, name = conf["url"], conf["tag"], conf["name"]
        if name in cache_conf:
            continue
        res = search_from_acl(url, tag, name, res)
        
    for conf in tqdm(iclr_conf, desc="[+] Collecting ICLR", dynamic_ncols=True):
        assert conf.get("name") and conf.get("url")
        url, name = conf["url"], conf["name"]
        if name in cache_conf:
            continue
        res = search_from_iclr(url, name, res)
        
    for conf in tqdm(thecvf_conf, desc="[+] Collecting openaccess.thecvf", dynamic_ncols=True):
        assert conf.get("name") and conf.get("url")
        url, name = conf["url"], conf["name"]
        if name in cache_conf:
            continue
        res = search_from_thecvf(url, name, res)
        

    for conf in tqdm(nips_conf, desc="[+] Collecting NeurIPS", dynamic_ncols=True):
        assert conf.get("name") and conf.get("url")
        url, name = conf["url"], conf["name"]
        if name in cache_conf:
            continue
        res = search_from_nips(url, name, res)

    for conf in tqdm(dblp_conf, desc="[+] Collecting DBLP", dynamic_ncols=True):
        assert conf.get("name") and conf.get("url")
        url, name = conf["url"], conf["name"]
        if name in cache_conf and name not in multi_volume_dblp_names:
            continue
        res = search_from_dblp(url, name, res)

    # Keep freshly collected conferences and only backfill untouched cached ones.
    for conf_name, papers in cache_res.items():
        if conf_name not in res:
            res[conf_name] = papers

    res = add_code_links(res)

    return res


def load_cache(path):
    """读取 JSONL，重组为 dict[conf_name] -> list[paper_dict]"""
    data = {}
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                paper = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed JSON on line {line_num} of {path}: {e}")
            if "conf" not in paper or not isinstance(paper["conf"], str):
                raise ValueError(
                    f"Missing or invalid 'conf' field on line {line_num} of {path}"
                )
            conf = paper.pop("conf")
            if conf not in data:
                data[conf] = []
            data[conf].append(paper)
    return data


def save_cache(path, data):
    """将 dict[conf_name] -> list[paper_dict] 写入 JSONL"""
    with open(path, "w", encoding="utf-8") as f:
        for conf, papers in data.items():
            for paper in papers:
                record = dict(paper)
                record["conf"] = conf
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def do_collect(cache_file=None, force=False):
    if force or cache_file is None or not os.path.exists(cache_file):
        print(f"[+] Collecting papers...")
        res = collect(cache_file, force=force)
        save_cache(cache_file, res)
    else:
        print(f"[+] Loading from cache...")
        res = load_cache(cache_file)
    return res


if __name__ == "__main__":
    do_collect(cache_file="cache/cache.jsonl", force=True)
