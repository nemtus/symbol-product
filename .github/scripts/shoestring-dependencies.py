#!/usr/bin/env python3
"""Keep the published nemtus-symbol-shoestring dependencies in step with requirements.txt.

Upstream symbol/product leaves `[tool.poetry.dependencies]` in `tools/shoestring/pyproject.toml` with only
the `python` constraint and fills it from `requirements.txt` at release time (Jenkins `publish.groovy`
runs `poetry add <line>` for each requirement). `requirements.txt` is therefore the single source of truth,
and upstream sync PRs / Dependabot bump only that file. This script reproduces the same step for
`publish-shoestring.yaml`:

  inject           rewrite the dependencies table of pyproject.toml from requirements.txt
                   (run on the CI checkout right before `python -m build`; never committed)
  verify <wheel>   fail unless the wheel's Requires-Dist names exactly the requirements.txt packages

Both subcommands take `--project-dir` (default: tools/shoestring).
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

DEPENDENCIES_HEADER = '[tool.poetry.dependencies]'
REQUIREMENT_PATTERN = re.compile(r'^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<spec>(?:~=|==|>=|<=|!=|<|>)\s*\S.*)$')


def normalize_name(name):
	return re.sub(r'[-_.]+', '-', name).lower()


def read_requirements(project_dir):
	requirements = []
	for raw_line in (project_dir / 'requirements.txt').read_text(encoding='utf8').splitlines():
		line = raw_line.split('#', 1)[0].strip()
		if not line:
			continue

		match = REQUIREMENT_PATTERN.match(line)
		if not match:
			raise ValueError(f'unsupported requirements.txt line: {raw_line!r}')

		requirements.append((match.group('name'), re.sub(r'\s+', '', match.group('spec'))))

	if not requirements:
		raise ValueError('requirements.txt has no requirements')

	return requirements


def inject(project_dir):
	pyproject_path = project_dir / 'pyproject.toml'
	lines = pyproject_path.read_text(encoding='utf8').splitlines()

	try:
		start = lines.index(DEPENDENCIES_HEADER) + 1
	except ValueError as error:
		raise ValueError(f'{pyproject_path} has no {DEPENDENCIES_HEADER} table') from error

	end = start
	while end < len(lines) and not lines[end].startswith('['):
		end += 1

	# keep only the python constraint (as upstream does), then append one entry per requirement
	python_lines = [line for line in lines[start:end] if re.match(r'^python\s*=', line)]
	if len(python_lines) != 1:
		raise ValueError(f'{DEPENDENCIES_HEADER} must contain exactly one python constraint')

	dependency_lines = [f'{name} = "{spec}"' for name, spec in read_requirements(project_dir)]
	lines[start:end] = python_lines + dependency_lines + ['']

	pyproject_path.write_text('\n'.join(lines) + '\n', encoding='utf8')
	print('\n'.join([DEPENDENCIES_HEADER] + python_lines + dependency_lines))


def verify(project_dir, wheel_path):
	with zipfile.ZipFile(wheel_path) as wheel:
		metadata_name = next(name for name in wheel.namelist() if name.endswith('.dist-info/METADATA'))
		metadata = wheel.read(metadata_name).decode('utf8')

	requires_dist = [line.split(':', 1)[1].strip() for line in metadata.splitlines() if line.startswith('Requires-Dist:')]
	published = {normalize_name(re.split(r'[\s;(<>=!~\[]', entry, maxsplit=1)[0]) for entry in requires_dist}
	expected = {normalize_name(name) for name, _ in read_requirements(project_dir)}

	print(f'{Path(wheel_path).name} Requires-Dist:')
	for entry in requires_dist:
		print(f'  {entry}')

	if published != expected:
		missing = sorted(expected - published)
		extra = sorted(published - expected)
		raise ValueError(f'Requires-Dist does not match requirements.txt (missing: {missing}, unexpected: {extra})')


def main():
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument('--project-dir', type=Path, default=Path('tools/shoestring'))
	subparsers = parser.add_subparsers(dest='command', required=True)
	subparsers.add_parser('inject')
	verify_parser = subparsers.add_parser('verify')
	verify_parser.add_argument('wheel', type=Path)
	args = parser.parse_args()

	try:
		if 'inject' == args.command:
			inject(args.project_dir)
		else:
			verify(args.project_dir, args.wheel)
	except ValueError as error:
		sys.exit(f'error: {error}')


if '__main__' == __name__:
	main()
