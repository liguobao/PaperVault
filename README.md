<p align="center">
<h1 align="center"> <img src="./pics/icon/ai.png" width="30" /> PaperVault</h1>
</p>
<p align="center">
  <a href="README.en.md">English</a> | <strong>简体中文</strong>
</p>

## :jack_o_lantern: 项目简介

PaperVault 是一个用于收集和检索人工智能领域学术论文的全自动化工具，覆盖 NLP、CV、ML、DM、DB 和语音等多个方向的顶级学术会议。

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
PaperVault 最初 fork 自 [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector)，现已作为独立项目持续发展。我们正在将其从一个静态论文清单工具，逐步建设为一个功能完善、数据丰富的在线学术搜索引擎。

## :open_book: 收录会议范围

<!-- confs-list-start -->

```text
- [EMNLP 2019-2022] [ACL 2019-2023] [NAACL 2019-2022] [COLING 2020-2022] 
- [ICASSP 2019-2022] [WWW 2019-2022] [ICLR 2019-2023] [ICML 2019-2022] 
- [AAAI 2019-2022] [IJCAI 2019-2022] [CVPR 2019-2023] [ICCV 2019-2021] 
- [MM 2019-2022] [KDD 2019-2022] [CIKM 2019-2022] [SIGIR 2019-2022] 
- [WSDM 2019-2023] [ECIR 2019-2022] [ECCV 2020-2022] [COLT 2019-2022] 
- [AISTATS 2019-2022] [INTERSPEECH 2019-2022] [ISWC 2019-2022] [JMLR 2019-2022] 
- [VLDB 2019-2021] [ICME 2019-2022] [TIP 2020-2022] [TPAMI 2020-2022] 
- [RECSYS 2019-2022] [TKDE 2020-2022] [TOIS 2020-2022] [ICDM 2019-2021] 
- [TASLP 2020-2022] [BMVC 2019-2021] [MICCAI 2019-2022] [IJCV 2020-2022] 
- [TNNLS 2020-2022] [FAST 2019-2023] [SIGMOD 2019-2022] [NIPS 2019-2022] 
- [MLSYS 2020-2022] [WACV 2020-2022] 
```


<!-- confs-list-end -->



## :books: 如何从 DBLP 添加新会议

### 通过 issue 触发工作流自动更新

如果您希望添加新的会议列表，请按照以下格式提交 issue。我们审核并添加标签后，工作流将自动运行。
[issue 格式](https://github.com/youngfish42/PaperVault/issues/10)


## :warning: 免责声明

由于本工具仍处于开发阶段，我们无法保证检索到的论文一定能满足您的需求，敬请谅解。此外，所有结果均来源于 [DBLP](https://dblp.org/)、[ACL](https://aclanthology.org/)、[NIPS](https://papers.nips.cc/)、[OpenReview](https://openreview.net/)，如果这侵犯了您的版权，您可以随时联系我们，我们将尽快删除，谢谢:)


## :scroll: 致谢

本项目 fork 自 [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector)，现已作为 **PaperVault** 独立发展。

我们衷心感谢 [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector) 的所有原作者与贡献者的杰出工作。原项目为数据采集架构、会议配置和 Web 界面设计提供了基础。

本项目继续采用 [GNU General Public License v3.0](LICENSE) 许可，与原项目保持一致。如果您使用或分发本项目，请确保遵守 GPL v3 许可证的要求。

---

📄 [技术细节](TECHNICAL.md)
