selector_to_html = {"a[href=\"#plot-annotation\"]": "<figure class=\"align-default\" id=\"plot-annotation\">\n<img alt=\"Annotated plot\" src=\"_images/annotation.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 18 </span><span class=\"caption-text\"><span class=\"caption-text\">\nExample plot generated with annotation enabled</span><a class=\"headerlink\" href=\"#plot-annotation\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"#annotation-zoom\"]": "<figure class=\"align-default\" id=\"annotation-zoom\">\n<img alt=\"Annotation zoom\" src=\"_images/annotation_zoom.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 19 </span><span class=\"caption-text\"><span class=\"caption-text\">\nZooming in on the plot</span><a class=\"headerlink\" href=\"#annotation-zoom\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"hammering.html\"]": "<h1 class=\"tippy-header\" id=\"performing-attacks-hammering\" style=\"margin-top: 0;\">Performing attacks (hammering)<a class=\"headerlink\" href=\"#performing-attacks-hammering\" title=\"Link to this heading\">\u00b6</a></h1><p>Rowhammer attacks can be run against a DRAM module.\nThe results can be then used for measuring cell retention.\nFor the complete list of script modifiers, see <code class=\"docutils literal notranslate\"><span class=\"pre\">--help</span></code>.</p><p>There are two versions of the rowhammer script:</p>", "a[href=\"#aggressors-vs-victims-output\"]": "<figure class=\"align-default\" id=\"aggressors-vs-victims-output\">\n<img alt=\"Aggressors vs. victims output\" src=\"_images/f4pga_visualizer_aggr_vs_vict.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 21 </span><span class=\"caption-text\"><span class=\"caption-text\">\nAgressors vs. victims flag output example</span><a class=\"headerlink\" href=\"#aggressors-vs-victims-output\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>", "a[href=\"#dq-pop-up\"]": "<figure class=\"align-default\" id=\"dq-pop-up\">\n<img alt=\"Per pad statistics\" src=\"_images/dqs_vict_vs_aggr.png\"/>\n<figcaption>\n<p><span class=\"caption-number\">Fig. 20 </span><span class=\"caption-text\"><span class=\"caption-text\">\nPer pad statistics</span><a class=\"headerlink\" href=\"#dq-pop-up\" title=\"Permalink to this image\">\u00b6</a></span></p></figcaption>\n</figure>"}
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
