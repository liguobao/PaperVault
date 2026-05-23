# PaperVault - Agent Development Guide

## Project Overview

PaperVault is a fully-automated web application for collecting and searching AI/ML research papers from top-tier academic conferences. It provides a unified search interface across 40+ conferences spanning NLP, CV, ML, DM, DB, and Speech fields.

This project was originally forked from [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector) and is now developed independently under the name **PaperVault**.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.8+, Flask, Flask-Bootstrap |
| **Frontend** | Vue 3 (Composition API + `<script setup>`), TypeScript, Vite 4 |
| **UI Framework** | Element Plus 2.2.30 |
| **HTTP Client** | Axios |
| **Data Collection** | BeautifulSoup4, Requests, PyYAML |
| **AI Features** | OpenAI GPT-3.5-turbo API (for "Guess You Like" keyword suggestions) |
| **Build Tool** | Vite with compression plugin |
| **Deployment** | Aliyun server via GitHub Actions (SSH deploy) |

## Project Structure

```
PaperVault/
├── app.py                    # Flask backend API server
├── collector.py              # Multi-source data collector for paper metadata
├── maintain.py               # README updater and force cache refresh utility
├── update_cache.py           # CLI tool to add conferences from GitHub issues
├── requirements.txt          # Python dependencies
├── cache/
│   └── cache.jsonl           # Local JSON database of all papers (JSON Lines)
├── conf/                     # Conference source configurations
│   ├── acl_conf.json         # ACL Anthology sources (NLP)
│   ├── dblp_conf.json        # DBLP sources (mixed venues)
│   ├── iclr_conf.json        # OpenReview ICLR/NeurIPS sources
│   ├── nips_conf.json        # NeurIPS & MLSys proceedings
│   └── thecvf_conf.json      # CVF Open Access (CVPR, ICCV, WACV)
├── web-vue/                  # Vue 3 frontend application
│   ├── package.json
│   ├── vite.config.ts        # Vite config: builds to ../static
│   ├── tsconfig.json
│   ├── src/
│   │   ├── main.ts           # App entry point
│   │   ├── App.vue           # Root component
│   │   ├── router/index.ts   # Vue Router (hash mode, single home route)
│   │   ├── api/paper.ts      # API calls: /search, /get_guess_you_like
│   │   ├── views/HomeView.vue           # Main search page
│   │   ├── components/
│   │   │   ├── SearchResultList.vue     # Results display with pagination/export
│   │   │   ├── ConfsTree.vue            # Conference/year filter tree
│   │   │   ├── GuessYourLike.vue        # AI keyword suggestions panel
│   │   │   └── AdvancedSettingDlg.vue   # Filters dialog (year, author, confs)
│   │   └── utils/
│   │       ├── axios.ts      # HTTP client with proxy config
│   │       └── file.ts       # CSV/TXT export utilities
│   └── public/               # Static assets
├── .github/
│   ├── workflows/
│   │   ├── aliyun_deploy.yml     # Deploy on push / cache update
│   │   ├── update_cache.yml      # Triggered by labeled issues
│   │   └── update_readme.yml     # Manual README refresh
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.md
│       ├── conference.md         # Template for adding new conferences
│       ├── feature_request.md
│       └── question.md
├── pics/                     # Icons, screenshots, profile images
└── README.md
```

## Development Setup

### Backend

```bash
# Create and activate virtual environment (conda example)
source F:/Miniforge3/etc/profile.d/conda.sh && conda activate llm

# Install dependencies
pip install -r requirements.txt

# Run Flask server
python app.py
```

The Flask server runs on `http://127.0.0.1:5000` by default.

**Required Environment Variables:**
- `OPENAI_API_KEY` - OpenAI API key for "Guess You Like" feature
- `OPENAI_API_BASE` - OpenAI API base URL (optional, defaults to official endpoint)

### Git LFS

The paper cache file (`cache/cache.jsonl`) is managed by [Git LFS](https://git-lfs.github.com) due to its large size. Make sure you have Git LFS installed before cloning:

```bash
# Install Git LFS (one-time setup)
git lfs install

# Then clone the repository normally
git clone https://github.com/youngfish42/PaperVault.git
```

If you already cloned the repo without LFS, pull the LFS objects with:
```bash
git lfs pull
```

### Frontend

```bash
cd web-vue

# Install dependencies
npm install

# Start development server
npm run dev
```

The Vite dev server runs on `http://localhost:8080` and proxies `/api` to the backend.

**Environment Files:**
- `.env.development` - Development environment variables
- `.env.production` - Production environment variables

### Build for Production

```bash
cd web-vue
npm run build
```

This builds the frontend into the `static/` directory at the project root, which Flask serves directly.

## Key Commands

| Command | Description |
|---------|-------------|
| `python app.py` | Start Flask backend server |
| `python collector.py` | Run collector to update `cache/cache.jsonl` |
| `python maintain.py` | Update README conference list from config files |
| `python maintain.py force` | Force full cache rebuild and README update |
| `python update_cache.py --issue "..."` | Parse issue body and add new conferences |
| `cd web-vue && npm run dev` | Start frontend dev server |
| `cd web-vue && npm run build` | Build frontend for production |

## Code Conventions

- **Python**: Follow PEP 8. Use type hints where practical.
- **Vue/TypeScript**: Use Composition API with `<script setup>` syntax. Component names use PascalCase.
- **API Endpoints**: All backend API routes are prefixed with `/api/` (proxied to `/` in dev).
- **Environment Variables**: Frontend uses `VITE_` or `VUE_` prefix (configured in `vite.config.ts`).

## Data Sources

The collector fetches paper metadata from:
- [ACL Anthology](https://aclanthology.org/) - NLP conferences
- [OpenReview](https://openreview.net/) - ICLR, NeurIPS
- [OpenAccess.thecvf](https://openaccess.thecvf.com/) - CVPR, ICCV, WACV
- [NeurIPS Proceedings](https://papers.nips.cc/) - NeurIPS, MLSys
- [DBLP](https://dblp.org/) - 30+ mixed venues

Code links are enriched from [MLNLP-World/Top-AI-Conferences-Paper-with-Code](https://github.com/MLNLP-World/Top-AI-Conferences-Paper-with-Code).

## CI/CD Workflows

| Workflow | Trigger | Action |
|----------|---------|--------|
| `update_cache.yml` | Issue labeled `require to update cache` | Parses issue, updates configs, rebuilds cache |
| `update_readme.yml` | Manual (`workflow_dispatch`) | Rebuilds cache and updates README conference list |
| `aliyun_deploy.yml` | Push to `main` or `update_cache` completion | Builds Vue frontend, SSH deploys to Aliyun, restarts service |

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

The original project [MLNLP-World/AI-Paper-Collector](https://github.com/MLNLP-World/AI-Paper-Collector) is also licensed under GPL v3.0. When modifying or distributing this project, ensure compliance with GPL v3 requirements including preservation of copyright notices and attribution.
