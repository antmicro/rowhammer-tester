selector_to_html = {"a[href=\"building_rowhammer.html\"]": "<h1 class=\"tippy-header\" id=\"building-rowhammer-designs\" style=\"margin-top: 0;\">Building Rowhammer designs<a class=\"headerlink\" href=\"#building-rowhammer-designs\" title=\"Link to this heading\">\u00b6</a></h1><p>This chapter provides building instructions for synthesizing the digital design for physical DRAM testers and simulation models.</p>", "a[href=\"#cell-retention-plot\"]": "<figure class=\"align-default\" id=\"cell-retention-plot\">\n<img alt=\"cell-retention-plot\" src=\"_images/rdimm-ddr5-cell-retention-plot.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 17 </span><span class=\"caption-text\"><span class=\"caption-text\">\nSample plot summarizing DRAM cell retention testing</span><a class=\"headerlink\" href=\"#cell-retention-plot\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"#default-all-rows-arguments\"]": "<table class=\"docutils data align-default\" id=\"default-all-rows-arguments\">\n<caption><span class=\"caption-number\">Table 1 </span><span class=\"caption-text\">Default values for arguments</span><a class=\"headerlink\" href=\"#default-all-rows-arguments\" title=\"Link to this table\">\u00b6</a></caption>\n<thead>\n<tr class=\"row-odd\"><th class=\"head\"><p>argument</p></th>\n<th class=\"head\"><p>default</p></th>\n</tr>\n</thead>\n<tbody>\n<tr class=\"row-even\"><td><p><code class=\"docutils literal notranslate\"><span class=\"pre\">--start-row</span></code></p></td>\n<td><p>0</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p><code class=\"docutils literal notranslate\"><span class=\"pre\">--row-jump</span></code></p></td>\n<td><p>1</p></td>\n</tr>\n<tr class=\"row-even\"><td><p><code class=\"docutils literal notranslate\"><span class=\"pre\">--row-pair-distance</span></code></p></td>\n<td><p>2</p></td>\n</tr>\n</tbody>\n</table>"}
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
