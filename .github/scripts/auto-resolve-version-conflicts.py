#!/usr/bin/env python3

"""
Auto-resolve the one upstream-sync conflict that is structural and recurring: the package `version`
line in the files the NEMTUS mirror layer rewrites.

Run from the repository root with a conflicted merge in progress (see `mirror-sync.yml`).

Why this exists
---------------
The mirror renames the packages (`symbol-lightapi` -> `nemtus-symbol-lightapi`, `symbol-shoestring` ->
`nemtus-symbol-shoestring`), and in both packaging files the `name` and `version` lines are adjacent.
Every upstream version bump therefore lands inside the same diff hunk as the NEMTUS rename and git
reports a conflict, even though the correct resolution is always mechanical: keep the NEMTUS metadata,
take the newer version. That made `mirror-sync` fail on most upstream bumps and the sync PRs pile up.

How it resolves
---------------
Not by preferring a side -- that would silently drop whatever else upstream changed in the file (a new
dependency, a classifier). Instead the version VALUE is replaced by a sentinel in all three merge
stages, the three-way merge is retried, and the sentinel is filled back in afterwards with the higher
of the two versions (PEP 440 ordering, so `0.0.10` vs `0.0.13` -> `0.0.13`, and a NEMTUS-only
`0.2.4.post1` vs upstream `0.2.4` -> `0.2.4.post1`).

The version line is thus the ONLY thing this script decides. If the file still conflicts once the
version is out of the picture, upstream changed something that needs a human, and the file is left
unmerged -- which keeps `mirror-sync`'s existing conflict path (fail the run, report in the job
summary) intact for everything that is not this one known case.
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

SENTINEL = '@@NEMTUS_MIRROR_SYNC_VERSION_SENTINEL@@'

# The files the mirror layer rewrites, with the pattern matching their version VALUE (group 'version').
# Anything not listed here is never touched.
RESOLVABLE_FILES = {
	'lightapi/python/setup.cfg': re.compile(r'(?m)^version = (?P<version>\S+)[ \t]*$'),
	'tools/shoestring/pyproject.toml': re.compile(r"(?m)^version = '(?P<version>[^']+)'[ \t]*$"),
}


def _git(*args, check=True):
	return subprocess.run(['git', *args], capture_output=True, text=True, check=check)


def unmerged_paths():
	return [line for line in _git('diff', '--name-only', '--diff-filter=U').stdout.splitlines() if line]


def _stage(stage, path):
	"""Content of a merge stage: 1 = merge base, 2 = ours, 3 = theirs. None when the stage is absent."""

	result = _git('show', f':{stage}:{path}', check=False)
	return result.stdout if 0 == result.returncode else None


def _version_key(version):
	"""PEP 440 sort key, with a fallback good enough for `X.Y.Z[.postN]` when `packaging` is absent."""

	try:
		from packaging.version import Version  # pylint: disable=import-outside-toplevel

		return Version(version)
	except ImportError:
		release, _, post = version.partition('.post')
		return (tuple(int(part) for part in release.split('.') if part.isdigit()), int(post) if post.isdigit() else 0)


def _pick_version(ours, theirs):
	return ours if _version_key(ours) >= _version_key(theirs) else theirs


def _sentinelize(pattern, text):
	"""Replace the version value with the sentinel. Returns (text, version), or (None, None)."""

	matches = list(pattern.finditer(text))
	if 1 != len(matches):
		return None, None

	match = matches[0]
	start, end = match.span('version')
	return text[:start] + SENTINEL + text[end:], match.group('version')


def _merge_file(ours, base, theirs):
	"""Three-way merge of three strings. Returns the merged text, or None when it conflicts."""

	with tempfile.TemporaryDirectory() as directory:
		paths = []
		for name, content in (('ours', ours), ('base', base), ('theirs', theirs)):
			path = Path(directory) / name
			path.write_text(content, encoding='utf8')
			paths.append(str(path))

		# `git merge-file -p a b c` merges the changes that took b -> c into a and prints the result;
		# a nonzero exit status is the number of conflicts left behind.
		result = _git('merge-file', '-p', '--no-diff3', *paths, check=False)
		return result.stdout if 0 == result.returncode else None


def resolve(path, pattern):
	"""Try to resolve one conflicted file. Returns a description of the resolution, or None."""

	base, ours, theirs = (_stage(stage, path) for stage in (1, 2, 3))
	if base is None or ours is None or theirs is None:
		print(f'{path}: not a three-way content conflict (add/add or delete/modify); leaving unmerged')
		return None

	masked_ours, ours_version = _sentinelize(pattern, ours)
	masked_theirs, theirs_version = _sentinelize(pattern, theirs)
	if not ours_version or not theirs_version:
		print(f'{path}: could not locate exactly one version line on both sides; leaving unmerged')
		return None

	# The base may predate the version line; masking it is best effort.
	masked_base = _sentinelize(pattern, base)[0] or base

	merged = _merge_file(masked_ours, masked_base, masked_theirs)
	if merged is None:
		print(f'{path}: conflicts beyond the version line; leaving unmerged for manual resolution')
		return None

	if 1 != merged.count(SENTINEL):
		print(f'{path}: version line did not survive the merge uniquely; leaving unmerged')
		return None

	version = _pick_version(ours_version, theirs_version)
	Path(path).write_text(merged.replace(SENTINEL, version), encoding='utf8')
	_git('add', '--', path)

	kept = 'ours' if version == ours_version else 'upstream'
	return f'{path}: version {ours_version} (ours) + {theirs_version} (upstream) -> {version} ({kept})'


def main():
	conflicted = unmerged_paths()
	if not conflicted:
		print('no unmerged files')
		return 0

	print('unmerged files:\n  ' + '\n  '.join(conflicted))

	resolutions = []
	for path in conflicted:
		pattern = RESOLVABLE_FILES.get(path)
		if pattern is None:
			print(f'{path}: not a known mirror-layer packaging file; leaving unmerged')
			continue

		resolution = resolve(path, pattern)
		if resolution:
			resolutions.append(resolution)

	if resolutions:
		print('\nauto-resolved:\n  ' + '\n  '.join(resolutions))

	remaining = unmerged_paths()
	if remaining:
		print('\nstill unmerged:\n  ' + '\n  '.join(remaining))
		return 1

	# Consumed by mirror-sync.yml to describe the resolution in the PR body. `--git-path` resolves
	# inside the real git directory, which is not `./.git` in a worktree.
	report = Path(_git('rev-parse', '--git-path', 'NEMTUS_AUTO_RESOLUTIONS').stdout.strip())
	report.write_text('\n'.join(resolutions) + '\n', encoding='utf8')

	print('\nall conflicts auto-resolved')
	return 0


if __name__ == '__main__':
	sys.exit(main())
