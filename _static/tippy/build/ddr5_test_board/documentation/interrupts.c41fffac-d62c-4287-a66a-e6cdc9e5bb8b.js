selector_to_html = {"a[href=\"timer0.html\"]": "<h1 class=\"tippy-header\" id=\"timer0\" style=\"margin-top: 0;\">TIMER0<a class=\"headerlink\" href=\"#timer0\" title=\"Link to this heading\">\u00b6</a></h1><p>Provides a generic Timer core.</p><p>The Timer is implemented as a countdown timer that can be used in various modes:</p>", "a[href=\"uart.html\"]": "<h1 class=\"tippy-header\" id=\"uart\" style=\"margin-top: 0;\">UART<a class=\"headerlink\" href=\"#uart\" title=\"Link to this heading\">\u00b6</a></h1><p><cite>Address: 0xf0008800 + 0x0 = 0xf0008800</cite></p>"}
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
