selector_to_html = {"a[href=\"build/zcu104/documentation/index.html\"]": "<h1 class=\"tippy-header\" id=\"documentation-for-row-hammer-tester-zcu104\" style=\"margin-top: 0;\">Documentation for Row Hammer Tester ZCU104<a class=\"headerlink\" href=\"#documentation-for-row-hammer-tester-zcu104\" title=\"Link to this heading\">\u00b6</a></h1>", "a[href=\"#zcu104\"]": "<figure class=\"align-default\" id=\"zcu104\">\n<img alt=\"ZCU104 board\" src=\"_images/zcu104.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 12 </span><span class=\"caption-text\"><span class=\"caption-text\">\nZCU104 board</span><a class=\"headerlink\" href=\"#zcu104\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
