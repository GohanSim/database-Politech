import json
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

import tkinter as tk
from tkinter import ttk

import psycopg2


CONFIG_FILE = "CONFIG.json"
FIELD_META_FILE = "FIELD_META.json"

DB_KEYS = {"dbname", "host", "user", "password", "port"}

DEFAULT_ADMIN_PASSWORD = "admin123"

OVERDUE_FINE_PER_DAY = Decimal("10.00")

TABLES = [
    "publishers",
    "authors",
    "books",
    "editions",
    "readers",
    "loans",
    "operations",
]

TYPE_OPERATIONS = [
    "Выдача книги",
    "Продление срока",
    "Возврат книги",
    "Штраф за просрочку",
    "Штраф за потерю/порчу",
]

OPERATION_STATUSES = [
    "Завершено",
    "В процессе",
    "Начислено",
    "Оплачено",
    "Отменено",
]


def _clean_str(value):
    """Убирает лишние пробелы по краям, если значение строковое."""
    return value.strip() if isinstance(value, str) else value


def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Файл конфигурации '{CONFIG_FILE}' не найден.")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cleaned = {
        str(key).strip(): _clean_str(value)
        for key, value in raw.items()
    }

    db_config = {
        key: cleaned[key]
        for key in DB_KEYS
        if key in cleaned
    }

    admin_password = str(cleaned.get("admin_password", DEFAULT_ADMIN_PASSWORD))

    return db_config, admin_password


def load_field_meta():
    if not os.path.exists(FIELD_META_FILE):
        raise FileNotFoundError(f"Файл метаданных '{FIELD_META_FILE}' не найден.")

    with open(FIELD_META_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    meta = {}

    for table_name, fields in raw.items():
        table_name_clean = str(table_name).strip()
        clean_fields = []

        for field in fields:
            clean_field = {
                str(key).strip(): value
                for key, value in field.items()
            }

            if "name" in clean_field:
                clean_field["name"] = str(clean_field["name"]).strip()

            if "label" in clean_field:
                clean_field["label"] = str(clean_field["label"]).strip()

            if "type" in clean_field:
                clean_field["type"] = str(clean_field["type"]).strip()

            if "ref" in clean_field and isinstance(clean_field["ref"], list):
                clean_field["ref"] = [
                    str(item).strip() for item in clean_field["ref"]
                ]

            clean_fields.append(clean_field)

        meta[table_name_clean] = clean_fields

    return meta


def create_connection(db_config):
    conn = psycopg2.connect(**db_config)
    conn.autocommit = False
    return conn


# Вспомогательные UI-компоненты
def create_scrolled_tree(parent, height=10):
    frame = ttk.Frame(parent)

    tree = ttk.Treeview(
        frame,
        show="headings",
        height=height
    )

    vsb = ttk.Scrollbar(
        frame,
        orient="vertical",
        command=tree.yview
    )

    hsb = ttk.Scrollbar(
        frame,
        orient="horizontal",
        command=tree.xview
    )

    tree.configure(
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set
    )

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")

    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    return frame, tree


def fill_tree(tree, columns, rows):
    tree["columns"] = columns
    tree["show"] = "headings" if columns else "tree"
    tree.delete(*tree.get_children())

    if not columns:
        return

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, stretch=True)

    for row in rows:
        clean_row = [
            "" if value is None else str(value)
            for value in row
        ]
        tree.insert("", "end", values=clean_row)


def create_scrolled_listbox(parent, values=(), height=4):
    frame = ttk.Frame(parent)

    listbox = tk.Listbox(
        frame,
        height=height,
        exportselection=False,
        activestyle="dotbox"
    )

    scrollbar = ttk.Scrollbar(
        frame,
        orient="vertical",
        command=listbox.yview
    )

    listbox.configure(yscrollcommand=scrollbar.set)

    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    for value in values:
        listbox.insert("end", value)

    return frame, listbox


def select_listbox_value(listbox, value):
    values = listbox.get(0, "end")

    listbox.selection_clear(0, "end")

    if value in values:
        index = values.index(value)
        listbox.selection_set(index)
        listbox.see(index)


def get_listbox_value(listbox, default=None):
    selection = listbox.curselection()

    if not selection:
        return default

    return listbox.get(selection[0])


def get_selected_tree_id(tree, id_index=0):
    selected = tree.selection()

    if not selected:
        return None

    values = tree.item(selected[0], "values")

    try:
        return int(values[id_index])
    except (ValueError, TypeError, IndexError):
        return None


def parse_date(value):
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()