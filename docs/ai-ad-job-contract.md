# AI-authored daily creative handoff (PR #3)

The human operator maintains the reviewed affiliate CSV. ChatGPT (or another authorized external AI process) selects a product and creates scene images, an ad image, and creative copy. GitHub only validates the submitted job and renders/QA-checks videos. **This PR does not schedule or call ChatGPT, fetch CSV itself, or automatically upload images.** The job and PNG files must exist on the checked-out branch before running.

To opt in, add `jobs/daily-ad-job.json` and its files under `assets/` then set the repository variable `AI_AD_JOB_ENABLED=true`. Keep `PRODUCT_ADS_ENABLED=false` while using this mode; the two are mutually exclusive. Dispatch `daily-shorts.yml` manually for the private YouTube upload. A regular push produces previews, not YouTube uploads.

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

To publish a product card, the external agent must provide `product_ad.enabled=true` together with `publication_approved=true` and a full existing PR #3 product-ad object: `status=verified`, `language=zh`, `voiceover=false`, `story_id`, `duration_seconds`, `headline`, `ad_copy_zh`, `slogan`, `cta`, `disclosure`, and `product` with the current validated TW affiliate fields from the approved source. Additionally `product_ad.card_image` must point to an actual 1080x1920 file under `assets/`. Never fabricate affiliate eligibility, dates, tracking links, or approval.

The job loader rejects story ID mismatch, fewer than six/more than eight scene images, missing or unsafe asset paths, and approved ads without a real card. It preserves the AI-written ad text rather than calling `make_ad()`. The original `PRODUCT_AD_FILE` route remains available when AI mode is off. QA and the uploader load the same AI job, protecting against mismatched product descriptions.

Example above is intentionally disabled; real affiliate offers and images are not bundled.
