# Publishing: GitHub repo, web version (Pages) and app version (desktop installers)

Written for an Ubuntu (WSL2) terminal and the `Normansrule` GitHub account through the SSH host alias
`github-normansrule`. Workflow files are pushed over SSH because an HTTPS gh token without the `workflow`
scope cannot push them. For another account pass `--user` / `--host` to the script (for example
`--user N0rmansrule --host github.com`).

## 1. Get the repo onto your machine (never inside a git-tracked home folder)

The repo ships as a git bundle (one file with the full history), saved to your Downloads folder.

**First time** (no copy yet):

```bash
mkdir -p ~/src && cd ~/src
git clone /mnt/c/Users/aleks/Downloads/skyforge-v18-falcon.bundle skyforge-v18-falcon
cd ~/src/skyforge-v18-falcon
git log --oneline | head -3
```

**Already have v0.2.0** in `~/src/skyforge-v18-falcon` (pushed or not) - the bundle continues the same history:

```bash
cd ~/src/skyforge-v18-falcon
git pull /mnt/c/Users/aleks/Downloads/skyforge-v18-falcon.bundle main
git log --oneline | head -3
```

## 2. Set up once

```bash
./scripts/setup_ubuntu.sh --gh          # apt packages, Node 22 if needed, .venv, npm packages, GitHub CLI
gh auth login                           # once, if the GitHub CLI is new (GitHub.com, SSH, browser)
make serve                              # check it locally: http://localhost:8080 in your Windows browser
```

## 3. Publish: one command

```bash
./scripts/publish_github.sh                  # create the repo if needed, push main, turn on Pages, deploy
./scripts/publish_github.sh --tag v0.3.0     # same, plus a tagged release: CI builds the desktop installers
```

The script refuses to run in your home folder or with uncommitted changes, checks SSH access first, and
prints the web address and the release page at the end. `make publish TAG=v0.3.0` does the same.

- **Web version:** `https://normansrule.github.io/skyforge-v18-falcon/`. In Chrome or Edge, the install icon in
  the address bar installs it as an offline app.
- **App version:** the release gets a Windows `.msi`/`-setup.exe`, macOS `.dmg` (Apple silicon and Intel) and
  Linux `.AppImage`/`.deb`/`.rpm`. They are not code-signed; on Windows, SmartScreen needs **More info → Run anyway**.

## 4. The same by hand

```bash
GH_USER=Normansrule; GH_HOST=github-normansrule; REPO=skyforge-v18-falcon
gh repo view "$GH_USER/$REPO" >/dev/null 2>&1 || gh repo create "$GH_USER/$REPO" --public \
  --description "SKYFORGE Falcon hybrid-VTOL build workbench: V18 analysis, V19 variants, BOM, wiring, web + desktop app"
git remote add origin "git@$GH_HOST:$GH_USER/$REPO.git" 2>/dev/null || git remote set-url origin "git@$GH_HOST:$GH_USER/$REPO.git"
git push -u origin main

# web version
gh api -X POST "repos/$GH_USER/$REPO/pages" -f build_type=workflow 2>/dev/null \
  || gh api -X PUT "repos/$GH_USER/$REPO/pages" -f build_type=workflow
gh workflow run pages.yml --repo "$GH_USER/$REPO"

# app version
git tag -a v0.3.0 -m "SKYFORGE Falcon workbench v0.3.0" && git push origin v0.3.0
gh run watch --repo "$GH_USER/$REPO" $(gh run list --repo "$GH_USER/$REPO" --workflow desktop.yml --limit 1 --json databaseId -q '.[0].databaseId')
```

Without gh: create an **empty** repo at https://github.com/new (no README, licence or .gitignore), push as above,
then **Settings → Pages → Source: GitHub Actions** and **Actions → Deploy to GitHub Pages → Run workflow**.

## 5. Later updates

```bash
cd ~/src/skyforge-v18-falcon
make budget && make check                  # after editing the BOM or measurements
git add -A && git commit -m "Describe the change" && git push
```

New desktop build: bump the version in `package.json`, `desktop/package.json`,
`desktop/src-tauri/tauri.conf.json` and `desktop/src-tauri/Cargo.toml` (`make check` verifies they agree),
commit, then `./scripts/publish_github.sh --tag vX.Y.Z`.

## 6. Re-run the analysis

```bash
make v18      # V18: extraction, mass, aero, checks, harness, balance study, interface parts (a few minutes)
make v19      # V19: search, variant geometry, report, web data (about 10 minutes)
make shots    # doc images from the web app (needs: .venv/bin/pip install playwright && .venv/bin/playwright install chromium)
make check
```

## 7. Desktop app locally

```bash
./scripts/setup_ubuntu.sh --desktop        # Rust + Tauri libraries, once
make desktop                               # development window
make desktop-build                         # installers for this OS in desktop/src-tauri/target/release/bundle
```
