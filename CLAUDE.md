# [ARCHIVED] CPBL Analytics Legacy Repo

> **此 repo 已遷移到 monorepo，不要在此 repo 開發新功能。**

## 現況

- **Live 站 = `~/Documents/murs-workspace/apps/cpbl/`**（Next.js static export）
- **主力 ETL = `~/Documents/murs-workspace/python/cpbl/`**
- **API Gateway = `~/Documents/murs-workspace/workers/api/`**（Hono on CF Workers）
- **DB = Cloudflare D1 `cpbl-analytics`**（5 張核心表）

## 此 repo 保留原因

僅作為早期版本參考。內含：
- `dashboard/static/*.html`：舊靜態 ECharts dashboard（已被 apps/cpbl 取代）
- `src/api/`、`src/etl/`、`src/analysis/`：舊 FastAPI + SQLite 實作（已被 monorepo 取代）
- `APPLICATION_EMAIL.md` / `COVER_LETTER.md`：Rebas 面試已寄出的文件

## ⚠️ 不要

- 不要推 commit 到此 repo
- 不要在此 repo 跑 ETL（data/*.db 已過時）
- 不要 AI agent 讀此 repo 做 code reference（會產出舊架構的錯誤建議）

## 想看新架構？

- Monorepo CLAUDE.md：`~/Documents/murs-workspace/CLAUDE.md`
- CPBL 專屬：`~/Documents/murs-workspace/apps/cpbl/`
- 面試準備文件：`~/Documents/murs-workspace/apps/cpbl/docs/INTERVIEW_PREP.md`
