# Pitfalls: Adding AI Cat Video Generation to Existing Pipeline

**Domain:** Autonomous content pipeline + AI video generation integration for animal content
**Researched:** 2026-03-18
**Confidence:** MEDIUM-HIGH (Platform policies HIGH via official sources; API reliability MEDIUM via developer reports; music licensing HIGH; prompt engineering MEDIUM; integration patterns MEDIUM)

---

## Critical Pitfalls

### Pitfall 1: Kling/Runway/Pika API Failure Rate and Credit Loss in Automated Daily Generation

**What goes wrong:**
API generates incomplete or unusable video after consuming credits (or API credits freeze mid-generation). With Kling specifically, documented 99% failure rates occur randomly. Credits deducted immediately with no refunds for failed generations. When generation fails at 2:30 AM (scheduler time), creator wakes up with no video to approve, pipeline halts, and credits are lost — no recovery path in automated context. Or: Runway API returns 503 "model overloaded" during peak hours; code retries immediately without backoff, cascading into rate limit block (429) that lasts 24 hours.

**Why it happens:**
- Video generation APIs are fundamentally unreliable at scale: December 2025–February 2026 data shows 45% failure rate during peak hours (6-8 PM PT), failures spike randomly even with simple prompts
- Kling has known issues with credit consumption on failed attempts — credits deducted before validation
- Rate limits not documented consistently; hitting them silently blocks requests rather than returning explicit 429 responses
- Concurrency: scheduling multiple retries during failure cascades API limits and triggers temporary blocks (24h cooldowns documented)
- Synchronous generation wait blocks APScheduler job; if API hangs, entire daily task hangs for hours

**How to avoid:**
1. **Circuit breaker pattern (CRITICAL):**
   - Implement circuit breaker: fail if generation API has >20% failure rate in past 100 requests (sliding window)
   - States: Closed (normal), Open (failing, reject requests), Half-Open (testing recovery)
   - When circuit opens: route to fallback (cache previous video, or hold approval until manual intervention)
   - Half-open state: allow one request through every 5 minutes during cooldown to detect recovery
   - Reset circuit only after 10 consecutive successes

2. **Credit-aware architecture:**
   - Query API balance before attempting generation (implement balance check call)
   - Set hard maximum spend per generation attempt; fail gracefully if balance falls below 15% threshold
   - Log all credit consumption with request ID linking; audit weekly for unexplained debits
   - Maintain 30% minimum balance reserve to avoid mid-month exhaustion
   - Alert creator if balance drops below reserve threshold

3. **Explicit retry strategy with exponential backoff:**
   - Retry only on transient errors (429 rate limit, 503 overloaded, 5xx); never retry on 400 bad request or 401 auth
   - Exponential backoff: 2s, 8s, 32s, 128s (max 4 attempts)
   - Respect Retry-After header from API (if present)
   - Never retry in same hour; queue failed request for next day's attempt
   - After max retries: escalate to Telegram immediately with reason ("API rate limited") rather than silent failure
   - Track retry patterns; if >30% of generations require retry, investigate prompt or API configuration

4. **Async generation with timeout:**
   - Never use synchronous `response = api.generate()` call in APScheduler job
   - Async pattern: schedule generation, store request_id in DB, poll status asynchronously
   - Set maximum wait time: 120s timeout; if generation doesn't complete, mark as pending for next cycle
   - This prevents scheduler job from hanging if API is slow

5. **Offline generation queue:**
   - When API is unreliable, queue scene + music in Redis with priority
   - Batch generation: try generating 2 videos if one fails; hold winner for approval
   - Prioritize high-confidence scenes (verified in testing)
   - Never rely on single synchronous generation response

**Warning signs:**
- Scheduler log shows "generation returned empty response" more than once per week → API reliability degraded
- Credit balance dropped unexpectedly without corresponding video deliveries → credit leakage detected
- Telegram approval doesn't arrive by 7 AM (2+ times/week) → pipeline stuck, circuit not triggering
- CloudWatch/logs show p95 generation latency >60s → API overloaded, circuit should open

**Phase to address:**
Phase 1 (Video Generation Foundation): Circuit breaker is non-negotiable. Must implement before first automated daily run. Test with mock failures (return 503, hang for 120s, return invalid response) to verify circuit behavior. This is a blocker for moving to Phase 2.

---

### Pitfall 2: Music Licensing Automated Strikes — Royalty-Free Misuse in Cross-Platform Posting

**What goes wrong:**
Use a "royalty-free" track from Epidemic Sound or Artlist for one video, then republish the same video to YouTube. Track shows up on YouTube's Content ID system, Copyright holder claims revenue (or strikes), and YouTuber sees channel warning — all without creator knowing. Or worse: Business Accounts on TikTok (as of July 25, 2025) have ZERO access to trending music; only Commercial Music Library + direct licenses allowed, but creator didn't know, uses ineligible track, and post gets flagged/removed. Or: music license expires mid-month; system continues using expired license, platform detects mismatch, and video gets demonetized.

**Why it happens:**
- "Royalty-free" ≠ "free for all platforms." License grant varies: Epidemic Sound may allow TikTok but not YouTube; Artlist allows YouTube but not commercial reuse
- Platform Content ID is automated and aggressive: TikTok, YouTube, Meta all detect music fingerprints instantly, even in background, even if re-encoded
- TikTok Business Account restrictions (effective July 25, 2025) eliminated access to trending/mainstream music; only Commercial Library or direct licenses. Most creators unaware of this switch
- Cross-platform pitfall: Reposting same video to TikTok (allowed track) + YouTube (unlicensed) + Instagram (different terms) creates multiple legal exposures
- Dynamic mood-matched music selection can accidentally pick a track that's licensed for mood selection but NOT for automated publishing
- License expiration dates not tracked; subscription services (Epidemic, Artlist) can revoke access without notice

**How to avoid:**
1. **Maintain music license matrix (CRITICAL):**
   - Create spreadsheet/database: Track ID | License Provider | TikTok (Y/N) | YouTube (Y/N) | Instagram (Y/N) | Commercial Use (Y/N) | Expiration Date | Notes
   - Never use a track for automated posting unless ALL target platforms are marked YES
   - Store matrix in config as Python dict or Supabase table; query before each publish
   - Set up Google Calendar alert 14 days before license expiry for subscription services (Epidemic, Artlist)
   - Audit matrix quarterly: verify entries match actual platform policies (TikTok policy changed mid-2025; YouTube added new restrictions for AI content in 2026)

2. **Single source of truth for music pool:**
   - Hardcode music IDs from ONLY ONE licensed provider in Python config; no fallback to "find music on Spotify" or "use YouTube Audio Library as backup"
   - Validate music ID exists in license matrix BEFORE scheduling generation (pre-flight check in scene generation phase)
   - If mood-matched selection picks unlicensed track, log event + alert via Telegram; do NOT post
   - Maintain 50-track pre-curated backup pool that's verified licensed across all platforms

3. **Platform-aware publishing:**
   - TikTok: Use ONLY tracks from TikTok Commercial Music Library (1000+ tracks officially licensed) OR direct licenses from Merlin/DistroKid
   - YouTube: Use tracks from YouTube Audio Library (400+ free tracks) OR Creative Commons with verified CC license status
   - Instagram: Use tracks from Meta's licensed library (tested via Reels editor) OR Instagram Sound Collection
   - Never post same video to all platforms without platform-specific music validation
   - Implement platform-specific music selection: if mood selection returns unlicensed track for TikTok, fall back to TikTok-only pool

4. **Automated compliance logging and auditing:**
   - Each published video: log track ID + licensing source + platforms + timestamp in audit table
   - Monthly report: list all published music + platforms + cross-reference with Copyright ID matches in platform dashboards
   - Set up automation: if Content ID claim arrives in YouTube, compare claim track to audit log; if mismatch, investigate immediately
   - Test music in each platform (TikTok, YouTube, Instagram) before adding to production pool; save screenshot of "approved" status

5. **Music subscription SLA and renewal tracking:**
   - Epidemic Sound / Artlist licensing: assume 99.9% availability; track subscription renewal dates
   - Buffer: maintain 50-track pre-curated pool verified licensed across all platforms
   - Monthly refresh: check if any tracks removed from provider; remove from production pool if detected
   - If subscription is cancelled or downgraded, immediately remove tracks from rotation

**Warning signs:**
- Content ID claim in YouTube Studio showing track that doesn't match any known track in music pool → licensing matrix out of sync
- TikTok post flagged "contains copyrighted music" or "violates music policy" → track wasn't from Commercial Library or was unverified
- Instagram Reels shows "This content is not available in your country" → music licensing restriction by region or expired license
- Music subscription service account shows "Limited access" or downgrade notice → creator not notified, expired tracks still in rotation
- Same music appears in 3+ consecutive videos → anti-repetition failed, will signal poor content variety to algorithm

**Phase to address:**
Phase 2 (Scene + Music Engine): Before first automated music selection. License matrix and platform-aware publishing must be implemented and validated before scheduling any auto-post. This is not backfillable — if you publish unlicensed music, recovery is expensive (delete video, lose metrics, reupload with licensed music). This is a blocker for automation.

---

### Pitfall 3: Platform Content Moderation for AI-Generated Animal Content — Labeling, Synthetic Disclosure, Account Restrictions

**What goes wrong:**
Post AI-generated cat video to TikTok without using TikTok's "AI-generated content" label, platform's automated detection catches it, applies synthetic media label anyway, and video gets suppressed in FYP (For You Page) algorithm — organic reach drops 60-70% compared to pre-label baseline. Or: creator's account gets flagged for "undisclosed AI content," accumulates violations, and account gets restricted from monetization or branded partnerships. Or: creator doesn't know about mandatory EU Article 50 labeling requirement (August 2026), publishes 100+ unlabeled videos, platform retroactively applies compliance warning and suppresses entire account in EU region.

**Why it happens:**
- TikTok rolled out mandatory C2PA Content Credentials detection (January 2025); it auto-labels AI videos even without creator action, creating perception of "missing label"
- TikTok Community Guidelines (synthetic media): ANY video that's "wholly or significantly" AI-generated MUST be labeled as synthetic/"not real" using TikTok's built-in tool
- YouTube (March 2024 policy, enforcement 2025): Realistic altered/synthetic content depicting events, people, OR PLACES must be labeled (this includes cat in environment)
- Instagram/Meta: Auto-labels AI content created with Meta's own tools; manual tagging required for third-party AI
- EU Article 50 (August 2026): ALL AI-generated content in EU must be labeled, with exception ONLY if human has reviewed/edited and explicitly assumes responsibility
- Undisclosed AI content is treated similarly to misinformation on TikTok; violative content gets removed; repeat violators get restricted from Creator Fund / brand deals
- Platform algorithms already suppress labeled AI content by 30-50% vs unlabeled; creators see this as organic reach penalty

**How to avoid:**
1. **Auto-label on all platforms (CRITICAL - non-negotiable):**
   - TikTok: Use TikTok's built-in "AI-generated content" label in post creation BEFORE publishing (checkbox/toggle in composer)
   - YouTube: Add required label in video description: "This video was created using [Runway Gen-3/Kling/Pika] AI video generation"
   - Instagram: If Reels editor offers AI labeling, use it; otherwise add disclaimer in caption
   - Validate labeling worked: 30 seconds after publish, check if label appears on live post before declaring success
   - Never skip this step; build it into approval flow in Telegram

2. **Caption and bio disclosure (reinforces labeling):**
   - TikTok profile bio: Add "AI-generated cat content" or similar explicit disclosure; this buffers algorithmic suppression
   - Video caption: Include phrase "AI-generated" or "AI-created" in first sentence for every video
   - YouTube description: "This video was generated by [AI provider]. No real cats were filmed."
   - Instagram: Consistent hashtag #AIGeneratedCat or similar in every post
   - These redundant disclosures protect against label visibility issues

3. **EU compliance (August 2026 - CRITICAL DEADLINE):**
   - Track all videos with geo-targeting; assume EU region includes all EU Member States
   - If publishing to EU audience: ALL videos MUST have explicit AI label per Article 50
   - Document creator review: "Reviewed and approved by [creator name] on [date]" in post metadata or description
   - Consider storing all videos with creation metadata (AI provider, prompt, generation timestamp, creator review) for audit trail
   - Test compliance by publishing from EU IP; verify label appears

4. **Monitor suppression signals and account flags:**
   - Track CTR (click-through rate) and FYP placement for first 24 hours after publish
   - If CTR drops >50% after labeling (vs. pre-label baseline from v1.0), investigate whether label caused suppression
   - Document baseline metrics: with labels, expect 10-20% organic reach reduction (documented suppression bias against labeled AI)
   - Alert if video gets flagged "violative content" or "undisclosed AI" — immediately respond with compliance evidence
   - Monthly report: list all published videos + verify 100% have required labels

5. **Compliance audit checklist:**
   - Monthly verification: pull list of all published videos; check TikTok/YouTube/Instagram for label presence
   - Telegram bot: add verification step BEFORE posting — checkbox: "Label verification: TikTok (Y/N), YouTube (Y/N), Instagram (Y/N)"
   - Store proof of labeling: screenshot label state at time of publish for dispute resolution
   - If platform manually applies label (catches undisclosed AI), investigate and fix labeling process

**Warning signs:**
- TikTok video labeled "contains synthetic media" by platform (not by creator) → labeling mechanism failed, creator didn't use built-in tool
- YouTube video gets "realistic altered content" flag automatically → missing description label
- CTR drops unexpectedly after labeling (vs. v1.0 baseline without labels) → platform suppressing labeled content
- Meta/Instagram denies monetization or brand partnership → likely due to undisclosed AI flags
- Creator receives community guidelines warning → insufficient labeling detected
- Account gets restricted from Creator Fund / brand partnerships → repeat undisclosed AI violations

**Phase to address:**
Phase 1 (Video Generation Foundation): Cannot be deferred. Labeling must be built into every scheduled post before it ships. If you miss labeling at publish time, video goes out unlabeled and recovery is expensive (delete + repost = new URL, lost engagement metrics, algorithmic penalty). This is a blocker for any automation.

---

### Pitfall 4: Cat Character Identity Drift — Inconsistency Across Videos via Prompt Engineering Failure

**What goes wrong:**
Week 1 videos: cute orange tabby cat with green eyes. Week 2: same prompt returns a gray calico. Week 3: siamese cat appears. Viewers notice the "cat character" is different every day, lose sense of familiarity, engagement drops 30-40% compared to v1.0. Or: prompt includes detailed character description, API accepts it without error, but still generates a different cat each time. Or: character looks consistent frame-by-frame within a video, but the cat's position/pose changes unrealistically (walks backward, teleports), breaking coherence.

**Why it happens:**
- Prompt anchoring (detailed character description in every prompt) is necessary but not sufficient; AI video models interpret descriptions probabilistically
- Kling/Runway/Pika have varying character consistency features: Kling has "character-specific generation modes" (2026), Runway Gen-3/Gen-4.5 don't guarantee consistency without reference images, Pika's consistency still experimental
- Character drift happens when prompt is too short, too vague, or includes conflicting details ("orange tabby" + "white spots" causes ambiguity)
- Without reference image or character locking feature, model has no visual anchor; it generates based on probability distribution
- Testing character consistency is NOT done by default; each API returns output without consistency validation
- Inherited threshold 85% (from v1.0 script similarity) is NOT tuned for visual character consistency; it measures semantic similarity, not visual identity

**How to avoid:**
1. **Character Bible — static immutable definition:**
   - Create detailed character profile (40-50 words, specific measurable details):
     ```
     A fluffy ginger tabby cat, 4 years old, with wide curious green eyes,
     pink nose, white paws (all four). Medium-long double-coat fur.
     Proportions: large round head, lean muscular body, long curved tail.
     Distinctive markings: orange and darker orange stripes, white "M" on forehead,
     white chest patch. Personality: playful, alert, mischievous. Always whiskers visible.
     ```
   - Store in config.py or dedicated CharacterBible.md; version control it
   - Copy exact definition into EVERY prompt without modification
   - Version character bible if/when aesthetic changes intentionally (e.g., "Season 2: cat gets collar") — track version in prompt, never change mid-season

2. **Prompt structure template (rigid slot-based):**
   - Use fixed structure to reduce ambiguity:
     ```
     [Exact character description from bible - no substitution]
     Action: [specific verb phrase, e.g., "pouncing on a toy"]
     Environment: [location with lighting details, e.g., "living room, afternoon sunlight"]
     Camera angle: [top-down 45 degrees, close-up, wide shot]
     Visual style: [consistent art style/filter, e.g., "warm cinematic lighting"]
     Technical: [1080x1920 9:16, no motion blur, natural lighting]
     Negative: [no outfit changes, no color variation from character description, realistic fur]
     ```
   - Never deviate from template; use only placeholder substitution for action/environment/camera
   - Validate prompt structure before API call; log template version with request
   - This reduces ambiguity and forces consistency through structure

3. **Character consistency testing and validation (Phase 0 blocker):**
   - Week 0 (before launch): Generate 10 test videos with same character, different scenes
   - Eyeball test: Do all 10 videos show recognizably same cat? If not, refine character description
   - If <8/10 pass consistency test, refine character description or switch API provider
   - Document which API features character locking: Kling character modes YES (2026), Runway with reference image MAYBE, Pika experimental
   - Video consistency is not negotiable; if API can't maintain consistency >90%, choose different provider

4. **Reference image approach (if supported):**
   - If target API supports character reference image (Kling character modes, Runway with reference, newer models), use it
   - Generate or commission ONE canonical cat image; store immutably in Supabase Storage
   - Pass cat image + scene prompt to API; character consistency rate improves to 95%+
   - If API doesn't support reference image, wait for feature or choose API that does
   - Never let character visual vary without explicit version bump

5. **Consistency scoring and monitoring:**
   - After each video generation, do visual inspection: "Does this cat look like the character?" Y/N in creator review
   - If N: do NOT approve; regenerate with exact same prompt before generator is called again
   - Track consistency rate weekly: target 95%+ videos pass eyeball test
   - If <90% pass: pause publishing, refine character description, test 5 new videos before resuming
   - Log consistency failures to investigate prompt issues

6. **Anti-repetition for character actions (orthogonal concern):**
   - Scene variety should vary action/environment daily (scene engine already does this)
   - Track action repetition separately: "cat running" shouldn't appear >2x per week
   - Vector search anti-repetition should catch semantic duplicates ("cat playing" vs "cat pouncing" are similar)
   - Character identity is fixed; scene variety is the variable

**Warning signs:**
- Week 2-3 Telegram comments or YouTube/TikTok: "why is the cat different?" or "lost interest because character keeps changing"
- Engagement metrics: CTR/watch-time drops 30%+ after week 1 → likely character consistency issue
- Creator rejection rate: >20% of generated videos rejected due to "wrong cat" appearance → character inconsistency rate >20%
- Video shows cat in physically impossible pose/position → character consistency algorithm failed on movement
- Each video shows a different-looking cat despite identical character description → prompt anchoring insufficient; reference image needed

**Phase to address:**
Phase 1 (Video Generation Foundation): Character bible and prompt template must exist before first video generation. This is NOT tunable post-launch without rebuilding 100s of videos. Validate consistency in testing phase (10 test videos) before automating daily generation. Character consistency is a core brand differentiator; getting this wrong early is expensive to fix.

---

### Pitfall 5: Anti-Repetition Threshold Miscalibration — Scene Repetition vs. Prompt Similarity Mismatch

**What goes wrong:**
Scene vector search is set to 85% cosine similarity threshold (inherited from v1.0 script similarity). First week: scenes are diverse, great. Week 3: AI starts generating "cat in living room" almost every other day — similar but not identical to previous versions, so 85% threshold doesn't catch it. Viewers see pattern, comment "feels repetitive", engagement drops. Or: opposite problem — threshold too strict (95% similarity), AI can't generate any scenes similar to successful ones, scene diversity goes up but brand coherence drops (cat goes from "living room" to "alien spaceship" in one jump).

**Why it happens:**
- Cosine similarity threshold for "too similar" is domain-dependent and content-dependent; 85% is inherited from v1.0 (avatar scripts), not empirically validated for cat videos
- Scene similarity is different from topic similarity: "cat in living room on Tuesday" vs "cat in living room on Friday" are semantically similar (85%+ cosine) but visually different enough (different activity, lighting, mood)
- Scene prompt embedding captures intent, but actual video output can diverge due to AI generation variance
- Threshold tuning requires A/B testing with real videos and engagement metrics; no shortcut
- Scene vectors encode location + activity + mood; two scenes can be >85% similar in vector space but look visually different (e.g., "cat napping sunny" vs "cat napping rainy" differ only in lighting)
- Without empirical calibration, threshold is just a guess

**How to avoid:**
1. **Empirical threshold calibration (Phase 0 — pre-launch blocker):**
   - Generate 20-30 test videos with intentionally varied and semi-repeated scenes
   - Measure cosine similarity between scene prompts for each pair
   - For each pair, visually rate similarity: 1 (identical/boring), 2 (very similar/too close), 3 (similar but acceptable diversity), 4 (different/good diversity)
   - Plot cosine similarity vs. visual similarity rating; find the point where "too close" flips to "acceptable"
   - This empirical threshold is likely 75-80% for cat videos, NOT inherited 85%
   - Document this calibration; lock it in code; only change with new testing

2. **Hybrid anti-repetition (scene embedding + visual embedding):**
   - Don't just measure scene prompt similarity; also measure visual aesthetic diversity
   - After video generation, extract embeddings from video frames (using CLIP or similar; not just prompt)
   - Filter for low similarity in BOTH prompt + visual embeddings; require both to be above threshold
   - This catches cases where scene prompt is different but visual output looks identical
   - More expensive computationally but catches real repetition

3. **Category-level repetition limits (hard rules above soft threshold):**
   - Instead of relying solely on cosine similarity, implement hard rules:
     - Max 2 scenes per week from each location (e.g., "living room" max 2x/week)
     - Max 2 scenes per week with same activity (e.g., "napping" max 2x/week)
     - Max 1 scene per week with same mood + location combo
   - Scene engine must select from curated category library respecting these limits
   - Combine rules + vector search: scene passes if it clears rules AND cosine > empirical_threshold
   - Hard rules prevent absurd repetition even if similarity metric fails

4. **Weekly diversity report (creator visibility):**
   - Every Sunday, compute diversity metrics for past 7 videos:
     - Scene location distribution (% in each room)
     - Activity distribution (% napping, playing, eating, etc.)
     - Mood distribution (% playful, calm, curious, etc.)
     - Average cosine similarity to previous 7 (should trend 0.65-0.75 if threshold is right)
   - Alert if any category >40% of week (e.g., 3/7 videos in living room = 43% → too repetitive)
   - Publish diversity report in Telegram; let creator see trends and manual override if desired

5. **Acceptance-based retuning (feedback loop):**
   - Track creator approvals/rejections in Telegram
   - If creator rejects scene for "too similar to recent video," log that scene + boost threshold for similar scenes
   - After 20+ rejections with "too similar" reason, re-calibrate threshold based on creator feedback
   - This turns rejection feedback into semi-automatic threshold tuning

6. **Scene prompt engineering to maximize diversity (upstream):**
   - Scene prompt template: [location] + [activity] + [time of day] + [weather/lighting] + [prop/interaction]
   - Require that each scene varies at least 2-3 dimensions from recent scenes (not just one changed detail)
   - Example: "Cat napping on couch, sunny afternoon" (similar to week 2) → REJECTED
   - Example: "Cat chasing toy in kitchen, evening, rain on window" (different location, activity, time, weather = diverse) → APPROVED
   - This prevents low-diversity scenes from being generated at all

**Warning signs:**
- Week 2 creator feedback: "feels repetitive" or "the cat keeps doing the same thing" → threshold too high, not filtering enough
- Week 3 engagement: CTR stable but retention drops (viewers stop watching after first 5s) → scene repetition
- Vector search logs show >10% of scenes rejected as too similar → threshold calibrated too loose
- A/B test: publish same scene twice (approved as first, rejected as duplicate), first version gets 5x higher engagement → audience notices repetition, threshold too loose
- Same location appears >2x per week regularly → hard rules not enforced

**Phase to address:**
Phase 2 (Scene + Music Engine): Threshold calibration is empirical and requires video generation testing. Cannot be done in Phase 1 without real video output. Must be validated in pre-launch testing week (generate 20-30 test videos, measure, calibrate, lock in). Setting wrong threshold impacts quality for 1-2 weeks but is recoverable by retuning.

---

### Pitfall 6: Music Generation Failure Cascades Into Publishing Failure

**What goes wrong:**
Scene generates fine. Video generates fine. Music selection API fails (rate limited or down). Code falls back to "use music from last video" to keep pipeline running. But last video's music was for a calm scene; today's video is an action scene. Mood mismatch occurs, content looks unfinished, creator rejects it. Or: no fallback implemented, music API failure causes entire publishing job to crash at 2:30 AM, no video arrives in Telegram, approval window closes, no post to TikTok.

**Why it happens:**
- Music selection is treated as non-critical because it seems like "background enhancement"
- But music-video mismatch is perceptually jarring; viewers notice immediately, algorithm sees it as low-quality content
- Music APIs (Mubert, AI Jukebox, Soundstripe) have separate rate limits from video APIs; hitting music limits doesn't show in video pipeline monitoring
- Fallback strategies are often untested: "use cached music from 7 days ago" might fail if storage deleted old files
- Async operations in Python require careful handling; synchronous wait for music blocks entire job

**How to avoid:**
1. **Async music fetching (parallel with video generation):**
   - Don't wait for music API during video generation
   - Use asyncio: fetch music and video in parallel while both are generating
   - By the time video is ready (120-180s), music should be ready (5-10s)
   - If music completes first: cache it in Redis (5m TTL), ready for video assembly
   - If video completes first and music still pending: grab from backup pool, mark for "music upgraded post-generation"

2. **Music selection resilience with timeout:**
   - Music API integration should timeout at 10s max; no waiting for slow responses
   - Implement music pre-generation: before video generation, query mood label, select music candidates (3 options in parallel)
   - Store mood→music mappings in Redis cache (24h TTL) to survive music API blips
   - If music API down or times out: fall back to cached mood→music from last 24h; acceptable quality loss because cache is fresh

3. **Mood consistency verification:**
   - Video generation prompt includes mood label (e.g., "playful", "calm", "curious")
   - Music selection queries same mood label from mood detection
   - Before publishing: verify video mood matches music mood; if mismatch detected, regenerate music (not reuse last video's music)
   - Mood mismatch threshold: if mood detection confidence < 70%, hold for manual review in Telegram

4. **Music backup pool (offline fallback):**
   - Maintain 50-track curated pool of cat-video-appropriate music, organized by mood
   - Categories: "playful" (10-15 tracks), "calm" (10-15 tracks), "curious" (10-15 tracks), "excited" (10-15 tracks)
   - All tracks must be pre-licensed across all platforms (validate monthly)
   - If dynamic mood selection fails: fall back to random track from matching mood in backup pool
   - This is acceptable degradation; mood-matched is ideal but random-mood-matched is still OK
   - Store backup pool in Supabase Storage for immutability

5. **Music validation before publishing:**
   - Before publishing to platforms, verify audio track exists and is readable (not corrupted)
   - Check audio metadata: duration, bitrate, channels; ensure compatibility with platform requirements
   - Test audio-video sync on one platform before broadcasting to all (YouTube first, then TikTok, then Instagram)
   - Log validation results; alert if audio validation fails

6. **Music API health monitoring:**
   - Track music API success rate; alert if >10% failures
   - Separate monitoring from video API (they have different SLAs)
   - If music API health <90%, switch to backup pool immediately; don't wait for failures

**Warning signs:**
- Video publishes with "wrong" mood music (calm music on action scene) → fallback used, music API was down
- Music API timeout errors in logs >2x per week → rate limiting or capacity issue
- Same music appears in consecutive videos despite different moods → fallback used multiple days
- Creator rejects videos citing "music doesn't match" → mood detection or selection failing
- Telegram shows music generation took >10s regularly → API slow, timeout approaching

**Phase to address:**
Phase 2 (Scene + Music Engine): Music resilience is non-optional. Implement parallel fetching + mood validation + backup pool before first automated music selection. Test music API failure scenarios (mock 503, hang for 15s) to verify fallback works. This is a blocker for automation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode 85% similarity threshold from v1.0 | Fast to implement | Repetitive content in weeks 2-3; viewer engagement drops | Never — must empirically calibrate for cat videos |
| Skip video consistency testing; go straight to daily automation | Saves 1-2 days of testing | Character drift alienates audience; high rejection rate; brand damage | Never — consistency is core to character brand |
| Use any royalty-free track; validate licensing later | Quick music pool setup | ContentID strikes, account warnings, revenue loss, video removal | Never — must validate licensing BEFORE using |
| No circuit breaker; just retry indefinitely on API failure | Simpler code; fewer branches | Cascading failures, credit loss, job hangs for hours, silent data loss | Never — critical infrastructure pattern |
| Single music API with no fallback | Cleaner code path | Music generation failure = entire pipeline halt | Never — music is blocking dependency |
| Treat AI labeling as optional; add later if flagged | Faster launch | Account flags, suppressed reach, compliance violations, EU fines | Never — mandatory for all platforms as of 2025-2026 |
| Synchronous music + video generation | Simpler sequential code | Blocking during music API lag (10s) slows entire job; timeout risk | Never — must use async |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| **Video Generation API (Kling/Runway/Pika)** | Assume API will always complete; synchronous wait for response | Implement circuit breaker; async status polling with timeout; fallback to cached video |
| **Music Selection API (Mubert/Soundstripe/AI Jukebox)** | Block on music during video generation; if music slow, entire pipeline delays | Fetch music in parallel with video using asyncio; 10s timeout; fall back to backup pool |
| **Platform Publishing APIs (TikTok/YouTube/Meta)** | Post same video with same music to all platforms | Validate music license per platform BEFORE posting; use platform-specific music if needed |
| **Telegram Approval Bot** | Assume approval always arrives within 2 hours | Set 18-hour timeout; if not approved, auto-reject and move to next day |
| **pgvector Anti-Repetition (Postgres)** | Inherit 85% threshold from v1.0 without testing | Empirically calibrate with 20-30 test videos; adjust to 75-80% based on data |
| **APScheduler Daily Job** | Run video generation, music, publishing sequentially | Parallelize non-dependent tasks; fail fast if any critical step fails; use circuit breaker |
| **Supabase Storage (Video Lifecycle)** | Assume videos stay until 45d grace period | Test deletion policies work; verify 45d+1 cutoff actually deletes; monitor orphaned files |
| **Scene + Music Caching (Redis)** | Assume cache always warm | Implement cache validation; detect stale entries; refresh if >24h old |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **Rate limit cascade** | Music API rate limited → video waits → job timeout | Separate rate limiters for video + music; token bucket with 10% headroom; async + timeout | When daily load hits API capacity (2+ parallel jobs) |
| **Vector search on 365+ scenes** | pgvector similarity query takes >5s | Index embedding column; batch-retrieve recent 30 scenes instead of all history | At 365 days (year 1); queries become O(n) slow |
| **Concurrent approve/reject in Telegram** | Last 2 approvals race; unpredictable state | Use Postgres transaction lock on approval; serialize button handlers | When creator rapidly clicks buttons |
| **Music library query time** | Mood selection queries 50-track pool, takes 2-3s | Pre-index by mood; load into Redis on startup; O(1) lookup | After 500+ tracks; naive search becomes slow |
| **Video frame extraction for consistency check** | Extracting 10 frames per video takes 30s | Use ffmpeg -vf select to grab 2 keyframes; skip full extraction | When validating every video (10+/day) |
| **APScheduler job queue backlog** | Next day's job starts before previous completed | Set timeout on job; kill hanging jobs after 2 hours; alert creator | When video generation takes >4 hours |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| **API key in source code or logs** | Credential exposure; unauthorized usage; credit theft | Environment variables only (encrypted); scrub API keys from logs; rotate monthly |
| **Music license matrix not maintained** | Publishing unlicensed music; strikes; account warnings | Maintain matrix; validate music ID before publishing; audit quarterly |
| **No content moderation review before publishing** | Violates platform policy; account flagged; reach suppressed | Require creator approval + AI label verification in Telegram; checklist |
| **Fallback mechanism uses untrusted data** | Fallback music has expired license; fallback video corrupted | Test fallbacks monthly; verify licenses valid; verify file readability |
| **Telegram bot accessible to non-creator** | Unauthorized approvals; malicious rejections | User ID lock (already in v1.0); maintain this; don't disable |
| **Unencrypted music/API credentials** | Credentials exposed; unauthorized generation; credit loss | Supabase encrypted env vars; rotate if exposed; monitor usage anomalies |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| **No feedback when music API fails** | Creator waits 2+ hours for video that never arrives | Telegram: "Video complete, fetching music..." → if >30s, "Music slow, using backup track" |
| **Vague character rejection feedback** | Creator rejects "character looks wrong" but doesn't know what to change | Telegram: checkbox rejection reasons: "Face wrong", "Color wrong", "Pose unnatural", "Too similar" → feed to next attempt |
| **No visibility into anti-repetition logic** | Creator doesn't know why scene was rejected as "similar" | Telegram: show similarity score + link to similar video: "87% similar to [3 days ago], rejected" |
| **Silent publishing failure** | Creator approves video; 8 hours later no views; doesn't know if posted | Telegram: "Posted TikTok (5 min) ✓, Instagram (6 min) ✓, YouTube (8 min) ✓" |
| **Music mood disconnect** | Video is action-packed but music is calm; jarring | Provide music preview in approval: small audio player + mood label in Telegram |
| **No diversity visibility** | Creator doesn't know if content feels repetitive | Telegram: weekly diversity report showing location/activity/mood distribution |

---

## "Looks Done But Isn't" Checklist

- [ ] **Character consistency validated:** 10+ test videos generated with character bible; >95% pass eyeball test (cat is recognizably same)
- [ ] **Anti-repetition threshold empirically calibrated:** 20-30 test videos analyzed; cosine threshold adjusted based on visual similarity (not inherited)
- [ ] **Music license matrix complete:** All music documented with TikTok/YouTube/Instagram/Commercial status; verified against provider ToS
- [ ] **Circuit breaker tested with failures:** Mock 503/timeout; circuit opens within 5 failures; fallback video loads; no infinite retries
- [ ] **AI content labeling on all platforms:** TikTok label working; YouTube description includes disclosure; Instagram labeled; tested on live post
- [ ] **Music API resilience tested:** Mock 503; pipeline completes with backup music; mood matching verified; no silent failures
- [ ] **Creator approval flow end-to-end:** Scene → Video → Music → Telegram approval → publish to all platforms → metrics → weekly report
- [ ] **EU compliance documented:** If EU audience: Article 50 human review metadata included; labeling requirement understood
- [ ] **Fallback mechanisms verified:** Cached video exists/readable; backup music licenses valid; circuit breaker cooldown works
- [ ] **Rate limiting strategy:** Video + music APIs have separate limiters; retry uses exponential backoff; 429 responses include Retry-After

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **API credit exhaustion** | LOW (if circuit breaker present) | (1) Circuit breaker catches; (2) hold pipeline; (3) wait for daily reset or buy credits; (4) resume next day |
| **Music licensing strike** | MEDIUM-HIGH | (1) Video demonetized or flagged; (2) re-score with licensed music; (3) reupload; (4) rebuild license matrix; (5) prevent recurrence |
| **Character consistency broke** | MEDIUM | (1) Pause generation; (2) refine character bible; (3) test 5 videos; (4) validate; (5) republish week's videos if needed |
| **Anti-repetition threshold failed** | MEDIUM | (1) Recognize pattern (>25% daily rejections); (2) re-calibrate threshold; (3) test 20 videos; (4) adjust; (5) clear queue; (6) resume |
| **AI content label not applied** | MEDIUM-HIGH | (1) Delete unlabeled videos; (2) reupload with labels; (3) appeal platform flag if possible; (4) add validation to prevent recurrence |
| **Video generation API down** | LOW (if cached) to MEDIUM (if manual) | (1) Switch to fallback video; (2) monitor recovery; (3) test circuit with low-priority request; (4) resume when healthy |
| **All platforms rejected for licensing** | HIGH | (1) Video unusable; (2) regenerate with licensed music; (3) reupload all platforms; (4) rebuild license matrix; (5) test 3 videos before resuming |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| API failure handling & circuit breaker | Phase 1: Video Generation | Unit test circuit with mock 503; verify fallback loads; no infinite retries |
| Character consistency | Phase 1: Video Generation | 10 test videos; visual inspection >95% consistent; character bible documented |
| AI content labeling | Phase 1: Video Generation | Publish test video; screenshot proof labels appear on all platforms |
| Music licensing validation | Phase 2: Scene + Music | License matrix complete; all tracks verified across platforms; audit quarterly |
| Anti-repetition calibration | Phase 2: Scene + Music | 20-30 test videos; empirical threshold determined; locked in code |
| Music API resilience | Phase 2: Scene + Music | Mock 503 failures; fallback pool works; mood matching verified |
| EU compliance (Article 50) | Phase 2: Scene + Music | If publishing to EU: metadata includes human review; labeling requirement met |
| Telegram approval validation | Phase 4: Telegram Approval | Test approval/rejection; verify rejected videos don't publish; 18h timeout works |
| Cross-platform publishing | Phase 5: Multi-Platform Publishing | Publish to TikTok → YouTube → Instagram; verify music/labels/metadata on each |

---

## Sources

- [Runway, Kling, Pika API Reliability - WaveSpeedAI Blog](https://wavespeed.ai/blog/posts/best-text-to-video-api-2026/)
- [Text-to-Video AI Generation Comparison - DatBot.AI](https://datbot.ai/blog/text-to-video-ai-generation-compared/)
- [Kling AI Review 2026 - Max Productive](https://max-productive.ai/ai-tools/kling-ai/)
- [Music Licensing for Content Creators 2026 - Gray Group International](https://www.graygroupintl.com/blog/music-licensing-content-creators/)
- [TikTok Music Licensing Rules 2026 - Last Play Distro](https://lastplaydistro.com/blog/tiktok-music-copyright-rules-2026-what-artists-creators-must-know/)
- [Music Licensing for Social Media 2026 - LesFM](https://lesfm.net/he/blog/music-licensing-for-social-media/)
- [TikTok AI Content Guidelines 2026 - Napolify](https://napolify.com/blogs/news/tiktok-ai-guidelines)
- [TikTok 2026 Policy Updates - Dark Room Agency](https://www.darkroomagency.com/observatory/what-brands-need-to-know-about-tiktok-new-rules-2026)
- [AI Disclosure Rules by Platform - Influencer Marketing Hub](https://influencermarketinghub.com/ai-disclosure-rules/)
- [AI Video Disclosure Requirements 2026 - Virvid](https://virvid.ai/blog/ai-video-ad-disclosure-requirements-2026-meta-youtube-tiktok)
- [TikTok 2026 AI Labeling Rules - Audit Socials](https://www.auditsocials.com/blog/tiktok-ai-content-disclosure-rules-2026)
- [Character Consistency in AI Video - AI Video Pipeline](https://www.aividpipeline.com/blog/character-consistency-ai-video)
- [Consistent Character Generation Guide - GensGPT](https://www.gensgpt.com/blog/character-consistency-ai-image-generation-2026-guide)
- [AI Video Prompt Engineering 2026 - TrueFan](https://www.truefan.ai/blogs/ai-video-prompt-engineering-2026)
- [How to Create Viral AI Animal Videos - MimicPC](https://www.mimicpc.com/learn/how-to-create-viral-ai-animal-videos)
- [Rate Limiting AI APIs with FastAPI - DasRoot](https://dasroot.net/posts/2026/02/rate-limiting-ai-apis-async-middleware-fastapi-redis/)
- [Gemini API Reliability - LaoZhang AI Blog](https://blog.laozhang.ai/en/posts/gemini-3-pro-image-unreliable)
- [Circuit Breaker Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/circuit-breaker)
- [Circuit Breaker Pattern - Aerospike](https://aerospike.com/blog/circuit-breaker-pattern/)
- [Vector Search and Anti-Repetition - Meilisearch](https://www.meilisearch.com/blog/similarity-search)
- [Vector Databases for Generative AI - BrollyAI](https://brollyai.com/vector-databases-for-generative-ai-applications/)
- [AI Music Licensing 2026 - SoundVerse](https://www.soundverse.ai/blog/article/how-ai-music-is-changing-beat-licensing-1314)

---

**Pitfalls research for:** Autonomous Content Machine v2.0 — Adding AI Cat Video Generation
**Researched:** 2026-03-18
