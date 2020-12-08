# ZCU104 boot image preparation

On ZCU104 board the Ethernet PHY is connected to PS (processing system) instead of PL (programmable logic).
For this reason it is necessary to route the Ethernet/EtherBone traffic through PC<->PS<->PL.
To do this a simple EtherBone server has been implemented (source code can be found in the `etherbone/` directory).

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
