selector_to_html = {"a[href=\"https://en.wikipedia.org/wiki/Serial_presence_detect\"]": "<p>\nIn computing, <b>serial presence detect</b> (<b>SPD</b>) is a standardized way to automatically access information about a memory module. Earlier 72-pin SIMMs included five pins that provided five bits of <i>parallel presence detect</i> (PPD) data, but the 168-pin DIMM standard changed to a serial presence detect to encode more information.</p>", "a[href^=\"https://en.wikipedia.org/wiki/Serial_presence_detect#\"]": "<p>\nIn computing, <b>serial presence detect</b> (<b>SPD</b>) is a standardized way to automatically access information about a memory module. Earlier 72-pin SIMMs included five pins that provided five bits of <i>parallel presence detect</i> (PPD) data, but the 168-pin DIMM standard changed to a serial presence detect to encode more information.</p>"}
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
