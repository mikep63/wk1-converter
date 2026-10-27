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


class FakeBox:
    """Stands in for the message box of the no-console --convert mode: every message is kept."""

    def __init__(self):
        self.messages = []

    def __call__(self, kind, text):
        self.messages.append((kind, text))


def check_convert_mode(d):
    plain = os.path.join(d, 'win.wk1')
    open(plain, 'wb').write(sample())
    bad = os.path.join(d, 'winbad.wk1')
    open(bad, 'wb').write(b'not a spreadsheet')
    box = FakeBox()
    check(wk1.run_windowed(['--convert', plain], box) == 0 and os.path.exists(os.path.join(d, 'win.csv')) and box.messages[0][0] == 'info', 'convert mode: a file')
    box = FakeBox()
    check(wk1.run_windowed(['--convert', '--quiet', plain], box) == 0 and not box.messages, 'convert mode: --quiet')
    box = FakeBox()
    check(wk1.run_windowed(['--convert', bad, plain], box) == 1 and box.messages[0][0] == 'error' and 'winbad.wk1' in box.messages[0][1], 'convert mode: a bad file is reported')


def check_window(d):
    """The window itself, with the file dialogs answered in advance. Skipped where there is no display."""
    import tkinter
    import wk1_app
    try:
        root = tkinter.Tk()
    except tkinter.TclError as e:
        print('no display (%s): window tests skipped' % e)
        return
    root.withdraw()
    try:
        plain, with_f = os.path.join(d, 'plain.wk1'), os.path.join(d, 'withf.wk1')
        open(plain, 'wb').write(sample())
        open(with_f, 'wb').write(formula_sample())
        app = wk1_app.App(wk1, root)
        app.infos, app.errors = [], []
        app.info = app.infos.append
        app.error = app.errors.append
        check(app.filemenu.entrycget('Save As...', 'state') == 'disabled' and app.status.get() == 'No file open', 'window: starts with nothing open and Save As off')
        # opening shows the file and writes nothing
        before = set(os.listdir(d))
        check(app.open_path(plain), 'window: open')
        app.wait_loaded()
        rows = [app.tree.item(i, 'values') for i in app.tree.get_children()]
        check(rows == [('1', 'Name', 'AB', 'AVG'), ('2', 'Abbott, K', '320', '0.297'), ('3', 'Caf\u00e9', '-4', '12')], 'window: rows %r' % (rows,))
        check([app.tree.heading(c, 'text') for c in app.tree['columns']] == ['', 'A', 'B', 'C'], 'window: column letters')
        check(str(app.tree.column('c0', 'anchor')) == 'w', 'window: a text column lines up on the left')
        check(set(os.listdir(d)) == before, 'window: opening a file writes nothing')
        check(app.filemenu.entrycget('Save As...', 'state') == 'normal' and 'plain.wk1' in app.root.title(), 'window: Save As is on and the title names the file')
        check('3 rows x 3 columns (A to C)' in app.status.get(), 'window: status %r' % app.status.get())
        # a file with more rows than one pass adds
        big = os.path.join(d, 'big.wk1')
        open(big, 'wb').write(b''.join(integer(r, 0, r) for r in range(wk1_app.CHUNK * 2 + 40)) + rec(0x01))
        check(app.open_path(big), 'window: open a large file')
        app.wait_loaded()
        check(len(app.tree.get_children()) == wk1_app.CHUNK * 2 + 40, 'window: all %d rows shown, got %d' % (wk1_app.CHUNK * 2 + 40, len(app.tree.get_children())))
        check(str(app.tree.column('c0', 'anchor')) == 'e', 'window: a column of numbers lines up on the right')
        # formulas: values by default, the decoded text when View > Show formulas is on
        app.open_path(with_f)
        app.wait_loaded()
        check(app.tree.item(app.tree.get_children()[2], 'values')[1] == '42' and 'formula cell' in app.status.get(), 'window: formula cells show their value')
        app.show_formulas.set(True)
        app.reload()
        app.wait_loaded()
        shown = [app.tree.item(i, 'values')[1] for i in app.tree.get_children()]
        check(any(v.startswith('=') for v in shown), 'window: formulas shown as text %r' % (shown,))
        app.show_formulas.set(False)
        # Save As: csv and xlsx, named by the dialog; cancelling writes nothing
        app.open_path(plain)
        app.wait_loaded()
        app.ask_save = lambda initialfile: os.path.join(d, 'saved.csv')
        app.save_dialog()
        text = open(os.path.join(d, 'saved.csv'), encoding='utf-8-sig').read().splitlines()
        check(text == ['Name,AB,AVG', '"Abbott, K",320,0.297', 'Caf\u00e9,-4,12'] and app.infos and not app.errors, 'window: save csv %r' % (text,))
        app.ask_save = lambda initialfile: ''
        n = len(os.listdir(d))
        app.save_dialog()
        check(len(os.listdir(d)) == n, 'window: cancelling Save As writes nothing')
        # a file that is not a WK1 file is reported and leaves the open file showing
        bad = os.path.join(d, 'bad.wk1')
        open(bad, 'wb').write(b'not a spreadsheet')
        check(not app.open_path(bad) and app.errors and 'no cells' in app.errors[-1] and app.path == plain, 'window: a bad file is reported and the open file stays')
        # copying selected rows puts tab-separated text on the clipboard
        kids = app.tree.get_children()
        app.tree.selection_set(kids[1:])
        app.copy_selection()
        check(root.clipboard_get() == 'Abbott, K\t320\t0.297\nCaf\u00e9\t-4\t12', 'window: copy %r' % root.clipboard_get())
        # several files at once, from the File menu
        out = os.path.join(d, 'many')
        os.makedirs(out)
        app.ask_open_many = lambda: [plain, with_f]
        app.ask_folder = lambda: out
        app.yes_no = lambda title, text: False
        app.batch_dialog()
        check(os.path.exists(os.path.join(out, 'plain.csv')) and os.path.exists(os.path.join(out, 'withf.csv')), 'window: convert several files')
        # About names the program and its version
        app.about()
        check(app.infos[-1].startswith('wk1-converter ' + wk1.__version__) and 'MIT' in app.infos[-1], 'window: about')
    finally:
        root.destroy()


def check_site(d):
    """The website builder: the page carries the program's version and every change in CHANGELOG.md, and refuses to build when they disagree."""
    import html
    import build_site
    out = os.path.join(d, 'site')
    page = build_site.build(out)
    check(os.path.exists(os.path.join(out, 'index.html')) and os.path.exists(os.path.join(out, 'screenshot.png')), 'site: index.html and the screenshot are written')
    check('Version %s' % wk1.__version__ in page and '{{' not in page, 'site: shows the version and no placeholder is left')
    entries = build_site.parse_changelog(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CHANGELOG.md'), encoding='utf-8').read())
    check(entries and entries[0][0] == wk1.__version__ and all(items for _, _, items in entries), 'site: CHANGELOG.md starts at the current version and every version lists changes')
    for version, date, items in entries:
        check('Version %s' % version in page and html.escape(date) in page, 'site: version %s and its date are on the page' % version)
        for item in items:
            plain = item.replace('`', '')
            check(html.escape(plain, quote=False) in page.replace('<code>', '').replace('</code>', ''), 'site: a change is missing from the page: %s' % item[:50])
    check(build_site.LATEST + 'wk1-converter-gui.exe' in page and build_site.LATEST + 'wk1-converter.exe' in page, 'site: both download links point at the latest release')
    check('https://' not in page.replace('https://github.com/mikep63/wk1-converter', ''), 'site: no other web address, fonts or scripts are loaded')
    real = build_site.read_version
    build_site.read_version = lambda: '9.9.9'
    try:
        build_site.build(os.path.join(d, 'site2'))
        check(False, 'site: a version missing from CHANGELOG.md must stop the build')
    except SystemExit:
        pass
    finally:
        build_site.read_version = real


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
        check_convert_mode(d)
        check_window(d)
        check_site(d)
    print('ok')


if __name__ == '__main__':
    main()
