selector_to_html = {"a[href=\"#id1\"]": "<figure class=\"align-default\" id=\"id1\">\n<img alt=\"\" src=\"_images/lpddr5-test-bed-1.0.0.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 16 </span><span class=\"caption-text\"><span class=\"caption-text\">\nLPDDR5 Test Bed</span><a class=\"headerlink\" href=\"#id1\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"so_dimm_ddr5_tester.html\"]": "<h1 class=\"tippy-header\" id=\"so-dimm-ddr5-tester\" style=\"margin-top: 0;\">SO-DIMM DDR5 Tester<a class=\"headerlink\" href=\"#so-dimm-ddr5-tester\" title=\"Link to this heading\">\u00b6</a></h1><p>The SO-DIMM DDR5 tester is an open source hardware test platform that enables testing and experimenting with various off-the-shelf DDR5 SO-DIMM modules.\nThis board also supports testing single LPDDR5 ICs via <a class=\"reference internal\" href=\"lpddr5_test_bed.html\"><span class=\"std std-doc\">LPDDR5 Test Bed</span></a>.</p><p>The hardware is open and can be found on GitHub:\n<a class=\"reference external\" href=\"https://github.com/antmicro/sodimm-ddr5-tester\">https://github.com/antmicro/sodimm-ddr5-tester</a></p>"}
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
