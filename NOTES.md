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
- Verify the opcode table against a published specification before trusting it; do not write it from memory.

Do not put third-party data files in the repository (the .gitignore excludes wk1, wks, csv, xlsx).
