# User configuration
TARGET 	    ?= arty
IP_ADDRESS  ?= 192.168.100.50
MAC_ADDRESS ?= 0x10e2d5000001
UDP_PORT    ?= 1234

# # #

# Set openFPGALoader board name
TOP := antmicro_$(TARGET)
ifeq ($(TARGET),arty)
OFL_BOARD := arty_a7_35t
TOP := digilent_arty
else ifeq ($(TARGET),ddr4_datacenter_test_board)
OFL_BOARD := antmicro_ddr4_tester
TOP := antmicro_datacenter_ddr4_test_board
else ifeq ($(TARGET),lpddr4_test_board)
OFL_BOARD := antmicro_lpddr4_tester
else ifeq ($(TARGET),lpddr5_test_board)
OFL_BOARD := antmicro_lpddr5_tester
else ifeq ($(TARGET),ddr5_tester)
OFL_BOARD := antmicro_ddr5_tester
OFL_EXTRA_ARGS := --freq 3e6
else ifeq ($(TARGET),ddr5_test_board)
OFL_BOARD := antmicro_lpddr4_tester
OFL_EXTRA_ARGS := --freq 3e6
else ifeq ($(TARGET),zcu104)
# For ZCU104 please copy the file build/zcu104/gateware/zcu104.bit to the boot partition on microSD card
TOP := xilinx_zcu104
else ifeq ($(TARGET),ddr5_tester_linux)
OFL_BOARD := antmicro_ddr5_tester
OFL_EXTRA_ARGS := --freq 3e6
TOP := antmicro_ddr5_tester
else ifeq ($(TARGET),sodimm_lpddr5_tester)
OFL_BOARD := antmicro_ddr5_tester
OFL_EXTRA_ARGS := --freq 3e6
TOP := antmicro_sodimm_ddr5_tester
else ifeq ($(TARGET),sodimm_ddr5_tester)
OFL_BOARD := antmicro_ddr5_tester
OFL_EXTRA_ARGS := --freq 3e6
TOP := antmicro_sodimm_ddr5_tester
else
$(error Unsupported board type)
endif


# Gateware args
ARGS ?=
NET_ARGS := --ip-address $(IP_ADDRESS) --mac-address $(MAC_ADDRESS) --udp-port $(UDP_PORT)
TARGET_ARGS := $(NET_ARGS) $(ARGS)
OFL_EXTRA_ARGS ?=

# Update PATH to activate the Python venv and include all required binaries
# Adding vnev/bin to PATH forces usage of the Python binary from venv,
# which is roughly equivalent to `source venv/bin/activate`
PATH := $(PWD)/venv/bin:$(PATH)
# other binaries
PATH := $(PWD)/bin:$(PATH)
PATH := $(PWD)/third_party/riscv64-unknown-elf-gcc/bin:$(PATH)
export PATH

PYTHON_FILES := $(shell find rowhammer_tester tests -name '*.py')

### Main targets ###

all:
	python rowhammer_tester/targets/$(TARGET).py $(TARGET_ARGS)

FORCE:

build: FORCE
	python rowhammer_tester/targets/$(TARGET).py --build $(TARGET_ARGS)

sim: sim-deps FORCE
	python rowhammer_tester/targets/$(TARGET).py --build --sim $(TARGET_ARGS)

sim-analyze: sim-deps FORCE
	python rowhammer_tester/scripts/sim_runner.py python rowhammer_tester/targets/$(TARGET).py --build --sim $(TARGET_ARGS)

reset_FTDI:
	openocd -f openocd_scripts/openocd_xc7_ft4232_reset.cfg

.PHONY: reset_FTDI

upload up load: FORCE
ifeq ($(TARGET),zcu104)
	@echo "For ZCU104 please copy the file build/zcu104/gateware/zcu104.bit to the boot partition on microSD card"
	@exit 1
else
	openFPGALoader --board $(OFL_BOARD) $(OFL_EXTRA_ARGS) build/$(TARGET)/gateware/$(TOP).bit
endif

flash: FORCE
ifeq ($(TARGET),zcu104)
	@echo "For ZCU104 please copy the file build/zcu104/gateware/zcu104.bit to the boot partition on microSD card"
	@exit 1
else ifeq ($(TARGET),lpddr4_test_board)
	python rowhammer_tester/targets/$(TARGET).py --flash $(TARGET_ARGS)
	# Enable Quad mode in spi flash module
	openocd -f prog/openocd_xc7_ft4232.cfg -c "init; jtagspi_init 0 prog/bscan_spi_xc7k70t.bit; jtagspi write_cmd 1 512 16 0; exit"
else
	openFPGALoader --board $(OFL_BOARD) build/$(TARGET)/gateware/$(TOP).bit --write-flash
endif

srv: FORCE
	litex_server --udp --udp-ip $(IP_ADDRESS) --udp-port $(UDP_PORT)

doc: FORCE
	$(MAKE) -C docs html

test: FORCE
	python -m unittest -v

clean::
	rm -rf build scripts/csr.csv analyzer.csv scripts/sdram_init.py

### Utils ###

# FIXME: should this be generating the files in top level directory?
protoc: FORCE
	protoc -I rowhammer_tester/payload/ --python_out . rowhammer_tester/payload/*.proto

env: venv/bin/activate
	@env bash --init-file "$(PWD)/venv/bin/activate"

# Exclude directoires that use Migen, as it doesn't play well with autoformatting
format: FORCE
	@yapf -i \
		--exclude "tests/*" \
		--exclude "rowhammer_tester/gateware/*" \
		--exclude "rowhammer_tester/targets/*" \
		$(PYTHON_FILES)

BRANCH := $(shell git rev-parse --abbrev-ref HEAD | tr '/' '_')
COMMIT := $(shell git rev-parse HEAD | head -c8)
ZIP_CONTENTS ?= $(addprefix build/$(TARGET)/,csr.csv defs.csv sdram_init.py litedram_settings.json gateware/$(TOP).bit)

.PHONY: pack
pack: $(ZIP_CONTENTS)
	zip -r "$(TARGET)-$(BRANCH)-$(COMMIT).zip" $^

### Dependencies ###

minimal-deps:: # Intentionally skipping --recursive as not needed (but doesn't break anything either)
	git submodule update --init
	(make --no-print-directory -C . \
		venv/bin/openFPGALoader \
		python-deps \
	)

deps: minimal-deps sim-deps
	(make --no-print-directory -C . \
		venv/bin/openocd \
		third_party/riscv64-unknown-elf-gcc \
	)

sim-deps: venv/bin/verilator

python-deps: venv/bin/activate  # installs python dependencies inside virtual environment
	pip install -r requirements.txt

venv/bin/activate:  # creates virtual environment if it does not exist
	python3 -m venv venv

third_party/riscv64-unknown-elf-gcc:
	@echo Downloading RISC-V toolchain
	curl -L https://static.dev.sifive.com/dev-tools/freedom-tools/v2020.08/riscv64-unknown-elf-gcc-10.1.0-2020.08.2-x86_64-linux-ubuntu14.tar.gz | tar -xzf -
	mv riscv64-unknown-elf-gcc-10.1.0-2020.08.2-x86_64-linux-ubuntu14 third_party/riscv64-unknown-elf-gcc

venv/bin/verilator: third_party/verilator/configure.ac
	cd third_party/verilator && autoconf
	cd third_party/verilator && ./configure --prefix=$(PWD)/venv
	make -C third_party/verilator -j`nproc`
	make -C third_party/verilator install

venv/bin/openFPGALoader: third_party/openFPGALoader/CMakeLists.txt
	cd third_party/openFPGALoader && cmake . -DCMAKE_INSTALL_PREFIX=$(PWD)/venv
	cd third_party/openFPGALoader && cmake --build . -j `nproc`
	cd third_party/openFPGALoader && cmake --install .

# required for flashing LPDDR4 board
venv/bin/openocd: third_party/openocd/bootstrap
	cd third_party/openocd && ./bootstrap
	cd third_party/openocd && ./configure --enable-ftdi --prefix=$(PWD)/venv
	make -C third_party/openocd -j`nproc`
	make -C third_party/openocd install
