from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import tkinter as tk
from tkinter import messagebox

from .ahk import DRAKE_DIR, ensure_csv_ahk_running
from .models import CsvItem, VALID_ACTIVATION_KEYS, ValidatedForm
from .validate import build_output_csv, settings_header, total_label


try:
    import customtkinter as ctk
except ModuleNotFoundError as exc:  # pragma: no cover - exercised by runtime environment.
    raise RuntimeError("customtkinter is required. Install dependencies from requirements.txt.") from exc


@dataclass(frozen=True)
class DragContext:
    item: CsvItem
    from_column: str


class DrakeLoadApp(ctk.CTk):
    def __init__(self, forms: list[ValidatedForm]):
        super().__init__()
        self.forms = forms
        self.form_keys: dict[str, tk.StringVar] = {}
        self.csv_warning_labels: dict[str, ctk.CTkLabel] = {}
        self.item_columns: dict[tuple[str, int, str], str] = {}
        self.item_widgets: dict[tuple[str, int, str], ctk.CTkFrame] = {}
        self.bucket_frames: dict[tuple[str, str], ctk.CTkFrame] = {}
        self.drag_context: DragContext | None = None
        self.drag_ghost: ctk.CTkFrame | None = None
        self._active_wheel_canvas: tk.Misc | None = None
        self._pending_ghost_move: tuple[int, int] | None = None
        self._ghost_move_scheduled = False

        self.title("Drake CSV Loader")
        self.geometry("1180x760")
        self.minsize(960, 620)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color="#f4f6f8")
        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="#ffffff", corner_radius=0)
        header.pack(fill="x")

        title = ctk.CTkLabel(
            header,
            text="Drake CSV Loader",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#172033",
        )
        title.pack(side="left", padx=18, pady=14)

        load_button = ctk.CTkButton(header, text="Load", width=130, command=self._load_files)
        load_button.pack(side="right", padx=18, pady=14)

        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color="#c6ccd6",
            scrollbar_button_hover_color="#919bad",
        )
        self.scroll.pack(fill="both", expand=True, padx=14, pady=14)
        self._bind_mousewheel(self.scroll)

        for form in self.forms:
            self._build_form_card(form)

    def _build_form_card(self, form: ValidatedForm) -> None:
        card = ctk.CTkFrame(self.scroll, fg_color="#ffffff", corner_radius=8, border_width=1, border_color="#d7dde7")
        card.pack(fill="x", padx=2, pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(top, text=form.page.key, font=ctk.CTkFont(size=16, weight="bold"), text_color="#111827")
        title.grid(row=0, column=0, sticky="w")

        key_var = tk.StringVar(value=form.activation_key)
        self.form_keys[form.page.key] = key_var
        dropdown = ctk.CTkOptionMenu(
            top,
            values=list(VALID_ACTIVATION_KEYS),
            variable=key_var,
            width=90,
            command=lambda _value, page_key=form.page.key: self._refresh_csv_warning(page_key),
        )
        dropdown.grid(row=0, column=1, padx=(12, 0), sticky="e")

        warning = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=12), text_color="#b45309")
        warning.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.csv_warning_labels[form.page.key] = warning
        self._refresh_csv_warning(form.page.key)

        summary = ctk.CTkLabel(
            card,
            text=self._summary_text(form),
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color="#374151",
        )
        summary.grid(row=1, column=0, sticky="ew", padx=14)

        buckets = ctk.CTkScrollableFrame(card, height=270, fg_color="#f8fafc", corner_radius=6)
        buckets.grid(row=2, column=0, sticky="ew", padx=14, pady=12)
        self._bind_mousewheel(buckets)
        for column_index in range(4):
            buckets.grid_columnconfigure(column_index, weight=1, uniform="bucket")

        for index, column in enumerate(form.page.columns):
            row = index // 4
            col = index % 4
            bucket = ctk.CTkFrame(buckets, fg_color="#ffffff", corner_radius=6, border_width=1, border_color="#e1e7ef")
            bucket.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            bucket.grid_columnconfigure(0, weight=1)
            self.bucket_frames[(form.page.key, column)] = bucket
            self._build_bucket(form, column)

    def _build_bucket(self, form: ValidatedForm, column: str) -> None:
        bucket = self.bucket_frames[(form.page.key, column)]
        for child in bucket.winfo_children():
            child.destroy()
        items = self._items_for_column(form, column)
        bucket_total = sum((item.amount for item in items), Decimal("0"))

        label = ctk.CTkLabel(
            bucket,
            text=f"{column}  {self._format_money(bucket_total)}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#111827",
            anchor="w",
        )
        label.pack(fill="x", padx=8, pady=(7, 3))

        if not items:
            empty = ctk.CTkLabel(bucket, text="", height=28, fg_color="#f9fafb", corner_radius=4)
            empty.pack(fill="x", padx=7, pady=(0, 7))
            return

        for item in items:
            self._build_item_row(bucket, form, item)

    def _build_item_row(self, parent: ctk.CTkFrame, form: ValidatedForm, item: CsvItem) -> None:
        key = self._item_key(form, item)
        row = ctk.CTkFrame(parent, fg_color="#eef4ff", corner_radius=5, border_width=1, border_color="#c7d7fe")
        row.pack(fill="x", padx=7, pady=(0, 6))
        row.grid_columnconfigure(0, weight=1)
        self.item_widgets[key] = row

        label = ctk.CTkLabel(row, text=item.label, font=ctk.CTkFont(size=12), text_color="#1f2937", anchor="w")
        label.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=(5, 1))

        amount = ctk.CTkLabel(row, text=self._format_money(item.amount), font=ctk.CTkFont(size=12, weight="bold"), text_color="#0f766e")
        amount.grid(row=1, column=0, sticky="w", padx=(8, 4), pady=(0, 5))

        for widget in (row, label, amount):
            widget.bind("<ButtonPress-1>", lambda event, selected=item: self._start_drag(event, form, selected))
            widget.bind("<B1-Motion>", self._drag_motion)
            widget.bind("<ButtonRelease-1>", lambda event, selected=item: self._end_drag(event, form, selected))

    def _start_drag(self, event: tk.Event, form: ValidatedForm, item: CsvItem) -> None:
        self.drag_context = DragContext(item=item, from_column=self.item_columns[self._item_key(form, item)])
        self.drag_ghost = ctk.CTkFrame(self, fg_color="#2563eb", corner_radius=6)
        self.drag_ghost.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.drag_ghost,
            text=f"{item.label}  {self._format_money(item.amount)}",
            text_color="#ffffff",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=7)
        self._move_ghost(event.x_root, event.y_root)
        self.drag_ghost.lift()

    def _drag_motion(self, event: tk.Event) -> None:
        if self.drag_ghost:
            self._schedule_ghost_move(event.x_root, event.y_root)

    def _end_drag(self, event: tk.Event, form: ValidatedForm, item: CsvItem) -> None:
        target_column = self._column_under_pointer(form, event.x_root, event.y_root)
        if self.drag_ghost:
            self.drag_ghost.destroy()
        self.drag_ghost = None

        if target_column and self.drag_context:
            key = self._item_key(form, item)
            previous_column = self.item_columns.get(key, item.column)
            self.item_columns[key] = target_column
            if previous_column != target_column:
                self._refresh_bucket(form, previous_column)
                self._refresh_bucket(form, target_column)
        self.drag_context = None

    def _load_files(self) -> None:
        try:
            written = []
            for form in self.forms:
                activation_key = self.form_keys[form.page.key].get()
                output_path = DRAKE_DIR / f"{activation_key}.csv"
                output_path.write_text(
                    settings_header(form.page.row_advance) + build_output_csv(form, self._moves_for_form(form)),
                    encoding="utf-8",
                    newline="",
                )
                written.append(output_path.name)
            ahk_status = ensure_csv_ahk_running()
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
            return

        for page_key in self.form_keys:
            self._refresh_csv_warning(page_key)
        messagebox.showinfo(
            "Loaded",
            "Wrote " + ", ".join(written) + f"\n{ahk_status}\nRecommend validating in Drake based on the totals summary.",
        )

    def _moves_for_form(self, form: ValidatedForm) -> dict[tuple[int, str], str]:
        moves = {}
        for item in form.items:
            current_column = self.item_columns[self._item_key(form, item)]
            if current_column != item.column:
                moves[(item.row_index, item.column)] = current_column
        return moves

    def _refresh_bucket(self, form: ValidatedForm, column: str) -> None:
        if (form.page.key, column) in self.bucket_frames:
            self._build_bucket(form, column)

    def _items_for_column(self, form: ValidatedForm, column: str) -> list[CsvItem]:
        items = []
        for item in form.items:
            key = self._item_key(form, item)
            self.item_columns.setdefault(key, item.column)
            if self.item_columns[key] == column:
                items.append(item)
        return items

    def _column_under_pointer(self, form: ValidatedForm, screen_x: int, screen_y: int) -> str | None:
        for column in form.page.columns:
            frame = self.bucket_frames[(form.page.key, column)]
            left = frame.winfo_rootx()
            top = frame.winfo_rooty()
            right = left + frame.winfo_width()
            bottom = top + frame.winfo_height()
            if left <= screen_x <= right and top <= screen_y <= bottom:
                return column
        return None

    def _refresh_csv_warning(self, page_key: str) -> None:
        activation_key = self.form_keys[page_key].get()
        path = DRAKE_DIR / f"{activation_key}.csv"
        label = self.csv_warning_labels[page_key]
        if path.exists():
            label.configure(text=f"Warning: {path.name} already exists and will be overwritten.")
        else:
            label.configure(text=f"{path.name} is available.")

    def _bind_mousewheel(self, frame: ctk.CTkScrollableFrame) -> None:
        canvas = getattr(frame, "_parent_canvas", None)
        if canvas is None:
            return

        def bind_wheel(_event: tk.Event) -> None:
            self._active_wheel_canvas = canvas

        def unbind_wheel(_event: tk.Event) -> None:
            if self._active_wheel_canvas is canvas:
                self._active_wheel_canvas = None

        frame.bind("<Enter>", bind_wheel, add="+")
        frame.bind("<Leave>", unbind_wheel, add="+")
        canvas.bind("<Enter>", bind_wheel, add="+")
        canvas.bind("<Leave>", unbind_wheel, add="+")

    def _on_global_mousewheel(self, event: tk.Event) -> str:
        canvas = self._active_wheel_canvas
        if canvas is None:
            return "break"
        try:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            return "break"
        return "break"

    def _schedule_ghost_move(self, screen_x: int, screen_y: int) -> None:
        self._pending_ghost_move = (screen_x, screen_y)
        if self._ghost_move_scheduled:
            return
        self._ghost_move_scheduled = True
        self.after(16, self._flush_ghost_move)

    def _flush_ghost_move(self) -> None:
        self._ghost_move_scheduled = False
        if not self.drag_ghost or not self._pending_ghost_move:
            return
        screen_x, screen_y = self._pending_ghost_move
        self._pending_ghost_move = None
        self._move_ghost(screen_x, screen_y)

    def _move_ghost(self, screen_x: int, screen_y: int) -> None:
        if not self.drag_ghost:
            return
        self.drag_ghost.place(x=screen_x - self.winfo_rootx() + 10, y=screen_y - self.winfo_rooty() + 10)

    def _summary_text(self, form: ValidatedForm) -> str:
        used = ", ".join(form.output_columns)
        totals = [
            f"{column}: {self._format_money(total)}"
            for column, total in form.column_totals.items()
            if total != 0
        ]
        total_text = " | ".join(totals) if totals else "No non-zero numeric totals."
        return f"Columns used: {used}\n{total_text}\n{total_label(form)}: {self._format_money(form.all_total)}"

    def _item_key(self, form: ValidatedForm, item: CsvItem) -> tuple[str, int, str]:
        return (form.page.key, item.row_index, item.column)

    def _format_money(self, amount: Decimal) -> str:
        return f"${amount:,.2f}"


def launch(forms: list[ValidatedForm]) -> None:
    app = DrakeLoadApp(forms)
    app.mainloop()
