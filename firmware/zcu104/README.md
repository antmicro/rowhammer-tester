# ZCU104 boot image preparation

On ZCU104 board the Ethernet PHY is connected to PS (processing system) instead of PL (programmable logic).
For this reason it is necessary to route the Ethernet/EtherBone traffic through PC<->PS<->PL.
To do this a simple EtherBone server has been implemented (source code can be found in the `firmware/zcu104/etherbone/` directory).

## Board configuration

To make the ZCU104 boot from SD card it is neccessary to ensure proper switches configuration.
The mode switch (SW6) consisting of 4 switches is located near the FMC LPC Connector (J5)
(the same side of the board as USB, HDMI, Ethernet). For a depiction check "ZCU104 Evaluation Board User Guide (UG1267)".
To use SD card configure the switches as follows:

1. ON
2. OFF
3. OFF
4. OFF

## ZCU104 microUSB

ZCU104 has a microUSB port connected to FTDI chip. It provides 4 channels, these are connected as follows

* Channel A is configured to support the JTAG chain.
* Channel B implements UART0 MIO18/19 connections.
* Channel C implements UART1 MIO20/21 connections.
* Channel D implements UART2 PL-side bank 28 4-wire interface.

In general they should show up as subsequent `/dev/ttyUSBx` devices (0-3 if no other were present).
Channel B is used as Linux console if there is a need to login to PS Linux system (user: root).

## Preparing SD card

Please use the pre-built SD card image `zcu104.img`. It has to be loaded to a microSD card.
To load it to the SD card, insert the card into your PC card slot and find the device name.
For example it can show up as `/dev/sdb` (`lsblk` command can be useful to check the name).
Make sure to unmount all partitions on the card (e.g. `sudo umount /dev/sdb1`).

> **IMPORTANT:** make sure that you selected proper device name or you may damage your system!

To load the image use (with correct device name):
```
sudo dd status=progress oflag=sync bs=4M if=zcu104.img of=/dev/sdb
```

Now the microSD card should be ready to use.

## Loading bitstream

Instead of loading bitstream through the JTAG interface, it must be copied to the microSD card BOOT partition (FAT32).
The bitstream will be loaded by the bootloader during system startup.
First build the bitstream, then copy the bitstream file `build/zcu104/gateware/zcu104.bit` to the FAT32 partition on the SD card.
Make sure it is named `zcu104.bit`.

## Building SD card image from sources

The SD card image consists of boot partiotion and rootfs.
Currently only rootfs is built using buildroot. The boot partition contents has to be built manually.

> In the future buildroot configuration should be revised to build all the required software. Initial configuration has been included but it is still WIP and does not boot.

### Bootloaders & kernel

Currently we are using Xilinx FSBL, but it should be possible to use U-Boot SPL ([link1](https://lucaceresoli.net/zynqmp-uboot-spl-pmufw-cfg-load/), [link2](http://buildroot-busybox.2317881.n4.nabble.com/Zynqmp-ZCU-102-Xilinx-td239716.html)).

FSBL and PMU Firmware can be built following the instuctions:

* https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842462/Build+PMU+Firmware
* https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841798/Build+FSBL

Build the rest of the required components:

* ARM trusted firmware: (https://github.com/Xilinx/arm-trusted-firmware.git) e6eea88b14aaf456c49f9c7e6747584224648cb9 (tag: xlnx_rebase_v2.2)
* U-Boot: (https://github.com/Xilinx/u-boot-xlnx.git) d8fc4b3b70bccf1577dab69f6ddfd4ada9a93bac (tag: xilinx-v2018.3)
* Linux kernel: (https://github.com/Xilinx/linux-xlnx.git) 22b71b41620dac13c69267d2b7898ebfb14c954e (tag: xlnx_rebase_v5.4_2020.1)

> NOTE: It may be required to apply the patches from `firmware/zcu104/buildroot/board/zynqmp/patches` when building U-Boot/Linux.

When building U-Boot make sure to update its configuration (`u-boot-xlnx/.config`) with the following options:
```
CONFIG_USE_BOOTARGS=y
CONFIG_BOOTARGS="earlycon clk_ignore_unused console=ttyPS0,115200 root=/dev/mmcblk0p2 rootwait rw earlyprintk rootfstype=ext4"
CONFIG_USE_BOOTCOMMAND=y
CONFIG_BOOTCOMMAND="load mmc 0:1 0x2000000 zcu104.bit; fpga load 0 0x2000000 $filesize; load mmc 0:1 0x2000000 system.dtb; load mmc 0:1 0x3000000 Image; booti 0x3000000 - 0x2000000"
```

These configure U-Boot to load the bitstream from SD card and then start the system. Unfolding `CONFIG_BOOTCOMMAND` we can see:
```
load mmc 0:1 0x2000000 zcu104.bit
fpga load 0 0x2000000 $filesize
load mmc 0:1 0x2000000 system.dtb
load mmc 0:1 0x3000000 Image
booti 0x3000000 - 0x2000000
```

Example of building ARM Trusted firmware:
```
make distclean
make -j`nproc` PLAT=zynqmp RESET_TO_BL31=1
```

Example of building U-Boot:
```
make -j`nproc` distclean
make xilinx_zynqmp_zcu104_revC_defconfig
# now modify .config directly or using `make menuconfig` as described earlier
make -j`nproc`
```

Example of building Linux:
```
make -j`nproc` ARCH=arm64 distclean
make ARCH=arm64 xilinx_zynqmp_defconfig
# optional `make menuconfig`
make -j`nproc` ARCH=arm64 dtbs
make -j`nproc` ARCH=arm64
```

Then download [zynq-mkbootimage](https://github.com/antmicro/zynq-mkbootimage) and prepare the following `boot.bif` file:
```
image:
{
    [fsbl_config] a53_x64
    [bootloader] fsbl.elf
    [pmufw_image] pmufw.elf
    [, destination_cpu=a53-0, exception_level=el-2] bl31.elf
    [, destination_cpu=a53-0, exception_level=el-2] u-boot.elf
}
```
Make sure that the files are in current directory (e.g. as symlinks) or specify full paths in `boot.bif`.

Finally use `mkbootimage --zynqmp boot.bif boot.bin` to create the `boot.bin` file.

### Root filesystem

Download buildroot
```
git clone git://git.buildroot.net/buildroot
git checkout 2020.08.2
```

Then prepare configuration using external sources and build everything:
```
make BR2_EXTERNAL=/PATH/TO/REPO/litex-rowhammer-tester/firmware/zcu104/buildroot zynqmp_zcu104_defconfig
make -j`nproc`
```

### Flashing SD card

Use [fdisk](https://wiki.archlinux.org/index.php/Fdisk) or other tool to partition the SD card. Recommended partitioning scheme:

* Partition 1, FAT32, 128M
* Partition 2, ext4, 128M

Then create the filesystems:
```
sudo mkfs.fat -F 32 -n BOOT /dev/OUR_SD_CARD_PARTITION_1
sudo mkfs.ext4 -L rootfs /dev/OUR_SD_CARD_PARTITION_2
```

Write the rootfs:
```
sudo dd status=progress oflag=sync bs=4M if=/PATH/TO/BUILDROOT/output/images/rootfs.ext4 of=/dev/OUR_SD_CARD_PARTITION_2
```

Mount the boot partition and copy the boot files and kernel image created earlier and a ZCU104 bitstream:
```
cp boot.bin /MOUNT/POINT/BOOT/
cp /PATH/TO/litex-rowhammer-tester/build/zcu104/gateware/zcu104.bit /MOUNT/POINT/BOOT/
cp /PATH/TO/linux-xlnx/arch/arm64/boot/Image /MOUNT/POINT/BOOT/
cp /PATH/TO/linux-xlnx/arch/arm64/boot/dts/xilinx/zynqmp-zcu104-revA.dtb /MOUNT/POINT/BOOT/system.dtb
```
Note: make sure to name the device tree blob `system.dtb` for the U-Boot to find (as shown in above commands).
