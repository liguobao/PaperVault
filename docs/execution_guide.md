# PaperVault 后续任务执行指南

> 分支：`analyze-sources`
> 本文件记录已完成的任务和待执行的后续操作，供随时恢复工作时参考。

---

## 一、已完成的任务（按提交顺序）

| Commit | 说明 |
|:---|:---|
| `19256b5` | 完成 `cache.jsonl` URL 分布与来源分析报告 (`docs/source_analysis.md`) |
| `2dfbffd` | 完成自动化获取规划文档 (`docs/automation_plan.md`) |
| `84a64ca` | 实现自动发现模块 `discovery/`（ACL/CVF/NeurIPS/MLSys/OpenReview/DBLP） |
| `10e37ef` | 修复 ACL Anthology 采集器适配新版页面结构（events→volume 跳转） |
| `18b6182` | 自动生成 2024/2025 会议配置（CVPR/ICCV/WACV/NeurIPS/MLSys/ACL 等） |
| `30ada73` | 新增 GitHub Actions 自动发现工作流（每月运行） |
| `f7f7933` | 将自动发现工作流改为**每天**运行 |
| `e33006f` | 修复 Discovery 模块连接池问题（每次请求新建 Session） |
| `9ff4ac9` | 实现期刊卷号自动映射（JMLR/VLDB/TIP/TPAMI/TKDE 等 9 种） |
| `477ad16` | 自动生成本科 2023–2025 DBLP 配置（新增 73 条，含期刊） |
| `057feae` | 补充 FL-tracker 参考的 16 个会议 + 8 个期刊到 DBLP 发现模块 |
| `b7de928` | 实现 Abstract 批量回填脚本（Crossref→SS→arXiv→OpenAlex） |
| `8108f99` | 替换废弃的代码链接采集方案为基于 Abstract 的正则扫描 |

---

## 二、待执行任务

### 任务 1：生成新会议/期刊配置（Phase 1B）

在 `discovery/dblp.py` 中已新增以下 venue 定义，但**尚未执行查询生成配置**：

- **会议（16 个）**：ALT, UAI, OSDI, SOSP, ISCA, EuroSys, SIGCOMM, INFOCOM, MobiCom, NSDI, DAC, NDSS, IEEE S&P, USENIX Security, ICSE, STOC
- **期刊（8 个）**：AI, MLJ, TOCS, TOS, TPDS, TCAD, TC, FOCS

**执行命令**：
```bash
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm
python -m discovery.generate_conf --start-year 2019 --end-year 2025
```

**预期结果**：`conf/dblp_conf.json` 自动追加新发现的 venue 条目。
**前置检查**：可先 review `discovery/dblp.py` 中的 `CONFERENCES` 和 `JOURNALS` 定义，确认 venue 名称和卷号公式无误。

---

### 任务 2：Abstract 批量回填（分三阶段执行）

当前 `cache/cache.jsonl` 中共有 **63,906** 条论文缺少 abstract（占 67.5%）。
脚本位置：`scripts/fetch_abstracts.py`

#### Phase A — 暖身轮（最新年份，约 5,000 条，预计 2–4 小时）
```bash
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm
python scripts/fetch_abstracts.py --phase a --chunk-size 500
```
- 目标：2024–2025 年所有会议的论文
- 特点：新论文 DOI 命中率高，Crossref/Semantic Scholar 通常一次成功

#### Phase B — 核心会议（约 25,000 条，预计 8–15 小时）
```bash
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm
python scripts/fetch_abstracts.py --phase b --chunk-size 1000
```
- 目标：NeurIPS, ICML, ICLR, CVPR, ICCV, ECCV, ACL, EMNLP, NAACL, COLING, AAAI, IJCAI, KDD, SIGIR, WWW, MM（2020–2023）

#### Phase C — 广泛回填（约 30,000 条，预计 10–20 小时）
```bash
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm
python scripts/fetch_abstracts.py --phase c --chunk-size 1000
```
- 目标：剩余所有 2019–2023 年论文（ICASSP, INTERSPEECH, MICCAI, CIKM, WSDM, BMVC, 期刊等）

#### 可选：重试失败项 / 单个会议
```bash
# 重试所有之前未获取到 abstract 的论文
python scripts/fetch_abstracts.py --phase all --retry-failed

# 只处理单个会议
python scripts/fetch_abstracts.py --conf AAAI2024 --chunk-size 500
```

**断点续传**：
- 进度自动保存到 `cache/abstract_backfill_progress.json`
- 每次启动脚本会自动跳过已处理的论文
- 可随时中断（Ctrl+C），下次运行自动恢复

**环境建议**：
```bash
# 设置联系邮箱（进入 Crossref polite pool，降低被限流概率）
export CONTACT_EMAIL=your_email@example.com
```

---

### 任务 3：代码链接扫描

脚本位置：`scripts/fetch_code_links.py`

**执行命令**：
```bash
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm
python scripts/fetch_code_links.py --year all
```

**执行时机**：建议在 **Phase A/B/C abstract 回填完成后**运行，这样新补充的 abstract 中的 GitHub 链接也能被扫描到。

**特点**：
- 纯正则匹配，无网络请求，处理全部 9 万条论文仅需数分钟
- 保留已有非 `#` 的 `paper_code` 不变
- 如果后续补充了更多 abstract，可重新运行：
  ```bash
  python scripts/fetch_code_links.py --year all --retry-failed
  ```

---

### 任务 4：提交 cache 更新

`cache/cache.jsonl` 由 Git LFS 管理。每完成一个 major phase 后建议提交：

```bash
git add cache/cache.jsonl cache/abstract_backfill_progress.json
git commit -m "chore: abstract backfill phase X completed"
```

**注意**：
- `cache/cache.jsonl` 文件很大，提交前确认 Git LFS 已安装且工作正常
- `cache/abstract_backfill_progress.json` 也应一并提交，便于其他环境恢复进度

---

## 三、快速参考卡片

```bash
# 激活环境
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm

# 生成新配置（新增 venue）
python -m discovery.generate_conf --start-year 2019 --end-year 2025

# Abstract 回填（三阶段）
python scripts/fetch_abstracts.py --phase a --chunk-size 500   # 2-4h
python scripts/fetch_abstracts.py --phase b --chunk-size 1000  # 8-15h
python scripts/fetch_abstracts.py --phase c --chunk-size 1000  # 10-20h

# 代码链接扫描（快）
python scripts/fetch_code_links.py --year all

# 验证配置 JSON 有效性
python -c "import json; [json.load(open(f)) for f in ['conf/acl_conf.json','conf/dblp_conf.json','conf/iclr_conf.json','conf/nips_conf.json','conf/thecvf_conf.json']]"
```

---

## 四、风险提醒

1. **Abstract 回填耗时长**：63,906 条空 abstract 全部处理完预计需要 **20–40 小时**的墙钟时间。请利用断点续传机制分多次执行。
2. **API 限流**：Crossref / Semantic Scholar / OpenAlex 均有可能返回 429。脚本已内置指数退避（遇到 429 自动等待），请勿频繁重启脚本。
3. **Cache 文件大**：`cache.jsonl` 约数百 MB，Git LFS 推送可能需要较长时间。
