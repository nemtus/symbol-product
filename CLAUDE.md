# Repository guide

This repository is a **NEMTUS mirror of [`symbol/product`](https://github.com/symbol/product)** (tracked
branch: `dev`). Most components are unmodified upstream code; a small NEMTUS layer makes the Symbol
node-setup tooling upstream-independent. See [`docs/nemtus-mirror.md`](docs/nemtus-mirror.md) for the full
picture.

## Conventions

- **Write published artifacts in English** — PR titles/descriptions, commit messages, code comments,
  docs, release notes, workflow comments. (Conversational replies may be in the user's language.)
- **Pin every GitHub Actions `uses:` to a full-length commit SHA** (with a `# vX.Y.Z` comment). The repo's
  Actions policy rejects mutable tags; Dependabot's `github-actions` group bumps the pins.
- **Following upstream uses git merge, never squash.** Sync PRs (from `mirror-sync.yml`) must be merged with
  a merge commit to preserve the upstream parent.

## NEMTUS mirror layer — do not regress

The mirror layer is real source code, not a regenerable patch. Keep these invariants (an upstream merge can
silently revert them):

- `tools/shoestring` is package `nemtus-symbol-shoestring`, depends on `nemtus-symbol-sdk` /
  `nemtus-symbol-lightapi`, and `PackageResolver.py` resolves network config from `nemtus/symbol-networks`
  (no upstream Release-API / `OFFICIAL_HASHES`).
- `lightapi/python` is package `nemtus-symbol-lightapi` (import module `symbollightapi` unchanged).
- Node images are `ghcr.io/nemtus/{catapult-server,symbol-rest}` (no `symbolplatform/` in shoestring source).

Validate at any time:

```bash
bash .github/scripts/check-nemtus-mirror-invariants.sh
```

## Running the tests locally

Needs `libssl-dev` + a compiler for the lightapi cffi/OpenSSL extension.

```bash
# lightapi
cd lightapi/python && pip install -e . && pip install -r dev_requirements.txt && bash scripts/ci/test.sh

# shoestring (install the in-repo lightapi first — nemtus-symbol-lightapi may not be on PyPI yet)
pip install ./lightapi/python
cd tools/shoestring
pip install -r requirements.txt -r dev_requirements.txt
bash scripts/ci/build.sh   # compiles i18n .mo files
bash scripts/ci/test.sh    # PYTHONPATH=. pytest --asyncio-mode=auto
```
