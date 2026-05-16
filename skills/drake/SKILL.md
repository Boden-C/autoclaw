---
name: drake
description: Drake Tax input-page workflow for the local Drake CLI. Use when Codex needs to search Drake page instructions, prepare page-specific CSV payloads, validate totals and field order, and load reviewed forms through the Drake CSV loader UI instead of writing `F1.csv` or `F2.csv` directly.
---

# Drake CLI

Use the local Drake CLI in this folder as the single workflow for Drake entry support.

## Core workflow

1. Search the page instructions before building output.
2. Read the returned page guidance and keep the CSV headers in Drake column order.
3. Write one CSV text block per Drake form.
4. Build one JSON payload with a `forms` array and pass it to `load`.
5. Let the CLI validate the CSV, write the Drake CSV files, and run the loader support.

## Commands

Run from [autoclaw](C:/Users/neoch/Documents/Playground/autoclaw) with Python:

```powershell
python .\skills\drake\drake.py search "W-2"
python .\skills\drake\drake.py search "8949"
```

Load validated forms:

```powershell
@'
{
  "forms": [
    {
      "page": "W-2",
      "csv_text": "item,Wages,Federal Tax wh\nEMPLOYER A,100,10\n"
    }
  ]
}
'@ | python .\skills\drake\drake.py load
```

Use `--no-ui` when you only need the validation summary:

```powershell
@'
{
  "forms": [
    {
      "page": "W-2",
      "csv_text": "item,Wages,Federal Tax wh\nEMPLOYER A,100,10\n"
    }
  ]
}
'@ | python .\skills\drake\drake.py load --no-ui
```

## Payload rules

- Send a JSON object with a non-empty `forms` array.
- Each form needs `page` and `csv_text`.
- The CLI assigns activation keys in order as `F1` through `F12`; do not include the activation key in the payload.
- Keep one form per W-2 and one page payload per page entry screen unless the page instructions say otherwise.
- Include an `item` column when possible so the review UI shows useful labels.
- Only use headers that appear on that page. Unknown headers fail validation.
- Keep headers unique and keep Drake columns spelled exactly as shown in the page instructions.
- The CLI totals numeric columns and warns when no item label column is present.

## Search and page selection

- Search by page name or source topic, then use the exact page key in the load payload.
- Exact page matches also return related pages when they exist, such as `8949` and `8949-DA`.
- If the search result is ambiguous, stop and confirm the target page before writing the payload.

## Review and load

- Read the validation summary before opening the UI and tie the totals to the source workpaper.
- The load UI can reclassify amounts between permitted columns before writing the Drake CSV files.
- The UI writes the assigned `F*.csv` files into this skill folder and starts `csv.ahk` when needed.
- ⚠️ Tell the user exactly which Drake field to click before they trigger the hotkey when the page instructions require a starting field.
- ⚠️ Tell the user to validate the imported totals in Drake after the load completes.

## Environment notes

- Use Python and pip from the current environment. Install missing packages from [requirements.txt](C:/Users/neoch/Documents/Playground/autoclaw/requirements.txt) only when the task is blocked by missing dependencies.
- If the CLI cannot launch because of an environment or permissions issue, say so plainly and continue with review-ready payloads if possible.
