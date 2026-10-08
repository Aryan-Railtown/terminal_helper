#!/usr/bin/env bash
# Installs sage for the current macOS/Linux user. Run from the repo folder:
#   ./install.sh                 (or: bash install.sh)
# Installs uv if missing (uv also fetches Python 3.11 if needed), installs the `sage`
# command, and creates ~/.sage/.env and config.toml from the examples.
# Safe to re-run: it upgrades sage and never overwrites your existing .env/config.
#   --no-path-update   skip adding uv's tool folder to your shell PATH (for CI/testing)
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
path_update=1
for arg in "$@"; do
  case "$arg" in
    --no-path-update) path_update=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

cyan() { printf '\033[36m%s\033[0m\n' "$1"; }
green() { printf '\033[32m%s\033[0m\n' "$1"; }

if ! command -v uv >/dev/null 2>&1; then
  cyan "Installing uv (Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

cyan "Installing sage..."
uv tool install --force --reinstall-package terminal-helper "$repo"
if [ "$path_update" = 1 ]; then
  uv tool update-shell >/dev/null 2>&1 || true
fi

sage_home="${SAGE_HOME:-$HOME/.sage}"
mkdir -p "$sage_home"
[ -f "$sage_home/.env" ] || cp "$repo/.env.example" "$sage_home/.env"
[ -f "$sage_home/config.toml" ] || cp "$repo/config.example.toml" "$sage_home/config.toml"

# Point `railtracks viz --beta` (run from this folder) at sage's run logs. railtracks reads
# the .env in the folder it starts from; this repo .env is gitignored and holds no keys.
repo_env="$repo/.env"
if ! { [ -f "$repo_env" ] && grep -Eq '^[[:space:]]*RAILTRACKS_HOME[[:space:]]*=' "$repo_env"; }; then
  if [ -s "$repo_env" ] && [ -n "$(tail -c 1 "$repo_env")" ]; then echo >> "$repo_env"; fi
  echo "RAILTRACKS_HOME=$sage_home" >> "$repo_env"
fi

echo
green "sage is installed."
echo "Next steps:"
if [ "$(uname)" = "Darwin" ]; then
  echo "  1. Add your API key:   open -e \"$sage_home/.env\""
else
  echo "  1. Add your API key:   \${EDITOR:-nano} \"$sage_home/.env\""
fi
echo "     (Gemini has a free tier: https://aistudio.google.com/apikey)"
echo "  2. Open a NEW terminal, then check setup:   sage --debug"
echo "  3. Ask something:      sage how do I find what is using port 3000"
echo "  4. View past runs:     uv run railtracks viz --beta   (from this folder, then open http://localhost:3031)"
