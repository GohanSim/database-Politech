import tkinter as tk
from tkinter import ttk, messagebox

import psycopg2
from psycopg2 import sql, Error

from datetime import datetime
from decimal import Decimal, InvalidOperation

import json

OVERDUE_FINE_PER_DAY = Decimal("10.00")

with open('CONFIG.json') as c:
    raw_conf = json.load(c)
    # Убираем пробелы в ключах и значениях, если они есть
    conf = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in raw_conf.items()}

with open('FIELD_META.json', 'r', encoding = 'utf-8') as f:
    field_meta = json.load(f)

TABLES = [
    "publishers",
    "authors",
    "books",
    "editions",
    "readers",
    "loans",
    "operations",
]

class LibraryApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("База данных библиотеки")
        self.geometry("1200x800")
        self.minsize(900, 600)

        self.conn = None
        self.add_entries = {}

        self.create_ui()
        self.connect_db(show_error=True)

        if self.conn:
            self.load_table()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # Работа с подключение
    def connect_db(self, show_error=False):
        try:
            self.conn = psycopg2.connect(**conf)
            self.conn.autocommit = False
            return True
        except Error as e:
            if show_error:
                messagebox.showerror(
                    "Ошибка подключения",
                    f"Не удалось подключиться к базе данных:\n\n{e}"
                )
            self.conn = None
            return False

    def ensure_connection(self):
        if self.conn is None or self.conn.closed:
            return self.connect_db(show_error=True)
        return True

    def safe_rollback(self):
        try:
            if self.conn and not self.conn.closed:
                self.conn.rollback()
        except Exception:
            pass

    # Интерфейс
    def create_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.view_tab = ttk.Frame(self.notebook)
        self.add_tab = ttk.Frame(self.notebook)
        self.sql_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.view_tab, text="Просмотр базы")
        self.notebook.add(self.add_tab, text="Добавление данных")
        self.notebook.add(self.sql_tab, text="SQL запрос")

        self.create_view_tab()
        self.create_add_tab()
        self.create_sql_tab()

    def create_scrolled_tree(self, parent):
        frame = ttk.Frame(parent)

        tree = ttk.Treeview(frame, show="headings")

        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)

        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        return frame, tree

    def create_view_tab(self):
        top = ttk.Frame(self.view_tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Таблица:").pack(side="left")

        self.view_table_combo = ttk.Combobox(
            top,
            values=TABLES,
            state="readonly",
            width=20
        )
        self.view_table_combo.pack(side="left", padx=5)
        self.view_table_combo.bind("<<ComboboxSelected>>", self.load_table)

        ttk.Button(
            top,
            text="Обновить",
            command=self.load_table
        ).pack(side="left", padx=5)

        frame, self.view_tree = self.create_scrolled_tree(self.view_tab)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        self.view_status = ttk.Label(
            self.view_tab,
            text="",
            foreground="black"
        )
        self.view_status.pack(anchor="w", padx=10, pady=(0, 10))

        self.view_table_combo.set(TABLES[0])

    def create_add_tab(self):
        top = ttk.Frame(self.add_tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Таблица:").pack(side="left")

        self.add_table_combo = ttk.Combobox(
            top,
            values=TABLES,
            state="readonly",
            width=20
        )
        self.add_table_combo.pack(side="left", padx=5)
        self.add_table_combo.bind(
            "<<ComboboxSelected>>",
            lambda event: self.build_add_form()
        )

        ttk.Button(
            top,
            text="Очистить поля",
            command=self.clear_add_form
        ).pack(side="left", padx=5)

        self.add_form = ttk.LabelFrame(self.add_tab, text="Поля")
        self.add_form.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        buttons = ttk.Frame(self.add_tab)
        buttons.pack(fill="x", padx=10, pady=(0, 5))

        ttk.Button(
            buttons,
            text="Сохранить запись",
            command=self.save_record
        ).pack(side="left")

        self.add_status = ttk.Label(
            self.add_tab,
            text="",
            foreground="black"
        )
        self.add_status.pack(anchor="w", padx=10, pady=(0, 10))

        self.add_table_combo.set(TABLES[0])
        self.build_add_form()

    def create_sql_tab(self):
        ttk.Label(
            self.sql_tab,
            text="Введите SQL запрос и нажмите «Выполнить»:"
        ).pack(anchor="w", padx=10, pady=(10, 0))

        text_frame = ttk.Frame(self.sql_tab)
        text_frame.pack(fill="x", padx=10, pady=5)

        self.sql_text = tk.Text(
            text_frame,
            height=8,
            wrap="none",
            font=("Consolas", 10)
        )

        self.sql_text.bind("<Control-v>", lambda e: self.sql_text.event_generate("<<Paste>>"))
        self.sql_text.bind("<Control-V>", lambda e: self.sql_text.event_generate("<<Paste>>"))
        self.sql_text.bind("<Control-c>", lambda e: self.sql_text.event_generate("<<Copy>>"))
        self.sql_text.bind("<Control-C>", lambda e: self.sql_text.event_generate("<<Copy>>"))
        self.sql_text.bind("<Control-x>", lambda e: self.sql_text.event_generate("<<Cut>>"))
        self.sql_text.bind("<Control-X>", lambda e: self.sql_text.event_generate("<<Cut>>"))
        self.sql_text.bind("<Control-a>", lambda e: self._select_all_sql())
        self.sql_text.bind("<Control-A>", lambda e: self._select_all_sql())

        sql_scroll = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.sql_text.yview
        )

        self.sql_text.configure(yscrollcommand=sql_scroll.set)

        self.sql_text.pack(side="left", fill="both", expand=True)
        sql_scroll.pack(side="right", fill="y")

        self.sql_text.insert("1.0", "SELECT * FROM publishers;")

        buttons = ttk.Frame(self.sql_tab)
        buttons.pack(fill="x", padx=10, pady=5)

        ttk.Button(
            buttons,
            text="Выполнить",
            command=self.execute_sql
        ).pack(side="left")

        ttk.Button(
            buttons,
            text="Очистить",
            command=self.clear_sql
        ).pack(side="left", padx=5)

        frame, self.sql_tree = self.create_scrolled_tree(self.sql_tab)
        frame.pack(fill="both", expand=True, padx=10, pady=(5, 5))

        self.sql_status = ttk.Label(
            self.sql_tab,
            text="",
            foreground="gray"
        )
        self.sql_status.pack(anchor="w", padx=10, pady=(0, 10))

    # Общие методы для таблиц
    def fill_tree(self, tree, columns, rows):
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

    # Просмотр таблицы
    def load_table(self, event=None):
        table = self.view_table_combo.get()

        if not table:
            return

        if not self.ensure_connection():
            self.view_status.config(text="Нет подключения к базе данных.")
            return

        try:
            with self.conn.cursor() as cur:
                query = sql.SQL(
                    "SELECT * FROM {} ORDER BY 1"
                ).format(sql.Identifier(table))

                cur.execute(query)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

            self.conn.commit()

            self.fill_tree(self.view_tree, columns, rows)
            self.view_status.config(
                text=f"Таблица: {table}. Показано строк: {len(rows)}."
            )

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка чтения таблицы", str(e))
            self.view_status.config(text="Ошибка чтения.")

    # Форма добавления записи
    def build_add_form(self):
        for widget in self.add_form.winfo_children():
            widget.destroy()

        self.add_entries.clear()

        table = self.add_table_combo.get()
        fields = field_meta.get(table, [])

        for row, field in enumerate(fields):
            label_text = field["label"]
            if field.get("required"):
                label_text += " *"

            ttk.Label(
                self.add_form,
                text=label_text
            ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

            entry = ttk.Entry(self.add_form, width=45)
            entry.grid(row=row, column=1, sticky="we", padx=10, pady=5)

            hints = []

            if field.get("type") == "date":
                hints.append("формат: ГГГГ-ММ-ДД")

            if field.get("type") == "int":
                hints.append("целое число")

            if field.get("type") == "numeric":
                hints.append("число, например 50.00")

            if field.get("ref"):
                ref_table, ref_column = field["ref"]
                hints.append(f"существующий ID из {ref_table}.{ref_column}")

            if hints:
                ttk.Label(
                    self.add_form,
                    text=", ".join(hints),
                    foreground="gray"
                ).grid(row=row, column=2, sticky="w", padx=5)

            self.add_entries[field["name"]] = entry

        self.add_form.columnconfigure(1, weight=1)

        if table == "operations":
            fine_frame = ttk.Frame(self.add_form)
            fine_frame.grid(
                row=len(fields),
                column=1,
                sticky="w",
                padx=10,
                pady=5
            )

            ttk.Button(
                fine_frame,
                text="Рассчитать штраф за просрочку",
                command=self.fill_overdue_fine
            ).pack(side="left", padx=(0, 5))

            ttk.Button(
                fine_frame,
                text="Рассчитать штраф за потерю/порчу",
                command=self.fill_loss_damage_fine
            ).pack(side="left")

        self.add_form.columnconfigure(1, weight=1)

    def clear_add_form(self):
        for entry in self.add_entries.values():
            entry.delete(0, tk.END)

    def parse_field(self, field, raw_value):
        if raw_value == "":
            if field.get("required"):
                raise ValueError(
                    f"Поле '{field['label']}' обязательно для заполнения."
                )
            return None

        field_type = field.get("type", "str")

        try:
            if field_type == "int":
                return int(raw_value)

            if field_type == "numeric":
                return Decimal(raw_value.replace(",", "."))

            if field_type == "date":
                return datetime.strptime(raw_value, "%Y-%m-%d").date()

            return raw_value

        except (ValueError, TypeError, InvalidOperation):
            raise ValueError(
                f"Неверный формат поля '{field['label']}'."
            )

    def foreign_key_exists(self, cur, ref_table, ref_column, value):
        query = sql.SQL(
            "SELECT 1 FROM {} WHERE {} = %s LIMIT 1"
        ).format(
            sql.Identifier(ref_table),
            sql.Identifier(ref_column)
        )

        cur.execute(query, (value,))
        return cur.fetchone() is not None

    # Добавление записи с проверкой зависимостей
    def save_record(self):
        table = self.add_table_combo.get()

        if not table:
            return

        if not self.ensure_connection():
            return

        fields = field_meta.get(table, [])
        values = {}

        # Проверка и преобразование значений
        try:
            for field in fields:
                raw_value = self.add_entries[field["name"]].get().strip()
                values[field["name"]] = self.parse_field(field, raw_value)

        except ValueError as e:
            messagebox.showerror("Ошибка ввода", str(e))
            return

        try:
            with self.conn.cursor() as cur:
                # Проверка внешних ключей
                for field in fields:
                    value = values.get(field["name"])
                    ref = field.get("ref")

                    if value is not None and ref:
                        ref_table, ref_column = ref

                        if not self.foreign_key_exists(
                            cur,
                            ref_table,
                            ref_column,
                            value
                        ):
                            self.safe_rollback()
                            messagebox.showerror(
                                "Ошибка зависимости",
                                "Указан несуществующий связанный ID.\n\n"
                                f"Таблица: {ref_table}\n"
                                f"Поле: {ref_column}\n"
                                f"Значение: {value}\n\n"
                                "Добавление записи прервано."
                            )
                            return

                # Подготовка вставки
                columns = [
                    field["name"]
                    for field in fields
                    if values.get(field["name"]) is not None
                ]

                if not columns:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Нет данных",
                        "Не заполнено ни одного поля."
                    )
                    return

                params = [values[col] for col in columns]

                query = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({}) RETURNING *"
                ).format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, columns)),
                    sql.SQL(", ").join([sql.Placeholder()] * len(columns))
                )

                cur.execute(query, params)
                inserted = cur.fetchone()

                self.conn.commit()

                inserted_id = inserted[0] if inserted else "OK"

                self.add_status.config(
                    text=f"Запись добавлена в таблицу '{table}'."
                )

                messagebox.showinfo(
                    "Успех",
                    f"Запись успешно добавлена.\n\n"
                    f"Таблица: {table}\n"
                    f"Новый идентификатор: {inserted_id}"
                )

                self.clear_add_form()

                # Автоматически обновляем просмотр этой таблицы
                self.view_table_combo.set(table)
                self.load_table()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    def set_operation_fields(self, operation_type, status, amount):
        self.add_entries["operation_type"].delete(0, tk.END)
        self.add_entries["operation_type"].insert(0, operation_type)

        self.add_entries["status"].delete(0, tk.END)
        self.add_entries["status"].insert(0, status)

        self.add_entries["amount"].delete(0, tk.END)
        self.add_entries["amount"].insert(0, str(amount))

    def fill_overdue_fine(self):
        loan_id_raw = self.add_entries["loan_id"].get().strip()

        if not loan_id_raw:
            messagebox.showwarning(
                "Штраф за просрочку",
                "Сначала укажите ID выдачи (loan_id)."
            )
            return

        try:
            loan_id = int(loan_id_raw)
        except ValueError:
            messagebox.showerror(
                "Ошибка ввода",
                "ID выдачи должен быть целым числом."
            )
            return

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        due_date,
                        COALESCE(return_date, CURRENT_DATE) AS calc_date,
                        GREATEST(
                            COALESCE(return_date, CURRENT_DATE) - due_date,
                            0
                        ) AS overdue_days
                    FROM loans
                    WHERE loan_id = %s
                """, (loan_id,))

                row = cur.fetchone()

            self.conn.commit()

            if row is None:
                messagebox.showerror(
                    "Ошибка зависимости",
                    "Выдача с таким loan_id не найдена."
                )
                return

            overdue_days = int(row[2])
            amount = Decimal(overdue_days) * OVERDUE_FINE_PER_DAY

            self.set_operation_fields(
                "Штраф за просрочку",
                "Начислено",
                amount
            )

            messagebox.showinfo(
                "Штраф за просрочку",
                f"Дней просрочки: {overdue_days}\n"
                f"Сумма штрафа: {amount} руб."
            )

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

    def fill_loss_damage_fine(self):
        loan_id_raw = self.add_entries["loan_id"].get().strip()

        if not loan_id_raw:
            messagebox.showwarning(
                "Штраф за потерю/порчу",
                "Сначала укажите ID выдачи (loan_id)."
            )
            return

        try:
            loan_id = int(loan_id_raw)
        except ValueError:
            messagebox.showerror(
                "Ошибка ввода",
                "ID выдачи должен быть целым числом."
            )
            return

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT e.price
                    FROM loans l
                    JOIN editions e ON e.edition_id = l.edition_id
                    WHERE l.loan_id = %s
                """, (loan_id,))

                row = cur.fetchone()

            self.conn.commit()

            if row is None:
                messagebox.showerror(
                    "Ошибка зависимости",
                    "Выдача с таким loan_id не найдена."
                )
                return

            amount = row[0] if row[0] is not None else Decimal("0.00")

            self.set_operation_fields(
                "Штраф за потерю/порчу",
                "Начислено",
                amount
            )

            if amount <= Decimal("0.00"):
                messagebox.showwarning(
                    "Штраф за потерю/порчу",
                    "Стоимость издания равна 0.\n"
                    "Проверьте поле 'Стоимость экземпляра' в таблице editions."
                )
            else:
                messagebox.showinfo(
                    "Штраф за потерю/порчу",
                    f"Сумма штрафа: {amount} руб."
                )

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

    # Выполнение произвольного SQL
    def execute_sql(self):
        query = self.sql_text.get("1.0", "end").strip()

        if not query:
            messagebox.showinfo("SQL запрос", "Введите SQL запрос.")
            return

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute(query)

                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()

                    self.fill_tree(self.sql_tree, columns, rows)

                    status = f"Запрос выполнен. Получено строк: {len(rows)}."
                else:
                    affected = cur.rowcount
                    affected_text = affected if affected >= 0 else "нет данных"

                    self.fill_tree(
                        self.sql_tree,
                        ["Результат"],
                        [[f"Запрос выполнен. Затронуто строк: {affected_text}."]]
                    )

                    status = "Запрос выполнен."

                self.conn.commit()
                self.sql_status.config(text=status)

        except Error as e:
            self.safe_rollback()
            self.sql_status.config(text="Ошибка SQL.")
            messagebox.showerror("Ошибка SQL", str(e))

        except Exception as e:
            self.safe_rollback()
            self.sql_status.config(text="Ошибка.")
            messagebox.showerror("Ошибка", str(e))

    def clear_sql(self):
        self.sql_text.delete("1.0", "end")

    def on_close(self):
        try:
            if self.conn and not self.conn.closed:
                self.conn.close()
        except Exception:
            pass

        self.destroy()


if __name__ == "__main__":
    app = LibraryApp()
    app.mainloop()