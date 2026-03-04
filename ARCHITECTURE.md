# Architecture

## 1. Goal
Build a focused job-information system for graduate candidates in:
- Clinical Laboratory Diagnostics (临床检验诊断学)
- Pharmacy (药学)
- Biology (生物学)

The system combines:
- Manual curation (web UI CRUD)
- Automated collection (daily ETL crawler)

## 2. System Components

### 2.1 Frontend (Static Site)
- Entry and dashboard: [index.html](./index.html)
- Job CRUD and filtering: [jobs.html](./jobs.html)
- Channel radar and strategy: [channels.html](./channels.html)
- Shared style: [styles.css](./assets/styles.css)
- Browser-side logic: [app.js](./assets/app.js)

Frontend storage:
- `localStorage` key: `clinical-job-hub-data-v1`

### 2.2 Collector / ETL
- Orchestration script: [fetch_daily_jobs.py](./collector/fetch_daily_jobs.py)
- Source definitions: [sources.json](./collector/sources.json)
- Domain keyword rules: [keywords.json](./collector/keywords.json)
- WeChat lead collector: [fetch_wechat_leads.py](./collector/fetch_wechat_leads.py)
- WeChat source definitions: [wechat_sources.json](./collector/wechat_sources.json)

ETL stages:
1. Extract: fetch HTML/RSS from source URLs with retry.
2. Transform: parse links, normalize text/date, score relevance.
3. Load: idempotent upsert into SQLite.
4. Export: latest/today/report JSON for downstream use.

WeChat lead pipeline (auxiliary):
1. Extract: fetch configured RSS/HTML clue sources.
2. Transform: keep only direct `mp.weixin.qq.com` article links.
3. Filter: keep clinical lab/pathology/pharmacy/biology related signals, exclude doctoral-only signals.
4. Load/Export: idempotent upsert to SQLite and output lead snapshots.

### 2.3 Data Layer
- SQLite DB: [jobs.db](./data/jobs.db) (generated at runtime)
- Snapshot exports:
  - [jobs_latest.json](./data/jobs_latest.json)
  - [jobs_today.json](./data/jobs_today.json)
  - [fetch_report.json](./data/fetch_report.json)
  - [wechat_leads_latest.json](./data/wechat_leads_latest.json)
  - [wechat_leads_today.json](./data/wechat_leads_today.json)
  - [wechat_fetch_report.json](./data/wechat_fetch_report.json)

## 3. Reliability Design
- Idempotent key: `sha1(source_id|title|link)`.
- Retry: network fetch retries with backoff sleep.
- Incremental behavior: `first_seen_at` + `last_seen_at` tracking.
- Duplicate safety: update existing records by deterministic ID.
- Degree policy (current phase): keep bachelor/master-track postings, filter doctoral-only postings.
- WeChat policy: keep only direct original article links; store metadata only (title/date/source/link).

## 4. Current Constraints
- Some sources are dynamic/anti-bot pages; parser quality varies by site.
- Coverage completeness requires province/city source matrix maintenance.
- Absolute "no missing posting" is not guaranteed; can be improved through auditing.
- Local execution may fail under restricted DNS/proxy; scheduled GitHub Actions is the primary runtime for online updates.

## 5. Delivery and Operations
- Repository: `biojiang25/clinical-job-hub` (branch: `main`).
- Static deployment: GitHub Pages via [deploy-pages.yml](./.github/workflows/deploy-pages.yml).
- Daily data refresh: GitHub Actions cron via [collect-jobs.yml](./.github/workflows/collect-jobs.yml).
- Local/manual update entry: [update_jobs.sh](./scripts/update_jobs.sh).
- Frontend sync entry: “同步最新岗位” button in [jobs.html](./jobs.html), powered by [app.js](./assets/app.js).
- WeChat sync entry: “刷新公众号线索” button in [jobs.html](./jobs.html), powered by [app.js](./assets/app.js).

## 6. Next Architecture Step
Implement province-level coverage control plane:
- Target matrix for Anhui/Zhejiang/Jiangsu (city + institution type)
- Source-health checks (success/failure/empty)
- Daily gap report and alert list
