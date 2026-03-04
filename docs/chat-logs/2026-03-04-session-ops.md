# Chat Log - 2026-03-04 (Ops & Deploy)

## Session Summary
Focus of this session:
- Enable GitHub deployment path end-to-end
- Confirm daily job update mechanism
- Adjust degree scope to bachelor/master only (exclude doctoral-only postings)

## Key Requests and Actions
1. User asked for direct GitHub deployment capability.
2. Added/validated two workflows:
   - Daily collector workflow (`collect-jobs.yml`)
   - GitHub Pages deploy workflow (`deploy-pages.yml`)
3. Added local update entry script (`scripts/update_jobs.sh`).
4. Added frontend sync control to import collector output into job list.
5. User requested to exclude doctoral-only postings.
   - Updated collector keyword rules and filtering logic.
   - Updated frontend degree options (keep 本科/硕士/本硕不限).
6. Assisted Git setup and remote push.
   - Initialized git repo, committed project, configured remote.
   - Resolved SSH auth and repository-not-found issues.
   - Final push confirmed (`main` tracking `origin/main`).

## Operational Notes
- Local dry-run crawl in sandbox environment showed DNS/proxy limitations.
- Recommended production refresh path is GitHub Actions scheduled jobs.

## Sensitive Data Handling
- No secrets were intentionally persisted in this log.
- Any token-like values shown during shell interaction should still be rotated if previously exposed.
