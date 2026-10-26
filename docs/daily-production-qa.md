# Daily production QA and GitHub notifications

## GitHub notifications (account setting)
GitHub Actions sends failure notifications according to the user's GitHub notification preferences; GitHub does **not** guarantee an email on every successful workflow run. Enable **Settings > Notifications > System > Actions** and choose email, then choose the desired notification level (failure-only or all activity, where available). Verify the email address and notification routing in GitHub settings. This repository cannot configure personal email preferences.

## Every daily task
1. Read `stories/today.json` and confirm image paths exist in `assets/episodes/YYYYMMDD/`.
2. Check the latest run of `.github/workflows/daily-shorts.yml` on `main` (not just its queue status). Match the run's head SHA to the latest relevant commit.
3. If in progress, report its run URL and check again on the next scheduled task; do not claim completion.
4. For a completed run, read the job steps and download the artifact named `midnight-shorts-RUN_ID-ATTEMPT`.
5. Inspect `production-status.json`: `build_result`, `qa_status`, `errors`, `warnings`, and each video's `duration_seconds`. The report lives inside the Actions artifact, **not** in the main branch.
6. On failure, inspect logs and fix the root cause. On warning, note the issue and prioritize fixes (the current 2026-10-26 script/story may produce shorts under 60 seconds).
7. Confirm real scene assets, nonempty audio, and bilingual output. A valid MP4 alone does not establish full creative quality. Review playback separately when available.
8. Include the run URL, outcome, two durations, findings, and next steps in the daily report.

## Behavior
- Build and QA failures fail the workflow; the artifact upload still runs using `if: always()`.
- Videos and `production-status.json` are uploaded as a per-run artifact.
- GitHub Actions notifications are controlled by each user's GitHub settings.
- Daily ChatGPT task scheduling and enabling are configured separately; changing this repository does not activate a disabled ChatGPT task.
