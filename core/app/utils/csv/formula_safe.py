"""Formula-injection-safe CSV writing.

CSV/spreadsheet exports are routinely opened in Excel / Google Sheets / LibreOffice.
Those applications interpret any cell whose text begins with a *formula trigger*
character as a live formula — so a value the application stored verbatim from
untrusted user input (a profile display name, a problem-report message, a chat
turn, …) can execute when an admin opens the exported file. This is CSV / formula
injection (a.k.a. "DDE injection").

Note that ``csv`` quoting does NOT defend against this: quoting only protects the
*CSV grammar* (delimiters, newlines, quotes inside fields). The spreadsheet still
strips the surrounding quotes and then evaluates the leading ``=`` / ``+`` / ``-`` /
``@`` as a formula.

Per OWASP CSV-injection guidance the mitigation is to prefix any cell whose value
begins with a trigger character with a safe prefix so the spreadsheet treats the
whole cell as text. We use a leading single-quote (``'``) — the conventional
choice; Excel/Sheets render it as a plain text cell and hide the prefix in the UI.

Trigger characters we neutralize (the OWASP set):

* ``=`` ``+`` ``-`` ``@`` — formula leaders.
* ``\t`` (TAB, U+0009) and ``\r`` (CR, U+000D) — control chars Excel uses to
  start a new cell / line and which can smuggle a formula into the following cell.

Negative-number handling decision
----------------------------------
A legitimate negative number such as ``-12.5`` begins with ``-`` and is therefore
prefixed to ``'-12.5``. We deliberately accept this per OWASP: the alternative
(trying to distinguish "real" negative numbers from a malicious payload like
``-2+3+cmd|'/C calc'!A0``) is fragile and exactly the kind of bypass attackers
target. The exported cell still *reads* as ``-12.5`` to a human and round-trips
back to the same string when re-imported as text; only the spreadsheet's
auto-numeric typing is suppressed. Most exported numeric columns here are produced
by code (ints/floats formatted by us) and never start with a trigger anyway, so
the practical impact is limited to free-text columns that happen to hold a leading
``-``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Protocol

# OWASP formula-injection trigger characters. A cell whose *first* character is one
# of these is neutralized by prefixing with ``'``.
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")

# Conventional neutralizing prefix: a leading single-quote forces a text cell.
_SAFE_PREFIX = "'"


class _SupportsWrite(Protocol):
    """Minimal file-like target accepted by :func:`csv.writer`."""

    def write(self, s: str) -> object: ...


def safe_csv_cell(value: object) -> object:
    """Return ``value`` neutralized against CSV/formula injection.

    Non-string values (ints, floats, ``None``, …) are returned unchanged so the
    csv writer renders them as it normally would; only ``str`` values that begin
    with a formula trigger are prefixed with ``'``. Empty strings pass through.

    R10: Google Sheets / some LibreOffice CSV-import paths strip leading whitespace
    before evaluating a cell, so a value like ``" =HYPERLINK(...)"`` or ``"\\n=..."``
    is still a live formula there. We therefore neutralize when the first
    *non-whitespace* character is a trigger (``value.lstrip()``), in addition to the
    literal first character — the latter still catches a genuine leading ``\\t``/``\\r``
    control trigger, which ``lstrip()`` would itself strip away.
    """
    if isinstance(value, str) and (
        value[:1] in _FORMULA_TRIGGERS or value.lstrip()[:1] in _FORMULA_TRIGGERS
    ):
        return _SAFE_PREFIX + value
    return value


class FormulaSafeWriter:
    """Drop-in wrapper around :func:`csv.writer` that sanitizes every cell.

    Construct it exactly like ``csv.writer`` (``FormulaSafeWriter(fileobj)``)
    and call :meth:`writerow` / :meth:`writerows` as usual; each cell is routed
    through :func:`safe_csv_cell` before being handed to the underlying writer.
    Header rows are sanitized too — that is harmless for our fixed, code-defined
    column names and means callers need no special-casing.
    """

    __slots__ = ("_writer",)

    def __init__(self, csvfile: _SupportsWrite, dialect: str = "excel") -> None:
        self._writer = csv.writer(csvfile, dialect=dialect)

    def writerow(self, row: Iterable[object]) -> object:
        return self._writer.writerow([safe_csv_cell(cell) for cell in row])

    def writerows(self, rows: Iterable[Iterable[object]]) -> None:
        for row in rows:
            self.writerow(row)
