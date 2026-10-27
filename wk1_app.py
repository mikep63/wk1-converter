# -*- coding: utf-8 -*-
"""The wk1-converter window: open a Lotus WK1 file, scroll through it, then save it as csv or xlsx.

File > Open shows the spreadsheet in a grid (row numbers down the side, column letters across the top) so you can look at it before
anything is written. File > Save As writes csv or xlsx. View > Show formulas switches the experimental formula decoding on. Help > About.

The reader is passed in (run(core, paths)) rather than imported, so the same code works when wk1.py is the program's entry script
inside a PyInstaller exe.
"""
import os
import struct
import tkinter
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

TITLE = 'wk1-converter'
CHUNK = 250            # rows added to the grid per pass, so a big file does not freeze the window
ABOUT = """{title} {version}

Reads Lotus 1-2-3 .WK1 spreadsheets, lets you look through them, and saves them as csv or xlsx.

The values Lotus stored are shown and saved. A formula cell keeps the last result Lotus stored; View > Show formulas (experimental) reads the formulas where every part is understood.

The WK1 layout follows Lotus's public file-format specification. Text is read as the DOS code page 437; number formats and dates are not kept.

Released under the MIT License."""


def cell_text(v):
    """How a value looks in the grid: whole numbers without a decimal point, other numbers to 10 significant digits."""
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return '%.10g' % v
    return str(v)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class App:
    def __init__(self, core, root=None):
        self.core = core
        self.root = root or tkinter.Tk()
        self.path = None
        self.rows = []
        self.formula_cells = 0
        self.loading = False
        self.show_formulas = tkinter.BooleanVar(value=False)
        self._build()

    # ---- the window ----------------------------------------------------------------------------------------------
    def _build(self):
        root = self.root
        root.title(TITLE)
        root.geometry('1050x640')
        root.minsize(520, 300)
        style = ttk.Style(root)
        try:
            style.theme_use('vista')
        except tkinter.TclError:
            pass
        style.configure('Grid.Treeview', rowheight=20)
        style.configure('Grid.Treeview.Heading', font=tkfont.nametofont('TkDefaultFont').copy())

        bar = tkinter.Menu(root)
        filemenu = tkinter.Menu(bar, tearoff=False)
        filemenu.add_command(label='Open...', accelerator='Ctrl+O', command=self.open_dialog)
        filemenu.add_command(label='Save As...', accelerator='Ctrl+S', command=self.save_dialog, state='disabled')
        filemenu.add_command(label='Convert several files...', command=self.batch_dialog)
        filemenu.add_separator()
        filemenu.add_command(label='Exit', accelerator='Ctrl+Q', command=root.destroy)
        viewmenu = tkinter.Menu(bar, tearoff=False)
        viewmenu.add_checkbutton(label='Show formulas (experimental)', variable=self.show_formulas, command=self.reload)
        helpmenu = tkinter.Menu(bar, tearoff=False)
        helpmenu.add_command(label='About wk1-converter', command=self.about)
        bar.add_cascade(label='File', menu=filemenu, underline=0)
        bar.add_cascade(label='View', menu=viewmenu, underline=0)
        bar.add_cascade(label='Help', menu=helpmenu, underline=0)
        root.config(menu=bar)
        self.filemenu = filemenu

        body = ttk.Frame(root)
        body.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(body, show='headings', style='Grid.Treeview', selectmode='extended')
        ys = ttk.Scrollbar(body, orient='vertical', command=self.tree.yview)
        xs = ttk.Scrollbar(body, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.tree.tag_configure('odd', background='#f3f6fa')
        self.hint = ttk.Label(self.tree, text='File > Open... (Ctrl+O) to choose a Lotus WK1 file', foreground='#555555')
        self.hint.place(relx=0.5, rely=0.45, anchor='center')

        self.status = tkinter.StringVar(value='No file open')
        ttk.Label(root, textvariable=self.status, anchor='w', relief='sunken', padding=(6, 2)).pack(fill='x', side='bottom')

        for key, fn in (('<Control-o>', self.open_dialog), ('<Control-s>', self.save_dialog), ('<Control-q>', lambda: root.destroy())):
            root.bind(key, lambda e, f=fn: f())
        self.tree.bind('<Control-c>', self.copy_selection)
        self.tree.bind('<Control-a>', lambda e: self.tree.selection_set(self.tree.get_children()))

    # ---- dialogs (small methods so the tests can stand in for them) ----------------------------------------------
    def ask_open(self):
        return filedialog.askopenfilename(parent=self.root, title='Open a Lotus WK1 file',
                                          filetypes=[('Lotus 1-2-3 WK1', '*.wk1 *.WK1'), ('All files', '*.*')])

    def ask_open_many(self):
        return list(filedialog.askopenfilenames(parent=self.root, title='Choose Lotus WK1 files to convert',
                                                filetypes=[('Lotus 1-2-3 WK1', '*.wk1 *.WK1'), ('All files', '*.*')]))

    def ask_save(self, initialfile):
        return filedialog.asksaveasfilename(parent=self.root, title='Save as', initialfile=initialfile, defaultextension='.csv',
                                            filetypes=[('CSV (opens in Excel)', '*.csv'), ('Excel workbook', '*.xlsx')])

    def ask_folder(self):
        return filedialog.askdirectory(parent=self.root, title='Choose the folder to save the converted files in')

    def yes_no(self, title, text):
        return messagebox.askyesno(title, text, parent=self.root)

    def info(self, text):
        messagebox.showinfo(TITLE, text, parent=self.root)

    def error(self, text):
        messagebox.showerror(TITLE, text, parent=self.root)

    # ---- opening and showing a file ------------------------------------------------------------------------------
    def open_dialog(self):
        path = self.ask_open()
        if path:
            self.open_path(path)

    def reload(self):
        if self.path:
            self.open_path(self.path)

    def open_path(self, path):
        """Read the file and show it. Nothing is written. Returns True when the grid has been filled."""
        try:
            found = {}
            self.core.read(path, found)
            rows = self.core.grid(path, {} if self.show_formulas.get() else None)
            if not rows:
                raise ValueError('%s has no cells; is it a Lotus WK1 file?' % os.path.basename(path))
        except (OSError, ValueError, struct.error) as e:
            self.error('Could not open %s:\n%s' % (os.path.basename(path), e))
            return False
        self.path, self.rows, self.formula_cells = path, rows, len(found)
        self.root.title('%s - %s' % (os.path.basename(path), TITLE))
        self.filemenu.entryconfigure('Save As...', state='normal')
        self.hint.place_forget()
        self._show(rows)
        return True

    def _show(self, rows):
        tree = self.tree
        tree.delete(*tree.get_children())
        ncols = len(rows[0])
        ids = ['n'] + ['c%d' % i for i in range(ncols)]
        tree.configure(columns=ids)
        font = tkfont.nametofont('TkDefaultFont')
        sample = rows[:300]
        tree.heading('n', text='')
        tree.column('n', width=max(40, font.measure(str(len(rows))) + 18), anchor='e', stretch=False)
        for i in range(ncols):
            name = self.core.col_name(i)
            texts = [cell_text(r[i]) for r in sample if r[i] != '']
            width = max([font.measure(name)] + [font.measure(t) for t in texts[:300]]) + 18
            filled = [r[i] for r in sample if r[i] != '']
            numeric = bool(filled) and sum(is_number(v) for v in filled) >= 0.8 * len(filled)      # one heading over a column of numbers still counts as numbers
            tree.heading('c%d' % i, text=name)
            tree.column('c%d' % i, width=min(280, max(46, width)), anchor='e' if numeric else 'w', stretch=False)
        self.loading = True
        self._add(rows, 0)
        self._set_status()

    def _add(self, rows, start):
        tree = self.tree
        for r in range(start, min(start + CHUNK, len(rows))):
            tree.insert('', 'end', values=[r + 1] + [cell_text(v) for v in rows[r]], tags=('odd',) if r % 2 else ())
        if start + CHUNK < len(rows):
            self.status.set('Loading %s... %d of %d rows' % (os.path.basename(self.path), start + CHUNK, len(rows)))
            self.root.after(1, self._add, rows, start + CHUNK)
        else:
            self.loading = False
            self._set_status()

    def _set_status(self):
        if self.loading or not self.rows:
            return
        n = len(self.rows[0])
        text = '%s  -  %d rows x %d columns (A to %s)' % (os.path.basename(self.path), len(self.rows), n, self.core.col_name(n - 1))
        if self.formula_cells:
            text += '  -  %d formula cell(s)%s' % (self.formula_cells, '' if self.show_formulas.get() else ' (values shown; View > Show formulas)')
        self.status.set(text)

    def wait_loaded(self):
        """For the tests: let the window finish filling the grid."""
        while self.loading:
            self.root.update()

    def copy_selection(self, event=None):
        lines = ['\t'.join(str(v) for v in self.tree.item(i, 'values')[1:]) for i in self.tree.selection()]
        if lines:
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(lines))

    # ---- saving ---------------------------------------------------------------------------------------------------
    def save_dialog(self):
        if not self.path:
            return
        out = self.ask_save(os.path.splitext(os.path.basename(self.path))[0] + '.csv')
        if not out:
            return
        try:
            self.core.convert(self.path, out, formulas=self.show_formulas.get())
        except (OSError, ValueError, struct.error, ImportError) as e:        # a locked output file, xlsx without openpyxl, and so on
            self.error('Could not save %s:\n%s' % (os.path.basename(out), e))
            return
        self.status.set('Saved %s' % out)
        self.info('Saved:\n%s' % out)

    def batch_dialog(self):
        paths = self.ask_open_many()
        if not paths:
            return
        folder = self.ask_folder()
        if not folder:
            return
        ext = 'xlsx' if self.yes_no('Output type', 'Save the %d file(s) as Excel workbooks (.xlsx)?\n\nNo: csv files.' % len(paths)) else 'csv'
        done, failed = [], []
        for src in paths:
            out = os.path.join(folder, os.path.splitext(os.path.basename(src))[0] + '.' + ext)
            try:
                self.core.convert(src, out, formulas=self.show_formulas.get())
                done.append(out)
            except (OSError, ValueError, struct.error, ImportError) as e:
                failed.append('%s: %s' % (os.path.basename(src), e))
        if failed:
            self.error('\n'.join(failed))
        if done:
            self.info('Saved:\n' + '\n'.join(done))

    def about(self):
        self.info(ABOUT.format(title=TITLE, version=getattr(self.core, '__version__', '')))


def run(core, paths=(), root=None):
    """Open the window (with the first of `paths` already showing, if given) and run it until it is closed."""
    app = App(core, root)
    if paths:
        app.root.after(50, app.open_path, paths[0])
    app.root.mainloop()
    return 0
