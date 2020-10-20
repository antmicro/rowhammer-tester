# FIXME: Default path of Vivado toolchain
VIVADO ?= /eda/xilinx/Vivado/2019.2/settings64.sh

PYTHONPATH = $(PWD)/migen:$(PWD)/litex:$(PWD)/liteeth:$(PWD)/liteiclink:$(PWD)/litescope:$(PWD)/litedram
export PYTHONPATH

all::
	$(WRAPPER) python3 arty.py \
		--cpu-type None \
		--no-timer --no-ctrl --no-uart \
		\
			--integrated-rom-size 0 \
			--integrated-sram-size 0 \
			--integrated-main-ram-size 0 \
		\
		--no-compile-software \
		--no-compile-gateware \
		--csr-csv csr.csv \
		\
		--ddrphy \
		--etherbone \
		--leds \
		--bulk \
		\
		$(ARGS)

FORCE:

build: FORCE
	( .  $(VIVADO) ; make --no-print-directory -C . ARGS="--build" all )

sim: FORCE
	( PATH="$(PWD)/verilator/image/bin:$(PWD)/bin:$$PATH" \
			make --no-print-directory -C . ARGS="--build --sim $(ARGS)" all )

sim-analyze: FORCE
	( PATH="$(PWD)/verilator/image/bin:$(PWD)/bin:$$PATH" \
			make --no-print-directory -C . WRAPPER="python3 sim_runner.py" ARGS="--build --sim $(ARGS)" all )

upload up:
	./xc3sprog/xc3sprog -c nexys4 build/arty/gateware/arty.bit

srv:
	./litex/litex/tools/litex_server.py --udp --udp-ip=192.168.100.50

#srv-uart:
#	./litex/litex/tools/litex_server.py --uart --uart-port=/dev/ttyUSB2

dump_regs:
	sleep 0.2 && python3 dump_regs.py &
	make --no-print-directory -C . srv || true

read_level:
	sleep 0.2 && python3 read_level.py &
	make --no-print-directory -C . srv || true

analyzer:
	python3 analyzer.py

leds:
	sleep 0.2 && python3 leds.py &
	make --no-print-directory -C . srv || true

mem:
	sleep 0.2 && python3 mem.py &
	make --no-print-directory -C . srv || true

bulk:
	sleep 0.2 && python3 bulk.py &
	make --no-print-directory -C . srv || true

clean::
	rm -rf build csr.csv analyzer.csv sdram_init.py

# Deps
deps:: # Intentionally skipping --recursive as not needed (but doesn't break anything either)
	git submodule update --init
	pip3 install --user pythondata-misc-tapcfg
	(make --no-print-directory -C . \
		verilator/image/bin/verilator \
		xc3sprog/xc3sprog)

verilator/image/bin/verilator: verilator/configure.ac
	(cd verilator && autoconf && \
		./configure --prefix=$(PWD)/verilator/image && \
		make -j`nproc` && make install) && touch $@

xc3sprog/xc3sprog: xc3sprog/CMakeLists.txt
	(cd xc3sprog && patch -Np1 < ../xc3sprog.patch && \
		cmake . && make -j`nproc`)
