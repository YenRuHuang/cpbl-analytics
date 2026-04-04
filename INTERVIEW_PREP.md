# CPBL Analytics — Rebas 面試 Narrative

## 30 秒 Elevator Pitch

> 我用 Rebas Open Data 和 CPBL 官網公開資料，建了一套進階數據分析系統。分析了 370 場比賽、近 11 萬筆逐球事件，算出 LOB%、投手疲勞曲線、Clutch 打者排行、球數分析四個模組 — 這些是台灣棒球圈目前沒有公開的指標。
>
> 技術上是 Python + FastAPI + SQLAlchemy 的 ETL pipeline，每日自動更新，部署在 Cloudflare Pages。我還寫了數據分析文章，用 LOB% 預測投手 ERA 回歸方向。

---

## 技術故事線（按面試問題整理）

### Q: 為什麼做這個專案？

「我在三個 Fantasy Baseball 聯盟裡打了幾年，對進階數據分析不陌生。看到 Rebas Open Data 開源了 CPBL 的逐球資料後，發現台灣棒球圈缺少 LOB%、投手疲勞曲線這類進階指標的公開分析。我想證明這些資料可以產出有價值的洞察。」

### Q: 資料怎麼來的？

「主要是 Rebas Open Data，ODC-By License。補充資料來自 CPBL 官網的公開 API — 特別是殘壘數欄位，Rebas 的 JSON 裡沒有。我寫了 ETL pipeline 把兩個來源的資料合併，用 game_date + home/away team 做 join key，球員名字做 fuzzy matching。」

**關鍵措辭：說「資料整合」不說「爬蟲」。說「基於你們的 Open Data 做延伸分析」。**

### Q: 技術架構是什麼？

```
Rebas Open Data JSON + CPBL API
  → ETL (seed_cpbl.py / seed_rebas.py)
  → SQLite (WAL mode)
  → Analysis modules (4 個)
  → FastAPI + Pydantic schemas
  → export_static.py → 靜態 JSON
  → ECharts 5.4.3 + Tailwind 前端
  → GitHub Actions daily cron
  → Cloudflare Pages (auto deploy)
```

### Q: 遇到什麼技術挑戰？

1. **CPBL API 沒有 player_id** — 只有中文名。需要建 player_mapping 表做對照，處理改名和交易。
2. **LOB% 公式在 HR=0 時分母可能 ≤ 0** — 需要 guard clause。
3. **CPBL 樣本量小**（一季 ~120 場 vs MLB 2,430 場）— 所有分析都加最低門檻 + 樣本量警示。
4. **逐球事件合併投手** — Rebas 的 pitch_events 表沒有直接的 pitcher_id，需要用 inning + top_bottom + pa_seq 去 JOIN plate_appearances 反查。
5. **前端 ECharts 在 hidden container 上 init 會得到 0x0** — 必須先顯示容器再初始化圖表。

### Q: 為什麼選這四個分析模組？

「刻意避開 Rebas 和灼見已經做的東西（wRC+、WAR、進壘點追蹤）。選的是：
- **LOB%** — 有預測價值，台灣還沒人公開算
- **投手疲勞曲線** — 教練決策直接參考
- **Clutch 表現** — 球迷最關心的問題
- **球數分析** — 投捕配球策略基礎

每個模組都對應一個不同的分析面向：預測、決策、評價、策略。」

### Q: 如果有更多時間你會做什麼？

1. **預測模型** — 用 LOB% + FIP + K/BB 建 regression model 預測隔年 ERA
2. **CPBL 版 RE24 矩陣** — 目前用 MLB 的 proxy，累積夠多場次後可以算 CPBL 自己的
3. **多年趨勢** — Rebas 有歷年資料，可以做 3 年滾動分析
4. **影像整合** — 結合 pitch tracking 做球種 + 位置的進階分析

---

## 數字（面試記住這些）

| 指標 | 數字 |
|------|------|
| 比賽場數 | 370（360 場 2025 + 10 場 2026）|
| 打席數 | 27,974 |
| 逐球事件 | 109,897 |
| API Endpoints | 17 |
| 分析模組 | 4 |
| 測試覆蓋率 | 84.78% (129 tests) |
| Dashboard 頁面 | 5 + 1 篇分析文章 |
| 部署 | Cloudflare Pages + GitHub Actions daily cron |

---

## 個人優勢定位

| 優勢 | 證據 |
|------|------|
| 產業人脈 | CPBL/PLG/T1 職業運動攝影師身份 |
| 工程速度 | 整套系統一週內完成（ETL → API → Dashboard → Deploy → 分析文章）|
| 棒球知識 | 三個 Fantasy Baseball 聯盟、169 筆 scout notes |
| 資料整合能力 | 雙資料源合併、27,974 打席處理 |
| 中英雙語 | 技術文件和代碼全英文 |

---

## 不要提的

- ❌ 不提「爬蟲」→ 用「資料整合」
- ❌ 不提 Vibe Coding → 展示成果就好
- ❌ 不提 AI assisted development → 不必要
- ❌ 不批評 Rebas 現有產品 → 強調「延伸分析」
