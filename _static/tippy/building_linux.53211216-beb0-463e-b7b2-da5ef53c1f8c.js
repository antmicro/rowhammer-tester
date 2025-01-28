selector_to_html = {"a[href=\"rdimm_ddr5_tester.html\"]": "<h1 class=\"tippy-header\" id=\"rdimm-ddr5-tester\" style=\"margin-top: 0;\">RDIMM DDR5 Tester<a class=\"headerlink\" href=\"#rdimm-ddr5-tester\" title=\"Link to this heading\">\u00b6</a></h1><p>The RDIMM DDR5 Tester is an open source hardware test platform that enables testing and experimenting with various DDR5 RDIMMs (Registered Dual In-Line Memory Module).</p><p>The hardware is open and can be found on <a class=\"reference external\" href=\"https://github.com/antmicro/rdimm-ddr5-tester\">GitHub</a>.</p>"}
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
