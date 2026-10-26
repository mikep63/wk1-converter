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


def formula(row, col, value, tokens):
    body = struct.pack('<BHHdH', 0xFF, col, row, value, len(tokens)) + tokens
    return rec(0x10, body)


def t_ref(col, row):
    return b'\x01' + struct.pack('<HH', col, row)


def t_range(c1, r1, c2, r2):
    return b'\x02' + struct.pack('<HHHH', c1, r1, c2, r2)


def t_int(v):
    return b'\x05' + struct.pack('<h', v)


END = b'\x03'

FORMULAS = [     # (tokens, expected Excel text or None when the formula must keep its value, why)
    (t_ref(0, 0) + t_ref(1, 0) + t_int(2) + b'\x0b' + b'\x09' + END, '=A1+(B1*2)', ''),
    (t_range(0, 0, 0, 2) + b'\x50\x01' + END, '=SUM(A1:A3)', ''),
    (t_ref(0, 0) + t_int(0) + b'\x13' + t_int(1) + t_int(2) + b'\x3b' + END, '=IF(A1>0,1,2)', ''),
    (t_ref(0, 0) + t_ref(1, 0) + b'\x09' + b'\x08' + t_int(2) + b'\x0b' + END, '=(-(A1+B1))*2', ''),
    (t_ref(0, 0) + t_ref(1, 0) + b'\x14' + END, '=AND(A1,B1)', ''),
    (b'\x00' + struct.pack('<d', 2.5) + t_ref(27, 99) + b'\x0c' + END, '=2.5/AB100', ''),
    (t_int(1) + t_int(2) + t_int(3) + b'\x55' + END, None, 'function 85 not converted'),          # VLOOKUP: not converted
    (t_ref(0x8001, 0) + t_int(1) + b'\x09' + END, None, 'relative cell reference'),
    (t_int(1) + b'\x09' + END, None, 'malformed formula'),
]


def formula_sample():
    parts = [rec(0x0000, struct.pack('<H', 0x0406))]
    for i, (tokens, _, _) in enumerate(FORMULAS):
        parts.append(formula(i, 0, 42.0, tokens))
    parts.append(rec(0x0001))
    return b''.join(parts)


def sample():
    return b''.join([
        rec(0x0000, struct.pack('<H', 0x0406)),          # beginning of file, version
        rec(0x0006, struct.pack('<HHHH', 0, 0, 2, 3)),   # dimensions
        label(0, 0, 'Name'), label(0, 1, 'AB'), label(0, 2, 'AVG'),
        label(1, 0, 'Abbott, K'), integer(1, 1, 320), number(1, 2, 0.297),
        label(2, 0, 'Café'), integer(2, 1, -4), number(2, 2, 12.0),   # cp437 stores the e with an acute accent as byte 0x82
        rec(0x0001),                                                      # end of file
    ])


class FakeUI:
    """Stands in for the dialog boxes: answers are given up front, and every message is kept."""

    def __init__(self, files, save=None, folder=None, yes=()):
        self.files, self.save, self.folder_, self.yes = files, save, folder, list(yes)
        self.asked, self.infos, self.errors = [], [], []

    def open_files(self):
        return self.files

    def save_as(self, initialfile):
        self.asked.append(initialfile)
        return self.save

    def folder(self):
        return self.folder_

    def yes_no(self, title, text):
        self.asked.append(title)
        return self.yes.pop(0)

    def info(self, text):
        self.infos.append(text)

    def error(self, text):
        self.errors.append(text)


def check_gui(d):
    plain, with_f = os.path.join(d, 'plain.wk1'), os.path.join(d, 'withf.wk1')
    open(plain, 'wb').write(sample())
    open(with_f, 'wb').write(formula_sample())
    # one file, no formulas: only the Save As box, named after the file
    ui = FakeUI([plain], save=os.path.join(d, 'g1.csv'))
    check(wk1.gui(ui) == 0 and ui.asked == ['plain.csv'] and os.path.exists(os.path.join(d, 'g1.csv')) and ui.infos, 'gui: one file')
    # formulas found and accepted: asked once, the list is written
    ui = FakeUI([with_f], save=os.path.join(d, 'g2.xlsx'), yes=[True])
    check(wk1.gui(ui) == 0 and ui.asked[0] == 'Formulas found' and os.path.exists(os.path.join(d, 'g2.formulas.csv')), 'gui: formulas')
    # formulas found and declined: values only, no list
    ui = FakeUI([with_f], save=os.path.join(d, 'g3.csv'), yes=[False])
    check(wk1.gui(ui) == 0 and not os.path.exists(os.path.join(d, 'g3.formulas.csv')), 'gui: formulas declined')
    # several files: a folder and an output type
    os.makedirs(os.path.join(d, 'out'))
    ui = FakeUI([plain, plain.replace('plain', 'plain')], folder=os.path.join(d, 'out'), yes=[False])
    check(wk1.gui(ui) == 0 and os.path.exists(os.path.join(d, 'out', 'plain.csv')), 'gui: several files')
    # cancelling at any box does nothing
    for ui in (FakeUI([]), FakeUI([plain], save=''), FakeUI([plain, plain], folder='')):
        check(wk1.gui(ui) == 0 and not ui.infos and not ui.errors, 'gui: cancel')
    # a file that is not a WK1 file is reported, not raised
    bad = os.path.join(d, 'bad.wk1')
    open(bad, 'wb').write(b'not a spreadsheet')
    ui = FakeUI([bad], save=os.path.join(d, 'g4.csv'))
    check(wk1.gui(ui) == 1 and ui.errors and 'no cells' in ui.errors[0] and not ui.infos, 'gui: bad file is reported')


def check_windowed(d):
    plain = os.path.join(d, 'win.wk1')
    open(plain, 'wb').write(sample())
    bad = os.path.join(d, 'winbad.wk1')
    open(bad, 'wb').write(b'not a spreadsheet')
    ui = FakeUI([])
    check(wk1.run_windowed([plain], ui) == 0 and os.path.exists(os.path.join(d, 'win.csv')) and ui.infos, 'windowed: a dropped file')
    ui = FakeUI([])
    check(wk1.run_windowed(['--quiet', plain], ui) == 0 and not ui.infos, 'windowed: --quiet')
    ui = FakeUI([])
    check(wk1.run_windowed([bad, plain], ui) == 1 and ui.errors and 'winbad.wk1' in ui.errors[0], 'windowed: a bad file is reported')
    ui = FakeUI([plain], save=os.path.join(d, 'win2.csv'))
    check(wk1.run_windowed([], ui) == 0 and os.path.exists(os.path.join(d, 'win2.csv')), 'windowed: no files opens the dialogs')


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
        # formulas: values by default, decoded text with the dict, the value kept where a formula is not understood
        fsrc = os.path.join(d, 'formulas.wk1')
        open(fsrc, 'wb').write(formula_sample())
        check(all(row == [42] for row in wk1.grid(fsrc)), 'formula cells give their stored value by default')
        found = {}
        g = wk1.grid(fsrc, found)
        for i, (_, want, why) in enumerate(FORMULAS):
            text, reason = found[(i, 0)]
            check(text == want and reason == why, 'formula %d: %r %r, wanted %r %r' % (i, text, reason, want, why))
            check(g[i][0] == (want if want else 42), 'grid cell %d: %r' % (i, g[i][0]))
        # the converter writes the list of formulas
        out2 = os.path.join(d, 'formulas.xlsx')
        wk1.convert(fsrc, out2, formulas=True)
        report = open(os.path.join(d, 'formulas.formulas.csv'), encoding='utf-8-sig').read().splitlines()
        check(len(report) == len(FORMULAS) + 1 and report[1].startswith('A1,42,=A1+(B1*2),'), 'formula list: %r' % (report[:2],))
        check_gui(d)
        check_windowed(d)
    print('ok')


if __name__ == '__main__':
    main()
