# Changelog

All notable changes to this project will be documented in this file.

## 2026-03-04

### Added
- Initialized project scaffold `clinical-job-hub` for graduate job information.
- Added landing page: [index.html](./index.html).
- Added jobs CRUD page: [jobs.html](./jobs.html).
- Added channel radar page: [channels.html](./channels.html).
- Added frontend data logic with local persistence: [app.js](./assets/app.js).
- Added core styles and responsive layout: [styles.css](./assets/styles.css).
- Added initial data collection pipeline:
  - Source config: [sources.json](./collector/sources.json)
  - Keyword config: [keywords.json](./collector/keywords.json)
  - Daily collector script: [fetch_daily_jobs.py](./collector/fetch_daily_jobs.py)
- Added one-click update script: [update_jobs.sh](./scripts/update_jobs.sh)
- Added GitHub Pages deployment workflow: [deploy-pages.yml](./.github/workflows/deploy-pages.yml)
- Added daily scheduled collector workflow: [collect-jobs.yml](./.github/workflows/collect-jobs.yml)
- Added dependency manifest for collector: [requirements.txt](./requirements.txt)
- Added frontend sync control for auto-collected jobs (button + status text).
- Added WeChat lead collector: [fetch_wechat_leads.py](./collector/fetch_wechat_leads.py)
- Added WeChat lead source config: [wechat_sources.json](./collector/wechat_sources.json)
- Added WeChat lead outputs:
  - [wechat_leads_latest.json](./data/wechat_leads_latest.json)
  - [wechat_leads_today.json](./data/wechat_leads_today.json)
  - [wechat_fetch_report.json](./data/wechat_fetch_report.json)

### Updated
- Extended job model to include `sourceChannel` and channel-based filtering.
- Updated site navigation to include "高频渠道雷达".
- Expanded degree coverage to include `本科` and `本硕不限` in UI and keyword matching.
- Updated collector rules to exclude doctoral-only postings (`博士`/`博士后`) in this phase.
- Updated README with GitHub deployment and daily update instructions.
- Added front-end sync action to merge collector output from `data/jobs_latest.json` into local job storage.
- Updated deployment status: repository pushed to `origin/main` (`biojiang25/clinical-job-hub`).
- Updated update script to run main job collector + WeChat lead collector in one command.
- Updated jobs page to show WeChat lead section (title/date/original link only).
- Updated GitHub Actions daily commit list to include WeChat lead JSON outputs.

### Docs
- Added project README run instructions: [README.md](./README.md).
- Added architecture documentation: [ARCHITECTURE.md](./ARCHITECTURE.md).
- Added chat log archive: [2026-03-04-session.md](./docs/chat-logs/2026-03-04-session.md).
- Added deployment/ops chat log archive: [2026-03-04-session-ops.md](./docs/chat-logs/2026-03-04-session-ops.md).

### In Progress
- Province/city-level source matrix for Anhui, Zhejiang, Jiangsu.
- Coverage gap report and missed-source alerting.
