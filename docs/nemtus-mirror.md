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
| Python deps | `symbol-sdk-python`, `catparser` | `nemtus-symbol-sdk` (import `symbolchain`), `nemtus-catparser` |
| Node images | `symbolplatform/symbol-server`, `symbolplatform/symbol-rest` | `ghcr.io/nemtus/catapult-server`, `ghcr.io/nemtus/symbol-rest` |
| Network config source | `symbol/symbol` releases + `symbol/networks` | branch archives of [`nemtus/symbol-networks`](https://github.com/nemtus/symbol-networks) (`main` / `test-sai`) |

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
`nemtus/symbol-networks` and no longer uses the upstream Release-API / `OFFICIAL_HASHES` path; and no
`symbolplatform/` image leaks into shoestring source. The `parity` job in `ci.yml` runs it on every PR.

## Following upstream

`mirror-sync.yml` (weekly + manual `workflow_dispatch`) tracks `symbol/product:dev`:

1. fetches `upstream` (`https://github.com/symbol/product.git`);
2. fast-path no-op if `dev` already contains every upstream commit;
3. otherwise merges upstream into a `sync/upstream-<sha>` branch:
   - **clean merge** → opens a PR;
   - **conflict** → aborts and files a tracking issue listing the conflicting files for manual resolution.

> **Always merge a sync PR with a MERGE COMMIT (not squash).** Squashing drops the upstream parent, which
> makes every later sync replay all of upstream history as one giant diff and breaks the fast-path.

After resolving any conflict, keep the NEMTUS mirror layer (above) and ensure
`check-nemtus-mirror-invariants.sh` passes before merging.

The `_symbol` submodule (`symbol/symbol`, used only for linters/build-ci) is a **separate** sync, owned by
the existing Jenkins `updateSubmodule` job — not handled by `mirror-sync.yml`.

## CI

- **`ci.yml`** (on PRs touching `tools/shoestring/**` or `lightapi/python/**`): runs `parity`, plus
  `lightapi` and `shoestring` test+build jobs. It uses only first-party, SHA-pinned actions so it runs even
  under a restrictive allowed-actions policy. The other ~14 monorepo components remain on upstream Jenkins.
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

(Optional) Settings → **Branches** → protect `dev`: require the `ci.yml` checks (`parity`, `lightapi`,
`shoestring`) before merge. Add them after the first CI run so the checks appear in the list.

## Release runbook (PyPI)

Publishing is via `publish-{shoestring,lightapi}.yaml` (tag-triggered, PyPI Trusted Publishing). Before the
first release:
- create a GitHub Environment named **`pypi-production`**;
- register PyPI **pending trusted publishers** for `nemtus-symbol-lightapi` (workflow `publish-lightapi.yaml`)
  and `nemtus-symbol-shoestring` (workflow `publish-shoestring.yaml`), environment `pypi-production`.

Publish order is **lightapi → shoestring** (shoestring depends on lightapi):

```bash
git tag nemtus-symbol-lightapi@0.0.9   && git push origin nemtus-symbol-lightapi@0.0.9
# confirm it is on PyPI, then:
git tag nemtus-symbol-shoestring@0.2.4 && git push origin nemtus-symbol-shoestring@0.2.4
```
<!-- /nemtus-mirror-notice -->
