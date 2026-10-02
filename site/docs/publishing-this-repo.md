# Publishing: GitHub repo, web version (Pages) and app version (desktop installers)

Written for an Ubuntu (WSL2) terminal and the `Normansrule` GitHub account through the SSH host alias
`github-normansrule`. Workflow files are pushed over SSH because an HTTPS gh token without the
`workflow` scope cannot push them. If this repo belongs on another account, change `GH_USER` and
`GH_HOST` (for example `N0rmansrule` and `github.com`).

## 1. Get the repo (never inside a git-tracked home folder)

The repo ships as a git bundle (one file with the full history):

```bash
mkdir -p ~/src && cd ~/src
git clone /mnt/c/Users/aleks/Downloads/skyforge-v18-falcon.bundle skyforge-v18-falcon
cd ~/src/skyforge-v18-falcon
git log --oneline | head -3
```

## 2. Create the GitHub repo and push

```bash
GH_USER=Normansrule
GH_HOST=github-normansrule
REPO=skyforge-v18-falcon
gh repo create "$GH_USER/$REPO" --public \
  --description "SKYFORGE V18 Falcon - hybrid-VTOL RC build workbench: V18 CAD analysis, balance study, BOM, wiring, web + desktop app"
git remote add origin "git@$GH_HOST:$GH_USER/$REPO.git" 2>/dev/null || git remote set-url origin "git@$GH_HOST:$GH_USER/$REPO.git"
git push -u origin main
```

Without gh: create an **empty** repo at https://github.com/new (no README, licence or .gitignore), then run
the last two lines.

## 3. Web version (GitHub Pages)

```bash
gh api -X POST "repos/$GH_USER/$REPO/pages" -f build_type=workflow 2>/dev/null \
  || gh api -X PUT "repos/$GH_USER/$REPO/pages" -f build_type=workflow
gh workflow run pages.yml --repo "$GH_USER/$REPO" && sleep 8
gh run watch --repo "$GH_USER/$REPO" $(gh run list --repo "$GH_USER/$REPO" --workflow pages.yml --limit 1 --json databaseId -q '.[0].databaseId')
echo "https://$(echo $GH_USER | tr 'A-Z' 'a-z').github.io/$REPO/"
```

Without gh: repository **Settings → Pages → Source: GitHub Actions**, then **Actions → Deploy to GitHub
Pages → Run workflow**.

Once the site is open in Chrome or Edge, the install icon in the address bar installs it as an offline app.

## 4. App version (Windows / macOS / Linux installers)

```bash
git tag v0.2.0
git push origin v0.2.0 && sleep 8
gh run watch --repo "$GH_USER/$REPO" $(gh run list --repo "$GH_USER/$REPO" --workflow desktop.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh release view v0.2.0 --repo "$GH_USER/$REPO" --web
```

The release gets a Windows `.msi`/`-setup.exe`, macOS `.dmg` (Apple silicon and Intel) and Linux
`.AppImage`/`.deb`/`.rpm`. They are not code-signed. On Windows, SmartScreen needs **More info → Run
anyway**.

## 5. Run it locally

```bash
cd ~/src/skyforge-v18-falcon
python3 -m http.server 8080 --directory site     # then open http://localhost:8080 in Windows
```

## 6. Later updates

```bash
cd ~/src/skyforge-v18-falcon
python3 tools/budget.py && python3 tools/check_repo.py     # after editing the BOM or measurements
git add -A && git commit -m "Describe the change" && git push
# new desktop build: bump the version in package.json, desktop/package.json,
# desktop/src-tauri/tauri.conf.json and desktop/src-tauri/Cargo.toml (check_repo.py checks they match), then:
git tag v0.2.1 && git push origin v0.2.1
```

Full re-run of the analysis from the V18 file (Python 3.11+):

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python3 tools/v18_extract.py && python3 tools/mass_cg.py && python3 tools/aero_vlm.py
python3 tools/geom_checks.py && python3 tools/harness.py && python3 tools/balance_study.py
python3 cad/interface/src/build.py && python3 tools/budget.py
npm ci && npm run vendor && python3 tools/export_web.py && npm run models && python3 tools/export_web.py --sw-only
python3 tools/check_repo.py && npm test
```
