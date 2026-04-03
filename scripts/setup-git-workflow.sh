#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

git config core.hooksPath .githooks
chmod +x .githooks/pre-push

if [[ -n "${1:-}" ]]; then
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$1"
  else
    git remote add origin "$1"
  fi
fi

echo "Git workflow setup complete."
echo "- hooksPath: $(git config --get core.hooksPath)"

if git remote get-url origin >/dev/null 2>&1; then
  echo "- origin: $(git remote get-url origin)"
else
  echo "- origin: not set"
fi
