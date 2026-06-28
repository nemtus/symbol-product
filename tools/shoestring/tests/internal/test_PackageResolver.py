import tempfile
from pathlib import Path
from zipfile import ZipFile

import pytest
from aiohttp import web

from shoestring.internal.PackageResolver import download_and_extract_package, resolve_package

from ..test.TestPackager import prepare_testnet_package

# pylint: disable=invalid-name

# region resolve_package

# Network configuration is resolved to NEMTUS mirror branch archives of nemtus/symbol-networks
# (see that repo's docs/contract.md): mainnet -> main, sai -> test-sai. No upstream Release API
# call and no SHA512 pin (branch archives are not byte-reproducible).


async def test_mainnet_resolution_returns_nemtus_main_branch_archive():
	# Act:
	download_descriptor = await resolve_package('mainnet')

	# Assert:
	assert {
		'name': 'configuration-package.zip',
		'url': 'https://github.com/nemtus/symbol-networks/archive/refs/heads/main.zip'
	} == download_descriptor


async def test_testnet_resolution_can_resolve_named_testnet():
	# Act:
	download_descriptor = await resolve_package('sai')

	# Assert:
	assert {
		'name': 'configuration-package.zip',
		'url': 'https://github.com/nemtus/symbol-networks/archive/refs/heads/test-sai.zip'
	} == download_descriptor


async def test_testnet_resolution_maps_legacy_upstream_alias_to_nemtus_mirror():
	# Act:
	download_descriptor = await resolve_package('https://github.com/symbol/networks/tree/sai')

	# Assert:
	assert {
		'name': 'configuration-package.zip',
		'url': 'https://github.com/nemtus/symbol-networks/archive/refs/heads/test-sai.zip'
	} == download_descriptor


async def test_resolution_passes_through_custom_url():
	# Act:
	download_descriptor = await resolve_package('https://foo.zip')

	# Assert:
	assert {
		'name': 'configuration-package.zip',
		'url': 'https://foo.zip'
	} == download_descriptor

# endregion


# region download_and_extract_package

@pytest.fixture
async def package_server(aiohttp_client):
	class MockPackageServer:
		def __init__(self):
			self.urls = []
			self.package_path = None

		def initialize_package(self, directory):
			self.package_path = prepare_testnet_package(directory, 'foobar.zip')

		async def package(self, request):
			self.urls.append(str(request.url))
			return web.FileResponse(self.package_path)

	# create a mock server
	mock_server = MockPackageServer()

	# create an app using the server
	app = web.Application()
	app.router.add_get('/package.zip', mock_server.package)
	server = await aiohttp_client(app)  # pylint: disable=redefined-outer-name

	server.mock = mock_server
	return server


async def test_can_download_and_extract(package_server):  # pylint: disable=redefined-outer-name
	# Arrange:
	with tempfile.TemporaryDirectory() as server_directory_name:
		package_server.mock.initialize_package(Path(server_directory_name))

		with tempfile.TemporaryDirectory() as output_directory_name:
			output_directory = Path(output_directory_name)

			# Act: instead of passing network name, pass full URI
			await download_and_extract_package(str(package_server.make_url('/package.zip')), output_directory)

			# Assert:
			top_level_names = sorted([path.name for path in output_directory.iterdir()])
			assert [
				'README.md',
				'configuration-package.zip',
				'mongo',
				'resources',
				'rest',
				'seed',
				'shoestring.ini'
			] == top_level_names


async def _assert_can_download_and_extract_local_package_using_file_protocol(add_files_to_archive):
	# Arrange: prepare dummy source file
	with tempfile.TemporaryDirectory() as source_directory_name:
		source_filepath = Path(source_directory_name) / 'foo.zip'
		with ZipFile(source_filepath, 'w') as archive:
			add_files_to_archive(archive)

		with tempfile.TemporaryDirectory() as output_directory_name:
			output_directory = Path(output_directory_name)

			# Act:
			await download_and_extract_package(f'file://{source_filepath}', output_directory)

			# Assert:
			temp_files = sorted(list(path.name for path in output_directory.iterdir()))
			assert ['configuration-package.zip', 'other', 'seed'] == temp_files

			# - check file contents
			with open(output_directory / 'seed' / 'index.dat', 'rb') as infile:
				file_contents = infile.read()
				assert b'abc' == file_contents

			with open(output_directory / 'other' / 'other.dat', 'rb') as infile:
				file_contents = infile.read()
				assert b'def' == file_contents


async def test_can_download_and_extract_local_package_using_file_protocol():
	# Arrange
	def add_files_to_archive(archive):
		archive.writestr(str(Path('seed') / 'index.dat'), 'abc')
		archive.writestr(str(Path('other') / 'other.dat'), 'def')

	# Act + Assert:
	await _assert_can_download_and_extract_local_package_using_file_protocol(add_files_to_archive)


async def test_can_find_seed_directory_one_level_down():
	# Arrange
	def add_files_to_archive(archive):
		archive.writestr(str(Path('foo/seed') / 'index.dat'), 'abc')
		archive.writestr(str(Path('foo/other') / 'other.dat'), 'def')

	# Act + Assert:
	await _assert_can_download_and_extract_local_package_using_file_protocol(add_files_to_archive)


async def test_cannot_find_seed_directory_multiple_levels_down():
	# Arrange
	def add_files_to_archive(archive):
		archive.writestr(str(Path('foo/bar/seed') / 'index.dat'), 'abc')
		archive.writestr(str(Path('foo/bar/other') / 'other.dat'), 'def')

	# Act + Assert:
	with pytest.raises(RuntimeError):
		await _assert_can_download_and_extract_local_package_using_file_protocol(add_files_to_archive)


# endregion
