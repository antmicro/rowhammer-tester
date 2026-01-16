selector_to_html = {"a[href=\"#inversion-example-table\"]": "<table class=\"docutils data align-default\" id=\"inversion-example-table\">\n<caption><span class=\"caption-number\">Table 2 </span><span class=\"caption-text\">Inversion example table</span><a class=\"headerlink\" href=\"#inversion-example-table\" title=\"Link to this table\">\u00b6</a></caption>\n<colgroup>\n<col style=\"width: 10.0%\"/>\n<col style=\"width: 10.0%\"/>\n<col style=\"width: 80.0%\"/>\n</colgroup>\n<thead>\n<tr class=\"row-odd\"><th class=\"head\"><p>Row number</p></th>\n<th class=\"head\"><p>Row number modulo divisor (8)</p></th>\n<th class=\"head\"><p>Value</p></th>\n</tr>\n</thead>\n<tbody>\n<tr class=\"row-even\"><td><p>0</p></td>\n<td><p>0</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>1</p></td>\n<td><p>1</p></td>\n<td><p>inverted pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>2</p></td>\n<td><p>2</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>3</p></td>\n<td><p>3</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>4</p></td>\n<td><p>4</p></td>\n<td><p>inverted pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>5</p></td>\n<td><p>5</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>6</p></td>\n<td><p>6</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>7</p></td>\n<td><p>7</p></td>\n<td><p>inverted pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>8</p></td>\n<td><p>0</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>9</p></td>\n<td><p>1</p></td>\n<td><p>inverted pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>10</p></td>\n<td><p>2</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-odd\"><td><p>11</p></td>\n<td><p>3</p></td>\n<td><p>pattern</p></td>\n</tr>\n<tr class=\"row-even\"><td><p>12</p></td>\n<td><p>4</p></td>\n<td><p>inverted pattern</p></td>\n</tr>\n</tbody>\n</table>"}
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
