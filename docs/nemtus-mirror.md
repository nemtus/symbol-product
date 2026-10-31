<!-- nemtus-mirror-notice -->
# NEMTUS mirror of symbol/product

This repository is a NEMTUS mirror of [`symbol/product`](https://github.com/symbol/product) (tracked
branch: `dev`). Most of the monorepo is unmodified from upstream. A small **NEMTUS mirror layer** makes
the Symbol node-setup tooling runnable **without any upstream dependency**, and is published under NEMTUS
package names.

## What differs from upstream

| Area | upstream | NEMTUS mirror |
|---|---|---|
| shoestring package | `symbol-shoestring` (PyPI) | **`nemtus-symbol-shoestring`** (PyPI) |
| lightapi package | `symbol-lightapi` (PyPI) | **`nemtus-symbol-lightapi`** (PyPI; import module `symbollightapi` unchanged) |
| Python deps | `symbol-sdk-python` (pulls `catparser`) | `nemtus-symbol-sdk` (import `symbolchain`; pulls `nemtus-catparser` transitively) |
| Node images | `symbolplatform/symbol-server`, `symbolplatform/symbol-rest` | `ghcr.io/nemtus/catapult-server`, `ghcr.io/nemtus/symbol-rest` |
| Network config source | `symbol/symbol` releases + `symbol/networks` | branch archives of [`nemtus/symbol-networks`](https://github.com/nemtus/symbol-networks) (`main` / `test-sai`) |
| `_symbol` submodule (linters/jenkins, CI+dev only) | `symbol/symbol` | **[`nemtus/symbol`](https://github.com/nemtus/symbol)** (merge-based mirror; only the fetch URL is NEMTUS — the pinned SHA still tracks upstream) |

The image names are not hardcoded in shoestring; they come from the `shoestring.ini [images]` inside the
network-config package served by `nemtus/symbol-networks` (see that repo's `docs/contract.md`).
`mongo` and `[services] nodewatch` are intentionally left as upstream (the latter is a follow-up for strict
full-independence).

## Mirror invariants

The mirror layer is **source code** (package renames, the `PackageResolver` rewrite), so it cannot be
regenerated from a patch. It is preserved through git history and protected by a parity gate:

```bash
bash .github/scripts/check-nemtus-mirror-invariants.sh
```

This asserts: shoestring depends on the `nemtus-*` mirrors (not `symbol-sdk-python` / `symbol-lightapi`);
the shoestring/lightapi package names are the `nemtus-*` names; `PackageResolver.py` resolves from
`nemtus/symbol-networks` and no longer uses the upstream Release-API / `OFFICIAL_HASHES` path; no
`symbolplatform/` image leaks into shoestring source; and the `_symbol` submodule fetches from
`nemtus/symbol`. The `parity` job in `ci.yml` runs it on every PR.

## Following upstream

`mirror-sync.yml` (daily 04:17 UTC + manual `workflow_dispatch`) tracks `symbol/product:dev`:

1. fetches `upstream` (`https://github.com/symbol/product.git`);
2. fast-path no-op if `dev` already contains every upstream commit;
3. otherwise merges upstream into a `sync/upstream-<sha>` branch:
   - **clean merge** → opens a PR;
   - **conflict in the packaging `version` line only** (what an upstream version bump always produces)
     → auto-resolved, then opens a PR that spells out the resolution (see below);
   - **any other conflict** → aborts the merge and **fails the run**, writing the conflicting files and
     the local resolution steps to the run's job summary. (This repo is an Issues-disabled fork, so the
     conflict is signalled by the red run + summary rather than a tracking issue.)

The sync PR is opened by `github-actions[bot]` (the built-in `GITHUB_TOKEN`), so its `ci.yml` runs start
in an approval-required state: click **"Approve workflows to run"** in the PR merge box to run
`parity`/`lightapi`/`shoestring`. This is intentional — automated changes don't run CI unattended.

> **Always merge a sync PR with a MERGE COMMIT (not squash).** Squashing drops the upstream parent, which
> makes every later sync replay all of upstream history as one giant diff and breaks the fast-path.

After resolving any conflict, keep the NEMTUS mirror layer (above) and ensure
`check-nemtus-mirror-invariants.sh` passes before merging.

Conflicts here are structural, not accidental: the mirror layer permanently rewrites a few packaging
files (`lightapi/python/setup.cfg`, `tools/shoestring/pyproject.toml`, `PackageResolver.py`, …), so any
upstream edit to them — most often a version bump — collides with the NEMTUS edit. They cannot be
eliminated (a rename mirror must diverge on `name`/deps); the goal is to resolve them quickly and safely.

The most common one is resolved automatically. In both packaging files the `name` and `version` lines are
adjacent, so an upstream version bump lands in the same diff hunk as the NEMTUS rename and git reports a
conflict even though the resolution is purely mechanical. Left to a human this failed the daily sync on
most upstream bumps, and the sync PRs piled up.
`.github/scripts/auto-resolve-version-conflicts.py` (run by `mirror-sync.yml`, and by the local helper
below) handles exactly that line:

- it masks the version **value** with a sentinel in all three merge stages, retries the three-way merge,
  and fills the sentinel back in with the higher of the two versions (PEP 440 ordering, so `0.0.10` vs
  `0.0.13` → `0.0.13`, and a NEMTUS-only `0.2.4.post1` vs an unchanged upstream `0.2.4` → `0.2.4.post1`);
- it therefore does **not** prefer a side — everything else in the file still comes from the normal
  three-way merge, so an upstream dependency or classifier change is not silently dropped;
- if the file still conflicts with the version line masked, upstream changed something that needs a human:
  the file is left unmerged and the run falls through to the manual path (abort + job summary) unchanged.

The version line it chose is quoted in the sync PR body. **Review it before merging** — it decides what
the next release publishes to PyPI.

Two further aids:

- **Helper script** — do the mechanical part (add the `upstream` remote, fetch, create the
  `sync/upstream-<sha>` branch, attempt the merge, auto-resolve the version line) and, on a conflict that
  needs a human, print the conflicting files, their hunks, and the exact resolution/PR steps. The merge is
  left in progress for you to edit:

  ```bash
  git checkout dev && git pull
  bash .github/scripts/resolve-upstream-sync.sh
  ```

- **`git rerere`** — enable it once so git records each conflict resolution and replays it automatically
  on the next structurally-identical conflict. This now covers the conflicts the auto-resolver declines
  (it only ever touches the version line):

  ```bash
  git config rerere.enabled true
  ```

The `_symbol` submodule (linters + jenkins config, sparse-checked-out by `init.sh`; consumed only by
Jenkins CI and local dev — **not** by GitHub Actions `ci.yml` nor by the published packages) **fetches from
the NEMTUS mirror [`nemtus/symbol`](https://github.com/nemtus/symbol)** instead of upstream `symbol/symbol`,
so an upstream outage cannot break dev/CI tooling (invariant #6 above). Only the fetch URL is NEMTUS: the
recorded pointer SHA still tracks upstream and is bumped by the merges arriving via `mirror-sync` and by the
existing Jenkins `updateSubmodule` job. Because `nemtus/symbol` is a **merge-based** mirror, every upstream
SHA the pointer references is preserved there as an ancestor; keep `nemtus/symbol`'s mirror-sync current (it
runs daily at 03:17 UTC — ahead of this repo's daily 04:17 sync) so the referenced SHA always exists before
it lands here. An
already-initialized clone picks up the URL change on the next `init.sh` (which now runs `git submodule sync`).

## CI

- **`ci.yml`** (every PR to `dev`, and every push to `dev`): runs `parity`, plus `lightapi` and
  `shoestring` test+build jobs. It uses only first-party, SHA-pinned actions so it runs even under a
  restrictive allowed-actions policy. The other ~14 monorepo components remain on upstream Jenkins.

  It is intentionally **not** path-filtered. The three jobs are required status checks on `dev`, and a
  path-filtered workflow does not run at all for a PR outside its filter — so the checks never report and
  the PR stays blocked forever. Upstream sync PRs that touch only other monorepo components hit exactly
  that. Separately, `parity` reads `.gitmodules`, which no component filter would cover, so a filtered
  gate could miss an upstream change that reverts the `_symbol` submodule invariant. The full workflow is
  ~50s of wall clock, which is cheaper than working around either problem.
- **`codeql-analysis.yaml`**, **`combine-dependabot-pr.yaml`**, **`publish-{shoestring,lightapi}.yaml`**:
  all third-party actions are pinned to full-length commit SHAs (kept current by Dependabot's
  `github-actions` group).

## Required GitHub repository settings (runbook)

Settings → **Actions → General**:
- **Actions permissions**: allow the actions in use. Either "Allow all actions and reusable workflows", or
  the allowlist `actions/*`, `github/*`, `pypa/gh-action-pypi-publish@*` (all SHA-pinned in-repo).
- **Workflow permissions**: "Read and write permissions" **and** check
  *Allow GitHub Actions to create and approve pull requests* (needed by `combine-dependabot-pr` and
  `mirror-sync`).

Settings → **Rules → Rulesets**: `dev` is protected by a ruleset (not legacy branch protection, so the
`branches/dev/protection` API reports "not protected"). It requires the `ci.yml` checks (`Mirror
invariants`, `lightapi (test + build)`, `shoestring (test + build)`), the CodeQL/Socket checks, and one
approving review; it allows the `merge` merge method only, matching the merge-commit rule above.

Two consequences worth knowing before you try to merge anything:

- **Required status checks must be able to run for every PR.** That is why `ci.yml` is not path-filtered
  (see the CI section) — a check that never reports blocks the PR permanently.
- **The approval requirement cannot be satisfied by the PR author**, and in practice every PR here is
  authored by the same maintainer, so merges go through the ruleset's admin bypass:

  ```bash
  gh pr merge <number> --repo nemtus/symbol-product --merge --admin
  ```

  Plain `gh pr merge --merge` fails with "the base branch policy prohibits the merge". `--admin` bypasses
  the ruleset — **including the required status checks** — so check the rollup yourself before using it:

  ```bash
  gh pr view <number> --repo nemtus/symbol-product --json statusCheckRollup \
    --jq '[.statusCheckRollup[]|"\(.name // .context)=\(.conclusion // .state)"]|join(" ")'
  ```

  Keep `--merge` — never `--squash` — for sync PRs.

## Release runbook (PyPI)

Publishing is via `publish-{shoestring,lightapi}.yaml` (tag-triggered, PyPI Trusted Publishing). Before the
first release:
- create a GitHub Environment named **`pypi-production`**;
- register PyPI **pending trusted publishers** for `nemtus-symbol-lightapi` (workflow `publish-lightapi.yaml`)
  and `nemtus-symbol-shoestring` (workflow `publish-shoestring.yaml`), environment `pypi-production`.

Publish order is **lightapi → shoestring** (shoestring depends on lightapi). Use the actual package
versions from `lightapi/python/setup.cfg` and `tools/shoestring/pyproject.toml`; the numbers below are
examples at the time of writing:

```bash
git tag nemtus-symbol-lightapi@<lightapi-version>   && git push origin nemtus-symbol-lightapi@<lightapi-version>
# e.g. nemtus-symbol-lightapi@0.0.9 ; confirm it is on PyPI, then:
git tag nemtus-symbol-shoestring@<shoestring-version> && git push origin nemtus-symbol-shoestring@<shoestring-version>
# e.g. nemtus-symbol-shoestring@0.2.4
```

The tag is the release coordinate, so each workflow first checks that the version in the tag matches the
version in the tree (`setup.cfg` / `pyproject.toml`) and fails before building if they disagree — a tag
pushed from the wrong commit cannot publish a version that was never built.

After a successful publish, a separate `release` job creates the **GitHub Release** for that tag
(matching `nemtus/symbol`, which does the same in its publish workflows): title
`<package> v<version> · PyPI`, body = a mirror-provenance line plus GitHub's auto-generated notes, scoped
to the previous release *of that package* (the two packages are released independently, so the newest
release in the repo is often the other one). It is idempotent — re-running a publish for an existing tag
leaves the Release alone. `contents: write` is confined to that job, which has no checkout and runs only
the `gh` CLI, so the build job keeps `contents: read`.

Releases are created only for tag-triggered runs; a manual `workflow_dispatch` has no tag and skips the
job. To add a Release for a version published before this automation existed:

```bash
gh release create nemtus-symbol-lightapi@0.0.13 --title 'nemtus-symbol-lightapi v0.0.13 · PyPI' --generate-notes
```

When upstream has not changed a package's version but the NEMTUS mirror needs a re-release (a packaging
fix, for example), append a PEP 440 post-release segment — `0.2.4` → `0.2.4.post1` → `0.2.4.post2` — so
the next upstream bump still sorts above it. PyPI never allows re-uploading a version that already exists.

`publish-shoestring.yaml` compiles the gettext catalogs (`pybabel compile`) before building, because the
`.mo` files shipped in the package are generated and gitignored; it then fails the run if the built
artifacts do not contain one catalog per language. Do not remove either step: without them the artifacts
carry only `.po` sources and shoestring aborts on startup with `FileNotFoundError: No translation file
found for domain: 'messages'` (the defect in the published `0.2.4` and `0.2.4.post1`).
<!-- /nemtus-mirror-notice -->
