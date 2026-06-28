import shutil
from zipfile import ZipFile

from .FileDownloader import download_file

# Network configuration is served by the NEMTUS mirror as branch archives of
# nemtus/symbol-networks (see that repo's docs/contract.md). This keeps shoestring
# independent of upstream (symbol/symbol, symbol/networks, symbol.tools) at runtime.
NEMTUS_NETWORKS_ARCHIVE_URL = 'https://github.com/nemtus/symbol-networks/archive/refs/heads/{branch}.zip'

# maps a named network to its nemtus/symbol-networks branch
NETWORK_BRANCHES = {
	'mainnet': 'main',
	'sai': 'test-sai',
}


def _resolve_url(package_identifier):
	if package_identifier in NETWORK_BRANCHES:
		return NEMTUS_NETWORKS_ARCHIVE_URL.format(branch=NETWORK_BRANCHES[package_identifier])

	# accept the legacy upstream testnet alias and map it to the NEMTUS mirror
	if 'https://github.com/symbol/networks/tree/sai' == package_identifier:
		return NEMTUS_NETWORKS_ARCHIVE_URL.format(branch='test-sai')

	# otherwise treat the identifier as a direct URL or file path
	return package_identifier


async def resolve_package(package_identifier):
	"""Resolves a package identifier into an object specifying download instructions."""

	return {
		'name': 'configuration-package.zip',
		'url': _resolve_url(package_identifier)
	}


def _move_to_parent(destination_directory):
	# github generated zips have additional subdirectory on top-level
	# if it's zipfile like that, just move all the files up

	seed_directory = destination_directory / 'seed'
	if seed_directory.exists():
		return

	# find dir that contains extracted package
	for subdir in destination_directory.glob('*'):
		if not subdir.is_dir():
			continue

		seed_directory = subdir / 'seed'
		if not seed_directory.is_dir():
			continue

		for file in subdir.glob('*'):
			shutil.move(str(file), str(destination_directory))

		subdir.rmdir()

		break
	else:
		raise RuntimeError('could not find package candidate directory')


async def download_and_extract_package(package_identifier, destination_directory):
	"""Downloads and extracts configuration package."""

	download_descriptor = await resolve_package(package_identifier)
	await download_file(download_descriptor, destination_directory)

	# extract all to temp directory
	with ZipFile(destination_directory / 'configuration-package.zip') as package:
		package.extractall(destination_directory)

	_move_to_parent(destination_directory)
