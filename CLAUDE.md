# CLAUDE.md — CPBL Analytics

> CPBL 進階數據分析系統。Rebas Open Data + CPBL 官網，計算 LOB%/Leverage/Count Splits/Pitcher Fatigue。
> Portfolio 專案，應徵 Rebas 野球革命。

## 技術棧
Python 3.12+ · uv · FastAPI · SQLAlchemy 2.0 · SQLite(WAL) · ECharts 5.4.3 · pytest · Docker · GitHub Actions · ruff · mypy(strict)

## 目錄結構
```
cpbl-analytics/
├── src/
│   ├── config/settings.py        # pydantic-settings
│   ├── db/                       # engine, models, migrations
│   ├── etl/                      # rebas_loader, cpbl_client, merge
│   ├── analysis/                 # lob_pct, leverage, count_splits, pitcher_fatigue
│   ├── api/                      # FastAPI routes + schemas
│   └── utils/                    # run_expectancy, constants
├── tests/                        # 目標 80%+ coverage
├── scripts/                      # seed_rebas, seed_cpbl, build_re_matrix
├── dashboard/                    # ECharts 靜態頁面（CF Pages 部署）
└── data/                         # git-ignored（除 re_matrix.json）
```

## 常用指令
```bash
cd ~/Documents/cpbl-analytics
uv sync
uv run python scripts/seed_rebas.py
uv run python scripts/seed_cpbl.py --year 2026
uv run uvicorn src.api.app:create_app --factory --reload --port 8000
uv run pytest -v --cov=src
```

## 資料來源
- **Rebas Open Data**（主）：JSON 巢狀，6 表。ODC-By License
- **CPBL 官網 getlive**（補）：POST，rate limit 2秒/場
- 合併鍵：`(game_date, home_team, away_team)`

## 四大分析模組
1. **LOB%**：殘壘效率。HR=0 時分母 guard
2. **Leverage/Clutch**：壓力指數 + 高壓打席表現。依賴 RE24 矩陣
3. **Count Splits**：不同球數表現 + Chase Rate
4. **Pitcher Fatigue**：每 15 球 bucket，changepoint detection

## 不做的（Rebas/灼見已有）
wRC+/WAR/OPS+ · 進壘點/球速/轉速 · 電子好球帶 · Statcast 系統

## 已知陷阱
> API 結構與 ECharts 細節由全域 hook（prompt-router.js + tool-guard.js）自動注入，不在此重複。

- CPBL API 無 player_id，靠 `player_mapping` 表對照
- Rebas JSON 巢狀需展平
- `pitch_number_game` 要自己算（pitcher_id + game_id 排序累加）
- SQLite 不支持 concurrent writes，ETL 和 API 不同時跑
- CPBL 樣本量小（~120場），加 min_pa/min_ip 過濾
- RE24 先用 MLB proxy，待累積後校正
- 從 `~/Documents/cpbl-analytics/` 執行，不 cd 到子目錄
- 永遠不要 `git add data/`

## 程式碼風格
Immutable(frozen=True) · Type hints everywhere · 函數<50行 · 檔案<400行 · 不 swallow errors
