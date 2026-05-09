from __future__ import annotations

import csv
import io
import re
from decimal import Decimal, InvalidOperation

from .models import CsvItem, PageSpec, VALID_ACTIVATION_KEYS, ValidatedForm


UI_ITEM_COLUMNS = {"item", "memo", "description source", "source item"}
NON_AMOUNT_COLUMNS = {
    "T/S",
    "ST",
    "City",
    "Description",
    "Date Acquired",
    "Date Sold",
    "S/L",
    "1099-B",
    "TSJ",
    "Tax ID Number",
    "Name",
    "Account Num",
    "Account #",
    "Marketplace identifier",
    "Marketplace assigned policy number",
    "Policy issuer's name",
    "Policy start date",
    "Policy termination date",
    "Start Date",
    "Termination Date",
    "Empty",
    "Account is For",
    "Financial institution",
    "Account number",
}


def parse_load_payload(payload: dict) -> list[dict[str, str]]:
    forms = payload.get("forms")
    if not isinstance(forms, list) or not forms:
        raise ValueError("load input must be a JSON object with a non-empty forms array.")
    if len(forms) > len(VALID_ACTIVATION_KEYS):
        raise ValueError(f"load supports at most {len(VALID_ACTIVATION_KEYS)} forms at once.")

    normalized = []
    for index, form in enumerate(forms, start=1):
        if not isinstance(form, dict):
            raise ValueError(f"forms[{index}] must be an object.")
        page = form.get("page")
        csv_text = form.get("csv_text")
        activation_key = VALID_ACTIVATION_KEYS[index - 1]
        if not isinstance(page, str) or not page.strip():
            raise ValueError(f"forms[{index}].page is required.")
        if not isinstance(csv_text, str) or not csv_text.strip():
            raise ValueError(f"forms[{index}].csv_text is required.")
        normalized.append({"page": page, "csv_text": csv_text, "activation_key": activation_key})
    return normalized


def validate_form(page: PageSpec, csv_text: str, activation_key: str) -> ValidatedForm:
    reader = csv.DictReader(io.StringIO(csv_text, newline=""))
    if not reader.fieldnames:
        raise ValueError(f"{page.key}: CSV must include a header row.")

    input_headers = [header.strip() for header in reader.fieldnames if header is not None]
    if len(input_headers) != len(set(input_headers)):
        raise ValueError(f"{page.key}: CSV headers must be unique.")

    header_map = {_normalize(header): header for header in input_headers}
    item_header = _find_item_header(header_map)
    page_column_map = {_normalize(column): column for column in page.columns}
    output_columns = [
        page_column_map[_normalize(header)]
        for header in input_headers
        if header != item_header and _normalize(header) in page_column_map
    ]

    unknown_headers = [
        header
        for header in input_headers
        if header != item_header and _normalize(header) not in page_column_map
    ]
    if unknown_headers:
        raise ValueError(f"{page.key}: unknown CSV columns: {', '.join(unknown_headers)}")
    if not output_columns:
        raise ValueError(f"{page.key}: CSV must include at least one Drake column.")

    rows: list[dict[str, str]] = []
    items: list[CsvItem] = []
    column_totals = {column: Decimal("0") for column in output_columns}

    for row_index, row in enumerate(reader, start=1):
        normalized_row = {column: _clean_cell(row.get(column, "")) for column in input_headers}
        rows.append(normalized_row)
        label = normalized_row.get(item_header or "", "") or f"Row {row_index}"
        for column in output_columns:
            value = normalized_row.get(column, "")
            if not value:
                continue
            if not _is_amount_column(column):
                continue
            amount = _parse_amount(value, page.key, column, row_index)
            if amount == 0:
                continue
            column_totals[column] += amount
            items.append(CsvItem(label=label, column=column, amount=amount, row_index=row_index))

    all_total = sum(column_totals.values(), Decimal("0"))
    warnings = _build_warnings(page, input_headers, output_columns)
    return ValidatedForm(
        page=page,
        activation_key=activation_key,
        input_headers=input_headers,
        output_columns=output_columns,
        rows=rows,
        items=items,
        column_totals=column_totals,
        all_total=all_total,
        warnings=warnings,
    )


def render_summary(form: ValidatedForm) -> str:
    lines = [f"{form.activation_key} - {form.page.key}", ""]
    lines.append("Columns used: " + ", ".join(form.output_columns))
    lines.append("")
    lines.append("Sums:")
    for column in form.output_columns:
        total = form.column_totals.get(column, Decimal("0"))
        if total == 0:
            continue
        pieces = [item.amount for item in form.items if item.column == column]
        detail = ""
        if len(pieces) > 1:
            detail = " (" + ", ".join(_format_money(piece) for piece in pieces) + ")"
        lines.append(f"- {column}: {_format_money(total)}{detail}")
    lines.append(f"- {total_label(form)}: {_format_money(form.all_total)}")
    if form.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in form.warnings)
    lines.append("")
    lines.append("Recommend validating in Drake based on the totals summary before entry.")
    return "\n".join(lines)


def build_output_csv(form: ValidatedForm, item_moves: dict[tuple[int, str], str] | None = None) -> str:
    item_moves = item_moves or {}
    rows: list[dict[str, str]] = []
    output_fieldnames = list(form.page.columns)

    for row_index, source_row in enumerate(form.rows, start=1):
        output_row = {column: source_row.get(column, "") for column in output_fieldnames}
        for (move_row_index, original_column), target_column in item_moves.items():
            if move_row_index != row_index or original_column == target_column:
                continue
            value = output_row.get(original_column, "")
            if not value:
                continue
            output_row[original_column] = ""
            output_row[target_column] = _add_amounts(output_row.get(target_column, ""), value)
        rows.append(output_row)

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=output_fieldnames, lineterminator="\n")
    for row in rows:
        writer.writerow(row)
    return stream.getvalue()


def settings_header(row_advance: str) -> str:
    return f'# {{"newline": "{row_advance}"}}\n'


def total_label(form: ValidatedForm) -> str:
    if any(token in form.page.key for token in ("Deductions", "Cost of Goods Sold", "8825")):
        return "All Expenses Total"
    return "All Numeric Total"


def _build_warnings(page: PageSpec, input_headers: list[str], output_columns: list[str]) -> list[str]:
    warnings: list[str] = []
    if not any(_normalize(header) in UI_ITEM_COLUMNS for header in input_headers):
        warnings.append("No Item column was provided; UI labels use Row N.")
    return warnings


def _find_item_header(header_map: dict[str, str]) -> str | None:
    for candidate in UI_ITEM_COLUMNS:
        if candidate in header_map:
            return header_map[candidate]
    return None


def _is_amount_column(column: str) -> bool:
    return column not in NON_AMOUNT_COLUMNS and "date" not in column.casefold()


def _parse_amount(value: str, page_key: str, column: str, row_index: int) -> Decimal:
    cleaned = value.strip()
    if not cleaned:
        return Decimal("0")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()").replace("$", "").replace(",", "")
    if cleaned.endswith("-"):
        negative = True
        cleaned = cleaned[:-1]
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"{page_key}: {column} row {row_index} is not numeric: {value!r}") from exc
    return -amount if negative else amount


def _add_amounts(left: str, right: str) -> str:
    total = _parse_amount(left or "0", "output", "amount", 0) + _parse_amount(right or "0", "output", "amount", 0)
    return _format_plain(total)


def _format_money(amount: Decimal) -> str:
    return f"${amount:,.2f}"


def _format_plain(amount: Decimal) -> str:
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def _clean_cell(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
