# CPBL Analytics — 後端工程 Portfolio

> ⚠️ **此 repo 是 v1 snapshot（單體 FastAPI + 靜態 HTML）**
> **2026-04 已遷移到 monorepo，完整現況見下方「最新架構」。**

**Live → [cpblanalysis.mursfoto.com](https://cpblanalysis.mursfoto.com)**

從零打造的 CPBL 棒球數據分析系統。整合 [Rebas Open Data](https://github.com/rebas-tw/rebas.tw-open-data)（ODC-By License）與 CPBL 官網公開資料，涵蓋 ETL 資料管線、資料庫設計、RESTful API、進階統計分析、互動式 Dashboard、自動化 CI/CD。

## 目前架構（2026-04 遷移後）

整個專案已整合進 Turborepo monorepo：

| 層 | 技術 | 位置 |
|---|---|---|
| **前端** | Next.js 16 static export + ECharts + Tailwind | `apps/cpbl/` |
| **API Gateway** | Hono on Cloudflare Workers + Drizzle | `workers/api/` |
| **ETL** | Python 3.12 + uv + SQLAlchemy → D1 sync | `python/cpbl/` |
| **資料庫** | Cloudflare D1（5 張核心表）+ 本地 SQLite ETL | — |
| **部署** | GitHub Actions 每日 22:00 UTC cron + push auto-deploy | CF Pages |

### 實際數字（2026-04）

| 指標 | |
|------|---|
| 比賽場數 | 377（2025 全季 + 2026 開季） |
| 打席 | 28,502 |
| 逐球事件 | 111,983 |
| D1 核心表 | 5（games, players, plate_appearances, batter_box, pitcher_box） |
| Hono API endpoints（CPBL） | 13 |
| Static JSON 資料檔 | 283（build-time 預產） |
| Python ETL tests | 30（含 schema consistency test） |
| Python LOC | ~3,291 行 |
| 更新頻率 | GitHub Actions 每日自動 |

### 四大分析模組

| 模組 | 核心指標 |
|------|---------|
| LOB% | 殘壘效率 `(LOB−L)/(LOB−1.4HR)` |
| Leverage / Clutch | 壓力指數 + 高壓打席（依 RE24 矩陣） |
| Count Splits | Ahead vs Behind + Chase Rate |
| Pitcher Fatigue | 每 15 球 bucket · changepoint detection |

**刻意不做**（Rebas/灼見已有）：wRC+、WAR、OPS+、球速、轉速、好球帶

---

## 此 repo（v1）保留的內容

- `src/api/`：早期 FastAPI 17 endpoints 實作（舊版本歷史參考）
- `src/etl/`、`src/analysis/`：單體版 Python ETL 與分析模組
- `dashboard/static/*.html`：舊版 ECharts 靜態 dashboard
- `APPLICATION_EMAIL.md` / `COVER_LETTER.md`：Rebas 面試申請文件

**若要看最新程式碼，請前往 [`murs-workspace` monorepo](https://github.com/YenRuHuang/murs-workspace)。**

---

## 架構演進（v1 → v2）

```
v1（本 repo · 2026-03 ~ 04 初）
  Rebas Open Data + CPBL API → Python ETL → SQLite → FastAPI → 靜態 HTML → CF Pages

v2（monorepo · 2026-04 遷移後）
  Rebas + CPBL → Python ETL → SQLite(本地) → D1 → static JSON + Hono API
                                              ↓
                                      Next.js static export → CF Pages
```

**為什麼遷移？**
- 統一 4 個 app（cpbl / fantasy / polymarket / mursfoto）共用 packages + API gateway
- 前端從 vanilla HTML 升級到 React + TypeScript（DX 和可維護性）
- API 從 FastAPI on Render（cold start）改為 Hono on CF Workers（edge 零冷啟動）
- 資料從 SQLite 同步到 D1（查詢走 edge + CF 自動備份）
