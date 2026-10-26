# -*- coding: utf-8 -*-
"""Read a Lotus 1-2-3 .WK1 file and write it as csv or xlsx.

    python wk1.py in.WK1 out.csv       # stored values; a formula cell gives its last result
    python wk1.py in.WK1 out.xlsx
    python wk1.py in.WK1               # writes in.csv; several files and --xlsx work too (wk1-converter without arguments shows the list)

A WK1 file is a run of records: a 2-byte opcode and a 2-byte length (little endian), then the data. The cell records are
0x0C blank, 0x0D integer (int16), 0x0E number (IEEE double), 0x0F label (a prefix character, then text ending in a null),
0x10 formula (its double result, then the formula, which is ignored here) and 0x33 the text result of a string formula.
Every cell record starts with a format byte, then the column and row (2 bytes each). Text is decoded as cp437, the DOS
code page Lotus used. Number formats and dates are not kept. Values are the default; with --formulas the formula tokens of
a 0x10 record are decoded to Excel formula text where every part is understood (see decode_formula), and the other
formula cells keep their stored value.
"""
import csv
import os
import struct
import sys

CELLS = {0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x33}


# ---- formulas -------------------------------------------------------------------------------------------------------
# Token codes and function opcodes: Lotus's public WK1 specification (WSFF2, WSFF4, WSFF5). Argument counts: that text for
# SUM..MAX, and LibreOffice's Lotus filter (sc/source/filter/lotus/lotform.cxx) for the rest. Only functions whose Excel
# meaning is the same, with no changed argument order or base, are listed; any other function makes the whole formula
# "unsupported", and its cell then keeps its stored value.
BINARY = {9: '+', 10: '-', 11: '*', 12: '/', 13: '^', 14: '=', 15: '<>', 16: '<=', 17: '>=', 18: '<', 19: '>'}
LOGIC = {20: 'AND', 21: 'OR'}          # #AND# and #OR# are two-argument operators in Lotus
# opcode: (Excel name, number of arguments); None for the argument count means a count byte follows the opcode
FUNCS = {
    31: ('NA', 0), 38: ('PI', 0), 51: ('FALSE', 0), 52: ('TRUE', 0), 53: ('RAND', 0), 55: ('NOW', 0),
    33: ('ABS', 1), 34: ('INT', 1), 35: ('SQRT', 1), 36: ('LOG10', 1), 37: ('LN', 1), 39: ('SIN', 1), 40: ('COS', 1),
    41: ('TAN', 1), 43: ('ATAN', 1), 44: ('ASIN', 1), 45: ('ACOS', 1), 46: ('EXP', 1), 49: ('ISNA', 1), 50: ('ISERR', 1),
    60: ('DAY', 1), 61: ('MONTH', 1), 62: ('YEAR', 1), 65: ('HOUR', 1), 66: ('MINUTE', 1), 67: ('SECOND', 1),
    70: ('LEN', 1), 71: ('VALUE', 1), 74: ('CHAR', 1), 75: ('CODE', 1), 102: ('UPPER', 1), 103: ('LOWER', 1),
    107: ('PROPER', 1), 109: ('TRIM', 1),
    42: ('ATAN2', 2), 47: ('MOD', 2), 63: ('ROUND', 2), 101: ('REPT', 2), 104: ('LEFT', 2), 105: ('RIGHT', 2),
    54: ('DATE', 3), 59: ('IF', 3), 64: ('TIME', 3),
    80: ('SUM', None), 81: ('AVERAGE', None), 82: ('COUNTA', None), 83: ('MIN', None), 84: ('MAX', None),
}


class Unsupported(Exception):
    pass


def col_name(c):
    name = ''
    c += 1
    while c:
        c, r = divmod(c - 1, 26)
        name = chr(65 + r) + name
    return name


def ref(col, row):
    if col & 0x8000 or row & 0x8000:
        raise Unsupported('relative cell reference')
    if col > 255 or row > 8191:
        raise Unsupported('cell reference out of range')
    return '%s%d' % (col_name(col), row + 1)


def number_text(v):
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return repr(v)


def decode_formula(tokens):
    """Excel formula text (without the =) for the reverse Polish token bytes of a WK1 formula, or raise Unsupported.

    Every binary operation is parenthesised, so the text means what the tree meant whatever the precedence rules."""
    stack = []                                   # (text, atomic)
    pos = 0

    def wrap(item):
        return item[0] if item[1] else '(%s)' % item[0]

    def pop(n=1):
        if len(stack) < n:
            raise Unsupported('malformed formula')
        out = stack[-n:]
        del stack[-n:]
        return out

    while pos < len(tokens):
        op = tokens[pos]
        pos += 1
        if op == 0x00:
            stack.append((number_text(struct.unpack_from('<d', tokens, pos)[0]), True))
            pos += 8
        elif op == 0x01:
            c, r = struct.unpack_from('<HH', tokens, pos)
            stack.append((ref(c, r), True))
            pos += 4
        elif op == 0x02:
            c1, r1, c2, r2 = struct.unpack_from('<HHHH', tokens, pos)
            stack.append(('%s:%s' % (ref(c1, r1), ref(c2, r2)), True))
            pos += 8
        elif op == 0x03:
            break
        elif op == 0x04:                                  # parentheses: ignored, every operation is already parenthesised
            pass
        elif op == 0x05:
            stack.append((str(struct.unpack_from('<h', tokens, pos)[0]), True))
            pos += 2
        elif op == 0x08:
            stack.append(('-' + wrap(pop()[0]), False))
        elif op == 0x17:                                  # unary plus
            pass
        elif op == 0x16:
            stack.append(('NOT(%s)' % pop()[0][0], True))
        elif op in BINARY:
            a, b = pop(2)
            stack.append(('%s%s%s' % (wrap(a), BINARY[op], wrap(b)), False))
        elif op in LOGIC:
            a, b = pop(2)
            stack.append(('%s(%s,%s)' % (LOGIC[op], a[0], b[0]), True))
        elif op in FUNCS:
            name, n = FUNCS[op]
            if n is None:
                n = tokens[pos]
                pos += 1
            args = pop(n) if n else []
            stack.append(('%s(%s)' % (name, ','.join(a[0] for a in args)), True))
        elif 31 <= op <= 115:
            raise Unsupported('function %d not converted' % op)
        else:
            raise Unsupported('token %d' % op)
    if len(stack) != 1:
        raise Unsupported('malformed formula')
    return stack[0][0]


def read_bytes(data, formulas=None):
    """{(row, col): value} and the (rows, cols) extent, zero based, from the bytes of a WK1 file.

    Pass a dict as formulas to get {(row, col): ('=text', '') or (None, reason)} for every formula cell."""
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
            if formulas is not None:
                size = struct.unpack_from('<H', body, 13)[0] if len(body) >= 15 else 0
                try:
                    formulas[(row, col)] = ('=' + decode_formula(body[15:15 + size]), '')
                except (Unsupported, struct.error, IndexError) as e:
                    formulas[(row, col)] = (None, str(e) or 'malformed formula')
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


def read(path, formulas=None):
    return read_bytes(open(path, 'rb').read(), formulas)


def grid(path, formulas=None):
    """A list of rows, each a list of values ('' for an empty cell). Pass a dict as formulas to put the decoded
    formula text ('=SUM(A1:A3)') in place of the stored value wherever the formula could be decoded; the dict is
    filled with {(row, col): (text or None, reason)} for every formula cell."""
    found = {} if formulas is not None else None
    cells, (nr, nc) = read(path, found)
    if formulas is not None:
        formulas.update(found)
        for k, (text, _) in found.items():
            if text:
                cells[k] = text
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


def convert(src, out=None, fmt='csv', formulas=False):
    out = out or os.path.splitext(src)[0] + '.' + fmt
    found = {} if formulas else None
    g = grid(src, found)
    if not g:
        raise ValueError('%s has no cells; is it a Lotus WK1 file?' % os.path.basename(src))
    write(g, out)
    print('%s: %d rows x %d columns -> %s' % (src, len(g), len(g[0]) if g else 0, out))
    if formulas:
        done = sum(1 for t, _ in found.values() if t)
        print('  formulas: %d found, %d written as formulas, %d kept as values' % (len(found), done, len(found) - done))
        if found:
            report = os.path.splitext(out)[0] + '.formulas.csv'
            cells, _ = read(src)
            with open(report, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(['cell', 'stored value', 'formula', 'kept as value because'])
                for (r, c), (text, why) in sorted(found.items()):
                    w.writerow(['%s%d' % (col_name(c), r + 1), cells.get((r, c), ''), text or '', why])
            print('  list of formulas: %s' % report)
    return out


class TkUI:
    """The Windows dialogs: pick the file or files, say where to save, and a short message at the end."""

    def __init__(self):
        import tkinter
        from tkinter import filedialog, messagebox
        self.fd, self.mb = filedialog, messagebox
        self.root = tkinter.Tk()
        self.root.withdraw()
        try:
            self.root.attributes('-topmost', True)       # so the dialogs open in front of other windows
        except tkinter.TclError:
            pass

    def open_files(self):
        return list(self.fd.askopenfilenames(
            parent=self.root, title='Choose Lotus WK1 file(s) to convert',
            filetypes=[('Lotus 1-2-3 WK1', '*.wk1 *.WK1'), ('All files', '*.*')]))

    def save_as(self, initialfile):
        return self.fd.asksaveasfilename(
            parent=self.root, title='Save as', initialfile=initialfile, defaultextension='.csv',
            filetypes=[('CSV (opens in Excel)', '*.csv'), ('Excel workbook', '*.xlsx')])

    def folder(self):
        return self.fd.askdirectory(parent=self.root, title='Choose the folder to save the converted files in')

    def yes_no(self, title, text):
        return self.mb.askyesno(title, text, parent=self.root)

    def info(self, text):
        self.mb.showinfo('wk1-converter', text, parent=self.root)

    def error(self, text):
        self.mb.showerror('wk1-converter', text, parent=self.root)


def gui(ui=None):
    """Ask which WK1 files to convert and where to save them, with dialog boxes. Returns an exit code."""
    ui = ui or TkUI()
    paths = ui.open_files()
    if not paths:
        return 0
    try:
        with_formulas = False
        n = 0
        for src in paths:
            found = {}
            read(src, found)
            n += len(found)
        if n and ui.yes_no('Formulas found', '%d formula cell(s) found.\n\nWrite them as formulas (experimental)?\n'
                           'Yes: formulas where they can be read, the stored value where not, and a list of every '
                           'formula next to the output.\nNo: the values Lotus stored.' % n):
            with_formulas = True
        if len(paths) == 1:
            out = ui.save_as(os.path.splitext(os.path.basename(paths[0]))[0] + '.csv')
            if not out:
                return 0
            outs = [(paths[0], out)]
        else:
            folder = ui.folder()
            if not folder:
                return 0
            ext = 'xlsx' if ui.yes_no('Output type', 'Save the %d files as Excel workbooks (.xlsx)?\n\nNo: csv files.' % len(paths)) else 'csv'
            outs = [(p, os.path.join(folder, os.path.splitext(os.path.basename(p))[0] + '.' + ext)) for p in paths]
        for src, out in outs:
            convert(src, out, formulas=with_formulas)
    except Exception as e:             # a file that is not a WK1 file, a locked output, and so on
        ui.error('%s' % e)
        return 1
    ui.info('Saved:\n' + '\n'.join(out for _, out in outs))
    return 0


GUI_USED = False

USAGE = """wk1-converter: Lotus 1-2-3 .WK1 to csv or xlsx

  wk1-converter in.WK1                  writes in.csv next to it
  wk1-converter in.WK1 out.xlsx         writes the named file (.csv or .xlsx)
  wk1-converter --xlsx a.WK1 b.WK1      converts each file to .xlsx next to it
  wk1-converter a.WK1 b.WK1             converts each file to .csv next to it
  wk1-converter --formulas in.WK1 out.xlsx
                                        writes formulas (real formulas in xlsx, =SUM(A1:A3) text in csv) where they
                                        can be read, and a list of every formula next to the output

You can also drag one or more .WK1 files onto the program. To choose files in dialog boxes use --gui, or
double-click wk1-converter-gui.exe (the same program without the black console window).
"""


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if '--gui' in argv:
        global GUI_USED
        GUI_USED = True
        return gui()
    fmt = 'xlsx' if '--xlsx' in argv else 'csv'
    formulas = '--formulas' in argv
    if not args:
        print(USAGE)
        return 2
    if len(args) == 2 and args[1].lower().endswith(('.csv', '.xlsx')):
        convert(args[0], args[1], formulas=formulas)
        return 0
    status = 0
    for src in args:
        try:
            convert(src, None, fmt, formulas)
        except (OSError, ValueError, struct.error) as e:
            print('%s: %s' % (src, e))
            status = 1
    return status


def run_windowed(argv, ui=None):
    """The no-console build (wk1-converter-gui.exe): dialog boxes with no files named, or the files dropped on it
    converted next to themselves, with a message box for the result (--quiet leaves the message out)."""
    paths = [a for a in argv if not a.startswith('--')]
    if not paths:
        return gui(ui)
    ui = ui or TkUI()
    fmt = 'xlsx' if '--xlsx' in argv else 'csv'
    done, failed = [], []
    for src in paths:
        try:
            done.append(convert(src, None, fmt, '--formulas' in argv))
        except (OSError, ValueError, struct.error) as e:
            failed.append('%s: %s' % (os.path.basename(src), e))
    if '--quiet' not in argv:
        if failed:
            ui.error('\n'.join(failed))
        else:
            ui.info('Saved:\n' + '\n'.join(done))
    return 1 if failed else 0


if __name__ == '__main__':
    if sys.stdout is None:                  # started without a console (the windowed build)
        sys.exit(run_windowed(sys.argv[1:]))
    code = main(sys.argv[1:])
    if getattr(sys, 'frozen', False) and not GUI_USED and (len(sys.argv) < 2 or code):      # failed, or opened without the dialogs: keep the window
        try:
            input('Press Enter to close ')
        except (EOFError, RuntimeError):      # no keyboard attached (a script, or a build runner)
            pass
    sys.exit(code)
