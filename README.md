# CPBL Analytics — 台灣職棒進階數據分析系統

![CI](https://github.com/your-username/cpbl-analytics/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-80%25-brightgreen)

## 專案簡介

CPBL Analytics 是一套針對台灣職棒（CPBL）的進階數據分析系統，整合 Rebas Open Data 與 CPBL 官網公開資料，計算台灣棒球圈尚未廣泛公開的進階指標，包含殘壘效率（LOB%）、關鍵時刻表現（Clutch/Leverage Index）、球數分裂分析（Count Splits）與投手疲勞曲線（Pitcher Fatigue），並透過 REST API 與互動式 Dashboard 呈現分析結果。

---

## 四大分析模組

| 模組 | 說明 |
|------|------|
| **LOB% 殘壘效率** | 計算投手讓壘上跑者未得分的比率，交叉驗證 CPBL API 殘壘欄位，識別幸運/不幸運投手 |
| **Clutch / Leverage Index** | 基於 RE24 矩陣計算情境壓力指數，量化打者在高壓局面（LI > 1.5）的表現差異 |
| **Count Splits** | 分析打者與投手在不同球數（領先/落後/平手）下的表現分裂，追蹤 Chase Rate |
| **Pitcher Fatigue** | 以每 15 球為單位追蹤投手表現衰退曲線，自動偵測疲勞臨界點 |

---

## 技術棧

| 層級 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| 套件管理 | uv |
| API 框架 | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 資料庫 | SQLite（WAL mode） |
| 視覺化 | Plotly.js（靜態 HTML Dashboard） |
| 測試 | pytest + pytest-cov（目標 80%+） |
| 容器 | Docker + docker-compose |
| CI | GitHub Actions |
| Linter / Type | ruff + mypy（strict mode） |

---

## 快速開始

### 1. 安裝依賴

```bash
git clone https://github.com/your-username/cpbl-analytics.git
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

### 5. 使用 Docker 啟動（推薦）

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

## Dashboard

> 互動式 Dashboard 截圖（建置完成後更新）

```
dashboard/
├── index.html          # 總覽頁
├── lob_pct.html        # LOB% 排行
├── clutch.html         # Clutch/Leverage
├── count_splits.html   # 球數分裂
└── pitcher_fatigue.html # 投手疲勞曲線
```

---

## 資料來源

| 來源 | 授權 | 說明 |
|------|------|------|
| [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data) | ODC-By License | 逐打席（PA）與逐球（event）歷史資料 |
| CPBL 官網公開資料 | 非商業用途 | 即時比分、殘壘數（Lobs / LeftBehindLobs） |

本專案基於 Rebas Open Data（ODC-By License）進行延伸分析，展示 CPBL 進階數據計算能力。

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
├── tests/              # pytest（目標 80%+ coverage）
├── scripts/            # 資料匯入腳本
├── dashboard/          # Plotly.js 靜態頁面
├── data/               # 原始資料（git-ignored，除 re_matrix.json）
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 開發指令

```bash
# 執行測試
uv run pytest -v --cov=src

# Lint 檢查
uv run ruff check src/ tests/

# Type check
uv run mypy src/
```
