selector_to_html = {"a[href=\"so_dimm_ddr5_tester.html\"]": "<h1 class=\"tippy-header\" id=\"so-dimm-ddr5-tester\" style=\"margin-top: 0;\">SO-DIMM DDR5 Tester<a class=\"headerlink\" href=\"#so-dimm-ddr5-tester\" title=\"Link to this heading\">\u00b6</a></h1><p>The SO-DIMM DDR5 tester is an open source hardware test platform that enables testing and experimenting with various off-the-shelf DDR5 SO-DIMM modules.\nThis board also supports testing single LPDDR5 ICs via <a class=\"reference internal\" href=\"lpddr5_test_bed.html\"><span class=\"std std-doc\">LPDDR5 Test Bed</span></a>.</p><p>The hardware is open and can be found on GitHub:\n<a class=\"reference external\" href=\"https://github.com/antmicro/sodimm-ddr5-tester\">https://github.com/antmicro/sodimm-ddr5-tester</a></p>", "a[href=\"rdimm_ddr5_tester.html\"]": "<h1 class=\"tippy-header\" id=\"rdimm-ddr5-tester\" style=\"margin-top: 0;\">RDIMM DDR5 Tester<a class=\"headerlink\" href=\"#rdimm-ddr5-tester\" title=\"Link to this heading\">\u00b6</a></h1><p>The RDIMM DDR5 Tester is an open source hardware test platform that enables testing and experimenting with various DDR5 RDIMMs (Registered Dual In-Line Memory Module).</p><p>The hardware is open and can be found on <a class=\"reference external\" href=\"https://github.com/antmicro/rdimm-ddr5-tester\">GitHub</a>.</p>", "a[href=\"#rdimm-ddr5-tester-pcie-integration\"]": "<figure class=\"align-default\" id=\"rdimm-ddr5-tester-pcie-integration\">\n<img alt=\"RDIMM DDR5 Tester PCIe integration\" src=\"_images/rdimm-ddr5-tester-pcie-integration.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 23 </span><span class=\"caption-text\"><span class=\"caption-text\">\nRDIMM DDR5 Tester connected to Intel NUC-series host PC over PCIe x8.</span><a class=\"headerlink\" href=\"#rdimm-ddr5-tester-pcie-integration\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
skip_classes = ["headerlink", "sd-stretched-link"]

window.onload = function () {
    for (const [select, tip_html] of Object.entries(selector_to_html)) {
        const links = document.querySelectorAll(`p ${select}`);
        for (const link of links) {
            if (skip_classes.some(c => link.classList.contains(c))) {
                continue;
            }

            tippy(link, {
                content: tip_html,
                allowHTML: true,
                arrow: true,
                placement: 'auto-start', maxWidth: 500, interactive: false,

            });
        };
    };
    console.log("tippy tips loaded!");
};
