"""
Report print: every member of a ledger report starts on its own printed page.

report_preview.html marks each member after the first with `rp-member-start`
(break-before: page) and the "****" separator as screen-only; report_print.js
prints the preview in a clean frame where page breaks apply.

Python 3.13+
"""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from app.core.numeric import fixed

TEMPLATES = Path(__file__).resolve().parents[1] / "app" / "web" / "templates"
PRINT_JS = Path(__file__).resolve().parents[1] / "app" / "web" / "static" / "js" / "report_print.js"


def _render(ledger: list[dict]) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    env.filters["fixed"] = fixed
    result = SimpleNamespace(
        header=["Date", "Qty"], footer={"total": 1.0}, ledger=ledger,
        metadata=SimpleNamespace(owner_name="Owner", report_name="Member Ledger", name="Center", code="1", address=None,
                                 is_range=True, start_date="01/11/2026", end_date="14/11/2026", start_shift="M", end_shift="E"),
    )
    return env.get_template("pages/reports/partials/report_preview.html").render(
        result=result, today="14/11/2026", mcc=SimpleNamespace(name="", code="")
    )


def _member(name: str) -> dict:
    return {"head": {"Member": name}, "rows": [{"date": "01/11", "qty": 10.5}], "footer": {"total_qty": 10.5}}


def test_each_member_after_the_first_starts_a_new_page():
    html = _render([_member("A"), _member("B"), _member("C")])

    assert html.count('class="rp-member-start"') == 2
    first, second, third = (html.index(f"Member: {name}") for name in "ABC")
    breaks = [i for i in range(len(html)) if html.startswith('class="rp-member-start"', i)]
    assert first < breaks[0] < second < breaks[1] < third
    assert "break-before: page" in html


def test_separator_is_screen_only():
    html = _render([_member("A"), _member("B")])
    assert html.count('class="rp-separator"') == 1


def test_animal_type_groups_stay_together():
    groups = [{"head": {"Animal Type": kind}, "rows": [], "footer": None} for kind in ("Cow", "Buffalo")]
    assert 'class="rp-member-start"' not in _render(groups)


def test_print_frame_undoes_the_absolute_layout():
    script = PRINT_JS.read_text(encoding="utf-8")
    assert ".thermal-receipt { position: static !important;" in script
    assert "mcc-report-preview-content" in script
