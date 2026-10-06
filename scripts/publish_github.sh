#!/usr/bin/env bash
# Put this repo on GitHub with the web version (GitHub Pages) and, with --tag, the desktop installers.
#
#   ./scripts/publish_github.sh                        # create the repo if needed, push main, enable Pages
#   ./scripts/publish_github.sh --tag v0.6.0           # ...and tag a release: GitHub Actions builds the installers
#   ./scripts/publish_github.sh --user N0rmansrule --host github.com --private
#
# Defaults: --user Normansrule --host github-normansrule (an SSH host alias in ~/.ssh/config) --repo skyforge-v18-falcon.
# Pushes over SSH so the workflow files go up even if your gh token lacks the 'workflow' scope.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
GH_USER=Normansrule; GH_HOST=github-normansrule; REPO=skyforge-v18-falcon; VIS=--public; TAG=""; PAGES=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) GH_USER="$2"; shift ;; --host) GH_HOST="$2"; shift ;; --repo) REPO="$2"; shift ;;
    --private) VIS=--private ;; --tag) TAG="$2"; shift ;; --no-pages) PAGES=0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
say() { printf '\n\033[1;33m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m%s\033[0m\n' "$*"; exit 1; }

[[ "$ROOT" != "$HOME" ]] || die "This is your home folder. Clone the repo into ~/src/skyforge-v18-falcon and run it there."
[[ "$(git rev-parse --show-toplevel 2>/dev/null)" == "$ROOT" ]] || die "$ROOT is not the top of a git repository."
[[ "$(git branch --show-current)" == "main" ]] || die "Switch to the main branch first (git switch main)."
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Uncommitted changes:"; git status --short | head -20
  die "Commit them first:  git add -A && git commit -m 'Describe the change'"
fi

# SSH alias or plain github.com
if ! ssh -G "$GH_HOST" >/dev/null 2>&1 || [[ "$(ssh -G "$GH_HOST" | awk '/^hostname /{print $2}')" != "github.com" ]]; then
  [[ "$GH_HOST" == "github.com" ]] || { echo "SSH host '$GH_HOST' is not set up; using github.com."; GH_HOST=github.com; }
fi
say "Checking SSH access as $GH_USER via $GH_HOST"
SSH_OUT=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T "git@$GH_HOST" 2>&1 || true)
grep -q "successfully authenticated" <<<"$SSH_OUT" \
  || die "SSH to git@$GH_HOST failed ($SSH_OUT). Add your key to GitHub (ssh-keygen -t ed25519, then github.com/settings/keys)."
echo "$SSH_OUT" | head -1

HAVE_GH=0
if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then HAVE_GH=1; fi

say "GitHub repository $GH_USER/$REPO"
if [[ $HAVE_GH == 1 ]]; then
  if gh repo view "$GH_USER/$REPO" >/dev/null 2>&1; then echo "exists"
  else
    gh repo create "$GH_USER/$REPO" "$VIS" \
      --description "SKYFORGE Falcon hybrid-VTOL build workbench: V18 analysis, V19 variants, BOM, wiring, web + desktop app"
  fi
else
  echo "GitHub CLI not available or not logged in (gh auth login). Create an EMPTY repository named '$REPO' at"
  echo "  https://github.com/new   (no README, licence or .gitignore)"
  read -r -p "Press Enter when it exists... " _
fi

URL="git@$GH_HOST:$GH_USER/$REPO.git"
if OLD=$(git remote get-url origin 2>/dev/null); then
  [[ "$OLD" == "$URL" ]] || echo "origin was $OLD - now $URL"
  git remote set-url origin "$URL"
else
  git remote add origin "$URL"
fi
say "Pushing main to $URL"
git push -u origin main

LOWER=$(echo "$GH_USER" | tr 'A-Z' 'a-z')
if [[ $PAGES == 1 ]]; then
  say "GitHub Pages (web version)"
  if [[ $HAVE_GH == 1 ]]; then
    gh api -X POST "repos/$GH_USER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 \
      || gh api -X PUT "repos/$GH_USER/$REPO/pages" -f build_type=workflow >/dev/null 2>&1 || true
    gh workflow run pages.yml --repo "$GH_USER/$REPO" >/dev/null 2>&1 || true
    sleep 6
    RUN=$(gh run list --repo "$GH_USER/$REPO" --workflow pages.yml --event workflow_dispatch --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
    [[ -n "$RUN" ]] && gh run watch "$RUN" --repo "$GH_USER/$REPO" --exit-status || true
  else
    echo "In the repo: Settings -> Pages -> Source: GitHub Actions; then Actions -> Deploy to GitHub Pages -> Run workflow."
  fi
  echo "Web version: https://$LOWER.github.io/$REPO/"
fi

if [[ -n "$TAG" ]]; then
  VER=$(node -p "require('./package.json').version")
  [[ "$TAG" == "v$VER" ]] || die "Tag $TAG does not match package.json version $VER (bump versions first; tools/check_repo.py checks they agree)."
  say "Tagging $TAG (desktop installers build in GitHub Actions, ~15 min)"
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    [[ "$(git rev-parse "$TAG^{commit}")" == "$(git rev-parse HEAD)" ]] || die "Tag $TAG already exists on another commit. Bump the version for a new release."
  else
    git tag -a "$TAG" -m "SKYFORGE Falcon workbench $TAG"
  fi
  git push origin "$TAG"
  if [[ $HAVE_GH == 1 ]]; then
    sleep 8
    RUN=$(gh run list --repo "$GH_USER/$REPO" --workflow desktop.yml --event push --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)
    [[ -n "$RUN" ]] && gh run watch "$RUN" --repo "$GH_USER/$REPO" --exit-status || true
  fi
  echo "Installers: https://github.com/$GH_USER/$REPO/releases/tag/$TAG"
fi
say "Done: https://github.com/$GH_USER/$REPO"
