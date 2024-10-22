selector_to_html = {"a[href=\"#id1\"]": "<figure class=\"align-default\" id=\"id1\">\n<a class=\"reference internal image-reference\" href=\"_images/zcu104_loading.jpg\"><img alt=\"_images/zcu104_loading.jpg\" src=\"_images/zcu104_loading.jpg\" style=\"width: 49%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 1 </span><span class=\"caption-text\"><span class=\"caption-text\">\nThe board without a bitstream.</span><a class=\"headerlink\" href=\"#id1\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"#id2\"]": "<figure class=\"align-default\" id=\"id2\">\n<a class=\"reference internal image-reference\" href=\"_images/zcu104_loaded.jpg\"><img alt=\"_images/zcu104_loaded.jpg\" src=\"_images/zcu104_loaded.jpg\" style=\"width: 49%;\"/>\n</a>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 2 </span><span class=\"caption-text\"><span class=\"caption-text\">\nThe state when the bitstream has been loaded successfully.</span><a class=\"headerlink\" href=\"#id2\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
