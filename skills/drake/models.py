from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


VALID_ACTIVATION_KEYS = tuple(f"F{index}" for index in range(1, 13))


@dataclass(frozen=True)
class PageSpec:
    """Drake input page instructions loaded from one page-key markdown file."""

    key: str
    title: str
    source_path: str
    instructions: str
    columns: tuple[str, ...]
    row_advance: str = "Tab"
    related: tuple[str, ...] = ()


@dataclass(frozen=True)
class CsvItem:
    """One UI-visible mapped amount from an agent-provided CSV row."""

    label: str
    column: str
    amount: Decimal
    row_index: int


@dataclass
class ValidatedForm:
    """Validated form payload passed from the CLI into the review UI."""

    page: PageSpec
    activation_key: str
    input_headers: list[str]
    output_columns: list[str]
    rows: list[dict[str, str]]
    items: list[CsvItem]
    column_totals: dict[str, Decimal]
    all_total: Decimal
    warnings: list[str] = field(default_factory=list)
