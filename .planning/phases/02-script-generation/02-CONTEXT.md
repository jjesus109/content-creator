# Phase 2: Script Generation - Context

**Gathered:** 2026-02-20 (updated 2026-02-20)
**Status:** Ready for planning

<domain>
## Phase Boundary

The system generates a Spanish script daily using the 6-Pillar framework. It enforces anti-repetition via semantic similarity checking, takes weekly mood direction from the creator via Telegram, and injects rejection feedback from future approval phases into subsequent generations. Video rendering, Telegram approval, and publishing are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Language
- All generated content is in neutral, natural Spanish — no exceptions

### 5-Pillar prompt design (6 pillars confirmed)
1. **Philosophical Root** — Every script grounds in a real school, thinker, or concept (Stoicism, Nietzsche, Zen, etc.)
2. **Universal Tension** — Opens with a contradiction or paradox the viewer recognizes in their own life
3. **Insight Flip** — The development reframes the common understanding — not a summary, a perspective shift
4. **Emotional Anchor** — Connects the insight to a specific feeling (peace, ambition, grief, clarity)
5. **Reflective CTA** — Asks the viewer to sit with one question or try one thing — no "follow for more"
6. **Creator Archetype** — Scripts reflect "The Seeker" persona: actively questions, explores openly, admits uncertainty, invites the viewer to think along — not a teacher, a fellow traveler

### Script length (dynamic)
- Creator picks target video duration in the weekly mood prompt (Step 3)
- 3 duration options:
  - **Short (30s)** → ~70 words — TikTok hook-only format, maximum completion rate
  - **Medium (60s)** → ~140 words — default, all-platform safe
  - **Long (90s)** → ~200 words — YT Shorts max, deeper philosophical development
- Default when creator skips: Medium (60s / ~140 words)
- Hook/Development/CTA proportions are flexible within the target word count — pillar intent governs structure, not fixed section ratios
- Scripts that exceed their target word count are auto-summarized before passing downstream — creator never sees an over-length script

### Topic selection strategy
- Hybrid model: weekly mood profile routes to one of 6 thematic pools; AI generates within selected pool
- 6 thematic pools:
  1. **Existential questions** — Meaning, identity, free will, the self (Sartre, Camus, Heidegger)
  2. **Practical wisdom** — Stoicism, resilience, decision-making (Marcus Aurelius, Seneca)
  3. **Human nature** — Relationships, loneliness, love, connection (Aristotle, Fromm)
  4. **Modern paradoxes** — Attention, technology, emptiness, abundance (Byung-Chul Han, Bauman)
  5. **Eastern philosophy** — Impermanence, flow, non-attachment (Zen, Taoism, Buddhism)
  6. **The creative life** — Originality, expression, artistic struggle (Nietzsche, Wittgenstein)

### Mood profile interaction
- Weekly Telegram prompt uses a three-step inline keyboard flow:
  - Step 1: Creator picks which thematic pool for the week
  - Step 2: Creator picks tone for the week
  - Step 3: Creator picks target video duration (30s / 60s / 90s)
- 4 tone options: **Contemplative** / **Provocative** / **Hopeful** / **Raw**
- No-response fallback: one reminder sent after 4 hours; if still no response, default to Contemplative tone + rotate to next pool + Medium (60s) duration
- Mood selection (pool + tone + duration) is injected into the generation prompt as contextual direction

### Anti-repetition behavior
- Similarity threshold: 85% cosine similarity via pgvector (already established in Phase 1 schema)
- Retry strategy on detection:
  1. First retry: same philosophical root, different angle/lens/thinker
  2. Second retry: completely different topic from the same pool
  - Planner determines exact retry count based on cost/latency tradeoffs
- All retries exhausted: escalate to creator via Telegram alert; creator can manually intervene or skip the day

### Rejection feedback loop
- When creator rejects a video (Phase 4), the rejection cause is:
  1. Injected as an explicit constraint into the next generation prompt
  2. The rejected pattern (topic, tone, or script class) is avoided for 7 days — not just the next run

### Claude's Discretion
- Exact retry count for anti-repetition (planner decides based on cost/latency)
- Specific pgvector query structure and embedding model choice
- Exact prompt template wording (within pillar framework)
- Mood profile database schema details

</decisions>

<specifics>
## Specific Ideas

- Creator persona is "The Seeker" — this should be felt in every script: questioning tone, not authoritative
- Mood profile drives both the thematic pool AND the emotional register — these two dimensions together shape each week's content

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 02-script-generation*
*Context gathered: 2026-02-20*
