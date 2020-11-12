# User configuration
TARGET 	    ?= arty
IP_ADDRESS  ?= 192.168.100.50
MAC_ADDRESS ?= 0x10e2d5000001
UDP_PORT    ?= 1234

# # #

# Gateware args
ARGS := --ip-address $(IP_ADDRESS) --mac-address $(MAC_ADDRESS) --udp-port $(UDP_PORT)

# Update PATH to activate the Python venv and include all required binaries
PATH := $(PWD)/venv/bin:$(PATH)
PATH := $(PWD)/bin:$(PATH)
PATH := $(PWD)/third_party/verilator/image/bin:$(PATH)
export PATH

all:
	python rowhammer_tester/targets/$(TARGET).py $(ARGS)

FORCE:

build: FORCE
	python rowhammer_tester/targets/$(TARGET).py --build $(ARGS)

sim: FORCE
	python rowhammer_tester/targets/$(TARGET).py --build --sim $(ARGS)

sim-analyze: FORCE
	python rowhammer_tester/scripts/sim_runner.py python rowhammer_tester/targets/$(TARGET).py --build --sim $(ARGS)

upload up: FORCE
	./third_party/xc3sprog/xc3sprog -c nexys4 build/$(TARGET)/gateware/$(TARGET).bit

srv: FORCE
	litex_server --udp --udp-ip $(IP_ADDRESS) --udp-port $(UDP_PORT)

doc: FORCE
	python rowhammer_tester/targets/$(TARGET).py --docs $(ARGS)
	python -m sphinx -b html build/documentation build/documentation/html

clean::
	rm -rf build scripts/csr.csv analyzer.csv scripts/sdram_init.py

# Deps
deps:: # Intentionally skipping --recursive as not needed (but doesn't break anything either)
	git submodule update --init
	(make --no-print-directory -C . \
		third_party/verilator/image/bin/verilator \
		third_party/xc3sprog/xc3sprog \
		python-deps)

python-deps: venv/bin/activate
	pip install -r requirements.txt

venv/bin/activate:
	python3 -m venv venv

third_party/verilator/image/bin/verilator: third_party/verilator/configure.ac
	(cd third_party/verilator && autoconf && \
		./configure --prefix=$(PWD)/third_party/verilator/image && \
		make -j`nproc` && make install) && touch $@

third_party/xc3sprog/xc3sprog: third_party/xc3sprog/CMakeLists.txt
	(cd third_party/xc3sprog && patch -Np1 < ../xc3sprog.patch && \
		cmake . && make -j`nproc`)

env: venv/bin/activate
	@env bash --init-file "$(PWD)/venv/bin/activate"

# FIXME: should be called from top level or tests subdirectory
test: FORCE
	python -m unittest -v

# FIXME: should this be generating the files in top level directory?
protoc: FORCE
	protoc -I scripts/ --python_out . scripts/*.proto
