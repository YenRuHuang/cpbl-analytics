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

### v1（本 repo · 2026-03 ~ 04 初）

```
Rebas Open Data + CPBL API
      ↓
Python ETL (pandas + SQLAlchemy)
      ↓
SQLite (local)
      ↓
FastAPI on Render (17 endpoints)
      ↓
靜態 HTML + Vanilla JS + ECharts CDN
      ↓
CF Pages (rsync deploy)
```

**v1 痛點：**
- FastAPI on Render 有 cold start（~3-5 秒）— 第一個用戶體驗差
- 前端 vanilla HTML + jQuery 風格 — 維護性差、無 TypeScript safety
- CI/CD 4 個 app 各一套 workflow（CPBL / Fantasy / Polymarket / mursfoto）— 改共用邏輯要改 4 份
- ETL / frontend / API 跨 3 種部署目標（Render / CF Pages / 手動）— 運維負擔大
- 沒有共享 UI components，每個 app 重寫 button / card / layout

### v2（murs-workspace monorepo · 2026-04 遷移後）

```
                    ┌─────────────────────────────────────┐
                    │    Turborepo + pnpm 10 workspace    │
                    └─────────────────────────────────────┘
                                    │
      ┌──────────────┬──────────────┼──────────────┬──────────────┐
      │              │              │              │              │
  apps/cpbl      apps/fantasy   apps/polymarket  apps/mursfoto   workers/api
  Next.js 16     Next.js 16     Next.js 16       Next.js 16      Hono on CF Workers
  static export  static export  static export    static export   Drizzle + D1
      │              │              │              │              │
      └──────────────┴──────────────┴──────────────┴──────────────┘
                            ↓        ↓        ↓
                    packages/design-system  (shadcn + oklch tokens)
                    packages/types          (shared TypeScript)
                    packages/utils          (date/TZ, validation)
                    packages/db             (Drizzle schemas)
                    packages/config         (ESLint + TS + Prettier)
                            ↓
                    python/cpbl  python/fantasy  python/polymarket
                    (uv + pytest, ETL + analytics)
                            ↓
                    4 × Cloudflare D1 DB (cpbl / fantasy / polymarket / mursfoto-ops)
                    + R2 備份（GitHub Actions 每日 cron）
```

### 遷移決策比較

| 層面 | v1 | v2 | Why |
|------|----|----|----|
| **API runtime** | FastAPI on Render | Hono on CF Workers | 零冷啟動、edge latency、免費 tier 夠用 |
| **API 部署** | 獨立 Render service | 跟前端同一個 monorepo push | 單一 PR 對應 full-stack 變更，避免 FE/BE schema drift |
| **資料層** | Local SQLite | Cloudflare D1 + R2 自動備份 | Edge query、跨區複製、備份策略化 |
| **前端** | Vanilla HTML + CDN jQuery | Next.js 16 App Router + Server Components | TypeScript safety、component 複用、static export 依然 CDN 純前端 |
| **UI 元件** | 每 app 重寫 | `@murs/design-system`（shadcn + oklch tokens） | 視覺一致、改一次全站套用 |
| **型別** | 各 app 獨立 | `@murs/types`（API 契約） | 後端改 schema 前端立刻知道 |
| **DB Schema** | 手寫 raw SQL + migration script | Drizzle ORM at `packages/db` | 型別安全 migration、多 DB 共用 schema 語法 |
| **CI/CD** | 4 個獨立 workflow | Turborepo pipeline + 4 合 1 workflow | 改共用 package 只 build affected apps |
| **本地開發** | `cd cpbl/ && python3 -m http.server` | `pnpm turbo run dev --filter=cpbl` | 並行啟多 app、cache hit 快 |
| **ETL** | 每 app 在自己的 repo | `python/{app}` 統一 uv workspace | Python 相依一次裝、共享測試 fixture |

### 實際遷移操作（5 stage）

1. **Stage 0 audit**（04-13）：盤點 4 個 repo 的共用邏輯、重複代碼、deploy 流程
2. **Stage 1 scaffold**（04-14）：建立 Turborepo + pnpm workspace、建 4 個 `@murs/*` packages
3. **Stage 2 app migration**（04-15～17）：
   - `cpbl-analytics/dashboard/*.html` → `apps/cpbl/` (Next.js 16 + ECharts + design-system)
   - `cpbl-analytics/src/api/` → `workers/api/src/cpbl.ts` (Hono routes，砍掉 FastAPI)
   - `cpbl-analytics/src/etl/` → `python/cpbl/` (uv 化)
   - SQLite → D1 sync via `scripts/sync_to_d1.py`
4. **Stage 3 infra**（04-18）：4 個 D1 DB + R2 + GitHub Actions 統一 CI + 每日備份 cron
5. **Stage 4 cleanup**（04-19）：舊 repo 歸檔、workflow disable、demo 站（cpblanalysis.mursfoto.com）切換 DNS 到新 CF Pages 專案 — **zero downtime**

### 遷移成果（量化）

| 指標 | v1 | v2 | Δ |
|------|----|----|----|
| API cold start | 3-5 秒 | < 50ms | -98% |
| Frontend bundle | ~180 KB (jQuery + ECharts CDN) | ~120 KB (Next.js static) | -33% |
| CI workflow 檔案數 | 4（每 app 一份） | 1（turbo pipeline）+ 1（backup） | 75% 整併 |
| Deploy 指令 | 4 個不同命令 | `git push`（一次部 4 app 對應變更） | — |
| 共享 UI 元件數 | 0 | `@murs/design-system` 提供 ~15 個 | — |
| 跨 app type safety | 各自 | `@murs/types` 統一 | 從 0 到 100% |

### 為什麼不直接在本 repo 重構？

考慮過「本 repo 內做 refactor」vs「建新 monorepo」：
- 本 repo 原先就不是 monorepo 結構（`src/` 單一 Python package + `dashboard/` 靜態目錄）
- 若強行在內加 Turborepo，git 歷史會混亂（Python 專案根目錄突然多出 `apps/` `packages/`）
- 4 個獨立 app repo 整併，**新建一個 monorepo 把所有 repo 當 subtree 吸進去**語意最清楚
- 保留舊 repo 作為 v1 snapshot + ETL 腳本歷史，新 repo 向前走

### Live 站如何維持零中斷遷移

1. 舊 CF Pages 專案 `cpbl-analytics` 繼續跑原靜態站
2. 新 monorepo build `apps/cpbl` → 推新 CF Pages 專案 `cpbl-analytics-v2`
3. 跑 smoke test 確認新站 13 個 API endpoint + 283 個 JSON data 檔都 200
4. **DNS 切換**：`cpblanalysis.mursfoto.com` 從舊專案指向新專案（CF Pages 支援 instant switch）
5. 觀察 24 小時沒 error → 舊專案歸檔

**使用者端 zero downtime、zero URL change。**

---

## 🎤 Rebas 面試官 QA 速查

> 📌 若您打開這個 repo 看到這段是因為：**我在 04 月把面試履歷的這個 repo 整合進 monorepo**，但新 monorepo 是私有的（含其他 side project），所以您直接看到的是 v1 snapshot。

### Q1. 為什麼要遷移？
見上方「v1 痛點」。核心：cold start、CI 分散、沒有共享元件。

### Q2. 為什麼選 Turborepo + pnpm？
- Turborepo cache 機制：改共用 package 時只 rebuild affected apps，省 CI 時間
- pnpm 10 workspace：硬鏈結節省磁碟，內建 `onlyBuiltDependencies` 安全控制
- 不用 Nx / Rush：這兩者對純前端 + Python 混合 monorepo 的 tooling 過重

### Q3. 為什麼 Hono 不 Express？
- Cloudflare Workers runtime，Hono 設計原生支援 Web Standard（Request/Response），Express 需要 shim
- 體積 14 KB，符合 Workers 1MB limit
- TypeScript-first

### Q4. 為什麼 D1 不 Postgres？
- 免費 tier 對 CPBL 這種 read-heavy 場景夠用
- Edge read replica 自動
- 跟前端 CF Pages 同 CF 生態不用跨雲
- Drizzle ORM 支援 D1，schema 可 migrate

### Q5. 這樣遷移會不會覆蓋這個 repo 的分析邏輯？
不會。Python 分析模組（LOB / Leverage / Clutch / Fatigue / Count Splits）**原封不動搬進 `python/cpbl/`**，只有重新 uv 化包裝。四個指標公式、changepoint detection、RE24 矩陣都是同一份程式碼。API 介面改 Hono 只是 transport layer，business logic 不變。

### Q6. 可以看新 repo 嗎？
私有 repo（含其他 side project 商業邏輯）。面試中可 **live screen share** 走一遍 monorepo 結構 + 任何 code section。

---
