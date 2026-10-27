# Shopee affiliate CSV adapter (candidate-only)

This supplements PR #3; it does **not** connect to Shopee Taiwan's affiliate API.
The operator exports an authorized product list and manually reviews it before
updating `data/affiliate/reviewed-products.csv`. Never commit account tokens,
personal data, raw account reports, or sensitive tracking details to this public
repository. If your export contains private fields, strip them first.

## CSV headers

`id,name,market,available,affiliate_eligible,affiliate_url,source,verified_at,expires_at,keywords,benefit_zh,commission_rate`

- `available` and `affiliate_eligible`: literal `true` / `false`; never infer.
- `verified_at` and `expires_at`: actual, independently verified ISO-8601 timestamps **with timezone**. Never fabricate or refresh the timestamps merely by importing the same weekly CSV.
- `affiliate_url`: the actual official link generated for this account. A normal Shopee listing URL alone does not prove eligibility.
- `keywords`: pipe-separated story tags, e.g. `深夜|公車|夜路`.
- `commission_rate`: optional fraction 0–1; price is not part of the current contract.
- `source`: audit reference for the authorized offer data.
- Headers are the adapter contract, not necessarily the native Shopee export headers. Map and review the real exported columns first.

## Run

```sh
python scripts/import_affiliate_csv.py --csv data/affiliate/reviewed-products.csv --out output/affiliate-feed.json
python scripts/build_product_candidate.py
```

The daily candidate workflow is opt-in with repository variable
`CANDIDATE_ADS_ENABLED=true`, and can also be run manually. It only uploads
`output/candidate-product-ad.json` as an Actions artifact. It never pushes to
`main`, renders videos, dispatches the Shorts workflow, or calls YouTube.
If the CSV is missing, stale, ineligible, or unrelated to the story, it creates
a blocked report rather than reusing yesterday's product.

**Important:** `PRODUCT_ADS_ENABLED` from PR #3 is a separate switch.
Keep `PRODUCT_ADS_ENABLED=false` (or unset). The existing automated video
end-card path does not include the approval gate and must not be enabled yet.
A candidate's `status=candidate_pending_user_confirmation` and
`enabled=false` prevent the existing `ad_for_language` function from
burning it into the video.

## Later integration

Replace the manual CSV provider with a documented authorized feed adapter,
while retaining the same field contract and review gate. Keep source story ID,
offer ID, expiry, approval identity and exact artifact/commit pinned when adding
the future approved production path.
