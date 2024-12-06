selector_to_html = {"a[href=\"references.html#lpddr4-test-board-prog-b1\"]": "<img alt=\"_images/PROG_B12.png\" id=\"lpddr4-test-board-prog-b1\" src=\"_images/PROG_B12.png\"/>", "a[href=\"references.html#lpddr4-test-board-j6\"]": "<img alt=\"_images/J62.png\" id=\"lpddr4-test-board-j6\" src=\"_images/J62.png\"/>", "a[href=\"references.html#lpddr4-test-board-mode1\"]": "<img alt=\"_images/MODE11.png\" id=\"lpddr4-test-board-mode1\" src=\"_images/MODE11.png\"/>", "a[href=\"references.html#lpddr4-test-board-s1\"]": "<img alt=\"_images/S12.png\" id=\"lpddr4-test-board-s1\" src=\"_images/S12.png\"/>", "a[href=\"references.html#lpddr4-test-board-j1\"]": "<img alt=\"_images/J11.png\" id=\"lpddr4-test-board-j1\" src=\"_images/J11.png\"/>", "a[href=\"#id1\"]": "<figure class=\"align-default\" id=\"id1\">\n<img alt=\"LPDDR4 Test Board with DDR5 Testbed\" src=\"_images/lpddr4-test-board.jpg\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 5 </span><span class=\"caption-text\"><span class=\"caption-text\">\nLPDDR4 Test Board with DDR5 Testbed</span><a class=\"headerlink\" href=\"#id1\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"references.html#lpddr4-test-board-j5\"]": "<img alt=\"_images/J52.png\" id=\"lpddr4-test-board-j5\" src=\"_images/J52.png\"/>", "a[href=\"references.html#lpddr4-test-board-j4\"]": "<img alt=\"_images/J41.png\" id=\"lpddr4-test-board-j4\" src=\"_images/J41.png\"/>"}
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
