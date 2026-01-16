selector_to_html = {"a[href=\"lpddr4_test_board.html\"]": "<h1 class=\"tippy-header\" id=\"lpddr4-test-board\" style=\"margin-top: 0;\">LPDDR4 Test Board<a class=\"headerlink\" href=\"#lpddr4-test-board\" title=\"Link to this heading\">\u00b6</a></h1><p>The LPDDR4 Test Board is a platform developed by Antmicro for testing LPDDR4 memory.\nIt uses the Xilinx Kintex-7 FPGA (XC7K70T-FBG484).</p><p>The hardware is open and can be found on GitHub (<a class=\"reference external\" href=\"https://github.com/antmicro/lpddr4-test-board\">https://github.com/antmicro/lpddr4-test-board</a>).</p>", "a[href=\"#id1\"]": "<figure class=\"align-default\" id=\"id1\">\n<img alt=\"\" src=\"_images/ddr5-test-bed-1.0.1.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 15 </span><span class=\"caption-text\"><span class=\"caption-text\">\nDDR5 Test Bed</span><a class=\"headerlink\" href=\"#id1\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
