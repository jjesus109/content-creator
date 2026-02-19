# Feature Research

**Domain:** AI-Automated Social Media Content Pipeline (Single Creator, Avatar Video)
**Researched:** 2026-02-19
**Confidence:** MEDIUM — Training data (August 2025 cutoff). External verification tools unavailable. Core claims grounded in well-established patterns for HeyGen, OpenAI, Telegram Bot API, and social publishing APIs. Flag any API-specific capability claims for manual verification before implementation.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the system cannot function without. Missing any of these = the pipeline breaks or delivers an unusable output.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily script generation (LLM) | Core pipeline trigger — without it, nothing else runs | MEDIUM | OpenAI GPT-4-class prompt with 5-Pillar constraints, language (neutral Spanish), tone, word-count cap (140 words), structure (hook + development + CTA) |
| Anti-repetition via vector similarity | Without it, the creator sees recycled topics within weeks; credibility collapses | MEDIUM | Embed each approved script; cosine similarity check before accepting; >85% = reject and regenerate. Requires vector DB (pgvector, Pinecone, or Weaviate) |
| HeyGen avatar video generation | The product IS the video; no video = no pipeline | HIGH | API call with avatar ID, script text, background ID, aspect ratio (9:16), resolution (1080p). Async — must poll or use webhook for completion |
| Background variety enforcement | Consecutive identical environments are visually monotonous; breaks aesthetic | LOW | Stateful: track last N background IDs in DB; exclude from next generation call |
| Telegram bot video delivery | Sole UI; if it breaks, creator has no way to approve/reject | MEDIUM | Send video file + caption (post copy) + inline keyboard [Approve] [Reject] |
| Approve/reject inline keyboard | Creator decision point; without it, everything auto-publishes or stalls | LOW | Telegram InlineKeyboardMarkup with callback_query handler |
| Rejection cause capture | Rejection without reason is wasted signal; no improvement possible | LOW | After [Reject], prompt with follow-up message asking for cause; store as negative context |
| Rejection negative context storage | Future iterations must know what to avoid | LOW | Persist rejection reason alongside script metadata; inject as "avoid:" block in next generation prompt |
| Multi-platform publish (TikTok, IG, FB, YT Shorts) | The whole point is reach; publishing to one platform defeats the system | HIGH | Ayrshare or Buffer API — single POST with video file + caption + platform targets |
| 9:16 1080p video format | All four target platforms require vertical short-form for Reels/Shorts surfaces | LOW | HeyGen parameter; validate at generation time before delivery |
| Environment variable secrets management | API keys in plaintext = critical security failure | LOW | python-dotenv or native env injection; all keys (OpenAI, HeyGen, Telegram, Ayrshare) must be env-only |
| Telegram bot locked to single user ID | Creator's private content must not be accessible to strangers | LOW | Check `message.from_user.id` against allowlist on every handler |
| Script word-count enforcement | HeyGen lip-sync degrades and timing breaks on overlong scripts; >140 words = truncation artifacts | LOW | Count words post-generation; if over, summarize/truncate before sending to HeyGen |

### Differentiators (Competitive Advantage)

Features beyond basic automation. These create the distinctive experience and compounding value over time.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 5-Pillar philosophical framework as prompt kernel | Content is tonally consistent across 365+ videos without manual curation; feels like a coherent voice, not random AI output | MEDIUM | Encode all 5 pillars (Radical Responsibility, Solitude, Praxis, Gravitas, Memento Mori) as system-level prompt context; reloaded on every generation |
| Weekly mood profile input via Telegram | Injects creator's current emotional/intellectual state into generation; content stays personally resonant, not generic | MEDIUM | Weekly cron prompts bot to ask creator 3-5 mood/theme questions; responses stored and injected into next 7 generations |
| Rejection feedback as negative training context | The system gets smarter over time without manual retraining; rejection history shapes future output | LOW | Accumulate rejections in a "rejection log" table; inject top-N most recent rejections as anti-examples in the generation prompt |
| 48-hour performance metric harvest | Decision-making is data-driven; creator knows what actually works, not what feels good | MEDIUM | Scheduled job at +48h post-publish; call platform APIs (or Ayrshare analytics endpoint) to pull views, shares, retention |
| Virality alert with format clone trigger | Viral content is captured and repeated before the window closes; most pipelines miss this | HIGH | Compare 48h metrics against rolling average; if >500%, trigger Telegram alert + flag for format analysis (topic, hook style, length) |
| Sunday weekly performance report | Creator has weekly situational awareness without logging into any platform | LOW | Aggregate prior week's metrics; generate summary; send via Telegram on Sunday morning |
| Tiered storage lifecycle with viral preservation | Cost-controlled at scale; viral content never accidentally deleted | MEDIUM | Hot (0-7d local/S3 standard), Warm (8-45d S3 IA), Cold/Delete (45d+ purge); viral flag = permanent exempt from deletion |
| Dark aesthetic + bokeh background visual identity | Aesthetic consistency is the brand; random-background pipelines produce visual noise | LOW | Constrained to approved background catalog (dark, bokeh, no bright environments); enforced at generation time |
| Audio post-processing (dark ambient style) | Voice-only avatar videos feel clinical; ambient audio makes content emotionally resonant | MEDIUM | ffmpeg or equivalent: mix HeyGen audio output with dark ambient bed track; normalize levels |
| Optimal publish scheduling based on platform peak hours | Publishing at wrong times halves organic reach; most naive pipelines post immediately | MEDIUM | Read platform peak-hour data (Ayrshare scheduling hints or hardcoded known peaks by platform); schedule accordingly |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem natural to add but would harm this specific system.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Web dashboard / analytics UI | "Real dashboards are more professional" | Contradicts core constraint (Telegram-only UI); builds tech debt with no user — the creator is one person who prefers Telegram | Weekly Telegram report + virality alerts cover 100% of the information need |
| Multi-user / multi-creator support | "What if I want to license this?" | Adds auth, tenancy, billing, per-user data isolation — all significant scope; delays shipping core value | Hard-code single creator; rebuild for multi-tenancy if/when product-market fit demands it |
| Manual content creation workflow | "What if I want to write my own script?" | Breaks the automation contract; introduces branching code paths; makes the system inconsistent | Reject with cause in Telegram is the manual override — it regenerates with human feedback |
| Long-form video (>60 seconds) | "Could we do YouTube main-feed too?" | HeyGen costs scale with duration; OpenAI prompt structure changes; platform APIs differ; entirely different product | Explicitly out of scope; separate project if ever desired |
| Horizontal video format (16:9) | "LinkedIn and Twitter/X also get traffic" | Four platforms are already in scope; adding formats requires separate HeyGen calls + different prompt optimization | If needed later, add as separate generation branch — not initial build |
| Real-time analytics streaming | "I want live views as they come in" | Platform APIs don't support true real-time; polling creates rate-limit risk; adds infrastructure complexity for marginal value | 48h batch harvest is sufficient for decision-making; virality alert covers the urgent case |
| Automatic topic selection without approval | "Why not just auto-approve everything?" | Removes the creator's editorial voice entirely; risks publishing off-brand content; one bad video can damage audience trust | Single-tap approval in Telegram is already minimal friction; keep the human in the loop |
| Content calendar / scheduling UI | "I want to plan topics in advance" | Planning UI becomes its own product; conflicts with autonomous generation ethos; mood profile + 5 Pillars already serve this function | Weekly mood input is the lightweight planning primitive; expand if strongly needed |
| A/B testing per post | "Test different hooks" | Requires 2x HeyGen API calls + split delivery logic + holdout logic + merge analytics; massive complexity for a 1-video/day cadence | With one video/day, the learning signal is already the daily experiment; no split needed |
| Caption/copy customization per platform | "TikTok copy should be different from YouTube" | Four variants to manage; prompt engineering complexity multiplies; approval flow becomes 4x longer | Single post copy optimized for short-form works across all four platforms; differentiate only if metrics demand it |

---

## Feature Dependencies

```
[Weekly Mood Profile Input]
    └──feeds──> [Script Generation]
                    └──requires──> [Anti-Repetition Vector Check]
                                       └──requires──> [Vector DB with approved script embeddings]
                    └──feeds──> [Word Count Enforcement]
                                    └──gates──> [HeyGen Video Generation]
                                                    └──requires──> [Background Variety Enforcement]
                                                    └──produces──> [Video File + Post Copy]
                                                                       └──delivers──> [Telegram Bot Delivery]
                                                                                          └──triggers──> [Approve/Reject Flow]
                                                                                                             └──[Approve]──> [Multi-Platform Publish]
                                                                                                                                └──schedules──> [Optimal Publish Scheduling]
                                                                                                                                └──triggers at +48h──> [Performance Metric Harvest]
                                                                                                                                                           └──feeds──> [Sunday Weekly Report]
                                                                                                                                                           └──checks──> [Virality Alert + Format Clone Trigger]
                                                                                                                                                           └──feeds──> [Storage Lifecycle Management]
                                                                                                             └──[Reject]──> [Rejection Cause Capture]
                                                                                                                                └──stores──> [Rejection Negative Context]
                                                                                                                                                 └──feeds back──> [Script Generation] (next iteration)

[5-Pillar Framework] ──system prompt──> [Script Generation]
[Dark Aesthetic Catalog] ──constrains──> [Background Variety Enforcement]
[Audio Post-Processing] ──enhances──> [Video File] (before Telegram delivery)
[Tiered Storage Lifecycle] ──governs──> [Video File retention]
[Virality Alert] ──exempts──> [Storage Lifecycle Management] (viral = never delete)
```

### Dependency Notes

- **Script Generation requires Anti-Repetition Vector Check:** Embeddings must be stored for every approved script; the check must run before the script is sent to HeyGen to avoid wasting API credits on a video that will be rejected for topic similarity.
- **HeyGen Video Generation requires Word Count Enforcement:** If script is over 140 words, truncate/summarize before the API call. HeyGen does not auto-truncate — it renders whatever it receives, causing timing and lip-sync issues.
- **Background Variety Enforcement requires stateful tracking:** Must persist last-used background IDs in the database. A stateless check is insufficient.
- **Multi-Platform Publish requires Approve action:** Never auto-publish without human approval. The callback_query handler on [Approve] fires the publish job.
- **Performance Metric Harvest requires published post IDs:** Ayrshare/Buffer returns post IDs per platform at publish time; store these to query platform-specific analytics at +48h.
- **Virality Alert requires Performance Metric Harvest AND historical average:** The 500% threshold is relative; need rolling average baseline stored in DB. No baseline = no alert.
- **Storage Lifecycle requires Virality flag:** Lifecycle management must query virality status before moving to Cold/Delete tier. Viral = permanent exemption.
- **Rejection Negative Context requires Rejection Cause Capture:** Storing an empty rejection reason is useless signal. Must prompt for cause before storing.

---

## MVP Definition

### Launch With (v1)

Minimum viable pipeline — what's needed for the system to generate, deliver, and publish one video per day with human approval.

- [ ] Script generation (OpenAI, 5-Pillar prompt, weekly mood profile injection) — without this, nothing exists
- [ ] Anti-repetition vector check (>85% similarity = regenerate) — without this, content degrades within weeks
- [ ] HeyGen avatar video generation (9:16, 1080p, dark aesthetic, background variety) — the core product deliverable
- [ ] Telegram bot delivery with Approve/Reject + rejection cause capture — the sole creator interaction point
- [ ] Rejection negative context storage and injection — closes the feedback loop, makes v1 self-improving
- [ ] Multi-platform publish via Ayrshare (TikTok, IG Reels, FB Reels, YT Shorts) — if it doesn't publish, it's a toy
- [ ] Environment variable secrets management + single-user Telegram lock — non-negotiable security baseline

### Add After Validation (v1.x)

Add once the core loop is running reliably and first week of content is published.

- [ ] 48-hour performance metric harvest — trigger: first published video exists to measure
- [ ] Sunday weekly report — trigger: first full week of metrics collected
- [ ] Virality alert (500% threshold) — trigger: baseline average established (~2 weeks of data)
- [ ] Tiered storage lifecycle (Hot/Warm/Cold) — trigger: storage costs become real (likely week 2-4)
- [ ] Audio post-processing (dark ambient mix) — trigger: creator reviews v1 video and requests aesthetic enhancement
- [ ] Optimal publish scheduling — trigger: first week shows timing variation in performance data

### Future Consideration (v2+)

Defer until v1 is stable and creator has validated the content direction.

- [ ] Format clone on virality — why defer: requires a video analysis step that is non-trivial to automate reliably; manual analysis for first few viral events is more accurate
- [ ] Mood profile question refinement — why defer: initial questions are hypothesis-driven; after 8 weeks, creator will know what signals actually improve output
- [ ] Background catalog expansion — why defer: start with 5-10 approved backgrounds; expand catalog as creator's aesthetic evolves

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Script generation (LLM + 5-Pillar) | HIGH | MEDIUM | P1 |
| Anti-repetition vector check | HIGH | MEDIUM | P1 |
| HeyGen video generation | HIGH | HIGH | P1 |
| Telegram bot delivery + approve/reject | HIGH | MEDIUM | P1 |
| Rejection cause capture + negative context | HIGH | LOW | P1 |
| Multi-platform publish (Ayrshare) | HIGH | MEDIUM | P1 |
| Background variety enforcement | MEDIUM | LOW | P1 |
| Word count enforcement | MEDIUM | LOW | P1 |
| Secrets management + single-user lock | HIGH | LOW | P1 |
| 48h performance metric harvest | HIGH | MEDIUM | P2 |
| Sunday weekly report | MEDIUM | LOW | P2 |
| Virality alert + format clone trigger | HIGH | HIGH | P2 |
| Tiered storage lifecycle | MEDIUM | MEDIUM | P2 |
| Optimal publish scheduling | MEDIUM | MEDIUM | P2 |
| Audio post-processing | MEDIUM | MEDIUM | P2 |
| Weekly mood profile input (Telegram) | MEDIUM | LOW | P1 — embed at v1 since it feeds generation |
| Format clone trigger (on viral) | LOW | HIGH | P3 |
| Background catalog expansion | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch — pipeline breaks or creator cannot operate without it
- P2: Should have — add within first 2 weeks post-launch when baseline data exists
- P3: Nice to have — future consideration, deferred until v1 is validated

---

## Competitor Feature Analysis

Comparable systems in the market: Opus Clip, Munch, Lately AI, generic n8n/Make.com automation flows, and bespoke creator automation stacks.

| Feature | Opus Clip / Munch (clip-based tools) | Generic n8n/Make.com flows | Our Approach |
|---------|--------------------------------------|---------------------------|--------------|
| Script generation | Not primary — repurposes existing content | Possible via OpenAI node, but generic prompt | 5-Pillar constrained + mood-adaptive; opinionated output |
| Avatar video | Not applicable — uses real footage | Not applicable | HeyGen hyper-realistic avatar; no real footage needed |
| Anti-repetition | None — clip repurposing means repetition is by design | None — generic flows have no semantic memory | Vector similarity check; >85% = hard reject and regenerate |
| Approval workflow | Manual export and review outside the tool | Varies — often no approval step | Telegram inline keyboard; single-tap approve/reject |
| Rejection learning | None | None — stateless | Rejection cause stored as negative context; injected into next generation |
| Philosophical coherence | None — optimizes for engagement signals | None — no content framework | 5-Pillar system ensures voice consistency across all content |
| Multi-platform publish | Supported in some tools | Supported via Ayrshare/Buffer nodes | Ayrshare single-API publish to 4 platforms |
| Performance analytics | Dashboard-based | Varies | Telegram report only; no dashboard |
| Virality detection | Not automated | Not standard | 500% above average triggers Telegram alert |
| Storage lifecycle | Not managed | Not standard | Hot/Warm/Cold tiers with viral exemption |
| Creator interface | Web app | Web app or email | Telegram bot only — zero-friction |

**Key insight:** No existing tool combines autonomous avatar video generation + semantic anti-repetition + approval-via-messaging-app + feedback-driven improvement + multi-platform publish in a single pipeline. This is a greenfield combination of well-understood primitives.

---

## Sources

- PROJECT.md (project constraints and requirements, 2026-02-19) — HIGH confidence
- HeyGen API design patterns: training data (August 2025 cutoff) — MEDIUM confidence; verify avatar IDs, background catalog access, and webhook vs polling behavior before implementation
- OpenAI prompt engineering for constrained generation: training data (August 2025 cutoff) — HIGH confidence for pattern; verify current model IDs and context window limits
- Telegram Bot API (inline keyboards, callback_query, file delivery): training data (August 2025 cutoff) — HIGH confidence; stable API surface
- Ayrshare multi-platform publish API: training data (August 2025 cutoff) — MEDIUM confidence; verify current platform support and rate limits
- Vector similarity anti-repetition pattern: training data (August 2025 cutoff) — HIGH confidence for pattern; verify pgvector vs dedicated vector DB choice against scale needs
- Social media short-form platform requirements (9:16, duration limits): training data (August 2025 cutoff) — MEDIUM confidence; platform specs change; verify TikTok, IG, FB, YT Shorts current limits before implementation
- Competitor analysis (Opus Clip, Munch, n8n flows): training data (August 2025 cutoff) — LOW confidence for current feature state; verify against current product offerings

---
*Feature research for: AI-Automated Social Media Content Pipeline (Solo Personal Development Creator)*
*Researched: 2026-02-19*
