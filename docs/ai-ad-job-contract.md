# AI-authored daily creative handoff (PR #3)

The human operator maintains the reviewed affiliate CSV. ChatGPT (or another authorized external AI process) selects a product and creates scene images, an ad image, and creative copy. GitHub only validates the submitted job and renders/QA-checks videos. **This PR does not schedule or call ChatGPT, fetch CSV itself, or automatically upload images.** The job and PNG files must exist on the checked-out branch before running.

Scene images may be still PNG, JPEG, or WebP files. They are decoded by Pillow and converted into lossless PNG intermediates before FFmpeg renders the 1080x1920 H.264 shorts. WebP support does not change the final MP4 format. Square images are center-cropped for vertical video, so provide 9:16 artwork when possible.

When `jobs/daily-ad-job.json` exists, the daily-shorts workflow now prefers it by default for preview rendering; set repository variable `AI_AD_JOB_ENABLED=false` to explicitly return to the legacy feed mode. Keep `PRODUCT_ADS_ENABLED=false` while using AI mode; the two are mutually exclusive. `daily-shorts.yml` produces videos, QA, artifacts and potentially **public GitHub Pages previews**, but never uploads to YouTube (including manual runs). Only the separate `upload-existing-artifact.yml` may upload, after explicit human review, a supplied run ID, run attempt, story ID, and approval checkbox. It checks source SHA against the artifact and uses the original build commit metadata.

The job payload is:

```json
{
  "schema_version": 1,
  "story_id": "EXACT_ID_FROM_stories/today.json",
  "publication_approved": false,
  "scene_images": [
    {"file": "assets/generated/episode/scene-01.png", "effect": "slow_zoom"},
    {"file": "assets/generated/episode/scene-02.png"},
    {"file": "assets/generated/episode/scene-03.png"},
    {"file": "assets/generated/episode/scene-04.png"},
    {"file": "assets/generated/episode/scene-05.png"},
    {"file": "assets/generated/episode/scene-06.png"}
  ],
  "product_ad": {"enabled": false}
}
```

To render a **review-only ad preview**, the external agent may provide `product_ad.enabled=true` while retaining `publication_approved=false` and a full existing PR #3 product-ad object: `status=verified`, `language=zh`, `voiceover=false`, `story_id`, `duration_seconds`, `headline`, `ad_copy_zh`, `slogan`, `cta`, `disclosure`, and `product` with the current validated TW affiliate fields from the approved source. An optional `product_ad.card_image` must point to a real 1080x1920 file under `assets/`; otherwise the renderer creates a text-only 1080x1920 card. The creative displays "商品推廣" without earnings claims; the full commercial disclosure is retained in publication metadata/comments. Never fabricate affiliate eligibility, dates, tracking links, or approval.

The job loader rejects story ID mismatch, fewer than six/more than eight scene images, missing or unsafe asset paths, and nonexistent user-provided card images. Preview does not authorize YouTube upload. It preserves the AI-written ad text rather than calling `make_ad()`. The original `PRODUCT_AD_FILE` route remains available when AI mode is off. QA and the uploader load the same AI job, protecting against mismatched product descriptions.

Example above is intentionally disabled; real affiliate offers and images are not bundled.

## V2 production handoff gates

- CSV has 12 adapter fields; extra review columns are ignored by `import_affiliate_csv.py`. The selected `product` must equal the adapter's 12-field object exactly.
- No fixed 24-hour `verified_at` age limit applies to candidate selection, approved ad rendering, or upload; the original timestamp is retained for audit. Validation still rejects expired (`expires_at`), future-dated, malformed, non-TW or ineligible offers and mismatches against the reviewed CSV. A long expiry is not proof that a Shopee affiliate link remains commercially active; the operator is responsible for accurate source data, and ad/publication authorization remains separate.
- Build a complete branch with 6–8 actual image assets and matching `stories/today.json` and optional `jobs/daily-ad-job.json`; no fake paths. Keep `publication_approved=false` until separately authorized; `product_ad.enabled=true` is allowed for reviewed GitHub preview rendering only, not YouTube upload.
- In AI-job mode, set `AI_AD_JOB_ENABLED=true`, `PRODUCT_ADS_ENABLED=false`. This switch is configured in GitHub repository Variables, not automatically by the prompt.
- Final videos must be 60–90 seconds. Chinese 8-second silent product end-card, if separately approved, must fit in that total; the English IG promo must also fit its total.
- The archive and build workflows are independent. Confirm their actual GitHub runs, artifact QA, original source SHA, subtitle and audio output, and potential public Pages exposure before reporting success.
- Explicit user authorization for any YouTube upload is a separate step, never inferred from story creation, preview rendering, or CI success.
- Affiliate links can be posted through the separate manual `post-affiliate-comment.yml` after a **previously authorized** YouTube video is unlisted or public; private videos do not support comments, and links in Shorts comments are not clickable. The script must validate the channel, video and exact reviewed product and preserve commercial disclosure. No comment is posted during ordinary CI runs.
