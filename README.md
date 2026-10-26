# wk1-converter

Read a Lotus 1-2-3 `.WK1` spreadsheet and write it as csv or xlsx. One Python file, no dependencies for csv
(`openpyxl` for xlsx).

```
python wk1.py in.WK1 out.csv
python wk1.py in.WK1 out.xlsx
```

From Python:

```python
import wk1
rows = wk1.grid('in.WK1')        # a list of rows; '' for an empty cell
wk1.write(rows, 'out.csv')
```

## What it reads

Numbers, integers and text labels, and for a formula cell the result Lotus last stored. Text is decoded as cp437, the
DOS code page Lotus used. Whole-number floats come back as integers.

## What it does not keep

Formulas (only their last result), number formats, dates, column widths, multiple sheets and the older or newer Lotus
formats (`.WKS`, `.WK3`, `.WK4`). A cell that Lotus left blank is empty in the output.

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

Values only. Reading the formula tokens and saving them as real spreadsheet formulas is planned. See `NOTES.md`.

## Licence

MIT.
