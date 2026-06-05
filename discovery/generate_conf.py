"""自动发现新会议并生成 conf/*.json"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

from discovery import (
    ACLDiscovery,
    CVFDiscovery,
    NeurIPSDiscovery,
    MLSysDiscovery,
    OpenReviewDiscovery,
    DBLPDiscovery,
)

CONF_DIR = Path("conf")
NAME_PATTERN = re.compile(r"^([A-Za-z]+)(\d+)$")


def load_conf(filename: str) -> list:
    path = CONF_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_conf(filename: str, data: list):
    path = CONF_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"[+] Saved {path} ({len(data)} entries)")


def _parse_conf_name_year(name: str):
    m = NAME_PATTERN.match(name or "")
    if m is None:
        return None, None
    return m.group(1), int(m.group(2))


def _find_insert_index(merged: list, item: dict) -> int:
    """Find a stable insertion index to keep related conferences grouped.

    Priority:
    1) Append after the last item with exactly the same `name`.
    2) Otherwise, insert among same-prefix conference years in chronological order.
    3) Fallback to appending at the end.
    """
    name = item.get("name")

    for i in range(len(merged) - 1, -1, -1):
        if merged[i].get("name") == name:
            return i + 1

    prefix, year = _parse_conf_name_year(name)
    if prefix is None:
        return len(merged)

    insert_after = -1
    first_greater = None
    for i, conf in enumerate(merged):
        conf_prefix, conf_year = _parse_conf_name_year(conf.get("name"))
        if conf_prefix != prefix or conf_year is None:
            continue
        if conf_year <= year:
            insert_after = i
        elif first_greater is None:
            first_greater = i

    if insert_after >= 0:
        return insert_after + 1
    if first_greater is not None:
        return first_greater
    return len(merged)


def merge_conf(existing: list, new: list, key: str = "url") -> list:
    """合并配置，以 url 为唯一键去重"""
    seen = {item[key] for item in existing if key in item}
    merged = list(existing)
    for item in new:
        if item.get(key) not in seen:
            insert_index = _find_insert_index(merged, item)
            merged.insert(insert_index, item)
            seen.add(item[key])
    return merged


def run(
    start_year: int = None,
    end_year: int = None,
    dry_run: bool = False,
    only: str = None,
    soft_timeout: float = None,
):
    if end_year is None:
        end_year = datetime.now().year
    if start_year is None:
        start_year = end_year - 1  # 默认只检查最近两年

    print(f"[*] Discovery range: {start_year} ~ {end_year}")
    if soft_timeout:
        print(f"[*] Soft timeout: {soft_timeout}s ({soft_timeout / 3600:.1f}h)")

    tasks = [
        ("acl_conf.json", ACLDiscovery),
        ("thecvf_conf.json", CVFDiscovery),
        ("nips_conf.json", NeurIPSDiscovery),
        ("nips_conf.json", MLSysDiscovery),  # 合并到 nips_conf.json
        ("iclr_conf.json", OpenReviewDiscovery),
        ("dblp_conf.json", DBLPDiscovery),
    ]

    # 按文件名分组
    grouped = {}
    for filename, cls in tasks:
        if only and filename != only:
            continue
        grouped.setdefault(filename, []).append(cls)

    start_time = time.time()

    def _is_timeout():
        if soft_timeout and start_time is not None:
            elapsed = time.time() - start_time
            if elapsed >= soft_timeout:
                print(f"[!] Soft timeout ({soft_timeout}s, elapsed {elapsed:.0f}s) reached.")
                return True
        return False

    # 预加载其他信源配置，供 DBLP 去重使用
    other_confs = []
    for other_file in ["acl_conf.json", "iclr_conf.json", "nips_conf.json", "thecvf_conf.json"]:
        other_path = CONF_DIR / other_file
        if other_path.exists():
            other_confs.extend(load_conf(other_file))

    for filename, classes in grouped.items():
        existing = load_conf(filename)
        all_new = []
        for cls in classes:
            if _is_timeout():
                break
            print(f"[*] Running {cls.__name__} for {filename} ...")
            if cls.__name__ == "DBLPDiscovery":
                inst = cls(existing_conf=existing, other_confs=other_confs)
            else:
                inst = cls(existing_conf=existing)
            try:
                new = inst.discover(start_year, end_year)
            except Exception as e:
                print(f"[!] {cls.__name__} failed: {e}")
                continue
            print(f"    Found {len(new)} new entries")
            all_new.extend(new)

        merged = merge_conf(existing, all_new)
        if dry_run:
            print(f"[DRY-RUN] {filename}: would add {len(merged) - len(existing)} entries")
            for item in all_new[:5]:
                print(f"    + {item}")
            if len(all_new) > 5:
                print(f"    ... and {len(all_new) - 5} more")
        else:
            save_conf(filename, merged)

        if _is_timeout():
            print("[!] Stopping due to soft timeout. Partial results have been saved.")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-discover conference configs")
    parser.add_argument("--start-year", type=int, help="Start year (inclusive)")
    parser.add_argument("--end-year", type=int, help="End year (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    parser.add_argument("--only", type=str, help="Only process one conf file, e.g. acl_conf.json")
    parser.add_argument("--soft-timeout", type=float, default=None,
                        help="Soft timeout in seconds. Save progress and exit gracefully when reached (e.g. 18000 for 5h)")
    args = parser.parse_args()

    run(
        start_year=args.start_year,
        end_year=args.end_year,
        dry_run=args.dry_run,
        only=args.only,
        soft_timeout=args.soft_timeout,
    )
