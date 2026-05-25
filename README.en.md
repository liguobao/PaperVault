<p align="center">
<h1 align="center"> <img src="./pics/icon/ai.png" width="30" /> PaperVault</h1>
</p>
<p align="center">
  <strong>English</strong> | <a href="README.md">简体中文</a>
</p>


## :jack_o_lantern: Motivation

Fully-automated scripts for collecting AI-related papers, spanning Natural Language Processing (NLP), Computer Vision (CV), Machine Learning (ML), Data Mining (DM), Database (DB), Speech, systems, security, networking, and theoretical computer science.

## 🚧 Project Status

> **This project is actively under construction.**

### Current Phase
- Expanding paper coverage from 2020 onward, especially high-quality **journals** (e.g., TIP, TPAMI, TKDE, TNNLS, TASLP, IJCV, etc.) and major **publishers** (e.g., IEEE, ACM, Springer, Elsevier).
- Backfilling **abstracts** for existing papers via automated scripts and GitHub Actions to enhance searchability.
- The database contains **94,000+** papers spanning 40+ top-tier conferences and journals across NLP, CV, ML, DM, DB, and Speech.

### Next Steps
- Upgrade the frontend and backend stack for a better search experience and UI.
- Redeploy and relaunch the web search service.

### Project History
PaperVault is evolving it from a static paper list into a fully-featured, data-rich online academic search engine (see Acknowledgements below for project origin).

## :open_book: Search Categories

<!-- confs-list-start -->

> Current database covers **2019-2026**, with **60+** top-tier conferences and journals.

### Natural Language Processing (NLP)
- **Conferences**: ACL · EMNLP · NAACL · COLING · EACL
- **Journals**: TASLP

### Computer Vision (CV)
- **Conferences**: CVPR · ICCV · ECCV · WACV · BMVC
- **Journals**: TIP · TPAMI · IJCV

### Machine Learning (ML)
- **Conferences**: ICML · ICLR · NIPS · COLT · AISTATS
- **Journals**: JMLR · MLJ · TNNLS

### Data Mining & Information Retrieval (DM & IR)
- **Conferences**: KDD · CIKM · SIGIR · WSDM · ECIR · RECSYS · ICDM
- **Journals**: TKDE · TOIS

### Database & Systems (DB & Systems)
- **Conferences**: SIGMOD · VLDB · FAST · NSDI
- **Journals**: TPDS · TC · TOS

### Speech & Multimedia
- **Conferences**: ICASSP · INTERSPEECH · MM · ICME

### Networking & Security
- **Conferences**: SIGCOMM · INFOCOM · MOBICOM · NDSS · SP

### Interdisciplinary & Others
- **Conferences**: AAAI · IJCAI · WWW · ISWC · DAC · MICCAI · STOC
- **Journals**: AI

<!-- confs-list-end -->



## :books: How to add new conferences from DBLP

### Automatically Updating via an issue-triggered workflow

If anyone wants to add a new list of conferences. please raise an issue following the format of this one.
We will check and label it, then the workflow will run automatically.
[issue format](https://github.com/youngfish42/PaperVault/issues/10)


## :warning: Disclaimer

Due to limitations in data sources and retrieval mechanisms, we can not guarantee that the papers found will meet your needs. In addition, all the results come from [DBLP](https://dblp.org/), [ACL](https://aclanthology.org/), [NIPS](https://papers.nips.cc/), [OpenReview](https://openreview.net/), if this violates your copyright, you can contact us at any time, we will delete it as soon as possible, thank you:)


## :scroll: Acknowledgements

This project is forked from [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector) and is now developed independently as **PaperVault**. We sincerely thank the original authors and contributors for laying the foundation. This project continues under the [GNU General Public License v3.0](LICENSE).

---

📄 [Technical Details](TECHNICAL.md)
