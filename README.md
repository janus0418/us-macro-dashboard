# US Macro Dashboard

A single-file, fully offline dashboard of US macro indicators (~2,800 series across ~65 categories — growth, inflation, labor, rates, PCE, the Fed balance sheet, markets, and more), rendered as interactive `<canvas>` charts. No server, no network, no charting library: the output is one self-contained `macro_dashboard.html` you open in any browser.

## Contents

| File | What it is |
|---|---|
| `build_dashboard.py` | All build source in one file — regenerates the indicator catalog from the data, then builds the dashboard. |
| `all_macro_data.parquet` | The data: long-format time series (`date, category, indicator, ticker, field, value`). |
| `build_dashboard.ipynb` | One-click build notebook — *Run All Cells* to build and open the dashboard. |

## Build it

**Notebook (easiest):** open `build_dashboard.ipynb` and run all cells. It checks/installs dependencies, builds `macro_dashboard.html`, and opens it.

**Command line:**

```bash
pip install pandas pyarrow
python3 build_dashboard.py
```

Either path produces `macro_dashboard.html` (~10 MB) in this folder. Open it in any modern browser — it works straight from `file://`, no server needed.

## Requirements

- Python 3.10+
- `pandas`, `pyarrow`

## Notes

`build_dashboard.py` regenerates `indicator_catalog.json` from the parquet on every run (all indicator metadata is embedded in the script), so the parquet is the only data input required. The built `macro_dashboard.html` and `indicator_catalog.json` are generated artifacts and are git-ignored.
