DDRPHY
======

Register Listing for DDRPHY
---------------------------

+----------------------------------------------------------------+------------------------------------------------+
| Register                                                       | Address                                        |
+================================================================+================================================+
| :ref:`DDRPHY_RST <DDRPHY_RST>`                                 | :ref:`0xf0000800 <DDRPHY_RST>`                 |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_DLY_SEL <DDRPHY_DLY_SEL>`                         | :ref:`0xf0000804 <DDRPHY_DLY_SEL>`             |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_HALF_SYS8X_TAPS <DDRPHY_HALF_SYS8X_TAPS>`         | :ref:`0xf0000808 <DDRPHY_HALF_SYS8X_TAPS>`     |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_WLEVEL_EN <DDRPHY_WLEVEL_EN>`                     | :ref:`0xf000080c <DDRPHY_WLEVEL_EN>`           |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_WLEVEL_STROBE <DDRPHY_WLEVEL_STROBE>`             | :ref:`0xf0000810 <DDRPHY_WLEVEL_STROBE>`       |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_RDLY_DQ_RST <DDRPHY_RDLY_DQ_RST>`                 | :ref:`0xf0000814 <DDRPHY_RDLY_DQ_RST>`         |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_RDLY_DQ_INC <DDRPHY_RDLY_DQ_INC>`                 | :ref:`0xf0000818 <DDRPHY_RDLY_DQ_INC>`         |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_RDLY_DQ_BITSLIP_RST <DDRPHY_RDLY_DQ_BITSLIP_RST>` | :ref:`0xf000081c <DDRPHY_RDLY_DQ_BITSLIP_RST>` |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_RDLY_DQ_BITSLIP <DDRPHY_RDLY_DQ_BITSLIP>`         | :ref:`0xf0000820 <DDRPHY_RDLY_DQ_BITSLIP>`     |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_WDLY_DQ_BITSLIP_RST <DDRPHY_WDLY_DQ_BITSLIP_RST>` | :ref:`0xf0000824 <DDRPHY_WDLY_DQ_BITSLIP_RST>` |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_WDLY_DQ_BITSLIP <DDRPHY_WDLY_DQ_BITSLIP>`         | :ref:`0xf0000828 <DDRPHY_WDLY_DQ_BITSLIP>`     |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_RDPHASE <DDRPHY_RDPHASE>`                         | :ref:`0xf000082c <DDRPHY_RDPHASE>`             |
+----------------------------------------------------------------+------------------------------------------------+
| :ref:`DDRPHY_WRPHASE <DDRPHY_WRPHASE>`                         | :ref:`0xf0000830 <DDRPHY_WRPHASE>`             |
+----------------------------------------------------------------+------------------------------------------------+

DDRPHY_RST
^^^^^^^^^^

`Address: 0xf0000800 + 0x0 = 0xf0000800`


    .. wavedrom::
        :caption: DDRPHY_RST

        {
            "reg": [
                {"name": "rst", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_DLY_SEL
^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x4 = 0xf0000804`


    .. wavedrom::
        :caption: DDRPHY_DLY_SEL

        {
            "reg": [
                {"name": "dly_sel[1:0]", "bits": 2},
                {"bits": 30},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_HALF_SYS8X_TAPS
^^^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x8 = 0xf0000808`


    .. wavedrom::
        :caption: DDRPHY_HALF_SYS8X_TAPS

        {
            "reg": [
                {"name": "half_sys8x_taps[4:0]", "attr": 'reset: 8', "bits": 5},
                {"bits": 27},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_WLEVEL_EN
^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0xc = 0xf000080c`


    .. wavedrom::
        :caption: DDRPHY_WLEVEL_EN

        {
            "reg": [
                {"name": "wlevel_en", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_WLEVEL_STROBE
^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x10 = 0xf0000810`


    .. wavedrom::
        :caption: DDRPHY_WLEVEL_STROBE

        {
            "reg": [
                {"name": "wlevel_strobe", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_RDLY_DQ_RST
^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x14 = 0xf0000814`


    .. wavedrom::
        :caption: DDRPHY_RDLY_DQ_RST

        {
            "reg": [
                {"name": "rdly_dq_rst", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_RDLY_DQ_INC
^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x18 = 0xf0000818`


    .. wavedrom::
        :caption: DDRPHY_RDLY_DQ_INC

        {
            "reg": [
                {"name": "rdly_dq_inc", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_RDLY_DQ_BITSLIP_RST
^^^^^^^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x1c = 0xf000081c`


    .. wavedrom::
        :caption: DDRPHY_RDLY_DQ_BITSLIP_RST

        {
            "reg": [
                {"name": "rdly_dq_bitslip_rst", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_RDLY_DQ_BITSLIP
^^^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x20 = 0xf0000820`


    .. wavedrom::
        :caption: DDRPHY_RDLY_DQ_BITSLIP

        {
            "reg": [
                {"name": "rdly_dq_bitslip", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_WDLY_DQ_BITSLIP_RST
^^^^^^^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x24 = 0xf0000824`


    .. wavedrom::
        :caption: DDRPHY_WDLY_DQ_BITSLIP_RST

        {
            "reg": [
                {"name": "wdly_dq_bitslip_rst", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_WDLY_DQ_BITSLIP
^^^^^^^^^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x28 = 0xf0000828`


    .. wavedrom::
        :caption: DDRPHY_WDLY_DQ_BITSLIP

        {
            "reg": [
                {"name": "wdly_dq_bitslip", "bits": 1},
                {"bits": 31},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_RDPHASE
^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x2c = 0xf000082c`


    .. wavedrom::
        :caption: DDRPHY_RDPHASE

        {
            "reg": [
                {"name": "rdphase[1:0]", "attr": 'reset: 2', "bits": 2},
                {"bits": 30},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


DDRPHY_WRPHASE
^^^^^^^^^^^^^^

`Address: 0xf0000800 + 0x30 = 0xf0000830`


    .. wavedrom::
        :caption: DDRPHY_WRPHASE

        {
            "reg": [
                {"name": "wrphase[1:0]", "attr": 'reset: 3', "bits": 2},
                {"bits": 30},
            ], "config": {"hspace": 400, "bits": 32, "lanes": 4 }, "options": {"hspace": 400, "bits": 32, "lanes": 4}
        }


