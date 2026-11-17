import tkinter as tk
from tkinter import ttk, messagebox

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from psycopg2 import sql, Error

from library_common import (
    load_config,
    load_field_meta,
    create_connection,
    create_scrolled_tree,
    fill_tree,
    TABLES,
    TYPE_OPERATIONS,
    OVERDUE_FINE_PER_DAY,
)


class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Библиотека — режим администратора")
        self.geometry("1100x700")
        self.minsize(950, 650)

        self.db_config, _ = load_config()
        self.field_meta = load_field_meta()

        self.conn = None
        self.add_entries = {}

        self.create_ui()

        if self.connect_db(show_error=True):
            self.load_table()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ================================================================
    # Подключение к базе данных
    # ================================================================

    def connect_db(self, show_error=False):
        try:
            self.conn = create_connection(self.db_config)
            return True
        except Exception as e:
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

    # ================================================================
    # Интерфейс
    # ================================================================

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

        frame, self.view_tree = create_scrolled_tree(
            self.view_tab,
            height=18
        )
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

        self.add_form = ttk.LabelFrame(
            self.add_tab,
            text="Поля"
        )
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

        self.sql_text.bind(
            "<Control-v>",
            lambda e: self.sql_text.event_generate("<<Paste>>")
        )
        self.sql_text.bind(
            "<Control-V>",
            lambda e: self.sql_text.event_generate("<<Paste>>")
        )
        self.sql_text.bind(
            "<Control-c>",
            lambda e: self.sql_text.event_generate("<<Copy>>")
        )
        self.sql_text.bind(
            "<Control-C>",
            lambda e: self.sql_text.event_generate("<<Copy>>")
        )
        self.sql_text.bind(
            "<Control-x>",
            lambda e: self.sql_text.event_generate("<<Cut>>")
        )
        self.sql_text.bind(
            "<Control-X>",
            lambda e: self.sql_text.event_generate("<<Cut>>")
        )
        self.sql_text.bind(
            "<Control-a>",
            lambda e: self._select_all_sql()
        )
        self.sql_text.bind(
            "<Control-A>",
            lambda e: self._select_all_sql()
        )

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

        frame, self.sql_tree = create_scrolled_tree(
            self.sql_tab,
            height=12
        )
        frame.pack(fill="both", expand=True, padx=10, pady=(5, 5))

        self.sql_status = ttk.Label(
            self.sql_tab,
            text="",
            foreground="gray"
        )
        self.sql_status.pack(anchor="w", padx=10, pady=(0, 10))

    def _select_all_sql(self):
        self.sql_text.tag_add("sel", "1.0", "end")
        return "break"

    # ================================================================
    # Просмотр таблицы
    # ================================================================

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

            fill_tree(self.view_tree, columns, rows)

            self.view_status.config(
                text=f"Таблица: {table}. Показано строк: {len(rows)}."
            )

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка чтения таблицы", str(e))
            self.view_status.config(text="Ошибка чтения.")

    # ================================================================
    # Форма добавления записи
    # ================================================================

    def build_add_form(self):
        for widget in self.add_form.winfo_children():
            widget.destroy()

        self.add_entries.clear()

        table = self.add_table_combo.get()
        fields = self.field_meta.get(table, [])

        for row, field in enumerate(fields):
            label_text = field["label"]

            if field.get("required"):
                label_text += " *"

            ttk.Label(
                self.add_form,
                text=label_text
            ).grid(row=row, column=0, sticky="w", padx=10, pady=5)

            if field.get("name") == "operation_type":
                entry = ttk.Combobox(
                    self.add_form,
                    values=TYPE_OPERATIONS,
                    state="readonly",
                    width=42
                )
                entry.set(TYPE_OPERATIONS[0])
            else:
                entry = ttk.Entry(self.add_form, width=45)

            entry.grid(
                row=row,
                column=1,
                sticky="we",
                padx=10,
                pady=5
            )

            hints = []

            if field.get("type") == "date":
                hints.append("формат: ГГГГ-ММ-ДД")

            if field.get("type") == "int":
                hints.append("целое число")

            if field.get("type") == "numeric":
                hints.append("число, например 50.00")

            ref = field.get("ref")

            if ref:
                ref_table, ref_column = ref
                hints.append(
                    f"существующий ID из {ref_table}.{ref_column}"
                )

            if hints:
                ttk.Label(
                    self.add_form,
                    text=", ".join(hints),
                    foreground="gray"
                ).grid(row=row, column=2, sticky="w", padx=5)

            self.add_entries[field["name"]] = entry

        self.add_form.columnconfigure(1, weight=1)

        if table == "loans":
            extra_frame = ttk.Frame(self.add_form)
            extra_frame.grid(
                row=len(fields),
                column=1,
                sticky="w",
                padx=10,
                pady=5
            )

            ttk.Button(
                extra_frame,
                text="Рассчитать срок возврата",
                command=self.fill_due_date
            ).pack(side="left", padx=(0, 5))

        if table == "operations":
            extra_frame = ttk.Frame(self.add_form)
            extra_frame.grid(
                row=len(fields),
                column=1,
                sticky="w",
                padx=10,
                pady=5
            )

            ttk.Button(
                extra_frame,
                text="Рассчитать штраф за просрочку",
                command=self.fill_overdue_fine
            ).pack(side="left", padx=(0, 5))

            ttk.Button(
                extra_frame,
                text="Рассчитать штраф за потерю/порчу",
                command=self.fill_loss_damage_fine
            ).pack(side="left")

    def clear_add_form(self):
        for name, entry in self.add_entries.items():
            if name == "operation_type":
                entry.set(TYPE_OPERATIONS[0])
            else:
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

    def save_record(self):
        table = self.add_table_combo.get()

        if not table:
            return

        if not self.ensure_connection():
            return

        fields = self.field_meta.get(table, [])
        values = {}

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

            self.view_table_combo.set(table)
            self.load_table()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # ================================================================
    # Автозаполнение операций
    # ================================================================

    def set_operation_fields(self, operation_type, status, amount):
        operation_entry = self.add_entries.get("operation_type")

        if operation_entry is not None:
            if isinstance(operation_entry, ttk.Combobox):
                operation_entry.set(operation_type)
            else:
                operation_entry.delete(0, tk.END)
                operation_entry.insert(0, operation_type)

        status_entry = self.add_entries.get("status")

        if status_entry is not None:
            status_entry.delete(0, tk.END)
            status_entry.insert(0, status)

        amount_entry = self.add_entries.get("amount")

        if amount_entry is not None:
            amount_entry.delete(0, tk.END)
            amount_entry.insert(0, str(amount))

    def fill_due_date(self):
        issue_raw = self.add_entries["issue_date"].get().strip()

        if not issue_raw:
            messagebox.showwarning(
                "Срок возврата",
                "Сначала укажите дату выдачи книги."
            )
            return

        try:
            issue_date = datetime.strptime(issue_raw, "%Y-%m-%d").date()
            due_date = issue_date + timedelta(days=14)

            self.add_entries["due_date"].delete(0, tk.END)
            self.add_entries["due_date"].insert(0, due_date.isoformat())

        except ValueError:
            messagebox.showerror(
                "Ошибка формата",
                "Неверный формат даты выдачи. Используйте формат ГГГГ-ММ-ДД."
            )

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
                cur.execute(
                    """
                    SELECT
                        due_date,
                        COALESCE(return_date, CURRENT_DATE) AS calc_date,
                        GREATEST(
                            COALESCE(return_date, CURRENT_DATE) - due_date,
                            0
                        ) AS overdue_days
                    FROM loans
                    WHERE loan_id = %s
                    """,
                    (loan_id,)
                )
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
                cur.execute(
                    """
                    SELECT e.price
                    FROM loans l
                    JOIN editions e ON e.edition_id = l.edition_id
                    WHERE l.loan_id = %s
                    """,
                    (loan_id,)
                )
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

    # ================================================================
    # Выполнение произвольного SQL
    # ================================================================

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

                    fill_tree(self.sql_tree, columns, rows)

                    status = f"Запрос выполнен. Получено строк: {len(rows)}."
                else:
                    affected = cur.rowcount
                    affected_text = affected if affected >= 0 else "нет данных"

                    fill_tree(
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
    app = AdminApp()
    app.mainloop()