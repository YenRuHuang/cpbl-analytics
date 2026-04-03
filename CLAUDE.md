# CLAUDE.md — CPBL Analytics

> CPBL 進階數據分析系統。基於 Rebas Open Data + CPBL 官網公開資料，計算台灣棒球圈尚未公開的進階指標。
> 作為應徵 Rebas 野球革命後端工程師的 portfolio 專案。

---

## 技術棧

| 層級 | 技術 |
|------|------|
| 語言 | Python 3.12+ |
| 套件管理 | uv |
| API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| 資料庫 | SQLite（WAL mode）|
| 視覺化 | ECharts 5.4.3（靜態 HTML dashboard）|
| 測試 | pytest + coverage |
| 容器 | Docker + docker-compose |
| CI | GitHub Actions（lint + test + build）|
| Linter | ruff |
| Type Check | mypy（strict mode）|

---

## 目錄結構

```
cpbl-analytics/
├── src/
│   ├── config/settings.py         # pydantic-settings 環境管理
│   ├── db/
│   │   ├── engine.py              # SQLite engine + session
│   │   ├── models.py              # SQLAlchemy ORM models
│   │   └── migrations/001_initial.sql
│   ├── etl/                       # 資料整合（Extract-Transform-Load）
│   │   ├── rebas_loader.py        # Rebas Open Data JSON → SQLite
│   │   ├── cpbl_client.py         # CPBL 官網公開資料 → SQLite
│   │   └── merge.py               # 雙資料源合併 + 球員對照
│   ├── analysis/                  # 四大分析模組
│   │   ├── lob_pct.py             # LOB% 殘壘效率
│   │   ├── leverage.py            # Clutch Hitting / Leverage Index
│   │   ├── count_splits.py        # Count Splits 球數分裂
│   │   └── pitcher_fatigue.py     # Pitcher Fatigue 投手疲勞曲線
│   ├── api/                       # FastAPI
│   │   ├── app.py                 # App factory
│   │   ├── deps.py                # DB session injection
│   │   ├── routes/                # 各 endpoint
│   │   └── schemas/               # Pydantic response models
│   └── utils/
│       ├── run_expectancy.py      # RE24 矩陣計算
│       └── constants.py           # CPBL 球隊代碼、年份等
├── tests/                         # pytest，目標 80%+ coverage
├── scripts/
│   ├── seed_rebas.py              # 匯入 Rebas Open Data
│   ├── seed_cpbl.py               # 整合 CPBL 官網公開資料
│   └── build_re_matrix.py         # 建 Run Expectancy 矩陣
├── dashboard/                     # Plotly.js 靜態頁面
├── data/                          # git-ignored（除了 re_matrix.json）
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 常用指令

```bash
cd ~/Documents/cpbl-analytics

# 環境
uv sync                                          # 安裝依賴
uv run python scripts/seed_rebas.py              # 匯入 Rebas Open Data
uv run python scripts/seed_cpbl.py --year 2026   # 整合 CPBL 官網公開資料
uv run python scripts/build_re_matrix.py         # 建 RE24 矩陣

# API
uv run uvicorn src.api.app:create_app --factory --reload --port 8000

# 測試
uv run pytest -v --cov=src
uv run ruff check src/ tests/

# Docker
docker compose up --build
```

---

## 資料來源

### 1. Rebas Open Data（主要）
- 來源：https://github.com/rebas-tw/rebas.tw-open-data
- 授權：ODC-By License（標註來源即可使用）
- 格式：JSON 巢狀，6 張表：game / batterBox / pitcherBox / PA / event / runner
- 用途：歷史比賽的完整逐打席（PA）和逐球（event）資料
- 存放：`data/rebas_raw/`（git-ignored）

### 2. CPBL 官網公開資料（補充）
- 端點：`POST https://cpbl.com.tw/box/getlive`
- 參數：`year`, `kindCode`（A=一軍）, `gameSno`
- 回傳：LiveLogJson, BattingJson（含 Lobs/LeftBehindLobs 殘壘數）, PitchingJson, ScoreboardJson
- 用途：即時資料 + 殘壘數（Rebas 沒有的欄位）
- Rate limit：每場間隔 2 秒，每分鐘不超過 30 次
- 存放：`data/cpbl_raw/`（git-ignored）

### 合併策略
- **Rebas 為主**（結構完整、有 player_id）
- **CPBL 為補充**（殘壘數 + 當日即時）
- 合併鍵：`(game_date, home_team, away_team)`
- 球員對照：`player_mapping` 表（中文名 ↔ Rebas player_id）

---

## 四大分析模組

### 1. LOB% 殘壘效率 (`src/analysis/lob_pct.py`)
- 投手讓壘上跑者未得分的比率
- 公式：`(H + BB + HBP - R) / (H + BB + HBP - 1.4 × HR)`
- CPBL API 的 `Lobs` / `LeftBehindLobs` 可交叉驗證
- 聯盟平均約 70%，> 78% 可能偏幸運，< 65% 可能偏不幸運

### 2. Leverage / Clutch (`src/analysis/leverage.py`)
- Leverage Index：情境壓力指數（局數 × 出局數 × 壘上 × 分差）
- Clutch Score：高壓打席（LI > 1.5）表現 vs 整體的差異
- 依賴 RE24 矩陣（`src/utils/run_expectancy.py`）

### 3. Count Splits (`src/analysis/count_splits.py`)
- 打者/投手在不同球數下的表現差異
- 分類：Ahead（1-0, 2-0, 3-1）/ Behind（0-1, 0-2, 1-2）/ Even
- Chase Rate：兩好球後壞球揮棒率

### 4. Pitcher Fatigue (`src/analysis/pitcher_fatigue.py`)
- 投手隨投球數增加的表現衰退曲線
- 每 15 球一個 bucket，追蹤被打率、K%、BB%
- 自動偵測衰退臨界點（changepoint detection）

---

## 不做的東西（Rebas / 灼見已有）

- ❌ wRC+ / WAR / OPS+（Rebas 核心功能）
- ❌ 進壘點 / 球速 / 轉速視覺化（Rebas 付費訂閱）
- ❌ 電子好球帶 / 影像追蹤（灼見 StatsInsight 的領域）
- ❌ 重建 Statcast 類系統（需要球場硬體）

---

## 已知陷阱（Claude 必讀）

- **CPBL API 無 player_id**：只有中文名，需靠 `player_mapping` 表做對照
- **Rebas JSON 巢狀格式**：每個檔案包含一場比賽的全部六張表，需展平
- **pitch_number_game 要自己算**：按 pitcher_id + game_id 的 pitch_seq 排序累加
- **CPBL 球員改名/交易**：player_mapping 需要手動維護邊界案例
- **SQLite 不支持 concurrent writes**：ETL 和 API server 不要同時跑，用 WAL mode
- **LOB% 公式在 HR=0 時**：分母 `(H+BB+HBP - 1.4×HR)` 可能 ≤ 0，需 guard
- **CPBL 樣本量小**（一季約 120 場）：所有分析加 `min_pa` / `min_ip` 過濾 + 樣本量警示
- **RE24 矩陣**：先用 MLB 的 RE24 作為 proxy，CPBL 版待資料累積後校正
- **執行路徑**：永遠從 `~/Documents/cpbl-analytics/` 執行，不要 cd 到子目錄

---

## 程式碼風格

- **Immutable**：dataclass 用 `frozen=True`
- **Type hints**：everywhere，mypy strict
- **函數**：< 50 行
- **檔案**：< 400 行
- **錯誤處理**：explicit，不 swallow errors
- **常數**：用 `constants.py`，不 hardcode

---

## 敏感檔案

- `.env` — API key 等（不進 git）
- `data/` — 原始資料（不進 git，除了 `data/re_matrix.json`）
- **永遠不要 `git add data/`**（除了明確列出的檔案）
