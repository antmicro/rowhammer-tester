selector_to_html = {"a[href=\"zcu104.html\"]": "<h1 class=\"tippy-header\" id=\"zcu104-board\" style=\"margin-top: 0;\">ZCU104 board<a class=\"headerlink\" href=\"#zcu104-board\" title=\"Link to this heading\">\u00b6</a></h1><p>The <a class=\"reference external\" href=\"https://www.xilinx.com/products/boards-and-kits/zcu104.html\">ZCU104 board</a> enables testing DDR4 SO-DIMM modules.\nIt features a Zynq UltraScale+ MPSoC device consisting of PS (Processing System with quad-core ARM Cortex-A53) and PL (programmable logic).</p><p>On the ZCU104 board the Ethernet PHY is connected to PS instead of PL.\nFor this reason it is necessary to route the Ethernet/EtherBone traffic through PC &lt;-&gt; PS &lt;-&gt; PL.\nTo do this, a simple EtherBone server has been implemented (the source code can be found in the <code class=\"docutils literal notranslate\"><span class=\"pre\">firmware/zcu104/etherbone/</span></code> directory).</p>", "a[href=\"arty.html\"]": "<h1 class=\"tippy-header\" id=\"arty-a7-board\" style=\"margin-top: 0;\">Arty-A7 board<a class=\"headerlink\" href=\"#arty-a7-board\" title=\"Link to this heading\">\u00b6</a></h1><p>The <a class=\"reference external\" href=\"https://reference.digilentinc.com/reference/programmable-logic/arty-a7/start\">Arty-A7 board</a> allows testing its on-board DDR3 module.\nThe board is designed around the Artix-7\u2122 Field Programmable Gate Array (FPGA) from Xilinx.</p>"}
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
