# User configuration
TARGET 	    ?= arty
IP_ADDRESS  ?= 192.168.100.50
MAC_ADDRESS ?= 0x10e2d5000001
UDP_PORT    ?= 1234

# # #

# Gateware args
ARGS ?=
NET_ARGS := --ip-address $(IP_ADDRESS) --mac-address $(MAC_ADDRESS) --udp-port $(UDP_PORT)
TARGET_ARGS := $(NET_ARGS) $(ARGS)

# Update PATH to activate the Python venv and include all required binaries
# Adding vnev/bin to PATH forces usage of the Python binary from venv,
# which is roughly equivalent to `source venv/bin/activate`
PATH := $(PWD)/venv/bin:$(PATH)
# other binaries
PATH := $(PWD)/bin:$(PATH)
PATH := $(PWD)/third_party/verilator/image/bin:$(PATH)
export PATH

### Main targets ###

all:
	python rowhammer_tester/targets/$(TARGET).py $(TARGET_ARGS)

FORCE:

build: FORCE
	python rowhammer_tester/targets/$(TARGET).py --build $(TARGET_ARGS)

sim: FORCE
	python rowhammer_tester/targets/$(TARGET).py --build --sim $(TARGET_ARGS)

sim-analyze: FORCE
	python rowhammer_tester/scripts/sim_runner.py python rowhammer_tester/targets/$(TARGET).py --build --sim $(TARGET_ARGS)

upload up load: FORCE
ifeq ($(TARGET),zcu104)
	@echo "For ZCU104 please copy the file build/zcu104/gateware/zcu104.bit to the boot partition on microSD card"
	@exit 1
else
	python rowhammer_tester/targets/$(TARGET).py --load $(TARGET_ARGS)
endif

srv: FORCE
	litex_server --udp --udp-ip $(IP_ADDRESS) --udp-port $(UDP_PORT)

doc: FORCE
	python rowhammer_tester/targets/$(TARGET).py --docs $(TARGET_ARGS)
	python -m sphinx -b html build/documentation build/documentation/html

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

### Dependencies ###

deps:: # Intentionally skipping --recursive as not needed (but doesn't break anything either)
	git submodule update --init
	(make --no-print-directory -C . \
		third_party/verilator/image/bin/verilator \
		third_party/xc3sprog/xc3sprog \
		python-deps)

python-deps: venv/bin/activate  # installs python dependencies inside virtual environment
	pip install -r requirements.txt

venv/bin/activate:  # creates virtual environment if it does not exist
	python3 -m venv venv

third_party/verilator/image/bin/verilator: third_party/verilator/configure.ac
	(cd third_party/verilator && autoconf && \
		./configure --prefix=$(PWD)/third_party/verilator/image && \
		make -j`nproc` && make install) && touch $@

third_party/xc3sprog/xc3sprog: third_party/xc3sprog/CMakeLists.txt
	(cd third_party/xc3sprog && patch -Np1 < ../xc3sprog.patch && \
		cmake . && make -j`nproc`)
