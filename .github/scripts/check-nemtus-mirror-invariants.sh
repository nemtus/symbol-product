#!/bin/bash
#
# check-nemtus-mirror-invariants.sh
#
# Asserts the NEMTUS "mirror layer" invariants that distinguish this repo from upstream
# symbol/product. These are the changes that make shoestring/lightapi upstream-independent
# (package renames, image repoint, network-config source). An upstream merge (mirror-sync)
# could silently revert any of them, so CI (ci.yml `parity` job) and mirror-sync run this
# script as a gate. It is also runnable locally:  bash .github/scripts/check-nemtus-mirror-invariants.sh
#
# Exits 0 if all invariants hold, 1 otherwise (printing each violation). See docs/nemtus-mirror.md.

set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 2

errors=0
fail() { printf 'FAIL: %s\n' "$1"; errors=$((errors + 1)); }
ok() { printf 'ok:   %s\n' "$1"; }

SHOESTRING_REQ='tools/shoestring/requirements.txt'
SHOESTRING_PYPROJECT='tools/shoestring/pyproject.toml'
PACKAGE_RESOLVER='tools/shoestring/shoestring/internal/PackageResolver.py'
LIGHTAPI_SETUP='lightapi/python/setup.cfg'
SAMPLE_INI='tools/shoestring/tests/resources/sai.shoestring.ini'

# 1. shoestring depends on the NEMTUS PyPI mirrors, not the upstream packages.
if grep -qE '^nemtus-symbol-sdk' "${SHOESTRING_REQ}" && grep -qE '^nemtus-symbol-lightapi' "${SHOESTRING_REQ}"; then
	ok "${SHOESTRING_REQ} depends on nemtus-symbol-sdk + nemtus-symbol-lightapi"
else
	fail "${SHOESTRING_REQ} must depend on nemtus-symbol-sdk and nemtus-symbol-lightapi"
fi
if grep -qE '^(symbol-sdk-python|symbol-lightapi)([~=<>! ]|$)' "${SHOESTRING_REQ}"; then
	fail "${SHOESTRING_REQ} still references upstream symbol-sdk-python / symbol-lightapi"
else
	ok "${SHOESTRING_REQ} has no upstream symbol-sdk-python / symbol-lightapi"
fi

# 2. shoestring is published under the NEMTUS package name.
if grep -qE "^name = 'nemtus-symbol-shoestring'" "${SHOESTRING_PYPROJECT}"; then
	ok "${SHOESTRING_PYPROJECT} name is nemtus-symbol-shoestring"
else
	fail "${SHOESTRING_PYPROJECT} name must be 'nemtus-symbol-shoestring'"
fi

# 3. PackageResolver resolves config from nemtus/symbol-networks, not the upstream Release API.
if grep -q 'nemtus/symbol-networks' "${PACKAGE_RESOLVER}"; then
	ok "${PACKAGE_RESOLVER} resolves config from nemtus/symbol-networks"
else
	fail "${PACKAGE_RESOLVER} must resolve network config from nemtus/symbol-networks"
fi
if grep -qE 'api\.github\.com/repos/symbol/symbol|OFFICIAL_HASHES' "${PACKAGE_RESOLVER}"; then
	fail "${PACKAGE_RESOLVER} still uses the upstream Release-API / OFFICIAL_HASHES path"
else
	ok "${PACKAGE_RESOLVER} has no upstream Release-API / OFFICIAL_HASHES path"
fi

# 4. lightapi is published under the NEMTUS package name (import module stays symbollightapi).
if grep -qE '^name = nemtus-symbol-lightapi' "${LIGHTAPI_SETUP}"; then
	ok "${LIGHTAPI_SETUP} name is nemtus-symbol-lightapi"
else
	fail "${LIGHTAPI_SETUP} name must be 'nemtus-symbol-lightapi'"
fi

# 5. No upstream symbolplatform images leak into shoestring source or the sample config.
#    (The abstract unit-test mocks under tests/** intentionally keep placeholder image strings
#     and are out of scope.)
leak=$(grep -rEl 'symbolplatform/' tools/shoestring/shoestring "${SAMPLE_INI}" 2>/dev/null)
if [ -n "${leak}" ]; then
	fail "symbolplatform/ image reference found in: ${leak}"
else
	ok "no symbolplatform/ image references in shoestring source or ${SAMPLE_INI}"
fi

echo
if [ "${errors}" -ne 0 ]; then
	printf 'mirror-invariants: %d violation(s)\n' "${errors}"
	exit 1
fi
echo 'mirror-invariants: all checks passed'
