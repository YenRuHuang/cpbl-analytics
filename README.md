# CPBL Analytics — 後端工程 Portfolio

[![CI](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/YenRuHuang/cpbl-analytics/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-168%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-84.11%25-brightgreen)

**Live → [cpblanalysis.mursfoto.com](https://cpblanalysis.mursfoto.com)**

從零打造的 CPBL 棒球數據分析系統。整合 [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data)（ODC-By License）與 CPBL 官網公開資料，涵蓋 ETL 資料管線、資料庫設計、RESTful API、進階統計分析、互動式 Dashboard、自動化 CI/CD。

| 指標 | |
|------|---|
| 比賽場數 | 377（2025 全季 + 2026 開季）|
| 打席 | 28,502 |
| 逐球事件 | 111,983 |
| API Endpoints | 17 |
| 分析模組 | 10 個 |
| 圖表類型 | 7 種（Savant / FanGraphs 風格）|
| 測試 | 168 個 / 84% coverage |
| 更新頻率 | GitHub Actions 每日自動 |

---

## 架構總覽

```
Rebas Open Data (JSON) ──┐
                         ├──→ ETL Pipeline ──→ SQLite (9 tables, WAL) ──→ FastAPI (17 endpoints) ──→ Static JSON Export
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
| 資料庫 | SQLite（WAL mode）/ 9 tables / 15+ indexes |
| 前端 | ECharts 5.4.3 + Tailwind CSS 3.4.1 |
| 測試 | pytest + pytest-cov（168 tests, 84% coverage）|
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
- Daily cron 自動更新（UTC 22:00 → 抓資料 → export → push → 自動部署）

### 資料庫設計
- 9 張表：games / plate_appearances / pitch_events / batter_box / pitcher_box / analysis_cache / player_mapping / players / run_expectancy_matrix
- WAL mode 支援讀寫分離
- analysis_cache 做查詢結果快取（TTL-based）

### API 設計
- 17 個 RESTful endpoints（FastAPI + Pydantic v2）
- Typed response models
- CORS + Health check
- 完整文件：**[API Docs 頁面](https://cpblanalysis.mursfoto.com/api-docs.html)**

### 測試策略
- 168 個測試（unit + integration）
- 84% code coverage
- 純函數 unit test（`calc_half_stats`、`_calc_lob_pct` 等）
- Integration test 使用 in-memory SQLite + monkeypatch 隔離
- CI 每次 push 自動跑 lint + test + coverage gate

---

## 分析模組（10 個）

### 核心分析

| 模組 | 說明 | 圖表類型 |
|------|------|---------|
| **LOB%** | 殘壘率 — 投手運氣成分，預測 ERA 回歸 | Scatter Plot |
| **Clutch / LI** | 基於 RE24 矩陣的高壓情境表現 | Scatter + Diverging Bar |
| **Count Splits** | 不同球數下的打擊/投球表現差異 | Table + Heat Map Grid |
| **Pitcher Fatigue** | 每 15 球追蹤衰退曲線，自動偵測疲勞臨界點 | Line Chart |

### 進階分析

| 模組 | 說明 | 圖表類型 |
|------|------|---------|
| **wRC+** | Park Factor 調整的加權得分創造力指數 | Savant Percentile Bars + Radar Chart |
| **Park Factor** | Team-based + Venue-based 主場優勢量化 | Bar Chart + Tables |
| **BABIP Regression** | 上半季 BABIP vs 下半季打擊率變化，展示均值回歸 | Scatter + Regression Line |
| **Half-Season Splits** | 上下半季 wOBA/OPS/AVG 差異，爆發與崩盤偵測 | Diverging Bar + Rolling wOBA Line |

### 圖表多樣性（7 種 Savant / FanGraphs 風格）
1. **Savant Percentile Bars** — 六維百分位橫條（wRC+ 頁）
2. **Radar Chart** — 兩人比較雷達圖（wRC+ 頁）
3. **Heat Map Grid** — 4×3 球數色溫矩陣（Count Splits 頁）
4. **Diverging Bar Chart** — 綠/紅正負對照（Clutch + Splits 頁）
5. **Rolling Line Chart** — 50PA 滾動 wOBA 走勢（Splits 頁）
6. **Scatter + Regression** — BABIP 回歸分析（BABIP 頁）
7. **Multi-Series Line** — 投手疲勞曲線（Fatigue 頁）

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
uv run python scripts/seed_cpbl.py --year 2025
uv run python scripts/build_re_matrix.py

# 進階分析（新增）
uv run python scripts/calc_wrc_plus.py
uv run python scripts/calc_park_factors.py
uv run python scripts/calc_babip_regression.py
uv run python scripts/calc_half_splits.py
uv run python scripts/calc_rolling_woba.py

# 啟動 API
uv run uvicorn src.api.app:create_app --factory --reload --port 8000
# → http://localhost:8000/docs

# Docker
docker compose up --build
```

---

## 開發指令

```bash
uv run pytest -v --cov=src      # 測試 + 覆蓋率（168 tests, 84%）
uv run ruff check src/ tests/   # Lint
uv run mypy src/                 # Type check
uv run python scripts/export_static.py  # 匯出靜態 JSON
```

---

## 目錄結構

```
cpbl-analytics/
├── src/
│   ├── config/         # pydantic-settings 環境管理
│   ├── db/             # SQLAlchemy ORM + engine + migrations
│   ├── etl/            # Rebas + CPBL 資料整合
│   ├── analysis/       # 4 個核心分析模組（LOB% / Clutch / Counts / Fatigue）
│   ├── api/            # FastAPI app + routes + schemas
│   └── utils/          # RE24 矩陣、常數
├── scripts/            # seed / export / 6 個進階分析腳本
├── tests/              # pytest（168 tests, 84% coverage）
├── dashboard/static/   # ECharts Dashboard（15 頁）+ 分析文章
├── data/               # 原始資料（git-ignored）
├── .github/workflows/  # CI (ci.yml) + Daily Cron (daily-update.yml)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
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
