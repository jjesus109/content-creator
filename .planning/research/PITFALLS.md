# Pitfalls Research

**Domain:** AI Automated Social Media Content Pipeline
**Researched:** 2026-02-19
**Confidence:** MEDIUM (WebFetch/WebSearch restricted; findings based on official API documentation patterns from training data + verified library behaviors. Flags LOW confidence where unverified.)

---

## Critical Pitfalls

### Pitfall 1: HeyGen Webhook Delivery Is Not Guaranteed — Polling Is Required as Fallback

**What goes wrong:**
The system registers a webhook URL for HeyGen video completion callbacks and assumes delivery. In reality, webhooks can fail silently: the HeyGen callback hits a cold Railway/Render instance that hasn't spun up yet, a transient network error drops the payload, or the endpoint returns a non-200 and HeyGen does not retry. The video renders successfully on HeyGen's side but the pipeline never knows — the daily video silently never reaches Telegram.

**Why it happens:**
Developers treat webhooks as guaranteed delivery. They aren't. HeyGen's webhook is a fire-and-forget HTTP POST. If the receiving server is down, sleeping (free tier), or returns an error, the notification is lost. There is no queue-based retry guarantee in the HeyGen webhook system (MEDIUM confidence — verify retry policy in HeyGen docs before relying on webhook-only).

**How to avoid:**
Implement a two-layer approach: webhook as fast path + polling as guaranteed fallback. After triggering a HeyGen generation, store the `video_id` in the database with status `pending`. A background job (APScheduler or Celery beat) polls `GET /v1/video_status.get?video_id=X` every 90 seconds for any videos still in `pending` state older than 3 minutes. When the video completes (either via webhook or poll), the job processes it and advances the pipeline. Never treat a day's generation as "lost" without polling confirmation.

```python
# Pattern: Dual-path completion detection
async def handle_heygen_webhook(payload: dict):
    video_id = payload.get("video_id")
    if payload.get("status") == "completed":
        await mark_video_ready(video_id, payload["video_url"])

# Fallback poller — runs every 90s via APScheduler
async def poll_pending_videos():
    pending = await db.get_videos_where(status="pending", created_before=minutes_ago(3))
    for video in pending:
        status = await heygen_client.get_video_status(video.heygen_id)
        if status["status"] == "completed":
            await mark_video_ready(video.heygen_id, status["video_url"])
        elif status["status"] == "failed":
            await mark_video_failed(video.heygen_id, status.get("error"))
```

**Warning signs:**
- Daily pipeline completes generation step but Telegram message never arrives, with no error log
- HeyGen dashboard shows video as "completed" but system DB still shows `pending`
- Webhook endpoint returning 5xx on cold start (Railway/Render sleep)

**Phase to address:** Phase covering HeyGen integration and async pipeline wiring (core video generation phase)

---

### Pitfall 2: HeyGen Video Generation Fails Silently on Script Length / Character Encoding

**What goes wrong:**
HeyGen silently accepts the API request and returns a `video_id`, but the video renders with corrupted audio, mismatched lip-sync, or fails at the render stage — because the script exceeded the practical character limit, contained special characters that broke SSML, or had punctuation the TTS engine mispronounces. In Spanish, characters like `¿`, `¡`, accents (`á`, `é`), and em-dashes frequently cause silent render failures or degraded lip-sync quality.

**Why it happens:**
The HeyGen API accepts the payload without validation errors but fails during the async render step. The 140-word limit specified in the project requirements is a business constraint — HeyGen's actual character limit is higher but TTS quality degrades with longer scripts. The lip-sync quality depends on the voice pacing matching the avatar's mouth movement, which is sensitive to punctuation patterns.

**How to avoid:**
Pre-validate scripts before sending to HeyGen: (1) enforce 140-word hard cap with auto-truncation at sentence boundaries, (2) strip or replace characters known to cause TTS issues — em-dashes become commas, ellipses become periods, (3) validate UTF-8 encoding explicitly, (4) log the exact script sent to HeyGen alongside the `video_id` so you can correlate render failures to content. Test with Spanish accent characters in the first development week before assuming they work.

**Warning signs:**
- Render status shows `failed` with vague error like `processing_error` or no error message
- Videos with accented characters fail at higher rate than ASCII-only scripts
- Lip-sync visually drifts after the 30-second mark (too-long script overflowing expected duration)

**Phase to address:** Script generation phase + HeyGen integration phase

---

### Pitfall 3: Railway/Render Sleeping Kills Webhook Reception and Cron Triggers

**What goes wrong:**
Free and entry-tier instances on Railway and Render sleep after inactivity periods (typically 15 minutes on Render free tier). The daily cron trigger fires at the scheduled time, but the instance is asleep. The HTTP request that wakes it adds 10-30 seconds of cold start delay. If the cron trigger is an external service hitting an endpoint (rather than an internal scheduler), it may time out before the instance wakes. Even on paid tiers, instance restarts cause webhook drops during the restart window.

**Why it happens:**
Developers assume a deployed service is always running. Serverless-adjacent platforms with sleep modes are not equivalent to always-on servers. This is particularly dangerous for a system where one missed trigger = one lost content day.

**How to avoid:**
Use one of: (1) Internal APScheduler within the FastAPI process (most reliable for single-instance — scheduler runs inside the process, wakes with the process), (2) Railway cron job (Railway-native, separate from the web service), or (3) External ping service (UptimeRobot pings the health endpoint every 5 minutes to prevent sleep). The safest is APScheduler inside the app for the daily trigger, with an external health ping to prevent sleep. Never rely on an external HTTP call to an endpoint as the sole cron mechanism.

**Warning signs:**
- Cron trigger logs show no activity despite scheduled time passing
- Cold start latency visible in Railway/Render logs on the first request each morning
- HeyGen webhook arriving when instance is mid-restart

**Phase to address:** Infrastructure setup phase (before any integration work)

---

### Pitfall 4: Ayrshare / TikTok Video Upload: Format Requirements Are Strict and Platform-Specific

**What goes wrong:**
A video that plays perfectly locally — and even on HeyGen's preview — gets rejected by Ayrshare's TikTok publishing endpoint with an opaque error like `invalid_video` or `video_processing_failed`. The root causes are: codec not H.264 (TikTok requires H.264/AAC), bitrate outside acceptable range, duration too short (TikTok minimum is 3 seconds, YT Shorts minimum is 15 seconds for Shorts eligibility), file delivered via URL that expires before TikTok finishes downloading it.

**Why it happens:**
HeyGen outputs MP4 files. The codec and bitrate are generally correct, but: (1) HeyGen's download URLs are time-limited (typically signed S3 URLs with 1-24h expiry), (2) platform requirements differ subtly between TikTok, Instagram, and YouTube, and (3) the video must be re-hosted at a stable URL before sending to Ayrshare, or uploaded as a binary — not forwarded via a time-limited HeyGen URL.

**How to avoid:**
Always download the HeyGen output to your own storage (Supabase Storage or S3) immediately upon completion, before sending to Ayrshare. Use the stable self-hosted URL for publishing. Validate video specs before publishing: use `ffprobe` (via `ffmpeg-python`) to confirm codec=H.264, audio codec=AAC, resolution=1080x1920, duration within platform bounds. Store the ffprobe output in the DB record for debugging. For TikTok specifically: minimum 3s, maximum 60s for standard, file size under 500MB, H.264/AAC required. (MEDIUM confidence — verify current TikTok limits via Ayrshare docs at build time.)

```python
# Pattern: Always re-host before publishing
async def process_completed_video(video_id: str, heygen_url: str):
    # Step 1: Download from HeyGen (time-limited URL)
    video_bytes = await download_with_retry(heygen_url)

    # Step 2: Store in own infrastructure
    stable_url = await supabase_storage.upload(f"videos/{video_id}.mp4", video_bytes)

    # Step 3: Validate format
    specs = await validate_video_specs(video_bytes)  # ffprobe
    assert specs.codec == "h264", f"Wrong codec: {specs.codec}"

    # Step 4: Publish from stable URL
    await ayrshare_client.post(video_url=stable_url, platforms=["tiktok", "instagram"])
```

**Warning signs:**
- Ayrshare returns success but TikTok shows upload as failed in platform dashboard
- Publishing errors appearing 1-3 hours after `ayrshare.post()` succeeds (async platform processing failure)
- HeyGen URL in Ayrshare request is expired (URL was >24h old)

**Phase to address:** Video storage phase (must precede publishing phase) and publishing integration phase

---

### Pitfall 5: Cost Runaway from Daily AI Generation Without Budget Guards

**What goes wrong:**
The daily pipeline runs autonomously. A bug causes the scheduler to trigger 5 times in one day instead of once. Or rejection feedback triggers re-generation loops — the bot rejects, generates again, rejects again, generating 3-4 videos per day. Each generation costs: GPT-4o script (~$0.01-0.03), HeyGen avatar video (~$0.50-2.00 per video depending on plan), ElevenLabs TTS (~$0.18-0.30 per 1k characters). Five accidental runs = $10-15 in a day. A looping rejection bug = $50-100/week in HeyGen credits alone.

**Why it happens:**
Autonomous systems without hard daily limits assume the scheduler works correctly. Rejection loops are particularly dangerous because they're by design — just unbounded by design.

**How to avoid:**
Implement a hard daily generation counter in the database with a circuit breaker. Before triggering ANY paid API call, check: has today's generation quota been reached? Default quota: 2 generations per day (one auto + one re-generate after rejection). On the third attempt, the bot sends a Telegram message to the creator: "Daily generation limit reached. Manual override required." Also implement ElevenLabs and HeyGen budget alerts via their respective dashboards, and set soft spend alerts at $50/month.

```python
MAX_DAILY_GENERATIONS = 2  # configurable env var

async def can_generate_today() -> bool:
    today_count = await db.count_generations_today()
    if today_count >= MAX_DAILY_GENERATIONS:
        await telegram_bot.notify_creator(
            "Daily generation limit reached. Reply /override to force generate."
        )
        return False
    return True
```

**Warning signs:**
- Database shows multiple generation records for same calendar date
- API cost dashboards (HeyGen, ElevenLabs, OpenAI) show unexpectedly high daily spend
- Rejection reason stored but no backoff between re-generation attempts

**Phase to address:** Core pipeline orchestration phase (day one of pipeline building)

---

### Pitfall 6: pgvector Similarity Threshold of 0.85 Is Arbitrary and Will Misfire

**What goes wrong:**
The 0.85 cosine similarity threshold is set in code and never revisited. In practice, it either: (a) blocks too many valid topics because the embedding space is dense for a narrow philosophical niche — "Estoicismo y soledad" and "La virtud en el silencio" might score 0.87 similarity with `text-embedding-ada-002` but are genuinely different videos, or (b) allows near-identical topics through because the rephrasing is sufficiently different to drop below 0.85. The system then generates repetitive content within weeks.

**Why it happens:**
Similarity thresholds are calibrated for general-purpose text. A content niche with consistent vocabulary (the 5 Pillars, Memento Mori, Amor Fati) will have higher baseline similarity across all content than a general knowledge base. The 0.85 threshold was chosen as a business rule, not calibrated against actual content.

**How to avoid:**
(1) Use `text-embedding-3-small` or `text-embedding-3-large` (OpenAI's newer embeddings — significantly better semantic separation than `ada-002`), (2) seed the vector database with 20-30 manually written example scripts representing distinct topics before launch to calibrate the actual similarity distribution, (3) store the similarity score with every generation attempt so you can analyze the distribution after 30 days and tune the threshold. Make the threshold a configurable env var, not a hardcoded constant. Consider using a lower threshold (0.80) initially and raising it if repetition occurs.

**Warning signs:**
- More than 30% of generation attempts are rejected for similarity in the first two weeks
- Topic diversity visible from titles is clearly shrinking week-over-week
- Rejected scripts are semantically different from stored content (threshold too aggressive)

**Phase to address:** Vector database setup phase

---

### Pitfall 7: Telegram Bot Loses Messages During Webhook vs Polling Race Condition

**What goes wrong:**
The Telegram bot is configured for webhook delivery (correct for production). During development, polling mode is also running locally. When both are active simultaneously — even briefly — Telegram only delivers each update to one receiver, randomly. The creator approves a video in production Telegram, but the approval message goes to the local dev instance, not the production one. The production pipeline never receives the approval.

**Why it happens:**
Telegram's bot update system uses either `setWebhook` (push) OR `getUpdates` polling — not both simultaneously. Starting polling on any client automatically removes the webhook. Many tutorials show polling for simplicity, so developers run local dev with polling while production uses webhook. Switching between them mid-development causes silent message drops.

**How to avoid:**
Strict environment separation: development always uses a separate bot token (create a second bot via @BotFather for dev). Never run the production token in polling mode. The production service should call `setWebhook` on startup with its public URL and log the result. Add a startup check: call `getWebhookInfo` and verify the webhook URL matches the expected production URL before accepting any traffic.

```python
async def startup_webhook_check():
    info = await bot.get_webhook_info()
    expected_url = settings.WEBHOOK_URL
    if info.url != expected_url:
        logger.warning(f"Webhook mismatch: got {info.url}, expected {expected_url}")
        await bot.set_webhook(expected_url)
        logger.info("Webhook re-registered")
```

**Warning signs:**
- Approval buttons work locally but not in production
- Creator taps [Approve] but no publish event fires in production logs
- Bot responds locally but not in the deployed environment

**Phase to address:** Telegram bot integration phase

---

### Pitfall 8: Telegram Bot Rate Limiting on Video Sending

**What goes wrong:**
Telegram limits file uploads: bots can send files up to 50MB via `sendVideo`, and up to 2GB if using `telegram.Bot.send_video` with a URL reference to an already-uploaded file. A 1080p 40-second video at HeyGen's output quality will typically be 30-80MB — right at the edge. If the pipeline sends the video directly from the file, and it's over 50MB, the send fails with `FILE_PART_TOO_LARGE` or similar. Additionally, Telegram rate-limits bots to 30 messages/second globally and 1 message/second per chat — the approval message + video together count as 2 sends.

**Why it happens:**
Developers test with compressed/short videos. The actual HeyGen output at 1080p/40s can easily exceed the 50MB `sendVideo` direct upload limit.

**How to avoid:**
Always send the video as a URL reference (Telegram fetches it from your storage URL) rather than uploading the file directly. Supabase Storage provides public URLs — use those. If the video must be uploaded directly, compress to under 50MB using ffmpeg before sending. Store the Telegram `message_id` of the sent video so you can delete it after approval/rejection (keeps the chat clean).

```python
# Correct: Send as URL (no 50MB limit for URL-referenced videos)
await bot.send_video(
    chat_id=CREATOR_CHAT_ID,
    video=stable_supabase_url,  # URL, not file bytes
    caption=post_copy_text,
    reply_markup=approval_keyboard
)
```

**Warning signs:**
- `FileTooLarge` exceptions in Telegram send logs
- Videos send successfully in testing but fail in production (production videos are longer/higher quality)

**Phase to address:** Telegram bot integration phase

---

### Pitfall 9: Platform Publishing Is Asynchronous — Ayrshare Success != Published

**What goes wrong:**
`ayrshare.post()` returns HTTP 200 with a `postIds` object. The pipeline marks the content as "published" and moves on. In reality, Ayrshare's response confirms the post was accepted into Ayrshare's queue — not that the platform (TikTok, Instagram) published it. TikTok's own video processing takes 2-10 minutes after Ayrshare submits. If TikTok rejects the video (wrong aspect ratio, policy violation, quota exceeded), the failure only appears in Ayrshare's webhook callback or via polling the post status endpoint.

**Why it happens:**
The Ayrshare API response is "we received your request," not "the video is live." This is common across social media scheduling APIs. Developers conflate API acceptance with platform publication.

**How to avoid:**
Implement a post-publish verification step: 15-30 minutes after Ayrshare submission, call `GET /post/{id}` on Ayrshare to verify platform-specific status for each platform. Store the `postId` per platform in the DB. Alert via Telegram if any platform shows status `error` or `rejected`. Build this verification into the pipeline as a scheduled task, not as a blocking wait in the initial publish flow.

**Warning signs:**
- Ayrshare shows success but no video appears in TikTok/Instagram creator studio
- 48-hour metrics harvest returns zero for a video that Ayrshare "published"
- Ayrshare dashboard shows `error` status on individual platform lines despite overall success

**Phase to address:** Publishing integration phase

---

### Pitfall 10: Rejection Feedback Loop Creates Negative Context Pollution

**What goes wrong:**
The rejection feedback system stores the reason for rejection and uses it as negative context for the next generation. After 30 days, the negative context grows to hundreds of entries. GPT-4o's context window starts to fill with "do not do X, do not do Y" instructions, increasing token cost and — more critically — confusing the model. The model begins hallucinating by trying to avoid so many constraints simultaneously, producing scripts that are technically "different" from rejected content but feel disjointed or off-brand.

**Why it happens:**
Negative context is additive without a pruning strategy. "Add rejection reason to context" is simpler to implement than "maintain a rolling window of the most relevant rejection reasons." Over time, the accumulation degrades quality.

**How to avoid:**
(1) Store rejection reasons with timestamps and categorize them (tone, topic, structure, length, philosophy deviation), (2) at prompt construction time, include only the top N=5-10 most recent rejections AND the top N=5 most semantically similar rejections (using pgvector similarity against the current script topic), (3) summarize recurring patterns: if 10 rejections all say "too preachy," compress them to one instruction "avoid preachy tone," (4) set a 30-day soft expiry on rejection reasons — older rejections carry less weight unless they're recurrent patterns.

**Warning signs:**
- GPT-4o prompt token count growing week over week
- Script quality degrading despite more rejection context (more isn't better)
- Rejection reasons for the current script have no semantic relationship to prior rejected scripts

**Phase to address:** Rejection feedback loop phase + any phase that touches prompt construction

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode similarity threshold (0.85) | Faster initial setup | Content repetition or over-rejection after 30+ days | Never — use env var from day 1 |
| Webhook-only for HeyGen (no polling fallback) | Simpler code | Silent video loss when webhook fails | Never — always implement polling fallback |
| Use HeyGen's time-limited URL directly in Ayrshare | Saves storage step | Expired URL = publish failure; no stable record | Never — always re-host |
| Store all rejection context indefinitely | Simpler than pruning | Token bloat, model confusion after 30 days | Never — implement rolling window from the start |
| Single bot token for dev and prod | Fewer tokens to manage | Webhook/polling conflict, message routing chaos | Never — always use separate tokens |
| Synchronous blocking wait for HeyGen render | Simple sequential code | FastAPI worker blocked for 3-8 minutes, can't serve other requests | Never — always async with background tasks |
| Polling 48h metrics synchronously at pipeline end | Avoids separate scheduler | Blocks pipeline completion, fails if platform is slow | Never — always schedule as a separate async job |
| Skip ffprobe format validation before publishing | Faster dev iteration | Silent platform rejections, hard to debug | Acceptable in first test run only |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| HeyGen | Treating `video_id` response as success | `video_id` only means "queued" — poll or webhook for actual completion |
| HeyGen | Not storing `video_id` before webhook arrives | Store `video_id` immediately after POST; webhook arrives minutes later |
| HeyGen | Sending scripts with Spanish special characters without testing | Test `¿¡áéíóúüñ` encoding in HeyGen TTS before production |
| ElevenLabs | Generating TTS and HeyGen avatar separately without syncing | HeyGen can use ElevenLabs voice directly via voice ID — avoids separate audio file management |
| Telegram (python-telegram-bot) | Using polling and webhook simultaneously | One mode per environment; dev bot ≠ prod bot |
| Telegram | Sending video file bytes when video >50MB | Send public URL instead; Telegram fetches from your storage |
| Ayrshare | Treating HTTP 200 from `post()` as "published" | Poll post status 15-30 min later to confirm platform delivery |
| Ayrshare | Submitting expired HeyGen URL | Always upload to Supabase/S3 first, submit stable URL |
| Ayrshare / TikTok | Not accounting for TikTok-specific content policy review | TikTok async review can take hours; final status not in initial API response |
| Supabase pgvector | Using `text-embedding-ada-002` for Spanish philosophical content | Use `text-embedding-3-small` or `3-large`; ada-002 has weaker multilingual semantic separation |
| OpenAI | Treating completion success as script quality | Validate: word count, structure (hook/body/CTA present), philosophy pillar reference |
| OpenAI | No retry on transient 429/503 errors | Implement exponential backoff (tenacity library); 429 spikes at high-traffic periods |
| Railway/Render | Assuming instance is always running | Use internal APScheduler for cron; keep alive via external health ping |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous video download from HeyGen blocking FastAPI | Request queue backs up during 3-8 min render wait | Use BackgroundTasks or Celery for all HeyGen interactions | Day 1 — every single render blocks |
| Full vector search across all stored scripts (no index) | pgvector query time grows linearly with script count | Create HNSW or IVFFlat index on embedding column at migration time | ~500 stored scripts (~1.5 years of daily content) |
| Downloading video to memory for ffprobe validation | Memory spike on Railway's small instances | Stream to temp file, run ffprobe on file, delete immediately | Videos over ~100MB |
| Polling Ayrshare status in a tight loop | Rate limit 429s from Ayrshare | Use exponential backoff starting at 30s intervals | Any polling without backoff |
| Storing full video bytes in Supabase DB (not Storage) | DB size explodes, queries slow | Use Supabase Storage for binary; DB for metadata/URLs only | First video stored in DB |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Telegram bot not locked to creator's user ID | Anyone who finds the bot link can trigger generation (cost attack) | Validate `update.effective_user.id == CREATOR_USER_ID` in every handler; reject all others |
| HeyGen webhook endpoint without signature verification | Anyone can POST fake completion events and trigger publishing | Verify HeyGen webhook signature header; reject unsigned requests (check HeyGen docs for their signature mechanism) |
| Ayrshare API key in code or logs | Key can be used to publish to all connected platforms without limit | Env var only; scrub from all log output; rotate if ever committed |
| Supabase anon key used for server-side operations | Anon key has RLS-limited access; may fail silently on protected tables | Use service role key server-side (never expose to any client) |
| HeyGen-generated video URLs logged with signed S3 params | Time-limited signed URLs in logs; leaked logs = content access | Log only the `video_id`, not the full signed URL |
| No rate limit on webhook endpoint | Webhook endpoint open to flooding | IP allowlist for HeyGen's IP ranges, or at minimum rate-limit per IP |

---

## UX Pitfalls

Common user experience mistakes in this domain (creator-facing Telegram interface).

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress indicator between generation trigger and Telegram delivery (3-8 min gap) | Creator thinks the system is broken | Send "Generating your video... (est. 5-8 min)" immediately after daily trigger fires |
| Approval message has no script preview — video only | Creator can't judge script quality without re-watching | Include script excerpt (first 40 words) and post copy in the approval message alongside video |
| No explicit "what was rejected and why" summary in re-generation message | Creator forgets what they rejected | After re-generation, show: "Rejected because: [reason]. New attempt:" |
| Weekly mood profile prompt arrives without context | Creator confused about what mood profile affects | Include brief explanation: "This affects this week's tone and topics. Current profile: [X]" |
| Virality alert fires at all hours (Sunday report + 500% spike alert) | Disruptive notification timing | Schedule Sunday report for 9am creator timezone; virality alerts respect quiet hours (22:00-08:00) |
| Publishing confirmation not sent to creator | Creator doesn't know if content went live | Send Telegram message with platform links after Ayrshare confirms publication |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **HeyGen integration:** Works for completion but missing failure status handling — verify `failed` and `processing` statuses are handled, not just `completed`
- [ ] **Telegram approval flow:** Buttons work but missing: what happens if creator never responds? Add 24h timeout with "No response — skipping today" auto-action
- [ ] **Ayrshare publishing:** Posts submitted but missing post-status verification 15-30 minutes later — a publish "success" is not a platform success
- [ ] **Vector similarity:** Database has embedding search but missing: HNSW index created? Embedding model matches between storage and query? (Same model must be used for both)
- [ ] **48h metrics harvest:** Scheduled task exists but missing: what if the video was never actually published (failed silently)? Harvest should check published status first
- [ ] **Storage lifecycle:** Code exists to upload videos but missing: the cleanup job that moves Hot→Warm→Cold and deletes at 45d (except viral flagged)
- [ ] **Cost circuit breaker:** Daily generation runs but missing: the counter check that prevents >2 generations per day
- [ ] **Rejection feedback:** Negative context stored but missing: the pruning logic that limits context to top N recent/relevant rejections
- [ ] **Railway/Render health:** Service deploys but missing: `/health` endpoint that verifies DB connection, Supabase connection, and scheduler is running
- [ ] **Spanish character validation:** Script generation works for English-style text but missing: explicit test with full Spanish character set through HeyGen TTS

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| HeyGen webhook missed, video lost | LOW | Query HeyGen `GET /v1/video_status.get` with stored `video_id`; re-trigger pipeline from completion handler |
| Cost runaway from scheduler bug | MEDIUM | Disable scheduler immediately via env var; audit DB for duplicate generations; request HeyGen credit review if caused by system bug |
| Platform publishing failure (wrong format) | LOW | Download video from Supabase, run ffmpeg transcode to correct specs, re-submit to Ayrshare |
| pgvector threshold too aggressive (blocking valid content) | LOW | Lower threshold env var; no data migration needed |
| Webhook/polling conflict (Telegram message loss) | MEDIUM | Delete dev bot webhook (`deleteWebhook`), recreate production webhook; re-send last missed approval message manually |
| Rejection feedback pollution degrading script quality | MEDIUM | Truncate rejection context to last 10 entries; summarize older entries into category rules; redeploy |
| Expired HeyGen URL in Ayrshare submission | MEDIUM | Re-fetch video from HeyGen if still within URL validity, or re-trigger generation if expired; add URL-age validation before submission |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| HeyGen webhook unreliable (Pitfall 1) | HeyGen integration phase | Simulate webhook failure; confirm polling catches the completion |
| Script encoding failures (Pitfall 2) | Script generation phase | Test with full Spanish character set, verify HeyGen accepts and renders correctly |
| Railway/Render sleeping (Pitfall 3) | Infrastructure setup phase (Phase 1) | Deploy health endpoint; verify APScheduler fires at scheduled time after 30-min idle |
| Ayrshare format/URL requirements (Pitfall 4) | Video storage phase (before publishing) | Publish test video from stable Supabase URL; verify via platform dashboard |
| Cost runaway (Pitfall 5) | Core pipeline orchestration phase | Trigger pipeline 3 times in one day; verify third attempt is blocked with Telegram alert |
| pgvector threshold miscalibration (Pitfall 6) | Vector database setup phase | Run similarity search on 10 semantically distinct topic pairs; verify expected rejection/acceptance behavior |
| Telegram webhook/polling conflict (Pitfall 7) | Telegram bot integration phase | Simultaneously run dev polling and prod webhook; verify production receives messages |
| Telegram file size limit (Pitfall 8) | Telegram bot integration phase | Send a 60MB test video as URL; verify delivery without size error |
| Ayrshare async publish status (Pitfall 9) | Publishing integration phase | Submit post; verify post-status check 15-30 min later catches any platform rejection |
| Rejection context pollution (Pitfall 10) | Rejection feedback loop phase | Insert 50 rejection entries; verify only top N are included in next generation prompt |

---

## Sources

- HeyGen API documentation patterns (async video generation, webhook/polling behavior) — MEDIUM confidence (training data; verify at https://docs.heygen.com before implementation)
- Ayrshare API documentation (multi-platform publishing, TikTok constraints) — MEDIUM confidence (verify at https://docs.ayrshare.com)
- TikTok for Developers: video upload requirements — MEDIUM confidence (verify current limits at https://developers.tiktok.com; TikTok API terms change frequently)
- python-telegram-bot and aiogram webhook vs polling behavior — HIGH confidence (well-documented library behavior)
- Supabase pgvector HNSW index requirements — HIGH confidence (Supabase docs are explicit about index creation requirement)
- OpenAI embedding models (`text-embedding-3-*` vs `ada-002`) — HIGH confidence (official OpenAI docs, embeddings upgrade documented)
- APScheduler behavior in FastAPI — HIGH confidence (widely documented pattern)
- Railway/Render sleep behavior — MEDIUM confidence (free tier behavior; paid tier may differ — verify at time of infrastructure selection)

---
*Pitfalls research for: AI Automated Social Media Content Pipeline*
*Researched: 2026-02-19*
