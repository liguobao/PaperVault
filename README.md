<p align="center">
<h1 align="center"> <img src="./pics/icon/ai.png" width="30" /> PaperVault</h1>
</p>
<p align="center">
  <a href="README.en.md">English</a> | <strong>简体中文</strong>
</p>

## :jack_o_lantern: 项目简介

PaperVault 是一个用于收集和检索人工智能领域学术论文的全自动化工具，覆盖自然语言处理（NLP）、计算机视觉（CV）、机器学习（ML）、数据挖掘（DM）、数据库（DB）、语音以及系统、安全、网络、理论计算机科学等多个方向的顶级学术会议与期刊。

## 🚧 项目状态

> **本项目仍在积极施工中。**

### 当前阶段
- 正在大幅扩展论文收录范围，重点补充 **2020 年至今** 的更多优质期刊（如 TIP、TPAMI、TKDE、TNNLS、TASLP、IJCV 等）以及主流出版社（如 IEEE、ACM、Springer、Elsevier 等）的论文清单。
- 已通过自动化脚本和 GitHub Actions 批量为论文填充 **摘要（abstract）** 信息，提升检索价值。
- 数据库已收录 **94,000+** 篇论文，覆盖 NLP、CV、ML、DM、DB、Speech 等 40+ 个顶级会议与期刊。

### 下阶段目标
- 升级前后端技术栈，优化搜索体验与界面设计。
- 重新部署并上线 Web 搜索服务，支持更高效的论文检索与浏览。

### 项目历程
PaperVault 由 [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector) 演进而来（fork 来源详见下方致谢），正在将其从一个静态论文清单工具逐步建设为一个功能完善、数据丰富的在线学术搜索引擎。

## :open_book: 收录会议范围

<!-- confs-list-start -->

> 当前数据库覆盖 **2019-2026** 年，共收录 **60+** 个顶级会议与期刊。

### 自然语言处理 (NLP)
- **会议**：ACL · EMNLP · NAACL · COLING · EACL
- **期刊**：TASLP

### 计算机视觉 (CV)
- **会议**：CVPR · ICCV · ECCV · WACV · BMVC
- **期刊**：TIP · TPAMI · IJCV

### 机器学习 (ML)
- **会议**：ICML · ICLR · NIPS · COLT · AISTATS
- **期刊**：JMLR · MLJ · TNNLS

### 数据挖掘与信息检索 (DM & IR)
- **会议**：KDD · CIKM · SIGIR · WSDM · ECIR · RECSYS · ICDM
- **期刊**：TKDE · TOIS

### 数据库与系统 (DB & Systems)
- **会议**：SIGMOD · VLDB · FAST · NSDI
- **期刊**：TPDS · TC · TOS

### 语音与多媒体 (Speech & Multimedia)
- **会议**：ICASSP · INTERSPEECH · MM · ICME

### 网络与安全 (Networking & Security)
- **会议**：SIGCOMM · INFOCOM · MOBICOM · NDSS · SP

### 跨领域与其他 (Interdisciplinary & Others)
- **会议**：AAAI · IJCAI · WWW · ISWC · DAC · MICCAI · STOC
- **期刊**：AI

<!-- confs-list-end -->



## :books: 如何从 DBLP 添加新会议

### 通过 issue 触发工作流自动更新

如果您希望添加新的会议列表，请按照以下格式提交 issue。我们审核并添加标签后，工作流将自动运行。
[issue 格式](https://github.com/youngfish42/PaperVault/issues/10)


## :warning: 免责声明

由于数据来源和检索机制的限制，我们无法保证检索到的论文一定能满足您的需求，敬请谅解。此外，所有结果均来源于 [DBLP](https://dblp.org/)、[ACL](https://aclanthology.org/)、[NIPS](https://papers.nips.cc/)、[OpenReview](https://openreview.net/)，如果这侵犯了您的版权，您可以随时联系我们，我们将尽快删除，谢谢:)


## :scroll: 致谢

本项目 fork 自 [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector)，现已作为 **PaperVault** 独立发展。我们衷心感谢原项目所有作者与贡献者为本项目奠定的基础。本项目继续采用 [GNU General Public License v3.0](LICENSE) 许可。

---

📄 [技术细节](TECHNICAL.md)
