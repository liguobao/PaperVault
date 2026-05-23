import json
import os
import re
import yaml
import requests
import time
from bs4 import BeautifulSoup
from tqdm import tqdm

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
}

def search_from_iclr(url, name, res):
    r = requests.get(url, headers=HEADERS)
    data = r.json()
    if name not in res:
        res[name] = []
    for item in data["notes"]:
        res[name].append(
            {
                "paper_name": item["content"]["title"], 
                "paper_url": "https://openreview.net/pdf?id=" + item["id"],
                "paper_authors": item["content"]["authors"],
                "paper_abstract": item['content']['abstract'],
                "paper_code": "#",
            }
        )
    return res

def search_abs_from_nips(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    abstract = soup.find(
        lambda tag: tag.name == "h4" and 'Abstract' in tag.text
    ).next_sibling.next_sibling.text.strip()
    return abstract

def search_from_nips(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []
    url_prefix = "https://" + url[8:].split("/")[0]
    for paper_item in soup.find(class_="col").ul.find_all("li"):
        paper_url = url_prefix + paper_item.a["href"]
        if paper_item.i.string is not None:
            paper_author = [author.strip() for author in paper_item.i.string.split(',')]
        else:
            paper_author = []
        try:
            paper_abstract = search_abs_from_nips(paper_url)
        except:
            print(f"Skip url:{paper_url}")
            paper_abstract = ""

        res[name].append(
            {
                "paper_name": paper_item.a.string, 
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

    if 'ieee' in r.url:
        abstract = yaml.safe_load(soup.find(
            lambda tag: tag.name == 'script' and 'xplGlobal.document.metadata' in tag.text
        ).text.split('\n\t')[-1].strip()[28:-1])['abstract']

    elif 'acm' in r.url:
        abstract = soup.find(class_="abstractSection").p.text.strip()

    elif 'openreview' in r.url:
        url = 'https://api.openreview.net/notes?forum=' + r.url.split("=")[-1]
        r = requests.get(url, headers=HEADERS)
        abstract = r.json()["notes"][-1]["content"]["abstract"]

    elif 'mlr.press' in r.url:
        abstract = soup.find(id="abstract").text.strip()

    elif 'aaai' in r.url:
        abstract = soup.find(class_="abstract").p.text.strip()

    elif 'ijcai' in r.url:
        abstract = soup.find(class_="proceedings-detail").find(class_="col-md-12").text.strip()

    elif 'springer' in r.url:
        abstract = soup.find(id="Abs1-content").next_element.text.strip()

    elif 'jmlr' in r.url:
        abstract = soup.find(class_="abstract").text.strip()

    else:
        abstract = ""

    return abstract


def search_from_dblp(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []

    for paper_item in soup.find_all("li", class_="entry"):
        paper_url = paper_item.find("li", class_="drop-down").div.a["href"]
        paper_name = paper_item.find(class_="title", itemprop="name")

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
        if paper[-1] == ".":
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
    abstract = soup.find(id="abstract").text.strip()
    return abstract

def search_from_thecvf(url, name, res):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    if name not in res:
        res[name] = []
        
    for paper_item in soup.find_all("dt", class_="ptitle"):
        url_postfix = paper_item.a["href"]
        if url_postfix[0] == '/':
            url_postfix = url_postfix[1:]
        paper_url = "https://openaccess.thecvf.com/" + paper_item.a["href"]
        paper = paper_item.a.string
        paper_authors = [author.string for author in paper_item.next_sibling.next_sibling.find_all('a', href='#')]
        try:
            paper_abstract = search_abs_from_thecvf(paper_url)
        except:
            print(f"Skip url:{paper_url}")
            paper_abstract = ""
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


def get_code_links(url):
    r = requests.get(url, headers=HEADERS)
    texts = [[text.strip().split('\r\n\r\n')[0].split('\n')[0].replace('#','').strip(), 
              text.strip().split('代码链接')[-1].replace('：',':').replace(':[','').replace(':h','h')
            ]for text in r.text.split('####') if text != '']
    for i, text in enumerate(texts):
        try:
            idx = texts[i][1].rindex('](')
            texts[i][1] = texts[i][1][:idx]
        except:
            pass
        try:
            idx = texts[i][1].rindex(')')
            texts[i][1] = texts[i][1][:idx]
        except:
            pass
    texts = [text for text in texts if text[1].startswith("http")]
    return texts

def add_code_links(res):
    url = 'https://github.com/MLNLP-World/Top-AI-Conferences-Paper-with-Code'
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    urls = [url['href'] for url in soup.find('table').find_all('a')]
    urls = {url.split('/')[-1][:-3].upper().replace('-','').replace('EUR',''):
            url.replace('github.com', 'raw.githubusercontent.com').replace('blob/','') for url in urls}

    for conf in urls:
        code_url = urls[conf]
        code_data = get_code_links(code_url)
        flag = False
        if conf not in res:
            continue
        for title, link in code_data:
            for ii, item in enumerate(res[conf]):
                paper_name = item['paper_name']
                if paper_name.endswith('.'):
                    paper_name = paper_name[:-1]
                if title.lower() == paper_name.lower():
                    flag = True
                    res[conf][ii]['paper_code'] = link
                    break
            if not flag:
                print(f"[!] Warning: no matching paper found in cache for code-link title: {title!r} (conf={conf})")
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
        if name in cache_conf:
            continue
        res = search_from_dblp(url, name, res)
     
    res.update(cache_res)

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
