#!/usr/bin/env bash
# One-time setup on Ubuntu / WSL2 Ubuntu for the SKYFORGE Falcon workbench.
#
#   ./scripts/setup_ubuntu.sh             # apt packages, Python venv (.venv), Node packages, vendored web libraries
#   ./scripts/setup_ubuntu.sh --desktop   # ...plus Rust and the Tauri libraries for the desktop app
#   ./scripts/setup_ubuntu.sh --gh        # ...plus the GitHub CLI (for scripts/publish_github.sh)
#   ./scripts/setup_ubuntu.sh --no-apt    # skip apt (no sudo); Python + Node must already be installed
#
# Safe to run again. Everything goes into this folder (.venv, node_modules) except apt packages and rustup.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
APT=1; DESKTOP=0; GH=0
for a in "$@"; do
  case "$a" in
    --desktop) DESKTOP=1 ;; --gh) GH=1 ;; --no-apt) APT=0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option $a"; exit 2 ;;
  esac
done
say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
if [[ "$ROOT" == "$HOME" ]]; then echo "Refusing to run in your home folder. Clone the repo into ~/src first."; exit 1; fi

if [[ $APT == 1 ]]; then
  say "apt packages (python3-venv, git, make, curl)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3 python3-venv python3-pip git make curl ca-certificates >/dev/null
  need_node=1
  if command -v node >/dev/null; then [[ $(node -p 'process.versions.node.split(".")[0]') -ge 20 ]] && need_node=0; fi
  if [[ $need_node == 1 ]]; then
    say "Node.js 22 (NodeSource)"
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - >/dev/null
    sudo apt-get install -y -qq nodejs >/dev/null
  fi
  if [[ $GH == 1 ]] && ! command -v gh >/dev/null; then
    say "GitHub CLI"
    sudo mkdir -p -m 755 /etc/apt/keyrings
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    sudo apt-get update -qq && sudo apt-get install -y -qq gh >/dev/null
  fi
  if [[ $DESKTOP == 1 ]]; then
    say "Tauri system libraries"
    sudo apt-get install -y -qq build-essential wget file libwebkit2gtk-4.1-dev libxdo-dev libssl-dev \
      libayatana-appindicator3-dev librsvg2-dev >/dev/null
  fi
fi

say "Python environment (.venv)"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

say "Node packages and vendored browser libraries"
npm ci --no-audit --no-fund
npm run vendor

if [[ $DESKTOP == 1 ]]; then
  if ! command -v cargo >/dev/null && [[ ! -x "$HOME/.cargo/bin/cargo" ]]; then
    say "Rust (rustup, current user only)"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
  fi
  # shellcheck disable=SC1091
  if [[ -f "$HOME/.cargo/env" ]]; then source "$HOME/.cargo/env"; fi
  (cd desktop && npm install --no-audit --no-fund)
fi

say "Checks"
.venv/bin/python3 tools/check_repo.py | tail -1
if npm test --silent >/dev/null 2>&1; then echo "web calculator == Python budget: OK"; else echo "npm test FAILED - run 'npm test' to see why"; fi

cat <<MSG

Done. Next:
  make serve            # web app at http://localhost:8080 (open it in your Windows browser under WSL)
  make help             # everything else
$( [[ $DESKTOP == 1 ]] && echo '  make desktop          # desktop app (new terminal first, or: source ~/.cargo/env)' )
MSG
