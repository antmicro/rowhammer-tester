# Building Linux target

The memory controllers synhesized for Rowhammer testing can be utilized as parts of a regular digital design that is capable of booting an operating system.
In such scenario the memory controller is used by the operating system for interacting with a DRAM memory.
This chapter describes a separate target configuration that has been created in order to synthesize a Linux-capable system that you can run on Antmicro's [RDIMM DDR5 Tester](rdimm_ddr5_tester.md).

## Base DDR5 Tester Linux Options

The `ddr5_tester_linux` target is configured via specifying the ``TARGET_ARGS`` variable and requires the following arguments:

|          Option          |                                                          Documentation                                                          |
|:------------------------:|:-------------------------------------------------------------------------------------------------------------------------------:|
|         `--build`        | When specified will invoke synthesis and hardware analysis tool (Vivado by default).<br /> Will produce programmable bitstream. |
|        `--l2-size`       |                                                   Specifies the L2 cache size.                                                  |
|   `--iodelay-clk-freq`   |                                                     IODELAY clock frequency.                                                    |
|        `--module`        |                                                   The DDR5 module to be used.                                                   |
| `--with-wishbone-memory` |                             VexRiscV SMP specific option.<br /> Disables native LiteDRAM interface.                             |
|  `--wishbone-force-32b`  |                         VexRiscV SMP specific option.<br /> Forces the wishbone bus to be 32 bits wide.                         |

Additionally, you can set up ``EtherBone`` or ``Ethernet`` to communicate with the system as described below.

### Ethernet Options

|         Option        |                          Documentation                         |
|:---------------------:|:--------------------------------------------------------------:|
|   `--with-ethernet`   |             Sets up Ethernet for the DDR5 Tester board.        |
| `--remote-ip-address` | The IP address of the remote machine connected to DDR5 Tester. |
|  `--local-ip-address` |                Local (DDR5 Tester's) IP address.               |

### Etherbone Options

|       Option       |               Documentation               |
|:------------------:|:-----------------------------------------:|
| `--with-etherbone` |  Sets up Ethernet for DDR5 Tester board.  |
|   `--ip-address`   |  IP address to be used for the EtherBone. |
|   `--mac-address`  | MAC address to be used for the EtherBone. |

## Building the RDIMM DDR5 Tester Linux Target

After configuring the RDIMM DDR5 Tester Linux, the target can be build with `make build`.
Below you can see a use example of a DDR5 Tester Linux Target with Ethernet configured:

```sh
make build TARGET=ddr5_tester_linux TARGET_ARGS="--build --l2-size 256 --iodelay-clk-freq 400e6 --module MTC10F1084S1RC --with-wishbone-memory --wishbone-force-32b --with-ethernet --remote-ip-address 192.168.100.100 --local-ip-address 192.168.100.50"
```

## Interacting with RDIMM DDR5 Tester Linux Target

First, load the bitstream onto the RDIMM DDR5 Tester with the help of `OpenFPGALoader`:

```bash
openFPGALoader --board antmicro_ddr5_tester build/ddr5_tester_linux/gateware/antmicro_ddr5_tester.bit --freq 3e6
```

In order to connect to the board, assign the `192.168.100.100` IP Address to the Ethernet interface that is plugged to the DDR5 Tester board and set up the device if needed, e.g. by running:

```sh
ip addr add 192.168.100.100/24 dev $ETH
ip link set dev $ETH up
```

Where ``ETH`` is the name of your Ethernet interface.
When the Ethernet interface has been set up correctly, you may access the BIOS console on the DDR5 Tester with:

```sh
picocom -b 115200 /dev/ttyUSB2
```

## Setting up a TFTP Server

Several Linux boot methods can be invoked here but booting via Ethernet is recommended.
In order to enable netboot, you need to set up a TFTP server first.

```{note}
Running a TFTP server varies between distributions in terms of TFTP implementation names and locations of the configuration file.
```

As an example, below is a quick guide on how to configure a TFTP server for Arch Linux.
Firstly, if not equipped already, get an implementation of a TFTP server, for example:

```sh
pacman -S tftp-hpa
```

The TFTP server is configured via a `/etc/conf.d/tftpd` file.
Here's a suggested configuration for the DDR5 Tester Linux boot process:

```sh
TFTP_USERNAME="tftp"
TFTPD_OPTIONS="--secure"
TFTP_DIRECTORY="/srv/tftp"
TFTP_ADDRESS="192.168.100.100:69"
```

``TFTP_ADDRESS`` is specified with the ``--remote-ip-address`` option whilst building the target and the port is the default one for the TFTP server.
The ``TFTP_DIRECTORY`` is the TFTP's root directory.

To start the TFTP service, run:

```sh
systemctl start tftpd
```

To check whether the TFTP sever is set up properly, run:

```sh
cd /srv/tftp/ && echo "TEST TFTP SERVER" > test

cd ~/ && tftp 192.168.100.100 -c get test
```

The ``test`` file should appear in the home directory with "TEST TFTP SERVER" as its content.

## Booting Linux on RDIMM DDR5 Tester Linux Target

You will need the following binaries:

* Linux kernel Image
* Compiled devicetree
* Opensbi's `fw_jump.bin`
* rootfs.cpio

All of these can be obtained with the use of provided `firmware/ddr5_tester/buildroot` buildroot external configuration.
To build binaries with buildroot, run:

```sh
git clone --single-branch -b 2023.05.x https://github.com/buildroot/buildroot.git
pushd buildroot
make BR2_EXTERNAL="$(pwd)/../firmware/ddr5_tester/buildroot" ddr5_vexriscv_defconfig
```

Then, transfer the binaries to the TFTP root directory:

```sh
mv buildroot/output/images/* /srv/tftp/
mv /srv/tftp/fw_jump.bin /srv/tftp/opensbi.bin
```

The address map of the binaries alongside boot arguments can be contained within the `boot.json` file, for example:

```json
{
    "/srv/tftp/Image":        "0x40000000",
    "/srv/tftp/rv32.dtb":     "0x40ef0000",
    "/srv/tftp/rootfs.cpio":  "0x42000000",
    "/srv/tftp/opensbi.bin":  "0x40f00000",
    "bootargs": {
        "r1":   "0x00000000",
        "r2":   "0x40ef0000",
        "r3":   "0x00000000",
        "addr": "0x40f00000"
    }
```

With Linux boot binaries in the TFTP's root directory with `boot.json`, netboot can be invoked from the BIOS console with:

```sh
netboot /srv/tftp/boot.json
```

Upon successful execution a similar log will be printed:

```
litex> netboot /srv/tftp/boot.json
Booting from network...
Local IP: 192.168.100.50
Remote IP: 192.168.100.100
Booting from /srv/tftp/boot.json (JSON)...
Copying /srv/tftp/Image to 0x40000000... (7395804 bytes)
Copying /srv/tftp/rv32.dtb to 0x40ef0000... (2463 bytes)
Copying /srv/tftp/rootfs.cpio to 0x42000000... (22128128 bytes)
Copying /srv/tftp/opensbi.bin to 0x40f00000... (1007056 bytes)
Executing booted program at 0x40f00000

--============= Liftoff! ===============--
```

Then, the OpenSBI and Linux boot log should follow:

```
OpenSBI v1.3-24-g84c6dc1
   ____                    _____ ____ _____
  / __ \                  / ____|  _ \_   _|
 | |  | |_ __   ___ _ __ | (___ | |_) || |
 | |  | | '_ \ / _ \ '_ \ \___ \|  _ < | |
 | |__| | |_) |  __/ | | |____) | |_) || |_
  \____/| .__/ \___|_| |_|_____/|____/_____|
        | |
        |_|

Platform Name             : LiteX / VexRiscv-SMP
Platform Features         : medeleg
Platform HART Count       : 8
Platform IPI Device       : aclint-mswi
Platform Timer Device     : aclint-mtimer @ 100000000Hz
Platform Console Device   : litex_uart
(...)
[    0.000000] Linux version 5.11.0 (riscv32-buildroot-linux-gnu-gcc.br_real (Buildroot 2023.05.2-154-g787a633711) 11.4.0, GNU ld (GNU Binutils) 2.38) #2 SMP Mon Sep 25 10:52:22 CEST 2023
[    0.000000] earlycon: sbi0 at I/O port 0x0 (options '')
[    0.000000] printk: bootconsole [sbi0] enabled
(...)
```

And then:

```
Welcome to Buildroot
buildroot login: root
             _     _
            | |   (_)
            | |    _ _ __  _   ___  __
            | |   | | '_ \| | | \ \/ /
            | |___| | | | | |_| |>  <
            \_____/_|_| |_|\__,_/_/\_\
                      _ _   _
                     (_) | | |
            __      ___| |_| |__
            \ \ /\ / / | __| '_ \
             \ V  V /| | |_| | | |
              \_/\_/ |_|\__|_| |_|
            __________________ _____
            |  _  \  _  \ ___ \  ___|
            | | | | | | | |_/ /___ \
            | | | | | | |    /    \ \
            | |/ /| |/ /| |\ \/\__/ /
            |___/ |___/ \_| \_\____/

  32-bit RISC-V Linux running on DDR5 Tester.

login[65]: root login on 'console'
```
