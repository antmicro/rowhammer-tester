selector_to_html = {"a[href=\"#tester-architecture\"]": "<figure class=\"align-default\" id=\"tester-architecture\">\n<img alt=\"Rowhammer Tester architecture\" src=\"_images/rowhammer_tester_architecture.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 1 </span><span class=\"caption-text\"><span class=\"caption-text\">\nRowhammer Tester suite architecture</span><a class=\"headerlink\" href=\"#tester-architecture\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
