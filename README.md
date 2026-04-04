# CPBL Analytics — 後端工程 Portfolio

[![CI](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-129%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-84.78%25-brightgreen)

**Live → [cpblanalysis.mursfoto.com](https://cpblanalysis.mursfoto.com)**

從零打造的 CPBL 棒球數據系統。整合 [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data)（ODC-By License）與 CPBL 官網公開資料，涵蓋 ETL 資料管線、資料庫設計、RESTful API、互動式 Dashboard、自動化 CI/CD。

| 指標 | |
|------|---|
| 比賽場數 | 370（2025 全季 + 2026 開季）|
| 打席 | 27,974 |
| 逐球事件 | 109,897 |
| API Endpoints | 17 |
| 測試 | 129 個 / 84.78% coverage |
| 更新頻率 | GitHub Actions 每日自動 |

---

## 架構總覽

```
Rebas Open Data (JSON) ──┐
                         ├──→ ETL Pipeline ──→ SQLite (8 tables, WAL) ──→ FastAPI (17 endpoints) ──→ Static JSON Export
CPBL 官網公開 API ────────┘                                                                            ↓
                                                                                         Cloudflare Pages (auto deploy)
                                                                                                       ↑
                                                                                         GitHub Actions (CI + Daily Cron)
```

詳細架構圖、DB Schema、CI/CD 流程、技術決策請見 **[Architecture 頁面](https://cpblanalysis.mursfoto.com/architecture.html)**。

---

## 技術棧

| 層級 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| 套件管理 | uv |
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 資料庫 | SQLite（WAL mode）/ 8 tables / 15+ indexes |
| 前端 | ECharts 5.4.3 + Tailwind CSS 3.4.1 |
| 測試 | pytest + pytest-cov |
| 容器 | Docker multi-stage build + docker-compose |
| CI/CD | GitHub Actions（lint + test + coverage + daily cron ETL）|
| Lint / Type | ruff + mypy（strict） |
| 部署 | Cloudflare Pages（GitHub 整合自動部署） |

---

## 工程亮點

### ETL 資料管線
- 雙資料源整合：Rebas JSON 巢狀結構展平 + CPBL API
- Join key：`game_date + home_team + away_team`
- 球員名稱模糊比對（處理改名、交易）
- Rate limiting（2s 間隔、30/min）
- 冪等載入（skip existing games）
- 磁碟快取 raw JSON

### 資料庫設計
- 8 張表：games / plate_appearances / pitch_events / batter_box / pitcher_box / analysis_cache / player_mapping / run_expectancy_matrix
- WAL mode 支援讀寫分離
- analysis_cache 做查詢結果快取（TTL-based）

### API 設計
- 17 個 RESTful endpoints（FastAPI + Pydantic v2）
- Typed response models
- CORS + Health check
- 完整文件：**[API Docs 頁面](https://cpblanalysis.mursfoto.com/api-docs.html)**

### CI/CD
- Push 觸發：ruff lint → pytest → coverage report → deploy
- Daily cron（UTC 22:00）：seed data → export static JSON → git push → auto deploy

---

## 分析模組

基於資料管線之上的 4 個棒球分析模組：

| 模組 | 說明 |
|------|------|
| **LOB%** | 殘壘率 — 投手運氣成分，預測 ERA 回歸 |
| **Clutch / LI** | 基於 RE24 矩陣的高壓情境表現 |
| **Count Splits** | 不同球數下的打擊/投球表現差異 |
| **Pitcher Fatigue** | 每 15 球追蹤衰退曲線，自動偵測疲勞臨界點 |

分析文章：
- [LOB% 解密](https://cpblanalysis.mursfoto.com/article-lob-2025.html)
- [投手疲勞曲線](https://cpblanalysis.mursfoto.com/article-fatigue-2025.html)
- [Clutch 打者排行](https://cpblanalysis.mursfoto.com/article-clutch-2025.html)

---

## 快速開始

```bash
# 安裝
git clone https://github.com/YenRuHuang/cpbl-analytics.git
cd cpbl-analytics
uv sync

# 環境變數
cp .env.example .env

# 匯入資料
uv run python scripts/seed_rebas.py
uv run python scripts/seed_cpbl.py --year 2026
uv run python scripts/build_re_matrix.py

# 啟動 API
uv run uvicorn src.api.app:create_app --factory --reload --port 8000
# → http://localhost:8000/docs

# Docker
docker compose up --build
```

---

## 目錄結構

```
cpbl-analytics/
├── src/
│   ├── config/         # pydantic-settings 環境管理
│   ├── db/             # SQLAlchemy ORM + engine + migrations
│   ├── etl/            # Rebas + CPBL 資料整合
│   ├── analysis/       # 4 個分析模組
│   ├── api/            # FastAPI app + routes + schemas
│   └── utils/          # RE24 矩陣、常數
├── tests/              # pytest（129 tests, 84.78% coverage）
├── scripts/            # seed / export / build 腳本
├── dashboard/static/   # ECharts Dashboard + 分析文章 + Architecture + API Docs
├── data/               # 原始資料（git-ignored）
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 開發指令

```bash
uv run pytest -v --cov=src      # 測試 + 覆蓋率
uv run ruff check src/ tests/   # Lint
uv run mypy src/                 # Type check
uv run python scripts/export_static.py  # 匯出靜態 JSON
```

---

## 資料來源

| 來源 | 授權 | 用途 |
|------|------|------|
| [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data) | ODC-By License | 逐打席 + 逐球歷史資料 |
| CPBL 官網公開資料 | 非商業用途 | 即時比分、殘壘數 |

---

## License

MIT
