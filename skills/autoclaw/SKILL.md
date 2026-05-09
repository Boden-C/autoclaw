# Autoclaw Skill

Use this repo to inspect and interact with Windows UI elements through `pywinauto` UI Automation. The entry point is `cli.py` and it supports four main workflows: listing windows, dumping the UI tree, finding nodes, acting on a node, and reading node content.

## Setup

Use the project virtual environment if it exists:

```powershell
.\.venv\Scripts\python.exe .\cli.py --help
```

If dependencies are missing, install from `requirements.txt` first.

## Common Commands

List top-level windows:

```powershell
.\.venv\Scripts\python.exe .\cli.py windows
```

Dump a UI tree for the active window:

```powershell
.\.venv\Scripts\python.exe .\cli.py tree
```

Limit traversal depth for speed:

```powershell
.\.venv\Scripts\python.exe .\cli.py tree --max-depth 5
```

Find matching nodes:

```powershell
.\.venv\Scripts\python.exe .\cli.py find --name-contains "Message @Noodles"
```

Act on a matched node:

```powershell
.\.venv\Scripts\python.exe .\cli.py act --name-contains "Message @Noodles" --action set-text --text "hello"
```

Read a node:

```powershell
.\.venv\Scripts\python.exe .\cli.py read --name-contains "Noodles" --mode summary
```

## Window Selection

Most commands accept `--window-title-contains`. Use it when the active window is not the one you want:

```powershell
.\.venv\Scripts\python.exe .\cli.py find --window-title-contains Discord --name-contains "Noodles"
```

If you omit it, the CLI uses the active window.

## Matching Nodes

Selectors are additive:

```powershell
.\.venv\Scripts\python.exe .\cli.py find --name-contains Button --control-type Button --match-index 0
```

Useful filters:

- `--node-id`: exact id from `tree` or `find` output
- `--name-contains`: case-insensitive substring on the UIA name
- `--control-type`: exact UIA control type such as `Button`, `Edit`, or `TabItem`
- `--match-index`: choose among multiple matches
- `--unnamed-only`: only unnamed nodes
- `--actionable-only`: only nodes with real interaction actions

## Actions

Supported `act` actions include:

- `click`
- `click-input`
- `invoke`
- `select`
- `toggle`
- `focus`
- `set-text`
- `append-text`
- `type-keys`
- `send`
- `set-value`
- `expand`
- `collapse`
- `scroll`
- `close`
- `minimize`
- `maximize`
- `restore`

For text entry, use `set-text` when you want to replace the current contents and `append-text` when you want to preserve what is already there.

`send` tries to submit the focused control with Enter.

## Reading Content

`read` supports these modes:

- `auto`
- `children`
- `subtree`
- `summary`
- `texts`
- `value`

Examples:

```powershell
.\.venv\Scripts\python.exe .\cli.py read --name-contains "Message @Noodles" --mode value
.\.venv\Scripts\python.exe .\cli.py read --name-contains "Noodles" --mode texts
```

## Performance Notes

This CLI is limited mostly by UI Automation traversal, not Python alone. The biggest speed wins are:

- Keep `--max-depth` as small as possible.
- Use `find` instead of full tree dumps when you only need one control.
- Use `act --no-after-tree` when you do not need a refreshed tree after the action.
- Keep `--after-tree-depth` small when you do want the refresh.

Examples:

```powershell
.\.venv\Scripts\python.exe .\cli.py act --name-contains "Message @Noodles" --action send --no-after-tree
.\.venv\Scripts\python.exe .\cli.py find --window-title-contains Discord --name-contains "Message @Noodles" --max-depth 6
```

## Practical Workflow

When targeting a control in a complex app:

1. Start with `windows` to confirm the target app is open.
2. Use `find` with a tight `--window-title-contains` and `--max-depth`.
3. If needed, refine with `--control-type` or `--match-index`.
4. Use `act` or `read` on the resolved node id.

