import argparse
import os
import sys
import json
import re
from datetime import datetime
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from collector import collect, save_cache, load_cache

try:
    from wordcloud import WordCloud
except ImportError:
    WordCloud = None

COMMENT_CONFS_LIST_START = "<!-- confs-list-start -->"
COMMENT_CONFS_LIST_END = "<!-- confs-list-end -->"
COMMENT_STATS_START = "<!-- stats-start -->"
COMMENT_STATS_END = "<!-- stats-end -->"
COMMENT_RECENT_UPDATE_START = "<!-- recent-update-start -->"
COMMENT_RECENT_UPDATE_END = "<!-- recent-update-end -->"
COMMENT_AUTO_SUMMARY_START = "<!-- auto-summary-start -->"
COMMENT_AUTO_SUMMARY_END = "<!-- auto-summary-end -->"

cache_path = os.path.join(os.path.dirname(__file__), "cache", "cache.jsonl")
readme_path = "README.md"
readme_en_path = "README.en.md"
acl_conf_path = os.path.join(os.path.dirname(__file__), "conf", "acl_conf.json")
dblp_conf_path = os.path.join(os.path.dirname(__file__), "conf", "dblp_conf.json")
nips_conf_path = os.path.join(os.path.dirname(__file__), "conf", "nips_conf.json")
iclr_conf_path = os.path.join(os.path.dirname(__file__), "conf", "iclr_conf.json")
thecvf_conf_path = os.path.join(os.path.dirname(__file__), "conf", "thecvf_conf.json")
stats_dir = os.path.join(os.path.dirname(__file__), "pics", "stats")
meta_path = os.path.join(os.path.dirname(__file__), "cache", "readme_meta.json")

# Nature-inspired color palette (muted, professional)
NATURE_COLORS = [
    "#2E5C8A", "#7BA05B", "#C44E52", "#DD8452",
    "#9370DB", "#55A3B9", "#8C8C8C", "#E3A018",
    "#4C4C4C", "#A0C4E8",
]

CATEGORY_MAP = {
    "机器学习": ["ICML", "NIPS", "ICLR", "COLT", "AISTATS", "MLSYS", "JMLR", "TNNLS", "AI"],
    "自然语言处理": ["ACL", "EMNLP", "NAACL", "EACL", "COLING", "TASLP"],
    "计算机视觉": ["CVPR", "ICCV", "ECCV", "WACV", "TIP", "TPAMI", "IJCV", "BMVC", "MICCAI"],
    "数据挖掘与信息检索": ["KDD", "SIGIR", "CIKM", "WSDM", "ECIR", "WWW", "ICDM", "RECSYS"],
    "数据库与系统": ["VLDB", "SIGMOD", "TKDE", "TOIS", "FAST", "TCAD", "TC", "TOS", "TPDS"],
    "语音与多媒体": ["ICASSP", "INTERSPEECH", "MM", "ICME"],
    "人工智能综合": ["AAAI", "IJCAI", "MLJ"],
    "网络与安全": ["SIGCOMM", "NSDI", "MOBICOM", "INFOCOM", "NDSS", "SP", "DAC"],
    "其他": ["ISWC", "STOC"],
}

CATEGORY_MAP_EN = {
    "Machine Learning": ["ICML", "NIPS", "ICLR", "COLT", "AISTATS", "MLSYS", "JMLR", "TNNLS", "AI"],
    "Natural Language Processing": ["ACL", "EMNLP", "NAACL", "EACL", "COLING", "TASLP"],
    "Computer Vision": ["CVPR", "ICCV", "ECCV", "WACV", "TIP", "TPAMI", "IJCV", "BMVC", "MICCAI"],
    "Data Mining & Information Retrieval": ["KDD", "SIGIR", "CIKM", "WSDM", "ECIR", "WWW", "ICDM", "RECSYS"],
    "Database & Systems": ["VLDB", "SIGMOD", "TKDE", "TOIS", "FAST", "TCAD", "TC", "TOS", "TPDS"],
    "Speech & Multimedia": ["ICASSP", "INTERSPEECH", "MM", "ICME"],
    "General AI": ["AAAI", "IJCAI", "MLJ"],
    "Networking & Security": ["SIGCOMM", "NSDI", "MOBICOM", "INFOCOM", "NDSS", "SP", "DAC"],
    "Others": ["ISWC", "STOC"],
}

# Map each publication series to its category color for consistent theming across charts
SERIES_COLOR_MAP = {}
for idx, names in enumerate(CATEGORY_MAP.values()):
    color = NATURE_COLORS[idx % len(NATURE_COLORS)]
    for name in names:
        SERIES_COLOR_MAP[name] = color


def _ensure_chinese_font():
    """Configure matplotlib to support Chinese characters on Windows."""
    plt.rcParams["font.sans-serif"] = ["SimHei", "Noto Sans SC", "Microsoft YaHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["axes.labelweight"] = "bold"
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["figure.titleweight"] = "bold"
    plt.rcParams["axes.labelcolor"] = "#1a1a1a"
    plt.rcParams["axes.edgecolor"] = "#1a1a1a"
    plt.rcParams["xtick.color"] = "#1a1a1a"
    plt.rcParams["ytick.color"] = "#1a1a1a"


def generate_new_readme(src: str, content: str, start_comment: str, end_comment: str) -> str:
    """Generate a new Readme.md by replacing content between markers."""
    pattern = f"{start_comment}[\\s\\S]+{end_comment}"
    repl = f"{start_comment}\n\n{content}\n\n{end_comment}"
    if re.search(pattern, src) is None:
        print(f"can not find section in src, please check it, it should be {start_comment} and {end_comment}")
        return src
    return re.sub(pattern, repl, src)


def _load_all_confs():
    """Load all conference configs and return a dict of {upper_name: set(years)}."""
    confs_list = {}
    for files in [acl_conf_path, dblp_conf_path, nips_conf_path, iclr_conf_path, thecvf_conf_path]:
        with open(files, "r", encoding="utf-8") as f:
            for conf in json.load(f):
                m = re.search(r"\d{4}", conf["name"])
                if not m:
                    continue
                year = m.group()
                conf_name = conf["name"][: m.start()].strip().upper()
                confs_list.setdefault(conf_name, set()).add(year)
    return confs_list


def compute_stats(cache_data: dict):
    """Compute statistics from cache data."""
    total_papers = sum(len(papers) for papers in cache_data.values())
    total_abstracts = 0
    papers_by_year = defaultdict(int)
    papers_by_conf = defaultdict(int)
    for conf_key, papers in cache_data.items():
        m = re.match(r"([A-Za-z]+)(\d{4})", conf_key)
        conf_base = m.group(1).upper() if m else conf_key
        year = m.group(2) if m else "Unknown"
        papers_by_conf[conf_base] += len(papers)
        papers_by_year[year] += len(papers)
        for p in papers:
            if p.get("paper_abstract") and str(p.get("paper_abstract")).strip():
                total_abstracts += 1

    confs_list = _load_all_confs()
    total_series = len(confs_list)
    total_instances = sum(len(years) for years in confs_list.values())

    # Category stats
    cat_stats = {}
    for cat, names in CATEGORY_MAP.items():
        cnt = sum(papers_by_conf.get(n, 0) for n in names)
        cat_stats[cat] = cnt

    return {
        "total_papers": total_papers,
        "total_abstracts": total_abstracts,
        "total_series": total_series,
        "total_instances": total_instances,
        "papers_by_year": dict(sorted(papers_by_year.items())),
        "papers_by_conf": dict(papers_by_conf),
        "cat_stats": cat_stats,
    }


def generate_charts(stats: dict):
    """Generate Nature-style statistical charts with bilingual labels and bold fonts."""
    _ensure_chinese_font()
    os.makedirs(stats_dir, exist_ok=True)

    # Bilingual category labels aligned with CATEGORY_MAP + CATEGORY_MAP_EN order
    cat_labels_bilingual = [f"{zh}\n({en})" for zh, en in zip(CATEGORY_MAP.keys(), CATEGORY_MAP_EN.keys())]

    # ---------- Chart 1: Papers by Category (horizontal bar) ----------
    fig, ax = plt.subplots(figsize=(11, 6))
    cats = list(stats["cat_stats"].keys())
    vals = list(stats["cat_stats"].values())
    colors = [NATURE_COLORS[i % len(NATURE_COLORS)] for i in range(len(cats))]

    bars = ax.barh(cat_labels_bilingual, vals, color=colors, height=0.55, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("论文数量 (Paper Count)", fontsize=13, fontweight="bold")
    ax.set_title("各研究领域论文分布 (Papers by Research Field)", fontsize=15, fontweight="bold", pad=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", labelsize=10, labelcolor="#1a1a1a")
    ax.invert_yaxis()

    for bar in bars:
        width = bar.get_width()
        ax.text(width + max(vals) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{int(width):,}", ha="left", va="center", fontsize=10, fontweight="bold", color="#1a1a1a")

    ax.set_xlim(0, max(vals) * 1.15)
    ax.grid(axis="x", linestyle="--", linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(stats_dir, "papers_by_category.png"), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # ---------- Chart 2: Papers by Year (vertical bar) ----------
    fig, ax = plt.subplots(figsize=(10, 4.8))
    years = [y for y in stats["papers_by_year"].keys()]
    year_vals = [stats["papers_by_year"][y] for y in years]
    ax.bar(years, year_vals, color="#2E5C8A", width=0.65, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("年份 (Year)", fontsize=13, fontweight="bold")
    ax.set_ylabel("论文数量 (Paper Count)", fontsize=13, fontweight="bold")
    ax.set_title("历年论文收录趋势 (Annual Paper Collection Trend)", fontsize=15, fontweight="bold", pad=18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(axis="both", labelsize=10, labelcolor="#1a1a1a")
    ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(stats_dir, "papers_by_year.png"), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # ---------- Chart 3: Overview Infographic (big numbers) ----------
    fig, ax = plt.subplots(figsize=(10, 2.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.4)
    ax.axis("off")

    metrics = [
        ("收录刊物系列\nPublication Series", f"{stats['total_series']}", NATURE_COLORS[0]),
        ("会议/年份实例\nConf / Year Instances", f"{stats['total_instances']}", NATURE_COLORS[1]),
        ("总论文数量\nTotal Papers", f"{stats['total_papers']:,}", NATURE_COLORS[2]),
        ("含摘要论文\nPapers w/ Abstract", f"{stats['total_abstracts']:,}", NATURE_COLORS[5]),
    ]
    n = len(metrics)
    x_positions = [1.25 + i * 2.5 for i in range(n)]
    for (label, value, color), x in zip(metrics, x_positions):
        ax.text(x, 1.55, value, fontsize=32, fontweight="black", ha="center", va="center", color=color)
        ax.text(x, 0.55, label, fontsize=12, ha="center", va="center", color="#444444", linespacing=1.4)
        if x < x_positions[-1]:
            ax.plot([x + 1.25, x + 1.25], [0.25, 1.85], color="#DDDDDD", linewidth=0.8)

    fig.tight_layout()
    fig.savefig(os.path.join(stats_dir, "stats_overview.png"), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def generate_wordcloud(stats: dict):
    """Generate a horizontal wordcloud of publication series weighted by paper count."""
    if WordCloud is None:
        print("[!] wordcloud package not installed, skipping wordcloud generation.")
        return

    _ensure_chinese_font()
    os.makedirs(stats_dir, exist_ok=True)

    frequencies = stats.get("papers_by_conf", {})
    if not frequencies:
        return

    wc = WordCloud(
        width=2400,
        height=900,
        background_color="white",
        max_words=100,
        relative_scaling=0.6,
        prefer_horizontal=0.92,
        min_font_size=12,
        max_font_size=260,
        color_func=lambda word, *args, **kwargs: SERIES_COLOR_MAP.get(word, "#8C8C8C"),
        random_state=42,
    ).generate_from_frequencies(frequencies)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.savefig(os.path.join(stats_dir, "wordcloud.png"), dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _build_hierarchical_confs_list(category_map, lang: str = "zh"):
    """Build a hierarchical markdown list of conferences grouped by category."""
    confs = _load_all_confs()
    assigned = set()
    lines = []

    series_label = "个系列" if lang == "zh" else "series"
    edition_label = "届" if lang == "zh" else "editions"
    others_label = "其他" if lang == "zh" else "Others"

    for cat, names in category_map.items():
        cat_confs = []
        for n in names:
            if n in confs:
                years = sorted(confs[n])
                cat_confs.append((n, years))
                assigned.add(n)
        if not cat_confs:
            continue
        cat_confs.sort(key=lambda x: x[0])
        lines.append(f"<details>\n<summary><b>{cat}</b> ({len(cat_confs)} {series_label})</summary>\n\n")
        for name, years in cat_confs:
            line = f"- **{name}** {min(years)}-{max(years)}"
            if len(years) > 1:
                line += f" ({len(years)} {edition_label})"
            lines.append(line + "\n")
        lines.append("\n</details>\n")

    # Any unassigned conferences
    unassigned = sorted(set(confs.keys()) - assigned)
    if unassigned:
        lines.append(f"<details>\n<summary><b>{others_label}</b> ({len(unassigned)} {series_label})</summary>\n\n")
        for name in unassigned:
            years = sorted(confs[name])
            line = f"- **{name}** {min(years)}-{max(years)}"
            if len(years) > 1:
                line += f" ({len(years)} {edition_label})"
            lines.append(line + "\n")
        lines.append("\n</details>\n")

    return "".join(lines)


def build_hierarchical_confs_list():
    return _build_hierarchical_confs_list(CATEGORY_MAP, lang="zh")


def build_hierarchical_confs_list_en():
    return _build_hierarchical_confs_list(CATEGORY_MAP_EN, lang="en")


def _read_meta():
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_meta(meta):
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _round_down_to_ten_thousand(n: int) -> int:
    return (n // 10000) * 10000


def build_auto_summary(stats: dict):
    total_rounded = _round_down_to_ten_thousand(stats["total_papers"])
    line = f"- 数据库已收录 **{total_rounded:,}+** 篇论文，覆盖 NLP、CV、ML、DM、DB、Speech 等 {stats['total_series']}+ 个顶级会议与期刊。"
    return line


def build_auto_summary_en(stats: dict):
    total_rounded = _round_down_to_ten_thousand(stats["total_papers"])
    line = f"- The database contains **{total_rounded:,}+** papers spanning {stats['total_series']}+ top-tier conferences and journals across NLP, CV, ML, DM, DB, and Speech."
    return line


def build_recent_update_brief(meta: dict, stats: dict):
    """Build the recent update brief markdown."""
    last_date = meta.get("last_update", datetime.now().strftime("%Y-%m-%d"))
    new_papers = meta.get("new_papers", 0)
    new_confs = meta.get("new_conferences", 0)

    lines = [
        f"- 📅 **最近更新日期**: {last_date}",
        f"- 🆕 **本次新增论文**: {new_papers:,} 篇",
    ]
    if new_confs:
        lines.append(f"- 📢 **本次新增会议**: {new_confs} 个")
    lines.append(f"- 📊 **数据库规模**: {stats['total_papers']:,} 篇论文 / {stats['total_series']} 个刊物系列 / {stats['total_abstracts']:,} 篇含摘要")

    return "\n".join(lines)


def build_recent_update_brief_en(meta: dict, stats: dict):
    """Build the English recent update brief markdown."""
    last_date = meta.get("last_update", datetime.now().strftime("%Y-%m-%d"))
    new_papers = meta.get("new_papers", 0)
    new_confs = meta.get("new_conferences", 0)

    lines = [
        f"- 📅 **Last Updated**: {last_date}",
        f"- 🆕 **New Papers This Update**: {new_papers:,}",
    ]
    if new_confs:
        lines.append(f"- 📢 **New Conferences This Update**: {new_confs}")
    lines.append(f"- 📊 **Database Scale**: {stats['total_papers']:,} papers / {stats['total_series']} publication series / {stats['total_abstracts']:,} with abstracts")

    return "\n".join(lines)


def build_stats_section():
    """Build the statistics markdown section referencing generated images."""
    lines = [
        '<p align="center">',
        '  <img src="./pics/stats/stats_overview.png" alt="统计概览" width="850" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/wordcloud.png" alt="刊物系列词云" width="900" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/papers_by_category.png" alt="各领域论文数量" width="800" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/papers_by_year.png" alt="历年论文收录趋势" width="800" />',
        "</p>",
    ]
    return "\n".join(lines)


def build_stats_section_en():
    """Build the English statistics markdown section referencing generated images."""
    lines = [
        '<p align="center">',
        '  <img src="./pics/stats/stats_overview.png" alt="Statistics Overview" width="850" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/wordcloud.png" alt="Publication Series Word Cloud" width="900" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/papers_by_category.png" alt="Papers by Research Field" width="800" />',
        "</p>",
        "",
        '<p align="center">',
        '  <img src="./pics/stats/papers_by_year.png" alt="Annual Paper Collection Trend" width="800" />',
        "</p>",
    ]
    return "\n".join(lines)


def _update_single_readme(path: str, lang: str, stats: dict, meta: dict):
    """Update a single README file (zh or en)."""
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    # Update auto-summary
    if lang == "zh":
        summary_md = build_auto_summary(stats)
    else:
        summary_md = build_auto_summary_en(stats)
    src = generate_new_readme(src, summary_md, COMMENT_AUTO_SUMMARY_START, COMMENT_AUTO_SUMMARY_END)

    # Update recent update section
    if lang == "zh":
        brief_md = build_recent_update_brief(meta, stats)
    else:
        brief_md = build_recent_update_brief_en(meta, stats)
    src = generate_new_readme(src, brief_md, COMMENT_RECENT_UPDATE_START, COMMENT_RECENT_UPDATE_END)

    # Update stats section
    if lang == "zh":
        stats_md = build_stats_section()
    else:
        stats_md = build_stats_section_en()
    src = generate_new_readme(src, stats_md, COMMENT_STATS_START, COMMENT_STATS_END)

    # Update confs list
    if lang == "zh":
        confs_md = build_hierarchical_confs_list()
    else:
        confs_md = build_hierarchical_confs_list_en()
    src = generate_new_readme(src, confs_md, COMMENT_CONFS_LIST_START, COMMENT_CONFS_LIST_END)

    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def update_readme():
    cache_data = load_cache(cache_path) if os.path.exists(cache_path) else {}
    stats = compute_stats(cache_data)
    meta = _read_meta()

    # Generate charts (shared between zh and en)
    generate_charts(stats)
    generate_wordcloud(stats)

    # Update Chinese README
    _update_single_readme(readme_path, "zh", stats, meta)

    # Update English README
    if os.path.exists(readme_en_path):
        _update_single_readme(readme_en_path, "en", stats, meta)


def force_update():
    res = collect(cache_file=None, force=True)
    save_cache(cache_path, res)
    stats = compute_stats(res)
    meta = {
        "last_update": datetime.now().strftime("%Y-%m-%d"),
        "new_papers": stats["total_papers"],
        "new_conferences": stats["total_instances"],
    }
    _write_meta(meta)
    update_readme()


def incremental_update(soft_timeout=None):
    """增量收集：只收集 conf 中有但 cache 中没有的会议，并更新 README。"""
    if not os.path.exists(cache_path):
        print("[!] Cache file not found, falling back to force update...")
        force_update()
        return

    print("[+] Running incremental collection...")
    if soft_timeout:
        print(f"[*] Soft timeout: {soft_timeout}s ({soft_timeout/3600:.1f}h)")
    before = load_cache(cache_path)
    before_count = sum(len(papers) for papers in before.values())
    before_confs = set(before.keys())

    res = collect(cache_file=cache_path, force=False, soft_timeout=soft_timeout)
    save_cache(cache_path, res)

    after_count = sum(len(papers) for papers in res.values())
    new_confs = set(res.keys()) - before_confs
    new_papers = after_count - before_count
    print(f"[+] Collected {new_papers} new papers across {len(new_confs)} new conference(s).")
    if new_confs:
        print(f"    New conferences: {', '.join(sorted(new_confs))}")

    failures_path = os.path.join(os.path.dirname(cache_path), "collect_failures.json")
    if os.path.exists(failures_path):
        try:
            with open(failures_path, "r", encoding="utf-8") as f:
                failures = json.load(f)
            if failures:
                print(f"[!] Previous/current run had {len(failures)} failure(s). They will be retried in the next run.")
        except Exception:
            pass

    meta = {
        "last_update": datetime.now().strftime("%Y-%m-%d"),
        "new_papers": new_papers,
        "new_conferences": len(new_confs),
    }
    _write_meta(meta)

    update_readme()
    print("[+] README updated.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaperVault maintenance utilities")
    parser.add_argument("command", nargs="?", choices=["force", "collect"], help="Command to run")
    parser.add_argument("--soft-timeout", type=float, default=None, help="Soft timeout in seconds (e.g. 18000 for 5h)")
    args = parser.parse_args()

    if args.command == "force":
        force_update()
    elif args.command == "collect":
        incremental_update(soft_timeout=args.soft_timeout)
    else:
        update_readme()
