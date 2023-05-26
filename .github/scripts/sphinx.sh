#!/usr/bin/env sh

set -e

cd $(dirname $0)/../../docs

ls -la ../third_party
ls -la ../third_party/migen

pip3 install --user -r requirements.txt

make html latex
