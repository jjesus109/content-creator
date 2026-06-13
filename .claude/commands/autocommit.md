Commit all current changes with a generated conventional commit message.

## Steps

1. Run `git status --short` to see what changed. If nothing changed, tell user and stop.

2. Run `git diff HEAD` (and `git diff --cached` for already-staged) to understand the changes.

3. Stage only safe files — DO NOT stage:
   - `.env`, `.env.*`, `*.env`
   - Files matching `*secret*`, `*credential*`, `*token*`, `*password*`
   - `*.pem`, `*.key`, `*.p12`, `*.pfx`
   - Any file in `.gitignore`
   
   Stage everything else with specific file paths (never `git add -A` blindly).

4. Generate a commit message following Conventional Commits:
   - Format: `<type>(<scope>): <subject>`
   - Types: `feat`, `fix`, `refactor`, `chore`, `docs`, `test`, `style`, `perf`
   - Subject: ≤50 chars, imperative mood, lowercase after colon
   - Body: only when "why" isn't obvious from subject — focus on motivation, not mechanics
   - No period on subject line

5. Commit using:
```bash
git commit -m "$(cat <<'EOF'
<generated message here>
EOF
)"
```

6. Report: what was committed, what was skipped (if any sensitive files detected), commit hash.

## Behavior

- If pre-commit hook blocks (lint/test/secrets failure): surface the error, do NOT force-push or bypass with `--no-verify`
- If nothing to commit: say so clearly
- If sensitive files detected: warn user explicitly before skipping them
