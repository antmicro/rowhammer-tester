#!/usr/bin/env python3

import sys
import argparse

from litex import RemoteClient
from litescope import LiteScopeAnalyzerDriver

parser = argparse.ArgumentParser()
#parser.add_argument("--ibus_stb",  action="store_true", help="Trigger on IBus Stb rising edge.")
#parser.add_argument("--ibus_adr",  default=0x00000000,  help="Trigger on IBus Adr value.")
parser.add_argument("--offset",    default=128,         help="Capture Offset.")
parser.add_argument("--length",    default=512,         help="Capture Length.")
args = parser.parse_args()

wb = RemoteClient()
wb.open()

# # #

analyzer = LiteScopeAnalyzerDriver(wb.regs, "analyzer", debug=True)
analyzer.configure_group(0)
#analyzer.add_rising_edge_trigger("simsoc_cpu_ibus_stb")
#analyzer.configure_trigger(cond={"simsoc_cpu_ibus_adr": int(args.ibus_adr, 0)})
#analyzer.configure_trigger(cond={})
analyzer.configure_trigger(cond={"basesoc_etherbone_liteethetherbonewishbonemaster_bus_adr":'0b10000000000'})
analyzer.run(offset=int(args.offset), length=int(args.length))

analyzer.wait_done()
analyzer.upload()
analyzer.save("dump.vcd")

# # #

wb.close()
