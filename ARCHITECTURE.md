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
- Entry and dashboard: [index.html](/Users/jianglan/clinical-job-hub/index.html)
- Job CRUD and filtering: [jobs.html](/Users/jianglan/clinical-job-hub/jobs.html)
- Channel radar and strategy: [channels.html](/Users/jianglan/clinical-job-hub/channels.html)
- Shared style: [styles.css](/Users/jianglan/clinical-job-hub/assets/styles.css)
- Browser-side logic: [app.js](/Users/jianglan/clinical-job-hub/assets/app.js)

Frontend storage:
- `localStorage` key: `clinical-job-hub-data-v1`

### 2.2 Collector / ETL
- Orchestration script: [fetch_daily_jobs.py](/Users/jianglan/clinical-job-hub/collector/fetch_daily_jobs.py)
- Source definitions: [sources.json](/Users/jianglan/clinical-job-hub/collector/sources.json)
- Domain keyword rules: [keywords.json](/Users/jianglan/clinical-job-hub/collector/keywords.json)

ETL stages:
1. Extract: fetch HTML/RSS from source URLs with retry.
2. Transform: parse links, normalize text/date, score relevance.
3. Load: idempotent upsert into SQLite.
4. Export: latest/today/report JSON for downstream use.

### 2.3 Data Layer
- SQLite DB: [jobs.db](/Users/jianglan/clinical-job-hub/data/jobs.db) (generated at runtime)
- Snapshot exports:
  - [jobs_latest.json](/Users/jianglan/clinical-job-hub/data/jobs_latest.json)
  - [jobs_today.json](/Users/jianglan/clinical-job-hub/data/jobs_today.json)
  - [fetch_report.json](/Users/jianglan/clinical-job-hub/data/fetch_report.json)

## 3. Reliability Design
- Idempotent key: `sha1(source_id|title|link)`.
- Retry: network fetch retries with backoff sleep.
- Incremental behavior: `first_seen_at` + `last_seen_at` tracking.
- Duplicate safety: update existing records by deterministic ID.
- Degree policy (current phase): keep bachelor/master-track postings, filter doctoral-only postings.

## 4. Current Constraints
- Some sources are dynamic/anti-bot pages; parser quality varies by site.
- Coverage completeness requires province/city source matrix maintenance.
- Absolute "no missing posting" is not guaranteed; can be improved through auditing.
- Local execution may fail under restricted DNS/proxy; scheduled GitHub Actions is the primary runtime for online updates.

## 5. Delivery and Operations
- Repository: `biojiang25/clinical-job-hub` (branch: `main`).
- Static deployment: GitHub Pages via [deploy-pages.yml](/Users/jianglan/clinical-job-hub/.github/workflows/deploy-pages.yml).
- Daily data refresh: GitHub Actions cron via [collect-jobs.yml](/Users/jianglan/clinical-job-hub/.github/workflows/collect-jobs.yml).
- Local/manual update entry: [update_jobs.sh](/Users/jianglan/clinical-job-hub/scripts/update_jobs.sh).
- Frontend sync entry: “同步最新岗位” button in [jobs.html](/Users/jianglan/clinical-job-hub/jobs.html), powered by [app.js](/Users/jianglan/clinical-job-hub/assets/app.js).

## 6. Next Architecture Step
Implement province-level coverage control plane:
- Target matrix for Anhui/Zhejiang/Jiangsu (city + institution type)
- Source-health checks (success/failure/empty)
- Daily gap report and alert list
