# Rebas 面試準備

> 面試官：KJ Chiu（CEO）
> 時間：2026/04/20-23 擇一（04/16 18:00 前回覆）
> 地點：台北市大安區和平東路二段 201 號 3 樓（可線上）

---

## 面試結構

| 階段 | 時長 | 主題 |
|------|------|------|
| 前半 | 30 min | 情境模擬：地端/雲端/Hybrid 系統設計 + 棒球數據資料庫設計 |
| 後半 | 30 min | 自我介紹 + 技術實作經歷分享 |

---

# Part 1：情境模擬

## 情境 A：系統架構（地端/雲端/Hybrid）

### 我的實戰經驗

| 架構模式 | 我做過什麼 | 可以延伸的思考 |
|---------|----------|-------------|
| **雲端** | Cloudflare Workers + D1 + KV + Pages（CPBL + TPVL 投票） | Serverless 適合流量不穩定的場景 — 球季中 vs 休賽期差 10 倍 |
| **Hybrid** | 本地 Python ETL → 雲端 D1 儲存 → CDN 前端 | 計算密集（分析）放本地/CI，查詢服務放雲端 |
| **CI/CD** | GitHub Actions cron（每日 6am 自動更新數據） | 排程 ETL 是 Hybrid 的典型模式 |
| **快取** | KV 60s TTL 排名快取（TPVL），analysis_cache 表（CPBL） | 不同層級的快取策略：CDN > KV > DB cache > 重新計算 |

### 如果問「幫 Rebas 設計系統架構」

> 前提：球季中每天 1-4 場比賽，每場 ~300 打席 + ~900 投球。非比賽日幾乎零流量。

**資料收集層（地端）**
- Trackman/影像數據 → 本地處理（球速、轉速、落點需要 GPU 運算）
- 文字記錄（box score、play-by-play）→ 可以純雲端 API

**儲存層（雲端）**
- 關聯式 DB（PostgreSQL）存事實表：games / PA / pitch events
- 球員、球隊、球場等維度表
- derived tables（wOBA、WAR、Park Factor）→ materialized view

**服務層（雲端）**
- API Server 提供即時查詢
- background job：每場結束後重算排行
- CDN 快取球員頁面（變動頻率低）

**為什麼 Hybrid？**
- 影像/Trackman 資料量大，處理完再上傳比較省
- 球場網路不穩定，本地先存保底
- ML 模型訓練需要 GPU，雲端 GPU 太貴

### 架構關鍵詞

- **Event Sourcing**：逐球事件是不可變的事實流，分析是投影
- **CQRS**：寫入（ETL）和讀取（API/Dashboard）分離
- **冪等性**：重跑 ETL 不會產生重複資料（INSERT OR IGNORE + UNIQUE constraint）

---

## 情境 B：棒球數據資料庫設計

### 面試時打開 cpblanalysis.mursfoto.com/architecture.html 秀 ER Diagram

核心設計思路：

```
games (一場比賽)
  ├── plate_appearances (每個打席 — 核心事件表)
  │     └── pitch_events (每一球)
  ├── batter_box (打者單場彙總)
  └── pitcher_box (投手單場彙總)

players (球員主檔)
player_mapping (CPBL 名字 ↔ Rebas ID 對照)
run_expectancy_matrix (24 states RE24 矩陣)
```

### 預期追問 & 回答

**Q: batter_box 和 plate_appearances 不是重複嗎？**
> batter_box 是「彙總統計」（一場幾安幾打幾分），PA 是「逐打席事件」（三局二打席，壘上一三壘，結果二壘打）。前者算 AVG/OPS，後者算 RE24/Clutch/Count Splits。粒度不同，用途不同。

**Q: 為什麼不直接從 PA 算 batter_box？**
> 可以，但 batter_box 有些欄位是來源直接提供的（LOB、left_behind_lob），不是從 PA 算得出來的。而且做 season aggregate 查詢效能好很多。

**Q: player_mapping 是怎麼回事？**
> CPBL 官方 API 不給 player_id，只給中文名字。同名球員可能存在。建了對照表把名字對應到 Rebas player_id，有 confidence score，邊界情況手動維護。

**Q: RE24 矩陣怎麼做？**
> 24 個狀態（0-2 出局 × 8 壘包組合），每個狀態的「預期得分」從歷史 PA 算出。目前用 MLB proxy 因為 CPBL 樣本不夠，等累積 3-5 年後校正。用來算 Leverage Index 和 Clutch Score。

**Q: 加球種/轉速/球速，schema 怎麼改？**
> pitch_events 加 `pitch_type`、`velocity`、`spin_rate`、`plate_x`、`plate_z`。如果有 Trackman 可能還加 `release_pos_x/y/z`、`break_x/z`。都是 per-pitch 維度，自然延伸，不需要新表。

**Q: 效能考量？**
> PA 28K 行、pitch_events 112K 行 — SQLite 綽綽有餘。CPBL 5 年歷史 + Trackman 可能到百萬級 → PostgreSQL + partition by season。索引策略：`(game_id, batter_id)` 和 `(pitcher_id, game_id)` 是最常用查詢路徑。

---

# Part 2：自我介紹 + 技術故事

## 開場（30 秒）

「我的背景比較特別 — 我是職業運動攝影師，同時也是三個 Fantasy Baseball 聯盟的重度玩家，對棒球數據不陌生。技術上我不是傳統的後端工程師，我比較像是 builder — 我擅長把各種工具和技術串在一起，快速把一個想法變成可以跑的系統。

這次看到你們的職缺，我直接用 Python + FastAPI 蓋了一套 CPBL 數據系統：兩個資料源的 ETL、9 張表、17 個 API、CI/CD 自動部署，一週內上線。我不只是會寫 code，我還是你們的付費會員，我花了很多時間研究你們每一個功能。」

---

## 技術故事（主力兩個 + 一個備用）

### ★ 故事 A：雙資料源合併（資料整合）

> Rebas 有完整逐球資料但缺 LOB，CPBL API 有 LOB 但缺 play-by-play。

**挑戰？** 兩個來源沒有 shared ID。CPBL API 連 player_id 都沒有。

**怎麼做的？**
1. 用 `(game_date, home_team, away_team)` 做 game-level 合併
2. 建 player_mapping 表對照名字 → ID
3. ETL 設計成冪等 — 重跑安全，不會重複

**對 Rebas 的意義？** 「這就是你們每天在處理的問題 — Trackman 資料、影像標記、文字記錄，三個來源要合在一起。我已經處理過兩個來源的合併，知道最難的不是 code，是資料對齊。」

### ★ 故事 B：從靜態 HTML 到 CI/CD 自動化（架構演進）

> 一開始只是幾張靜態 HTML + ECharts 圖表，後來長成完整自動化系統。

**演進過程？**
1. v1：手動跑 script → 手動改 HTML
2. v2：FastAPI 提供 API → 前端讀 JSON
3. v3：GitHub Actions 每日 cron → 自動 seed + export + deploy

**對 Rebas 的意義？** 「每次迭代都是實際需求驅動。加 API 是因為手動改資料太痛苦；加 CI/CD 是因為球季中每天有比賽，手動更新不可能持續。我習慣從最小可行版本開始，根據實際痛點逐步升級架構。」

### 備用：AB/H 反轉 Bug（資料品質）

> 如果聊到資料品質時自然帶出

CPBL 資料裡打數和安打對調了。匯入後全聯盟打擊率 300%+，不合理。ETL 加了 sanity check — `h > ab` 自動交換 + 告警。

**一句話版：** 「外部資料永遠不可信，ETL 層必須有 validation。你們的人工標記流程很重視品質，我在資料管線也是用同樣的態度。」

---

## 我的 Portfolio 數字

377 場比賽 / 28,502 打席 / 111,983 逐球事件 / 9 張表 / 17 個 API / 168 個 pytest / 84% coverage / 每日自動更新 / Cloudflare Pages 部署

線上：https://cpblanalysis.mursfoto.com

---

## 30 秒回覆清單

| 問題 | 回答 |
|------|------|
| 後端經驗多久？ | 不是大公司出來的，但這套系統是完整後端：ETL + DB + API + CI/CD，一個人從零到上線 |
| 不會 NodeJS？ | 主力 Python，後端核心概念相通。比找一個會 NodeJS 但要花三個月搞懂棒球的人更快上手 |
| 為什麼選 SQLite？ | 12 萬行綽綽有餘且零維護。規模長大後遷移 PostgreSQL 很簡單 |
| 為什麼選 Cloudflare？ | 免費、全球 CDN、Serverless 按用量計費。球季流量波動大，比固定 VM 省 |
| 怎麼測試？ | 168 個 pytest，84% coverage。ETL 有 integration test 打真實 SQLite |
| 你的專案跟我們有什麼不同？ | 做「延伸分析」（LOB%/Clutch/Fatigue），不重複你們的核心指標。進去後可整合 |
| 為什麼選我們不選大公司？ | 我想做棒球數據。台灣做這件事的就是你們，沒有第二家。全遠端讓我繼續在球場拍照 |
| 後端經驗不夠多？ | 我學東西快、能獨立做出完整系統、真的懂 domain。上手總時間比純工程師短 |

---

## 絕對不要說的

- ❌「爬蟲」→ ✅「資料整合」
- ❌「你們的網站有問題」→ ✅「我看到一些可以優化的地方」
- ❌「Vibe Coding」→ ✅「我善用 AI 工具加速開發」
- ❌ 跟 Rebas 比數據深度 → ✅ 強調建造能力和 domain knowledge
- ❌ 假裝資深後端 → ✅ 誠實說是 builder，學什麼都很快
- ❌ 批評人工標記 → ✅「加上 ML 預標記可以更快」

---

## 加分話題（他們問到再聊）

### 我研究過你們的產品

> 語氣：不是批評，是「如果我進來，會想處理這些」

- **前端效能**：166 張圖沒 lazy loading、Google Fonts 18 個 woff2 分片可以 subset、圖片沒 WebP
- **SEO**：CRA SPA 架構，球員頁搜尋不到。加 JSON-LD + canonical，長期考慮 Next.js SSR
- **手機版**：排行榜 17 欄擠在一起，建議 sticky 球員名 + 水平滾動
- **功能**：球員比較（side-by-side）、篩選 Deep Link（URL 帶參數）、排行榜可排序

### 你們即將推出的功能

- **wRC+**：公式不難，難的是 Park Factor。CPBL 五個主場差異大，我用 2025 全季資料試算過
- **聯盟平均本壘板紀律**：左右打要分開、球數情境要分開，不能算一個大平均
- **打者 WAR**：最難的是守備評價。沒 Statcast 可以用 RF/9 近似，FanGraphs 早期也是這樣

### 人工標記可以用 ML 加速

你們同時在徵 4 名影像紀錄員，代表流程靠人力撐。用歷史資料訓練分類器（投手慣用球種 + 球速區間 → 球種預測），標記人員只需校正模型標錯的部分。Python 擅長的事。

---

## 技術對照表

| 職缺要求 | 我的狀況 |
|---------|---------|
| 1 年+ 後端開發 | 完整後端系統：ETL + DB + API + CI/CD，從零到部署 |
| 雲端服務 | Cloudflare Pages + Workers + D1 + KV。理解雲端概念 |
| 關聯式資料庫 | SQLite 9 張表、index 策略、WAL mode |
| NodeJS | 主力 Python，學習新框架不是障礙 |
| Git | GitHub Actions CI/CD pipeline，每日 cron |
| 棒球知識（加分） | 三聯盟 Fantasy + 職業棒球攝影 + 四個分析模組 |
| 外部 API 串接（加分） | CPBL API、Rebas JSON、Yahoo Fantasy、Discord、Spotify |
| Python（加分） | 最熟的語言，portfolio 全 Python |
| Docker（加分） | multi-stage Dockerfile + docker-compose |
| 獨立開發能力（加分） | 整套系統一個人做完 |
