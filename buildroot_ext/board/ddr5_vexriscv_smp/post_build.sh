#!/bin/bash
set -euo pipefail

cd "$1"

# Automatic root shell without login prompt
sed -i 's:/sbin/getty.*:-/bin/sh:' etc/inittab
# Remove the now misleading comment about getty
sed -i '/getty/d' etc/inittab
