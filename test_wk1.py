# -*- coding: utf-8 -*-
"""Tests for wk1.py. The sample file is written here, from the published record layout, so the repo holds no third-party data.

    python test_wk1.py
"""
import os
import struct
import tempfile

import wk1


def rec(op, body=b''):
    return struct.pack('<HH', op, len(body)) + body


def integer(row, col, v):
    return rec(0x0D, struct.pack('<BHHh', 0xFF, col, row, v))


def number(row, col, v):
    return rec(0x0E, struct.pack('<BHHd', 0xFF, col, row, v))


def label(row, col, text):
    return rec(0x0F, struct.pack('<BHH', 0xFF, col, row) + b"'" + text.encode('cp437') + b'\x00')


def sample():
    return b''.join([
        rec(0x0000, struct.pack('<H', 0x0406)),          # beginning of file, version
        rec(0x0006, struct.pack('<HHHH', 0, 0, 2, 3)),   # dimensions
        label(0, 0, 'Name'), label(0, 1, 'AB'), label(0, 2, 'AVG'),
        label(1, 0, 'Abbott, K'), integer(1, 1, 320), number(1, 2, 0.297),
        label(2, 0, 'Café'), integer(2, 1, -4), number(2, 2, 12.0),   # cp437 stores the e with an acute accent as byte 0x82
        rec(0x0001),                                                      # end of file
    ])


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def main():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'sample.wk1')
        open(src, 'wb').write(sample())
        g = wk1.grid(src)
        check(g == [['Name', 'AB', 'AVG'], ['Abbott, K', 320, 0.297], ['Café', -4, 12]], 'grid: %r' % (g,))
        out = os.path.join(d, 'sample.csv')
        wk1.write(g, out)
        text = open(out, encoding='utf-8-sig').read().splitlines()
        check(text == ['Name,AB,AVG', '"Abbott, K",320,0.297', 'Café,-4,12'], 'csv: %r' % (text,))
        try:
            import openpyxl
        except ImportError:
            print('openpyxl not installed, xlsx test skipped')
        else:
            x = os.path.join(d, 'sample.xlsx')
            wk1.write(g, x)
            ws = openpyxl.load_workbook(x).active
            check([[c.value for c in r] for r in ws.iter_rows()] == g, 'xlsx round trip')
        # a truncated file must not raise
        wk1.read_bytes(sample()[:-9])
    print('ok')


if __name__ == '__main__':
    main()
