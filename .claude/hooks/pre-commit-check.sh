#!/bin/bash
# Pre-commit guard: ruff lint + pytest + gitleaks secrets scan

COMMAND=$(jq -r '.tool_input.command // ""' 2>/dev/null)

if ! echo "$COMMAND" | grep -qE 'git\s+commit'; then
  exit 0
fi

FAIL=0
MESSAGES=""

# 1. Ruff linting
if command -v ruff &>/dev/null; then
  if ! OUT=$(ruff check . 2>&1); then
    FAIL=1
    MESSAGES="[LINT] ruff check failed:\n$OUT"
  fi
fi

# 2. Pytest (only if tests exist, prefer venv python)
_run_pytest() {
  local PYTHON
  for PYTHON in .venv/bin/python venv/bin/python .env/bin/python "$(command -v python3)"; do
    [ -x "$PYTHON" ] && break
  done
  find . -maxdepth 4 -not -path './.git/*' \( -name "test_*.py" -o -name "*_test.py" \) 2>/dev/null | grep -q . || return 0
  local OUT EXIT
  OUT=$("$PYTHON" -m pytest --tb=short -q 2>&1); EXIT=$?
  # exit 0 = passed, exit 1 = real failures, exit 2 = collection/import errors (skip, not our fault)
  if [ "$EXIT" -eq 1 ]; then
    MESSAGES="$MESSAGES\n[TESTS] pytest failed:\n$OUT"
    return 1
  fi
  return 0
}
if ! _run_pytest; then
  FAIL=1
fi

# 3. Secrets scan — gitleaks (preferred) with grep fallback
_secrets_gitleaks() {
  local OUT
  # exits 0 = clean, 1 = leaks found
  if ! OUT=$(gitleaks protect --staged --no-banner 2>&1); then
    MESSAGES="$MESSAGES\n[SECRETS] gitleaks detected credentials:\n$OUT"
    return 1
  fi
  return 0
}

_secrets_grep_fallback() {
  local DIFF
  DIFF=$(git diff --cached 2>/dev/null || true)
  [ -z "$DIFF" ] && return 0

  local FOUND
  FOUND=$(echo "$DIFF" | grep '^+' \
    | grep -ivE '^(\+\+\+|.*#\s|.*//\s)' \
    | grep -iE \
      'sk-[A-Za-z0-9]{20,}|'\
      'ghp_[A-Za-z0-9]{36,}|ghs_[A-Za-z0-9]{36,}|gho_[A-Za-z0-9]{36,}|'\
      'AKIA[0-9A-Z]{16}|'\
      'xox[baprs]-[0-9A-Za-z\-]+|'\
      'eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+|'\
      'AIza[0-9A-Za-z\-_]{35}|'\
      'ya29\.[0-9A-Za-z\-_]+|'\
      '-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----|'\
      '(password|passwd|secret|api_key|apikey|access_key|auth_token|private_key)\s*[=:]\s*["\x27][^"\x27\s]{8,}' \
    2>/dev/null || true)

  if [ -n "$FOUND" ]; then
    MESSAGES="$MESSAGES\n[SECRETS] Potential credentials in staged changes:\n$FOUND"
    return 1
  fi
  return 0
}

# Ensure gitleaks installed — brew (mac/linux) → apt/dnf/yum → binary download
_install_gitleaks() {
  echo "[SECRETS] gitleaks not found — installing..." >&2

  if command -v brew &>/dev/null; then
    brew install gitleaks &>/dev/null && return 0
  fi

  local OS ARCH
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)          ARCH="x64" ;;
    aarch64|arm64)   ARCH="arm64" ;;
    armv7l)          ARCH="armv7" ;;
    i386|i686)       ARCH="x32" ;;
    *)               ARCH="" ;;
  esac

  if [ "$OS" = "linux" ]; then
    # Package managers (gitleaks in official repos on some distros)
    if command -v apt-get &>/dev/null && apt-cache show gitleaks &>/dev/null 2>&1; then
      sudo apt-get install -y gitleaks &>/dev/null && return 0
    elif command -v dnf &>/dev/null; then
      sudo dnf install -y gitleaks &>/dev/null && return 0
    elif command -v yum &>/dev/null; then
      sudo yum install -y gitleaks &>/dev/null && return 0
    elif command -v pacman &>/dev/null; then
      sudo pacman -Sy --noconfirm gitleaks &>/dev/null && return 0
    fi

    # Binary download from GitHub releases (fallback)
    if [ -n "$ARCH" ] && command -v curl &>/dev/null; then
      local VERSION TMPDIR INSTALL_DIR
      VERSION=$(curl -sf "https://api.github.com/repos/gitleaks/gitleaks/releases/latest" \
        | grep '"tag_name"' | sed 's/.*"v\([^"]*\)".*/\1/')
      [ -z "$VERSION" ] && return 1

      TMPDIR=$(mktemp -d)
      curl -sL "https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_${OS}_${ARCH}.tar.gz" \
        | tar -xz -C "$TMPDIR" gitleaks 2>/dev/null

      if [ -f "$TMPDIR/gitleaks" ]; then
        if [ -w /usr/local/bin ]; then
          INSTALL_DIR=/usr/local/bin
        else
          INSTALL_DIR="$HOME/.local/bin"
          mkdir -p "$INSTALL_DIR"
        fi
        mv "$TMPDIR/gitleaks" "$INSTALL_DIR/gitleaks"
        chmod +x "$INSTALL_DIR/gitleaks"
        export PATH="$INSTALL_DIR:$PATH"
      fi
      rm -rf "$TMPDIR"
      command -v gitleaks &>/dev/null && return 0
    fi
  fi

  return 1
}

if ! command -v gitleaks &>/dev/null; then
  # Add ~/.local/bin to PATH in case it was installed there previously
  export PATH="$HOME/.local/bin:$PATH"
  if ! command -v gitleaks &>/dev/null; then
    _install_gitleaks
  fi
fi

if command -v gitleaks &>/dev/null; then
  if ! _secrets_gitleaks; then
    FAIL=1
  fi
else
  echo "[SECRETS] gitleaks not found — using grep fallback (install: brew install gitleaks)" >&2
  if ! _secrets_grep_fallback; then
    FAIL=1
  fi
fi

if [ "$FAIL" -eq 1 ]; then
  printf '%b\n' "$MESSAGES" >&2
  printf '{"decision":"block","reason":"Pre-commit checks failed — fix lint/test/secrets issues before committing."}'
  exit 1
fi

exit 0
