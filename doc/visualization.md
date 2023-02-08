# Visualization

If you have already executed some attacks on your board you can use the results to draw a plot or visualize it in the [F4PGA Database Visualizer](https://github.com/chipsalliance/f4pga-database-visualizer).

## Plot bitflips - `logs2plot.py`

This script can plot graphs out of generated logs. It can generate two different types of graphs:

1. Distribution of bitflips across rows and columns. For example, you can generate some graphs by calling:

   ```sh
      (venv) $ python logs2plot.py your_error_summary.json
   ```

   One graph will be generated for every attack.
   So if you attacked two row pairs ``(A, B)``, ``(C, D)`` with two different read counts each ``(X, Y)``, for a total of 4 attacks, you will get 4 plots:

   - read count: ``X`` and pair: ``(A, B)``
   - read count: ``X`` and pair: ``(C, D)``
   - read count: ``Y`` and pair: ``(A, B)``
   - read count: ``Y`` and pair: ``(C, D)``

   You can control the number of displayed columns with ``--plot-columns``.
   For example if your module has 1024 columns and you provide ``--plot-columns 16``, then the DRAM columns will be displayed in groups of 64.

2. Distribution of rows affected by bitflips due to targeting single rows. For example one can generate a graph by calling:

   ```sh
      (venv) $ python logs2plot.py --aggressors-vs-victims your_error_summary.json
   ```

   One graph will be generated with victims on the X axis and aggressors on the Y axis. The colors of the tiles indicate how many bitflips occurred on each victim.

   You can enable additional annotation with ``--annotate bitflips`` so that the number of occurred bitflips will be explicitly labeled on top of each victim tile.

   Example plot generated with annotation enabled:
   ```{image} images/annotation.png
   ```
   You can zoom-in on interesting parts by using a matplotlib's zoom tool (in the bottom left corner):
   ```{image} images/annotation_zoom.png
   ```

   This type of plot has built-in DQ per pad statistics for each attack. After clicking a specific tile you will see a new pop-up window with a plot:
   ```{image} images/dqs_vict_vs_aggr.png
   ```

## Plot per DQ pad - `logs2dq.py`

This script allows you to visualize bitflips and group them per DQ pad.
Pads themselves are grouped using colors to differentiate modules.
Using this script you can visualize and check which module is failing the most.

By default it shows you mean bitflips across all attacks with standard deviation.

First run `rowhammer.py` or `hw_rowhammer.py` with the `--log-dir log_directory` flag.

Then run:

```sh
python3 logs2dq.py log_directory/your_error_summary.json
```

You can also pass optional arguments:

- `--dq DQ` - how many pads are connected to one module
- `--per-attack` - allows you to also view DQ groupings for each attacked pair of rows

## Use F4PGA Visualizer - `logs2vis.py`

Similarly to `logs2plot.py`, you can generate visualizations using the [F4PGA Database Visualizer](https://github.com/chipsalliance/f4pga-database-visualizer).

To view results using the visualizer you need to:

1. Clone and build the visualizer with:

   ```sh
   git clone https://github.com/chipsalliance/f4pga-database-visualizer
   cd f4pga-database-visualizer
   npm run build
   ```

2. Run `rowhammer.py` or `hw_rowhammer.py` with `--log-dir log_directory`

   Generate JSON files for the visualizer:

   ```sh
   python3 logs2vis.py log_directory/your_error_summary.json vis_directory
   ```

3. Copy generated JSON files from `vis_directory` to `/path/to/f4pga-database-visualizer/dist/production/`

4. Start a simple HTTP server inside the production directory:

   ```sh
   python -m http.server 8080
   ```

An example output generated with the `--aggresors-vs-victims` flag looks like this:
```{image} images/f4pga_visualizer_aggr_vs_vict.png
```
