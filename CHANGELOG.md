# Changes

The newest version comes first. The website (`site/`) is built from this file and from `__version__` in `wk1.py`:
keep the top entry in step with the version number, with one short line per change.

## 0.2.0 - 27 October 2026

- A window: File > Open shows the spreadsheet in a grid you can scroll in both directions, so you can look at it before saving anything.
- File > Save As writes csv or xlsx. File > Convert several files saves a whole batch into one folder.
- View > Show formulas (experimental) shows the decoded formulas where they can be read.
- Help > About shows the version. Ctrl+O opens, Ctrl+S saves, Ctrl+C copies selected rows for pasting into Excel.
- A file named on the command line or dropped on the program opens in the window. `--convert` keeps the old no-window conversion.

## 0.1.0 - 25 October 2026

- Reads Lotus 1-2-3 .WK1 files and writes csv or xlsx: numbers, text and the last result of formula cells.
- Command-line program, with drag and drop and several files at once.
- Two Windows programs that need no Python: a command-line one and a double-click one with file dialogs.
- Experimental formula decoding (`--formulas`) for formulas whose every part is understood, with a list of the rest.
