# Rebas 投遞信（定稿）

## 信件標題

```
黃彥儒_應徵後端工程師(正職)
```

---

## 信件內容

Hi Rebas 團隊，

我是黃彥儒，想應徵後端工程師（正職）。

為了這次應徵，我用你們的 Open Data 做了一個作品：

**https://cpblanalysis.mursfoto.com**

整合 Rebas Open Data 與 CPBL 官網公開資料，涵蓋 377 場比賽、近 11.2 萬筆逐球事件。刻意挑選了一些你們平台上還沒有的指標（像 Park Factor、BABIP 回歸、投手疲勞曲線等）作為分析範例，希望展示我對棒球數據的理解和後端工程的實作能力。

GitHub repo：https://github.com/YenRuHuang/cpbl-analytics

### 我的背景

我的路徑比較非典型 — 政大數位內容碩士學位學程（修過 Java、前端開發、互動裝置控制），畢業後做了幾年互動裝置設計和職業攝影，因為拍 CPBL、PLG、TPVL 而深入接觸運動產業。後來玩 Fantasy Baseball 玩到需要自己寫工具做數據分析，就一路從 API 串接、自動化做到完整的後端系統。

看到你們的 Open Data 之後，覺得同樣的分析思維可以用在 CPBL 上，就做了 CPBL Analytics。從 ETL pipeline 到 Dashboard 到分析文章，一個人完成。

我不會說自己是資深工程師，但我能獨立把一個想法從零做到上線，而且我真的懂棒球數據。

### 接觸過的技術

- **後端**：Node.js（Express + Redis + MySQL + JWT + Rate Limiting）、Python（FastAPI + SQLAlchemy）
- **資料庫**：PostgreSQL、MySQL、SQLite、Cloudflare D1
- **雲端**：GCP（OAuth 2.0 + Workspace API）、Cloudflare Workers/Pages、GitHub Actions CI/CD
- **API 串接**：Yahoo Fantasy API、CPBL API、Discord Webhook、Cloudflare API
- **前端**：Vue 3、ECharts、Tailwind CSS
- **其他**：Docker、Git、WebSocket

### 棒球與運動圈背景

我是 CPBL、PLG、TPVL（台灣職業排球聯盟）的職業運動攝影師，主要拍球員和球隊形象照，跟多支球隊有合作關係。

棒球數據方面：
- 三個 Fantasy Baseball 聯盟的活躍玩家（含 177 筆球員 scout notes）
- 熟悉 wRC+、FIP、WAR、LOB% 等進階指標的計算邏輯
- 理解你們 Open Data 的 JSON 結構（6 張表、PA → event → runner 的巢狀關係）
另外我之前做過互動裝置設計（科技部未來科技展、白晝之夜），對硬體控制有實作經驗。如果未來有 Trackman 或感測器端的資料串接需求，軟硬體之間我也能幫上忙。

### 相關連結

- CPBL Analytics：https://cpblanalysis.mursfoto.com
- GitHub：https://github.com/YenRuHuang/cpbl-analytics
- 分析文章（7 篇）：https://cpblanalysis.mursfoto.com/#articles

附件有簡要履歷，期待有機會聊聊！

黃彥儒

---

## 寄出前 Checklist

- [ ] 確認姓名正確
- [ ] 標題格式：「姓名_應徵後端工程師(正職)」
- [ ] GitHub repo 已設為 public
- [ ] cpblanalysis.mursfoto.com 所有頁面可正常存取
- [ ] 附上 PDF 履歷
- [ ] 最後讀一遍語氣是否自然

---

## 策略備註（不放進信裡）

### 「非本科」的包裝邏輯

信裡主動坦白不是工程背景，這是刻意的策略：

1. **先發制人** — 他們看 GitHub 或面試時一定會發現，不如自己先說
2. **轉化成優勢** — 「非典型路徑」= 有棒球 domain knowledge + 獨立解決問題能力
3. **用成果證明** — 坦白之後馬上接「但我能獨立從零做到上線」，讓他們看到你不是在學的學生
4. **Rebas 自己也是非典型** — 兩個高中同學做出台灣版 FanGraphs，他們理解非傳統路徑的價值

### 不提 Vibe Coding / AI 的原因

「Vibe Coding」這個詞在技術圈有負面含義（暗示不懂原理只靠 AI 產出）。但你的實際狀況是：
- 你能解釋 LOB% 公式裡每個變數的意義
- 你知道為什麼 ECharts 在 hidden container 會 init 失敗
- 你處理過 CPBL API 的各種 edge case

這叫「快速學習 + AI-assisted development」，不叫 Vibe Coding。面試時如果被問到開發流程，可以說「我善用工具加速開發，但每個技術決策我都能解釋為什麼這樣做。」

### Fantasy 專案作為起源故事的價值

- 證明你做 CPBL Analytics 不是為了求職而硬做的，是從 Fantasy 自然延伸
- Yahoo API OAuth 串接 = 真實的 API 串接經驗
- Discord Webhook = 他們可能也在用（棒球社群常用 Discord）
- 177 筆 scout notes = 你是認真在分析棒球，不是玩票

### 攝影師身份的正確使用方式

- 不要說「跑現場」（會被以為是記者），說「球員和球隊形象照」
- TPVL 是加分 — 證明你在運動產業有跨聯盟的合作關係
- 核心價值不是攝影技術，而是「球隊認識你、你認識球隊」= 產業人脈

### 面試準備

| 問題 | 應對 |
|------|------|
| 你不是工程背景，能勝任嗎？ | 「CPBL Analytics 從 ETL 到 Dashboard 到部署是我獨立完成的，可以現場走讀程式碼。我的學習速度快，而且你們需要的棒球 domain knowledge 我已經有了。」 |
| Node.js 熟練度？ | 「我用 Express + Redis + MySQL 做過 API Gateway，有 JWT 認證和 Rate Limiting。CPBL 專案用 Python 是因為資料分析生態更好，但 Node.js 我能直接上手。」 |
| 金流串接做過嗎？ | 「沒有直接做過金流串接。但我做過多個第三方 API 的 OAuth 串接流程，金流的 API 模式類似，我有信心能快速學會。」 |
| 你的程式是 AI 寫的嗎？ | 「我善用 AI 工具加速開發，就像用 IDE 的 autocomplete 一樣。但架構決策、資料模型設計、分析邏輯都是我自己做的 — 你可以問我任何一個模組的設計理由。」 |
| 薪資期望？ | 你們開的 45K 我可以接受。（或：如果你想談高一點，準備好理由） |
| 為什麼想來 Rebas？ | 「我從 Fantasy 開始接觸進階數據，看到你們的 Open Data 後做了 CPBL Analytics。台灣棒球需要更好的數據工具，我想參與這件事。」 |
