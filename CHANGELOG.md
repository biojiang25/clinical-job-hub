# Changelog

All notable changes to this project will be documented in this file.

## 2026-03-04

### Added
- Initialized project scaffold `clinical-job-hub` for graduate job information.
- Added landing page: [index.html](/Users/jianglan/clinical-job-hub/index.html).
- Added jobs CRUD page: [jobs.html](/Users/jianglan/clinical-job-hub/jobs.html).
- Added channel radar page: [channels.html](/Users/jianglan/clinical-job-hub/channels.html).
- Added frontend data logic with local persistence: [app.js](/Users/jianglan/clinical-job-hub/assets/app.js).
- Added core styles and responsive layout: [styles.css](/Users/jianglan/clinical-job-hub/assets/styles.css).
- Added initial data collection pipeline:
  - Source config: [sources.json](/Users/jianglan/clinical-job-hub/collector/sources.json)
  - Keyword config: [keywords.json](/Users/jianglan/clinical-job-hub/collector/keywords.json)
  - Daily collector script: [fetch_daily_jobs.py](/Users/jianglan/clinical-job-hub/collector/fetch_daily_jobs.py)
- Added one-click update script: [update_jobs.sh](/Users/jianglan/clinical-job-hub/scripts/update_jobs.sh)
- Added GitHub Pages deployment workflow: [deploy-pages.yml](/Users/jianglan/clinical-job-hub/.github/workflows/deploy-pages.yml)
- Added daily scheduled collector workflow: [collect-jobs.yml](/Users/jianglan/clinical-job-hub/.github/workflows/collect-jobs.yml)
- Added dependency manifest for collector: [requirements.txt](/Users/jianglan/clinical-job-hub/requirements.txt)
- Added frontend sync control for auto-collected jobs (button + status text).

### Updated
- Extended job model to include `sourceChannel` and channel-based filtering.
- Updated site navigation to include "高频渠道雷达".
- Expanded degree coverage to include `本科` and `本硕不限` in UI and keyword matching.
- Updated collector rules to exclude doctoral-only postings (`博士`/`博士后`) in this phase.
- Updated README with GitHub deployment and daily update instructions.
- Added front-end sync action to merge collector output from `data/jobs_latest.json` into local job storage.
- Updated deployment status: repository pushed to `origin/main` (`biojiang25/clinical-job-hub`).

### Docs
- Added project README run instructions: [README.md](/Users/jianglan/clinical-job-hub/README.md).
- Added architecture documentation: [ARCHITECTURE.md](/Users/jianglan/clinical-job-hub/ARCHITECTURE.md).
- Added chat log archive: [2026-03-04-session.md](/Users/jianglan/clinical-job-hub/docs/chat-logs/2026-03-04-session.md).
- Added deployment/ops chat log archive: [2026-03-04-session-ops.md](/Users/jianglan/clinical-job-hub/docs/chat-logs/2026-03-04-session-ops.md).

### In Progress
- Province/city-level source matrix for Anhui, Zhejiang, Jiangsu.
- Coverage gap report and missed-source alerting.
