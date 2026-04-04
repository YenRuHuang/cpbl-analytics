# CPBL Analytics — 台灣職棒進階數據分析系統

[![CI](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-129%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-84.78%25-brightgreen)

**Live Demo → [cpblanalysis.mursfoto.com](https://cpblanalysis.mursfoto.com)**

整合 [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data)（ODC-By License）與 CPBL 官網公開資料，計算台灣棒球圈尚未廣泛公開的進階指標。

| 數據規模 | |
|---------|---|
| 比賽場數 | 370（2025 全季 + 2026 開季） |
| 打席數 | 27,974 |
| 逐球事件 | 109,897 |

---

## 四大分析模組

| 模組 | 說明 |
|------|------|
| **LOB% 殘壘效率** | 投手讓壘上跑者未得分的比率，交叉驗證 CPBL API 殘壘欄位，識別幸運/運氣差投手 |
| **Clutch / Leverage Index** | 基於 RE24 矩陣計算情境壓力指數，量化打者在高壓局面（LI > 1.5）的表現差異 |
| **Count Splits** | 打者與投手在不同球數（領先/落後/平手）下的表現分裂，追蹤 Chase Rate |
| **Pitcher Fatigue** | 每 15 球為單位追蹤投手表現衰退曲線，自動偵測疲勞臨界點 |

### 分析文章

- [誰是 2025 CPBL 最幸運的投手？LOB% 解密](https://cpblanalysis.mursfoto.com/article-lob-2025)
- [投手疲勞曲線：魔神樂 vs 後勁型投手](https://cpblanalysis.mursfoto.com/article-fatigue-2025)
- [Clutch 打者排行：誰在關鍵時刻最可靠？](https://cpblanalysis.mursfoto.com/article-clutch-2025)

---

## 技術棧

| 層級 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| 套件管理 | uv |
| API 框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 資料庫 | SQLite（WAL mode） |
| 視覺化 | ECharts 5.4.3 + Tailwind CSS 3.4.1 |
| 測試 | pytest + pytest-cov（84.78% coverage） |
| 容器 | Docker + docker-compose |
| CI/CD | GitHub Actions（CI + Daily Cron 自動更新） |
| Linter / Type | ruff + mypy（strict mode） |
| 部署 | Cloudflare Pages（GitHub 整合自動部署） |

---

## 架構

```
Rebas Open Data JSON + CPBL 官網公開資料
  → ETL (seed_cpbl.py / seed_rebas.py)
  → SQLite (WAL mode)
  → Analysis modules (4 個)
  → FastAPI + Pydantic schemas
  → export_static.py → 靜態 JSON
  → ECharts Dashboard
  → GitHub Actions daily cron (UTC 22:00)
  → Cloudflare Pages (auto deploy)
```

---

## 快速開始

### 1. 安裝依賴

```bash
git clone https://github.com/YenRuHuang/cpbl-analytics.git
cd cpbl-analytics
uv sync
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env，設定 DATABASE_URL 等參數
```

### 3. 匯入資料

```bash
# 匯入 Rebas Open Data（將 JSON 放入 data/rebas_raw/）
uv run python scripts/seed_rebas.py

# 整合 CPBL 官網公開資料
uv run python scripts/seed_cpbl.py --year 2026

# 建立 Run Expectancy 矩陣
uv run python scripts/build_re_matrix.py
```

### 4. 啟動 API Server

```bash
uv run uvicorn src.api.app:create_app --factory --reload --port 8000
```

API 文件：http://localhost:8000/docs

### 5. 使用 Docker 啟動

```bash
docker compose up --build
```

---

## API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| `GET` | `/health` | 健康檢查 |
| `GET` | `/api/v1/players` | 球員列表 |
| `GET` | `/api/v1/players/{player_id}/lob` | 球員 LOB% 統計 |
| `GET` | `/api/v1/players/{player_id}/clutch` | 球員 Clutch Score |
| `GET` | `/api/v1/players/{player_id}/count-splits` | 球數分裂數據 |
| `GET` | `/api/v1/pitchers/{player_id}/fatigue` | 投手疲勞曲線 |
| `GET` | `/api/v1/games/{game_id}/leverage` | 單場 Leverage Index |

---

## 目錄結構

```
cpbl-analytics/
├── src/
│   ├── config/         # pydantic-settings 環境管理
│   ├── db/             # SQLAlchemy ORM models + engine
│   ├── etl/            # Rebas + CPBL 資料整合
│   ├── analysis/       # 四大分析模組
│   ├── api/            # FastAPI app + routes + schemas
│   └── utils/          # RE24 矩陣、常數
├── tests/              # pytest（129 tests, 84.78% coverage）
├── scripts/            # 資料匯入 + 靜態 JSON 匯出
├── dashboard/static/   # ECharts 互動式 Dashboard + 分析文章
├── data/               # 原始資料（git-ignored，除 re_matrix.json）
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 資料來源

| 來源 | 授權 | 說明 |
|------|------|------|
| [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data) | ODC-By License | 逐打席（PA）與逐球（event）歷史資料 |
| CPBL 官網公開資料 | 非商業用途 | 即時比分、殘壘數（Lobs / LeftBehindLobs） |

---

## 開發指令

```bash
# 執行測試
uv run pytest -v --cov=src

# Lint 檢查
uv run ruff check src/ tests/

# Type check
uv run mypy src/

# 匯出靜態 JSON（部署用）
uv run python scripts/export_static.py
```

---

## License

MIT
