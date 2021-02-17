# This file provides fast way for defininig new SDRAM modules.
# Modules defined in this files, after verifying that the settings are correct,
# should be later moved to LiteDRAM repository in a PR and removed from here.

from litedram.modules import _TechnologyTimings, _SpeedgradeTimings, DDR4Module

class MTA4ATF1G64HZ(DDR4Module):
    # geometry
    ngroupbanks = 4
    ngroups     = 2
    nbanks      = ngroups * ngroupbanks
    nrows       = 128*1024
    ncols       = 1024
    # timings
    trefi = {"1x": 64e6/8192,   "2x": (64e6/8192)/2, "4x": (64e6/8192)/4}
    trfc  = {"1x": (None, 350), "2x": (None, 260),   "4x": (None, 160)}
    technology_timings = _TechnologyTimings(tREFI=trefi, tWTR=(4, 7.5), tCCD=(4, 6.25), tRRD=(4, 7.5), tZQCS=(128, None))
    speedgrade_timings = {
        "2666": _SpeedgradeTimings(tRP=13.75, tRCD=13.75, tWR=15, tRFC=trfc, tFAW=(28, 30), tRAS=32),
    }
    speedgrade_timings["default"] = speedgrade_timings["2666"]
