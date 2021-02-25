#!/usr/bin/env bash

mkdir "$TARGET_DIR/boot"
echo "/dev/mmcblk0p1 /boot            vfat    rw              0       2" >> "$TARGET_DIR/etc/fstab"
