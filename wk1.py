# -*- coding: utf-8 -*-
"""Read a Lotus 1-2-3 .WK1 file and write it as csv or xlsx.

    python wk1.py in.WK1 out.csv       # stored values; a formula cell gives its last result
    python wk1.py in.WK1 out.xlsx

A WK1 file is a run of records: a 2-byte opcode and a 2-byte length (little endian), then the data. The cell records are
0x0C blank, 0x0D integer (int16), 0x0E number (IEEE double), 0x0F label (a prefix character, then text ending in a null),
0x10 formula (its double result, then the formula, which is ignored here) and 0x33 the text result of a string formula.
Every cell record starts with a format byte, then the column and row (2 bytes each). Text is decoded as cp437, the DOS
code page Lotus used. Number formats, dates and formulas are not kept, only the values.
"""
import csv
import struct
import sys

CELLS = {0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x33}


def read_bytes(data):
    """{(row, col): value} and the (rows, cols) extent, zero based, from the bytes of a WK1 file."""
    pos, cells, last = 0, {}, None
    while pos + 4 <= len(data):
        op, ln = struct.unpack_from('<HH', data, pos)
        body = data[pos + 4:pos + 4 + ln]
        pos += 4 + ln
        if op not in CELLS or len(body) < 5:
            continue
        col, row = struct.unpack_from('<HH', body, 1)
        if op == 0x0C:
            continue
        if op == 0x0D and len(body) >= 7:
            v = struct.unpack_from('<h', body, 5)[0]
        elif op == 0x0E and len(body) >= 13:
            v = struct.unpack_from('<d', body, 5)[0]
        elif op == 0x0F:
            v = body[6:].split(b'\x00')[0].decode('cp437')
        elif op == 0x10 and len(body) >= 13:
            v = struct.unpack_from('<d', body, 5)[0]
            last = (row, col)
        elif op == 0x33 and last is not None:     # the text result belongs to the formula cell before it
            row, col = last
            v = body.split(b'\x00')[0].decode('cp437')
        else:
            continue
        if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
            v = int(v)
        cells[(row, col)] = v
    rows = max((r for r, _ in cells), default=-1) + 1
    cols = max((c for _, c in cells), default=-1) + 1
    return cells, (rows, cols)


def read(path):
    return read_bytes(open(path, 'rb').read())


def grid(path):
    """A list of rows, each a list of values ('' for an empty cell)."""
    cells, (nr, nc) = read(path)
    return [[cells.get((r, c), '') for c in range(nc)] for r in range(nr)]


def write(rows, out):
    if out.lower().endswith('.xlsx'):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        for r in rows:
            ws.append(r)
        wb.save(out)
    else:
        with open(out, 'w', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerows(rows)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    g = grid(sys.argv[1])
    write(g, sys.argv[2])
    print('%d rows x %d columns -> %s' % (len(g), len(g[0]) if g else 0, sys.argv[2]))
