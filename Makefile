PYTHONPATH = $(PWD)/migen:$(PWD)/litex:$(PWD)/liteeth:$(PWD)/liteiclink:$(PWD)/litescope:$(PWD)/litedram
export PYTHONPATH

all::
	python3 arty.py \
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
		\
		$(ARGS)

FORCE:

build: FORCE
	( . /eda/xilinx/Vivado/2019.2/settings64.sh ; \
			make --no-print-directory -C . ARGS="--build" all )

sim: FORCE
	( PATH="$(PWD)/verilator/image/bin:$(PWD)/bin:$$PATH" \
			make --no-print-directory -C . ARGS="--build --sim" all )

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

clean::
	rm -rf build csr.csv analyzer.csv sdram_init.py
