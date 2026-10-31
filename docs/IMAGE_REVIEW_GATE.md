# Mandatory visual approval before GitHub image upload

**Required for every future 《午夜異常廣播》 episode.** The 2026-10-31 bonus
episode was produced with weak procedural artwork without image-by-image
approval. That workflow is now halted by default.

## Required sequence

1. Generate 6-8 distinct, cinematic, legible **9:16** scene images. Do not
   crop a montage into individual images or upscale poor-quality placeholders.
   Check continuity, characters, backgrounds, visual storytelling, and technical
   quality. Provide a contact sheet **and all full-resolution individual scenes
   directly in the ChatGPT conversation**; the ad card must also be shown.
2. Wait for the user's **explicit approval for this exact episode and these
   exact images**. No silence, older approval, "start a daily episode",
   GitHub PR review, or green CI status counts as image approval.
3. Until that approval, **DO NOT upload images/assets to GitHub, create image
   blobs, commit the episode, dispatch builds, deploy preview pages, or publish
   on YouTube**. A local preview ZIP in the conversation is allowed.
4. After approval, record all approved images' SHA-256 hashes in
   `reviews/<story_id>.json`. Never invent approval, invent hashes, or
   update the manifest to silently accept edited images. The manifest is
   a record of real human approval, not proof by itself.

   Example (illustrative only; NOT an approval):

   ```json
   {
     "story_id": "reviewed_example_20261101",
     "episode_id": "20261101-reviewed-example",
     "visual_review_approved": true,
     "images": [
       {"file": "assets/episodes/20261101-reviewed-example/scene01.webp",
        "sha256": "<SHA-256 from the image the user actually approved>"}
     ]
   }
   ```

5. After human approval, commit only the exact approved image bytes and
   accompanying story/job/manifest; do not replace scenes without a new review.
   `scripts/verify_visual_approval.py` rejects missing approval records,
   wrong story IDs, missing images, and changed image bytes.
6. The daily and historical bonus workflows no longer start on `push`. Use
   explicit **GitHub Actions > Run workflow** only after human review, with
   matching approved story ID and `visual_review_approved=true`. A workflow
   checkbox is an additional safeguard, not a substitute for showing images
   to the user before GitHub transfer. Workflows also verify hashes.
7. Render with Edge TTS and production QA. YouTube upload and posting affiliate
   comments are **separate later user approvals**. The new visual approval
   does not authorize them.

Note: Repository-level branch protection or required external human reviewers
would add stronger enforcement against direct manual image pushes. These are
not configured by this change; current controls address the assistant's
workflow, the daily task, and automated video rendering.
