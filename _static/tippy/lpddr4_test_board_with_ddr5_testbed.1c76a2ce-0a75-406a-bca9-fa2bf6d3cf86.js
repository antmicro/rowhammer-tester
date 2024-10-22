selector_to_html = {"a[href=\"references.html#lpddr4-test-board-j5\"]": "<img alt=\"_images/J52.png\" id=\"lpddr4-test-board-j5\" src=\"_images/J52.png\"/>", "a[href=\"references.html#lpddr4-test-board-j6\"]": "<img alt=\"_images/J62.png\" id=\"lpddr4-test-board-j6\" src=\"_images/J62.png\"/>", "a[href=\"references.html#lpddr4-test-board-s1\"]": "<img alt=\"_images/S12.png\" id=\"lpddr4-test-board-s1\" src=\"_images/S12.png\"/>", "a[href=\"references.html#lpddr4-test-board-prog-b1\"]": "<img alt=\"_images/PROG_B12.png\" id=\"lpddr4-test-board-prog-b1\" src=\"_images/PROG_B12.png\"/>", "a[href=\"references.html#lpddr4-test-board-mode1\"]": "<img alt=\"_images/MODE11.png\" id=\"lpddr4-test-board-mode1\" src=\"_images/MODE11.png\"/>", "a[href=\"references.html#lpddr4-test-board-j1\"]": "<img alt=\"_images/J11.png\" id=\"lpddr4-test-board-j1\" src=\"_images/J11.png\"/>", "a[href=\"references.html#lpddr4-test-board-j4\"]": "<img alt=\"_images/J41.png\" id=\"lpddr4-test-board-j4\" src=\"_images/J41.png\"/>"}
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
