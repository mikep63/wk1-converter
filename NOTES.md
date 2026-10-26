# Notes for the next session

Where this came from: the RSBL projection guide project (`../rsbl.org`) needed Strat-O-Matic's yearly card files. Strat
saved its 1990s data as Lotus WK1; the folders also hold text versions. This reader was written to confirm the text
files against the originals and to turn WK1 into csv/xlsx. A copy of `wk1.py` is also in `../rsbl.org/tools/analysis/`.

State
- `wk1.py`: values reader and csv/xlsx writer. `test_wk1.py`: self-contained test (writes its own sample file).
- Checked on 22 real files (none contain formula records) and against Strat's text exports of 1997 and 1998: no differences.
- The 1998 hitters text has 3 more rows than the WK1 (523 against 520); not investigated.
- No remote repository yet; nothing published.

Next: formulas
- Formula cells (opcode `0x10`) hold the cached double result, a 2-byte length, then a token stream (postfix-style): constants,
  cell references (relative/absolute flags in the high bit), ranges, operators, parentheses, a function table (~100
  functions, some with a count byte). Plan: decode to infix text, write real formulas to xlsx with the cached value, give csv
  an option for text or value.
- No file here contains a formula, so decoding can only be tested on files made from the published layout. Real Lotus files
  are needed before calling it finished. Mark it experimental until then.
- Lotus released the WK1 specification (WSFF1 to WSFF5) into the public domain; copies are at https://oss.sheetjs.com/notes/lotus/
  (WSFF2.TXT, WSFF4.TXT, WSFF5.TXT). Read on 25 Oct 2026 (through a summarising fetch, so recheck against the text itself):
  - Formula record 0x10: bytes 0 format, 1-2 column, 3-4 row, 5-12 cached IEEE double, 13-14 formula size, then the code in
    reverse Polish notation, up to 2048 bytes.
  - Token codes: 0 constant (8-byte double), 1 variable/cell (4 bytes: column, row), 2 range (8 bytes), 3 return (end),
    4 parentheses, 5 2-byte signed integer, 8 unary minus, 9 + , 10 - , 11 * , 12 / , 13 ^ , 14 = , 15 <> , 16 <= , 17 >= ,
    18 < , 19 > , 20 #AND# , 21 #OR# , 22 #NOT# , 23 unary plus. Codes 6, 7 and 24 to 30 are not described. The spec does not
    describe a relative-reference bit in the cell tokens (check the sheet's real files; Release 2 kept row/column in the high
    bit in some tools' notes).
  - Functions are opcodes 31 (@NA) to 115 (@INDIRECT): the names are in WSFF5, in order (31 NA, 32 ERR, 33 ABS, 34 INT, 35 SQRT,
    36 LOG, 37 LN, 38 PI, 39 SIN, 40 COS, 41 TAN, 42 ATAN2, 43 ATAN, 44 ASIN, 45 ACOS, 46 EXP, 47 MOD, 48 CHOOSE (listed as @sel),
    49 ISNA, 50 ISERR, 51 FALSE, 52 TRUE, 53 RAND, 54 DATE, 55 NOW, 56 PMT, 57 PV, 58 FV, 59 IF, 60 DAY, 61 MONTH, 62 YEAR, 63 ROUND,
    64 TIME, 65 HOUR, 66 MINUTE, 67 SECOND, 68 ISNUMBER, 69 ISSTRING, 70 LENGTH, 71 VALUE, 72 FIXED, 73 MID, 74 CHR, 75 ASCII,
    76 FIND, 77 DATEVALUE, 78 TIMEVALUE, 79 CELLPOINTER, 80 SUM, 81 AVG, 82 CNT, 83 MIN, 84 MAX, 85 VLOOKUP, 86 NPV, 87 VAR, 88 STD,
    89 IRR, 90 HLOOKUP, 91 DSUM, 92 DAVG, 93 DCNT, 94 DMIN, 95 DMAX, 96 DVAR, 97 DSTD, 98 INDEX, 99 COLS, 100 ROWS, 101 REPEAT,
    102 UPPER, 103 LOWER, 104 LEFT, 105 RIGHT, 106 REPLACE, 107 PROPER, 108 CELL, 109 TRIM, 110 CLEAN, 111 S, 112 V, 113 STREQ,
    114 CALL, 115 INDIRECT).
  - **Still missing:** the number of arguments of each function. The spec says only that functions taking a variable number of
    arguments are followed by a 1-byte count (80 to 84 are named for it); no table of fixed counts was found. Without the arity
    a postfix stream cannot be turned into infix text. Sources to try: the example signatures in WSFF2 (opcodes 31 to 97), and
    the Lotus filter in LibreOffice (sc/source/filter/lotus/, lotform.cxx), which has a function table with counts.
- Do not finish the decoder until the arities are verified, and test it on at least one real WK1 file that contains formulas.

Do not put third-party data files in the repository (the .gitignore excludes wk1, wks, csv, xlsx).
