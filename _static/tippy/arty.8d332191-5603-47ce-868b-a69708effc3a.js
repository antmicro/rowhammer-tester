selector_to_html = {"a[href=\"#arty-a7\"]": "<figure class=\"align-default\" id=\"arty-a7\">\n<img alt=\"arty-a7\" src=\"_images/arty-a7.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 13 </span><span class=\"caption-text\"><span class=\"caption-text\">\nArty-A7 board</span><a class=\"headerlink\" href=\"#arty-a7\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
