#!/bin/bash
#
# resolve-upstream-sync.sh
#
# Local helper for resolving an upstream mirror-sync conflict by hand. It mirrors what
# .github/workflows/mirror-sync.yml does in CI, but is meant to run on a maintainer's machine:
# it LEAVES the merge in progress on conflict (CI aborts it) so you can edit the conflict
# hunks, and it prints the exact next steps (invariants check, push, PR).
#
# Usage:
#   bash .github/scripts/resolve-upstream-sync.sh                 # sync from symbol/product:dev
#   UPSTREAM_BRANCH=main bash .github/scripts/resolve-upstream-sync.sh
#
# It is intentionally idempotent-ish: re-running while a sync branch already exists just checks
# it out. See docs/nemtus-mirror.md ("Following upstream").

set -uo pipefail

UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-https://github.com/symbol/product.git}"
UPSTREAM_BRANCH="${UPSTREAM_BRANCH:-dev}"
LOCAL_BRANCH="${LOCAL_BRANCH:-dev}"

cd "$(git rev-parse --show-toplevel)" || exit 2

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# 1. upstream remote (add if missing; never push to it)
if ! git remote get-url upstream >/dev/null 2>&1; then
	say "adding upstream remote -> ${UPSTREAM_REMOTE}"
	git remote add upstream "${UPSTREAM_REMOTE}"
fi

say "fetching upstream/${UPSTREAM_BRANCH}"
git fetch --no-tags upstream "${UPSTREAM_BRANCH}" || exit 1
UPSTREAM_SHA="$(git rev-parse --short "upstream/${UPSTREAM_BRANCH}")"
SYNC_BRANCH="sync/upstream-${UPSTREAM_SHA}"

# 2. fast-path: already contains every upstream commit?
if git merge-base --is-ancestor "upstream/${UPSTREAM_BRANCH}" "${LOCAL_BRANCH}"; then
	say "Already up to date with upstream@${UPSTREAM_SHA}; nothing to sync."
	exit 0
fi

# 3. work on a sync branch off the local tracking branch
say "creating ${SYNC_BRANCH} off ${LOCAL_BRANCH}"
git checkout "${LOCAL_BRANCH}" || exit 1
git checkout -B "${SYNC_BRANCH}" || exit 1

say "merging upstream/${UPSTREAM_BRANCH}@${UPSTREAM_SHA}"
if git merge --no-ff --no-edit "upstream/${UPSTREAM_BRANCH}"; then
	say "Clean merge. Running mirror invariants..."
	bash .github/scripts/check-nemtus-mirror-invariants.sh || {
		echo "!! invariants FAILED on a clean merge — upstream likely reverted the mirror layer; reconcile before pushing."
		exit 1
	}
	cat <<EOF

Clean merge complete. Next:
  git push -u origin ${SYNC_BRANCH}
  gh pr create --repo nemtus/symbol-product --base ${LOCAL_BRANCH} --head ${SYNC_BRANCH} \\
    --title 'Sync upstream symbol/product:${UPSTREAM_BRANCH}@${UPSTREAM_SHA}'
  # merge the PR with a MERGE COMMIT (not squash).
EOF
	exit 0
fi

# 4. conflict — leave the merge in progress for manual resolution
CONFLICTS="$(git diff --name-only --diff-filter=U | sort)"
say "CONFLICT while merging upstream@${UPSTREAM_SHA}. Files:"
printf '%s\n' "${CONFLICTS}"

say "conflict hunks (git diff):"
git --no-pager diff --diff-filter=U

cat <<EOF

The merge is LEFT IN PROGRESS. Resolve it:
  1. Edit each file above. Keep the NEMTUS mirror layer (package names, deps, images,
     PackageResolver source) and take upstream's real changes (e.g. version bumps).
     See docs/nemtus-mirror.md.
  2. git add <resolved files>
  3. bash .github/scripts/check-nemtus-mirror-invariants.sh   # must print: all checks passed
  4. git commit --no-edit
  5. git push -u origin ${SYNC_BRANCH}
  6. gh pr create --repo nemtus/symbol-product --base ${LOCAL_BRANCH} --head ${SYNC_BRANCH} \\
       --title 'Sync upstream symbol/product:${UPSTREAM_BRANCH}@${UPSTREAM_SHA}'
     # merge the PR with a MERGE COMMIT (not squash).

To bail out: git merge --abort
EOF
exit 1
