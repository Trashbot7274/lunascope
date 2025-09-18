# Lunascope Function Overview

This page sketches a "you are here" map of the primary functions and mixins that wire the Qt UI together. It is intentionally terse so that someone new to the project can spot the main entry points before diving into the code.

## Startup Flow at a Glance

```
app.main()
└── parse CLI arguments → optional sample list path
└── _load_ui() → build widgets from `ui/main.ui`
└── Controller(ui, proj)
    ├── SListMixin._init_slist()         # sample list table + file pickers
    ├── MetricsMixin._init_metrics()     # EDF metadata + annotation toggles
    ├── HypnoMixin._init_hypno()         # hypnogram canvas & stats
    ├── AnalMixin._init_anal()           # Luna command panel & outputs
    ├── SignalsMixin._init_signals()     # waveform plots & range selector
    ├── ManipsMixin._init_manips()       # signal manipulation controls
    ├── SettingsMixin._init_settings()   # parameters/command docks
    ├── CTreeMixin._init_ctree()         # computation tree viewer
    ├── SpecMixin._init_spec()           # spectrogram requests & canvas
    └── SoapPopsMixin._init_soap_pops()  # SOAP & POPS summaries
```

*`Controller._attach_inst()` is invoked whenever the sample-list selection changes. It clears previous state, attaches the chosen record (`lp.proj.inst(...)`), populates helpers, and triggers the first render.*

## Component Reference Tables

### Core module `app.py`

| Function | Purpose |
| --- | --- |
| `_load_ui()` | Loads the Qt Designer `.ui` file, registering the `PlotWidget` custom widget, and returns the constructed main window. |
| `_parse_args(argv)` | Handles the optional sample-list CLI argument. |
| `main(argv)` | Bootstraps Luna (`lp.proj()`), spins up `QApplication`, loads the UI, instantiates the `Controller`, optionally pre-loads the sample list, and enters the Qt event loop. |

### `controller.py`

| Function | Purpose |
| --- | --- |
| `Controller.__init__(ui, proj)` | Mixes in all feature panels, wires the dock menu shortcuts, and arranges the initial layout and status bar. |
| `Controller._attach_inst(current, _)` | Responds to sample selection: resets state, applies parameters, attaches an EDF record, refreshes metrics/spectrogram/SOAP lists, and triggers the initial signal render. |
| `Controller._clear_all()` | Clears tables, combo boxes, plots, and cached proxies before loading a different record. |
| `clear_rows(target, keep_headers=True)` | Utility that empties Qt table models or views (used across components). |
| `add_dock_shortcuts(win, view_menu)` | Adds global and per-dock keyboard shortcuts under the “View” menu. |

### Mixins (`components/`)

| Mixin | Primary responsibilities | Key functions to inspect |
| --- | --- | --- |
| `SListMixin` | Sample list ingestion from files/folders or single EDF files, populating and filtering the table view. | `_init_slist()`, `_read_slist_from_file()`, `open_folder()`, `open_edf()`, `df_to_model()` |
| `MetricsMixin` | Displays EDF header metadata, builds selectable signal/annotation tables, and keeps an events table in sync with annotation selections. | `_init_metrics()`, `_update_metrics()`, `_update_instances()`, `_on_row_changed()` |
| `HypnoMixin` | Manages the hypnogram Matplotlib canvas and computes sleep statistics from annotations. | `_init_hypno()`, `_calc_hypnostats()` |
| `SignalsMixin` | Owns signal rendering (pyqtgraph plots), histogram updates, hypnogram overlay, and the interactive `XRangeSelector` for navigation. | `_init_signals()`, `_render_histogram()`, `_render_signals()`, `_render_signals_simple()`, `_update_pg1()` |
| `AnalMixin` | Wraps Luna command execution: loading/saving scripts, sending commands, capturing outputs, and populating the analysis results tree/table. | `_init_anal()`, `_exec_luna()`, `_update_table()`, `_on_tree_sel()`, `_parse_tab_pairs()` |
| `SpecMixin` | Drives spectrogram/Hjorth requests and populates the spectrogram canvas. | `_init_spec()`, `_update_spectrogram_list()`, `_calc_spectrogram()`, `_calc_hjorth()` |
| `SoapPopsMixin` | Lists available SOAP/POPS configurations and issues the calculations when requested. | `_init_soap_pops()`, `_update_soap_list()`, `_calc_soap()`, `_calc_pops()` |
| `ManipsMixin` | Hooks up manual signal manipulation controls (e.g., overlays) and delegates work to the signals mixin. | `_init_manips()` |
| `SettingsMixin` | Provides settings/parameters dock behavior. | `_init_settings()` |
| `CTreeMixin` | Presents computational tree results and search helpers. | `_init_ctree()`, `expand_and_show_matches()` |

### Supporting Utilities

| Module | Function(s) | What they support |
| --- | --- | --- |
| `components/metrics.py` | `add_check_column()` and `expand_interval()` | Checkbox columns for tables and zooming around events. |
| `components/signals.py` | `XRangeSelector`, `TextBatch`, `TrackManager` | Encapsulate the time-range selector logic, text overlays, and track toggling used by the signal viewer. |
| `components/plts.py` | `spec()`, `plot_hjorth()`, `plot_spec()`, `hypno_density()` | Matplotlib helpers shared by spectrogram and hypnogram panels. |

## How to Use This Map

1. **Start with the `app.main()` flow** to understand how the Qt application spins up.
2. **Open `Controller.__init__`** to see which mixins correspond to which UI panels, then jump into the mixin that matches the area you want to modify.
3. **Use the helper tables above** to find entry-point functions responsible for a behavior (e.g., loading annotations → `MetricsMixin._update_instances`).
4. **Look at utilities** when you need the reusable mechanisms: table checkbox wiring (`add_check_column`), dock shortcuts, or the pyqtgraph range selector.

Keeping these relationships handy should make it easier to trace user interactions from the UI into the underlying Luna project calls.
