# -*- coding: utf-8 -*-
"""Build the one-page website into _site/: site/index.html with the version, date and list of changes filled in.

    python build_site.py

The version comes from __version__ in wk1.py and the changes from CHANGELOG.md (newest first, "## version - date" then "- item" lines), so the page
cannot disagree with the program. The download buttons point at the newest GitHub Release, so they work once a version tag has been released.
"""
import html
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_site')
REPO = 'mikep63/wk1-converter'
REPO_URL = 'https://github.com/' + REPO
RELEASES = REPO_URL + '/releases'
LATEST = RELEASES + '/latest/download/'


def read_version():
    for line in open(os.path.join(HERE, 'wk1.py'), encoding='utf-8'):
        m = re.match(r"__version__\s*=\s*'([^']+)'", line)
        if m:
            return m.group(1)
    raise SystemExit('no __version__ in wk1.py')


def parse_changelog(text):
    """[(version, date, [items])], newest first, from the '## 0.2.0 - 27 October 2026' headings and '- item' lines."""
    out = []
    for line in text.splitlines():
        m = re.match(r'^##\s+(\S+)\s+-\s+(.+?)\s*$', line)
        if m:
            out.append((m.group(1), m.group(2), []))
        elif out and line.startswith('- '):
            out[-1][2].append(line[2:].strip())
    return out


def inline(text):
    """Escape the text and turn `code` into <code>."""
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', html.escape(text, quote=False))


def changes_html(entries, current):
    parts = []
    for version, date, items in entries:
        flag = '<span class="current">current</span>' if version == current else ''
        lis = '\n'.join('      <li>%s</li>' % inline(i) for i in items)
        parts.append('    <div class="version">\n      <h3>Version %s%s<span>%s</span></h3>\n      <ul>\n%s\n      </ul>\n    </div>'
                     % (html.escape(version), flag, html.escape(date), lis))
    return '\n'.join(parts)


def build(out=OUT):
    version = read_version()
    entries = parse_changelog(open(os.path.join(HERE, 'CHANGELOG.md'), encoding='utf-8').read())
    if not entries or entries[0][0] != version:
        raise SystemExit('CHANGELOG.md starts at %s but wk1.py is version %s: add the entry for %s' % (entries[0][0] if entries else 'nothing', version, version))
    if not entries[0][2]:
        raise SystemExit('the %s entry in CHANGELOG.md has no changes listed' % version)
    page = open(os.path.join(HERE, 'site', 'index.html'), encoding='utf-8').read()
    fill = {'version': html.escape(version), 'date': html.escape(entries[0][1]), 'changes': changes_html(entries, version),
            'download_gui': LATEST + 'wk1-converter-gui.exe', 'download_cli': LATEST + 'wk1-converter.exe', 'releases': RELEASES, 'repo_url': REPO_URL}
    for k, v in fill.items():
        page = page.replace('{{%s}}' % k, v)
    left = re.findall(r'\{\{\w+\}\}', page)
    if left:
        raise SystemExit('placeholders left in the page: %s' % left)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    with open(os.path.join(out, 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)
    for name in os.listdir(os.path.join(HERE, 'site')):
        if name != 'index.html':
            shutil.copy(os.path.join(HERE, 'site', name), os.path.join(out, name))
    for src, dst in (('LICENSE', 'license.txt'), ('THIRD-PARTY-NOTICES.txt', 'third-party-notices.txt')):
        shutil.copy(os.path.join(HERE, src), os.path.join(out, dst))
    print('wrote %s (version %s, %d versions listed)' % (os.path.join(out, 'index.html'), version, len(entries)))
    return page


if __name__ == '__main__':
    build()
    sys.exit(0)
