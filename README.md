# wk1-converter

Read a Lotus 1-2-3 `.WK1` spreadsheet and write it as csv or xlsx. One Python file, no dependencies for csv
(`openpyxl` for xlsx).

```
python wk1.py in.WK1 out.csv
python wk1.py in.WK1 out.xlsx
```

## Windows programs, no Python needed

Two programs, the same code bundled with its own Python runtime (about 12 MB each):

- **`wk1-converter-gui.exe`**: double-click it. A window opens with **File**, **View** and **Help** menus. **File > Open** (Ctrl+O)
  picks a WK1 file and shows it in a grid you can scroll in both directions (row numbers down the side, column letters across
  the top), so you can look at it before anything is written. **File > Save As** (Ctrl+S) writes it as csv or xlsx.
  **File > Convert several files** does a batch into one folder. **View > Show formulas (experimental)** shows the decoded
  formulas where they can be read. **Help > About** names the version. Select rows and press Ctrl+C to copy them (tab separated,
  ready to paste into Excel). Drop a WK1 file on the program (or give its name) and it opens in the window. There is no black
  console window. With `--convert` in front of the file names (`wk1-converter-gui.exe --convert a.WK1 b.WK1`) it converts them next
  to themselves with no window, and `--quiet` leaves out the message at the end.
- **`wk1-converter.exe`**: for a command prompt or a script:

```
wk1-converter in.WK1                  writes in.csv next to it
wk1-converter in.WK1 out.xlsx
wk1-converter --xlsx a.WK1 b.WK1
```

The Releases page has a build made by the workflow in `.github/workflows/build.yml` from the code in this
repository. Build them yourself with `build.bat` (needs Python once, on the build machine; it installs PyInstaller and openpyxl into a
`.venv` folder here and writes both exes to `dist\`). The exes are not stored in the repository: download them from the
Releases page, or build them. Single-file programs made with PyInstaller are sometimes flagged by antivirus software; if
yours does, build them from the source above.

From Python:

```python
import wk1
rows = wk1.grid('in.WK1')        # a list of rows; '' for an empty cell
wk1.write(rows, 'out.csv')
```

## What it reads

Numbers, integers and text labels, and for a formula cell the result Lotus last stored. Text is decoded as cp437, the
DOS code page Lotus used. Whole-number floats come back as integers.

## Formulas (experimental)

By default a formula cell gives its stored value. With `--formulas` the formula itself is decoded and written as Excel
text: a real formula in an xlsx, `=SUM(A1:A3)` text in a csv. A list of every formula (cell, stored value, formula, and why
any was left as a value) is written next to the output as `<name>.formulas.csv`.

```
wk1-converter --formulas in.WK1 out.xlsx
```

It converts only what it is sure of: the operators `+ - * / ^`, the comparisons, `#AND#`, `#OR#`, `#NOT#`, cell and range
references, and these functions: `@ABS @INT @SQRT @LOG @LN @PI @SIN @COS @TAN @ATAN @ATAN2 @ASIN @ACOS @EXP @MOD @ROUND
@IF @NA @TRUE @FALSE @RAND @NOW @ISNA @ISERR @DAY @MONTH @YEAR @HOUR @MINUTE @SECOND @LENGTH @VALUE @CHR @ASCII @UPPER
@LOWER @PROPER @TRIM @REPEAT @LEFT @RIGHT @DATE @TIME @SUM @AVG @CNT @MIN @MAX`. A formula that uses anything else keeps
its stored value, and the list says why. That includes functions whose Excel version counts from a different base or takes
its arguments in a different order (`@MID`, `@FIND`, `@VLOOKUP`, `@HLOOKUP`, `@CHOOSE`, `@INDEX`, `@IRR`, `@PMT` and the
database functions), strings written into a formula, and cell references stored relative to the cell.

Things to know before relying on it:

- It is tested only on files built from the published record layout, because no real Lotus file with formulas has been
  available to the author. Check the list against your sheet. Reports of real files that fail are welcome.
- Every operation is parenthesised, so `A1+B1*2` comes out as `A1+(B1*2)`: correct, a little verbose.
- Lotus comparisons give 1 or 0, Excel gives TRUE or FALSE; Lotus `@COUNT` counts non-blank cells, so it becomes `COUNTA`.
- Excel recalculates the formulas when the file opens, so the numbers can differ from Lotus's stored results where the two
  programs differ (rounding, error values, dates before 1900). The list shows the stored value for comparison.

## What it does not keep

Number formats, dates, column widths, multiple sheets and the older or newer Lotus formats (`.WKS`, `.WK3`, `.WK4`). A
cell that Lotus left blank is empty in the output.

## Testing

```
python test_wk1.py
```

The test writes its own small WK1 file from the record layout, so the repository holds no one else's data. The reader was
also checked on real files: 22 WK1 files written between 1997 and 2014, and, for four of them, every
value against a text export of the same data made by the program that wrote them: 27,216 values compared, none different.

## File format, briefly

A WK1 file is a stream of records: a 2-byte opcode and a 2-byte length (little endian), then the data. The cell records
start with a format byte and the column and row (2 bytes each): `0x0D` integer (int16), `0x0E` number (double), `0x0F`
label (a prefix character, then text ending in a null), `0x10` formula (the double result, then the formula tokens) and
`0x33` the text result of a string formula.

## Status

Values: tested on real files. Formulas: experimental, see above. `NOTES.md` has the sources and open questions.

## Licence

MIT.

## The website

`site/index.html` is a one-page website: what the program does, a screenshot, a Download button, the current version and the list of changes.
`python build_site.py` fills in the version (from `__version__` in `wk1.py`), its date and every entry of `CHANGELOG.md`, and writes the finished page to
`_site/`. The two buttons point at the newest GitHub Release (`.../releases/latest/download/wk1-converter-gui.exe` and `wk1-converter.exe`), so they work
once a version has been released. The screenshot uses made-up sample data (no one else's files).

To publish a new version:

1. Change `__version__` in `wk1.py` and add an entry at the top of `CHANGELOG.md` (`## 0.3.0 - 12 November 2026`, then one `- ` line per change).
   `python test_wk1.py` fails if the two disagree.
2. Commit and push, then tag the version (`git tag v0.3.0` and `git push origin v0.3.0`). The `build` workflow tests and builds both exes and attaches
   them to a Release.
3. Publishing the Release runs the `website` workflow, which rebuilds the page and publishes it with GitHub Pages. It can also be started by hand
   from the Actions tab.

One-time setup: Settings > Pages > Source: GitHub Actions. GitHub Pages sites are public to the whole internet, and Pages for a private repository needs a
paid plan, so on a free account the repository has to be made public first (Settings > General > Danger Zone > Change visibility).
