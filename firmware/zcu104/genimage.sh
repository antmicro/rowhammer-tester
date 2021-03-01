#!/usr/bin/env bash

set -e

if (( $# < 6 )); then
    echo "Usage: $(basename $0) image.cfg boot.bin Image system.dtb zcu104.bit BUILDROOT_OUTPUT"
    echo
    echo "Creates sd card image using genimage tool."
    echo "Specify paths to the required bootfiles and buildroot outputs as arguments."
    echo
    echo "It is asumed that genimage host tool is available at BUILDROOT_OUTPUT/host/bin"
    echo "and that rootfs image is available at BUILDROOT_OUTPUT/images/rootfs.ext4."
    exit 1
fi

image_cfg="$1"
boot_bin="$2"
kernel_img="$3"
system_dtb="$4"
bitstream="$5"
buildroot_out="$6"

HERE="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
build=$HERE/genimage-build

echo "### Cleaning build directory $build ..."
rm -rf $build
mkdir $build
mkdir $build/input $build/images $build/root $build/tmp

echo "### Copying input files to $build/input ..."
cp $boot_bin $build/input/boot.bin
cp $kernel_img $build/input/Image
cp $system_dtb $build/input/system.dtb
cp $bitstream $build/input/zcu104.bit
cp $buildroot_out/images/rootfs.ext4 $build/input/rootfs.ext4

echo "### Generating image using $image_cfg ..."
export PATH="$(realpath $buildroot_out/host/bin):$PATH"
image_cfg=$(realpath $image_cfg)
cd $build
genimage --config $image_cfg --outputpath images

echo "### Output image in $build/images"
