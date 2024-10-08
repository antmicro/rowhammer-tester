selector_to_html = {"a[href=\"references.html#data-center-dram-tester-prog-b1\"]": "<img alt=\"_images/PROG_B1.png\" id=\"data-center-dram-tester-prog-b1\" src=\"_images/PROG_B1.png\"/>", "a[href=\"references.html#data-center-dram-tester-d8\"]": "<img alt=\"_images/D8.png\" id=\"data-center-dram-tester-d8\" src=\"_images/D8.png\"/>", "a[href=\"references.html#data-center-dram-tester-d6\"]": "<img alt=\"_images/D6.png\" id=\"data-center-dram-tester-d6\" src=\"_images/D6.png\"/>", "a[href=\"references.html#data-center-dram-tester-s2\"]": "<img alt=\"_images/S2.png\" id=\"data-center-dram-tester-s2\" src=\"_images/S2.png\"/>", "a[href=\"references.html#data-center-dram-tester-d5\"]": "<img alt=\"_images/D5.png\" id=\"data-center-dram-tester-d5\" src=\"_images/D5.png\"/>", "a[href=\"references.html#data-center-dram-tester-d9\"]": "<img alt=\"_images/D9.png\" id=\"data-center-dram-tester-d9\" src=\"_images/D9.png\"/>", "a[href=\"references.html#data-center-dram-tester-d10\"]": "<img alt=\"_images/D10.png\" id=\"data-center-dram-tester-d10\" src=\"_images/D10.png\"/>", "a[href=\"references.html#data-center-dram-tester-j6\"]": "<img alt=\"_images/J6.png\" id=\"data-center-dram-tester-j6\" src=\"_images/J6.png\"/>", "a[href=\"#id1\"]": "<figure class=\"align-default\" id=\"id1\">\n<img alt=\"\" src=\"_images/data-center-rdimm-ddr4-tester-descriptions.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 4 </span><span class=\"caption-text\"><span class=\"caption-text\">\nDDR4 data center dram tester interface map</span><a class=\"headerlink\" href=\"#id1\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"references.html#data-center-dram-tester-j9\"]": "<img alt=\"_images/J9.png\" id=\"data-center-dram-tester-j9\" src=\"_images/J9.png\"/>", "a[href=\"references.html#data-center-dram-tester-j3\"]": "<img alt=\"_images/J3.png\" id=\"data-center-dram-tester-j3\" src=\"_images/J3.png\"/>", "a[href=\"references.html#data-center-dram-tester-d17\"]": "<img alt=\"_images/D17.png\" id=\"data-center-dram-tester-d17\" src=\"_images/D17.png\"/>", "a[href=\"references.html#data-center-dram-tester-j7\"]": "<img alt=\"_images/J7.png\" id=\"data-center-dram-tester-j7\" src=\"_images/J7.png\"/>", "a[href=\"references.html#data-center-dram-tester-d7\"]": "<img alt=\"_images/D7.png\" id=\"data-center-dram-tester-d7\" src=\"_images/D7.png\"/>", "a[href=\"references.html#data-center-dram-tester-d1\"]": "<img alt=\"_images/D1.png\" id=\"data-center-dram-tester-d1\" src=\"_images/D1.png\"/>", "a[href=\"references.html#data-center-dram-tester-j8\"]": "<img alt=\"_images/J8.png\" id=\"data-center-dram-tester-j8\" src=\"_images/J8.png\"/>", "a[href=\"references.html#data-center-dram-tester-d15\"]": "<img alt=\"_images/D15.png\" id=\"data-center-dram-tester-d15\" src=\"_images/D15.png\"/>", "a[href=\"references.html#data-center-dram-tester-s1\"]": "<img alt=\"_images/S1.png\" id=\"data-center-dram-tester-s1\" src=\"_images/S1.png\"/>", "a[href=\"references.html#data-center-dram-tester-j2\"]": "<img alt=\"_images/J2.png\" id=\"data-center-dram-tester-j2\" src=\"_images/J2.png\"/>", "a[href=\"references.html#data-center-dram-tester-s3\"]": "<img alt=\"_images/S3.png\" id=\"data-center-dram-tester-s3\" src=\"_images/S3.png\"/>", "a[href=\"references.html#data-center-dram-tester-j5\"]": "<img alt=\"_images/J5.png\" id=\"data-center-dram-tester-j5\" src=\"_images/J5.png\"/>", "a[href=\"references.html#data-center-dram-tester-pwr1\"]": "<img alt=\"_images/PWR1.png\" id=\"data-center-dram-tester-pwr1\" src=\"_images/PWR1.png\"/>", "a[href=\"references.html#data-center-dram-tester-u14\"]": "<img alt=\"_images/U14.png\" id=\"data-center-dram-tester-u14\" src=\"_images/U14.png\"/>"}
skip_classes = ["headerlink", "sd-stretched-link"]

window.onload = function () {
    for (const [select, tip_html] of Object.entries(selector_to_html)) {
        const links = document.querySelectorAll(` ${select}`);
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
