
#!/bin/bash

set -ex

# Pick up the submodule URL from .gitmodules (the _symbol submodule fetches from the NEMTUS mirror
# nemtus/symbol; see docs/nemtus-mirror.md). `sync` makes an already-initialized clone adopt a changed
# URL instead of keeping the stale one in .git/config.
git submodule sync _symbol
git submodule update --init
git -C _symbol config core.sparseCheckout true
echo 'jenkins/*' >>.git/modules/_symbol/info/sparse-checkout
echo 'linters/*' >>.git/modules/_symbol/info/sparse-checkout
git submodule update --force --checkout _symbol
