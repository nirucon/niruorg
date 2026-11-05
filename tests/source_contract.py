"""Format-insensitive access to the NIRUORG sources for contract tests.

Many regression tests assert that a piece of code still exists. They were
written against the original one-line style of ``niruorg/app.py``. Since
0.6.0 the code is formatted with a standard formatter and split into
modules under ``niruorg/`` (M1), so these helpers:

* read every ``niruorg/**/*.py`` file, so a contract holds wherever the code
  now lives;
* compare normalised text: whitespace and line breaks, ``;`` statement
  separators, the quote style and trailing commas before a closing bracket
  do not matter. ``'x' in app_source()``, ``.index()``, ``.count()``,
  ``.find()`` and slicing all work on the normalised text, with the needle
  normalised the same way.

``find_def()`` returns the real (unnormalised) source of a function or
class, for tests that parse or execute it.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'niruorg'


def source_files():
    """app.py first, then every other module, in a stable order."""
    app = PACKAGE / 'app.py'
    rest = sorted(p for p in PACKAGE.rglob('*.py') if p != app and '__pycache__' not in p.parts)
    return [app] + rest


def raw_source() -> str:
    return '\n'.join(p.read_text(encoding='utf-8') for p in source_files())


_WS = re.compile(r'\s+')
_TRAILING_COMMA = re.compile(r',([)\]}])')


def norm(text: str) -> str:
    text = text.replace('"', "'")
    text = _WS.sub('', text)
    text = text.replace(';', '')
    return _TRAILING_COMMA.sub(r'\1', text)


class Src(str):
    """Normalised source text whose search methods normalise their needle."""

    def __new__(cls, text: str, normalised: bool = False):
        return str.__new__(cls, text if normalised else norm(text))

    def __contains__(self, needle):
        return str.__contains__(self, norm(needle))

    def index(self, needle, *args):
        return str.index(self, norm(needle), *args)

    def find(self, needle, *args):
        return str.find(self, norm(needle), *args)

    def rfind(self, needle, *args):
        return str.rfind(self, norm(needle), *args)

    def count(self, needle, *args):
        return str.count(self, norm(needle), *args)

    def startswith(self, prefix, *args):
        return str.startswith(self, norm(prefix) if isinstance(prefix, str) else tuple(map(norm, prefix)), *args)

    def split(self, sep=None, maxsplit=-1):
        parts = str.split(self, norm(sep) if sep is not None else None, maxsplit)
        return [Src(x, normalised=True) for x in parts]

    def __getitem__(self, key):
        return Src(str.__getitem__(self, key), normalised=True)


def app_source() -> Src:
    """All NIRUORG sources, normalised for format-insensitive contracts."""
    return Src(raw_source())


def find_def(name: str, kinds=(ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef), top_level=False):
    """Return (node, module_source, path) of the first definition named ``name``."""
    for path in source_files():
        text = path.read_text(encoding='utf-8')
        tree = ast.parse(text)
        nodes = tree.body if top_level else ast.walk(tree)
        for node in nodes:
            if isinstance(node, kinds) and node.name == name:
                return node, text, path
    raise LookupError(name)


def def_source(name: str, **kw) -> str:
    node, text, _ = find_def(name, **kw)
    return ast.get_source_segment(text, node) or ''
