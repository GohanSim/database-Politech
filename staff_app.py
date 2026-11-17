import tkinter as tk
from tkinter import ttk, messagebox

from datetime import date, timedelta
from decimal import Decimal

from psycopg2 import Error

from library_common import (
    load_config,
    create_connection,
    create_scrolled_tree,
    create_scrolled_listbox,
    fill_tree,
    select_listbox_value,
    get_listbox_value,
    get_selected_tree_id,
    parse_date,
    OVERDUE_FINE_PER_DAY,
)

ISSUE_STATUSES = [
    "Завершено",
    "В процессе",
]

RETURN_STATUSES = [
    "Завершено",
    "В процессе",
]

FINE_STATUSES = [
    "Начислено",
    "Оплачено",
]


class StaffApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Библиотека — режим работника")
        self.geometry("1150x750")
        self.minsize(1000, 650)

        self.db_config, _ = load_config()
        self.conn = None

        self.create_ui()

        if self.connect_db(show_error=True):
            self.refresh_all()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # Подключение к базе данных
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

    # Интерфейс
    def create_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.reader_tab = ttk.Frame(self.notebook)
        self.issue_tab = ttk.Frame(self.notebook)
        self.return_tab = ttk.Frame(self.notebook)
        self.fine_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.reader_tab, text="Новый читатель")
        self.notebook.add(self.issue_tab, text="Выдача книги")
        self.notebook.add(self.return_tab, text="Возврат книги")
        self.notebook.add(self.fine_tab, text="Штрафы")

        self.create_reader_tab()
        self.create_issue_tab()
        self.create_return_tab()
        self.create_fine_tab()

        self.status = ttk.Label(self, text="")
        self.status.pack(fill="x", padx=8, pady=(0, 8))

    def create_reader_tab(self):
        form = ttk.LabelFrame(
            self.reader_tab,
            text="Данные нового читателя"
        )
        form.pack(fill="both", expand=True, padx=10, pady=10)

        fields = [
            ("ФИО читателя *", "full_name"),
            ("Дата регистрации (ГГГГ-ММ-ДД)", "registration_date"),
            ("Телефон", "phone"),
            ("Email", "email"),
        ]

        self.reader_entries = {}

        for row, (label_text, key) in enumerate(fields):
            ttk.Label(
                form,
                text=label_text
            ).grid(
                row=row,
                column=0,
                sticky="w",
                padx=10,
                pady=5
            )

            entry = ttk.Entry(form, width=45)
            entry.grid(
                row=row,
                column=1,
                sticky="we",
                padx=10,
                pady=5
            )

            self.reader_entries[key] = entry

        self.reader_entries["registration_date"].insert(
            0,
            date.today().isoformat()
        )

        ttk.Button(
            form,
            text="Сохранить читателя",
            command=self.add_reader
        ).grid(
            row=len(fields),
            column=1,
            sticky="w",
            padx=10,
            pady=10
        )

        form.columnconfigure(1, weight=1)

    def create_issue_tab(self):
        self.issue_tab.columnconfigure(0, weight=1)
        self.issue_tab.columnconfigure(1, weight=1)
        self.issue_tab.rowconfigure(0, weight=1)

        reader_frame = ttk.LabelFrame(
            self.issue_tab,
            text="Читатели"
        )
        reader_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=5,
            pady=5
        )

        self.reader_list_frame, self.reader_tree = create_scrolled_tree(
            reader_frame,
            height=16
        )
        self.reader_list_frame.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        edition_frame = ttk.LabelFrame(
            self.issue_tab,
            text="Издания"
        )
        edition_frame.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=5,
            pady=5
        )

        self.edition_list_frame, self.edition_tree = create_scrolled_tree(
            edition_frame,
            height=16
        )
        self.edition_list_frame.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        bottom = ttk.Frame(self.issue_tab)
        bottom.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=5
        )

        self.issue_date_label = ttk.Label(bottom, text="")
        self.issue_date_label.pack(side="left", padx=(5, 15))

        self.issue_due_label = ttk.Label(bottom, text="")
        self.issue_due_label.pack(side="left", padx=(0, 15))

        ttk.Label(
            bottom,
            text="Статус операции:"
        ).pack(side="left", padx=(10, 5))

        self.issue_status_frame, self.issue_status_list = create_scrolled_listbox(
            bottom,
            values=ISSUE_STATUSES,
            height=3
        )
        self.issue_status_frame.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        select_listbox_value(self.issue_status_list, "Завершено")

        ttk.Button(
            bottom,
            text="Выдать книгу",
            command=self.issue_book
        ).pack(side="left", padx=10)

    def create_return_tab(self):
        top = ttk.LabelFrame(
            self.return_tab,
            text="Активные выдачи"
        )
        top.pack(fill="both", expand=True, padx=10, pady=10)

        self.active_loan_frame, self.active_loan_tree = create_scrolled_tree(
            top,
            height=18
        )
        self.active_loan_frame.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        bottom = ttk.Frame(self.return_tab)
        bottom.pack(fill="x", padx=10, pady=5)

        ttk.Label(
            bottom,
            text="Статус операции возврата:"
        ).pack(side="left", padx=(0, 5))

        self.return_status_frame, self.return_status_list = create_scrolled_listbox(
            bottom,
            values=RETURN_STATUSES,
            height=3
        )
        self.return_status_frame.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        select_listbox_value(self.return_status_list, "Завершено")

        ttk.Button(
            bottom,
            text="Вернуть книгу",
            command=self.return_book
        ).pack(side="left", padx=10)

    def create_fine_tab(self):
        self.fine_notebook = ttk.Notebook(self.fine_tab)
        self.fine_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.overdue_tab = ttk.Frame(self.fine_notebook)
        self.loss_tab = ttk.Frame(self.fine_notebook)

        self.fine_notebook.add(self.overdue_tab, text="Штраф за просрочку")
        self.fine_notebook.add(self.loss_tab, text="Штраф за потерю/порчу")

        # Просрочка
        overdue_top = ttk.LabelFrame(
            self.overdue_tab,
            text="Просроченные активные выдачи"
        )
        overdue_top.pack(fill="both", expand=True, padx=8, pady=8)

        self.overdue_frame, self.overdue_tree = create_scrolled_tree(
            overdue_top,
            height=15
        )
        self.overdue_frame.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        overdue_bottom = ttk.Frame(self.overdue_tab)
        overdue_bottom.pack(fill="x", padx=8, pady=5)

        ttk.Label(
            overdue_bottom,
            text="Статус штрафа:"
        ).pack(side="left", padx=(0, 5))

        self.overdue_status_frame, self.overdue_status_list = create_scrolled_listbox(
            overdue_bottom,
            values=FINE_STATUSES,
            height=3
        )
        self.overdue_status_frame.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        select_listbox_value(self.overdue_status_list, "Начислено")

        ttk.Button(
            overdue_bottom,
            text="Назначить штраф за просрочку",
            command=self.assign_overdue_fine
        ).pack(side="left", padx=10)

        # Потеря / порча
        loss_top = ttk.LabelFrame(
            self.loss_tab,
            text="Активные выдачи"
        )
        loss_top.pack(fill="both", expand=True, padx=8, pady=8)

        self.loss_frame, self.loss_tree = create_scrolled_tree(
            loss_top,
            height=15
        )
        self.loss_frame.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        loss_bottom = ttk.Frame(self.loss_tab)
        loss_bottom.pack(fill="x", padx=8, pady=5)

        ttk.Label(
            loss_bottom,
            text="Статус штрафа:"
        ).pack(side="left", padx=(0, 5))

        self.loss_status_frame, self.loss_status_list = create_scrolled_listbox(
            loss_bottom,
            values=FINE_STATUSES,
            height=3
        )
        self.loss_status_frame.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        select_listbox_value(self.loss_status_list, "Начислено")

        ttk.Button(
            loss_bottom,
            text="Назначить штраф за потерю/порчу",
            command=self.assign_loss_damage_fine
        ).pack(side="left", padx=10)

    # Обновление данных
    def refresh_all(self):
        if not self.conn:
            self.status.config(text="Нет подключения к базе данных.")
            return

        self.update_date_labels()
        self.refresh_readers()
        self.refresh_editions()
        self.refresh_active_loans()
        self.refresh_overdue_loans()
        self.refresh_loss_loans()

        self.status.config(
            text=f"Данные обновлены: {date.today().isoformat()}"
        )

    def update_date_labels(self):
        issue_date = date.today()
        due_date = issue_date + timedelta(days=14)

        self.issue_date_label.config(
            text=f"Дата выдачи: {issue_date.isoformat()}"
        )
        self.issue_due_label.config(
            text=f"Срок возврата: {due_date.isoformat()}"
        )

    def fetch_all(self, query, params=None, show_error=True):
        if not self.ensure_connection():
            return None

        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

            self.conn.commit()
            return rows

        except Error as e:
            self.safe_rollback()

            if show_error:
                messagebox.showerror("Ошибка PostgreSQL", str(e))

            return None

    def refresh_readers(self):
        rows = self.fetch_all(
            """
            SELECT
                reader_id,
                full_name,
                phone,
                email
            FROM readers
            ORDER BY full_name
            """
        )

        if rows is not None:
            fill_tree(
                self.reader_tree,
                ["Номер", "ФИО", "Телефон", "Email"],
                rows
            )

    def refresh_editions(self):
        rows = self.fetch_all(
            """
            SELECT
                e.edition_id,
                e.title AS edition_title,
                b.title AS book_title,
                a.full_name AS author,
                p.name AS publisher,
                e.publication_year,
                e.storage_location,
                e.quantity - COALESCE(active_loans.cnt, 0) AS available
            FROM editions e
            JOIN books b ON b.book_id = e.book_id
            JOIN authors a ON a.author_id = b.author_id
            JOIN publishers p ON p.publisher_id = e.publisher_id
            LEFT JOIN (
                SELECT
                    edition_id,
                    COUNT(*) AS cnt
                FROM loans
                WHERE return_date IS NULL
                GROUP BY edition_id
            ) active_loans ON active_loans.edition_id = e.edition_id
            ORDER BY e.title
            """
        )

        if rows is not None:
            fill_tree(
                self.edition_tree,
                [
                    "Номер",
                    "Издание",
                    "Книга",
                    "Автор",
                    "Издатель",
                    "Год",
                    "Место хранения",
                    "Доступно",
                ],
                rows
            )

    def refresh_active_loans(self):
        rows = self.fetch_all(
            """
            SELECT
                l.loan_id,
                r.full_name,
                e.title,
                l.issue_date,
                l.due_date,
                GREATEST(CURRENT_DATE - l.due_date, 0) AS overdue_days
            FROM loans l
            JOIN readers r ON r.reader_id = l.reader_id
            JOIN editions e ON e.edition_id = l.edition_id
            WHERE l.return_date IS NULL
            ORDER BY l.due_date, l.loan_id
            """
        )

        if rows is not None:
            fill_tree(
                self.active_loan_tree,
                [
                    "Номер",
                    "Читатель",
                    "Издание",
                    "Дата выдачи",
                    "Срок возврата",
                    "Дней просрочки",
                ],
                rows
            )

    def refresh_overdue_loans(self):
        rows = self.fetch_all(
            """
            SELECT
                l.loan_id,
                r.full_name,
                e.title,
                l.due_date,
                CURRENT_DATE - l.due_date AS overdue_days,
                (CURRENT_DATE - l.due_date) * 10.00 AS fine_amount
            FROM loans l
            JOIN readers r ON r.reader_id = l.reader_id
            JOIN editions e ON e.edition_id = l.edition_id
            WHERE
                l.return_date IS NULL
                AND l.due_date < CURRENT_DATE
            ORDER BY l.due_date, l.loan_id
            """
        )

        if rows is not None:
            fill_tree(
                self.overdue_tree,
                [
                    "Номер",
                    "Читатель",
                    "Издание",
                    "Срок возврата",
                    "Дней просрочки",
                    "Сумма штрафа",
                ],
                rows
            )

    def refresh_loss_loans(self):
        rows = self.fetch_all(
            """
            SELECT
                l.loan_id,
                r.full_name,
                e.title,
                COALESCE(e.price, 0) AS price
            FROM loans l
            JOIN readers r ON r.reader_id = l.reader_id
            JOIN editions e ON e.edition_id = l.edition_id
            WHERE l.return_date IS NULL
            ORDER BY r.full_name, l.loan_id
            """
        )

        if rows is not None:
            fill_tree(
                self.loss_tree,
                [
                    "Номер",
                    "Читатель",
                    "Издание",
                    "Стоимость издания",
                ],
                rows
            )

    # Добавление читателя
    def add_reader(self):
        full_name = self.reader_entries["full_name"].get().strip()

        if not full_name:
            messagebox.showwarning(
                "Новый читатель",
                "Укажите ФИО читателя."
            )
            return

        registration_raw = self.reader_entries["registration_date"].get().strip()

        if not registration_raw:
            registration_raw = date.today().isoformat()

        try:
            registration_date = parse_date(registration_raw)
        except ValueError:
            messagebox.showerror(
                "Ошибка формата",
                "Дата регистрации должна быть в формате ГГГГ-ММ-ДД."
            )
            return

        phone = self.reader_entries["phone"].get().strip() or None
        email = self.reader_entries["email"].get().strip() or None

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO readers (
                        full_name,
                        registration_date,
                        phone,
                        email
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING reader_id
                    """,
                    (
                        full_name,
                        registration_date,
                        phone,
                        email
                    )
                )

                reader_id = cur.fetchone()[0]

            self.conn.commit()

            messagebox.showinfo(
                "Новый читатель",
                f"Читатель добавлен.\n\nНомер читателя: {reader_id}"
            )

            self.reader_entries["full_name"].delete(0, tk.END)
            self.reader_entries["phone"].delete(0, tk.END)
            self.reader_entries["email"].delete(0, tk.END)

            self.reader_entries["registration_date"].delete(0, tk.END)
            self.reader_entries["registration_date"].insert(
                0,
                date.today().isoformat()
            )

            self.status.config(
                text=f"Добавлен читатель: {full_name}"
            )

            self.refresh_readers()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # Выдача книги
    def issue_book(self):
        reader_id = get_selected_tree_id(self.reader_tree)

        if reader_id is None:
            messagebox.showwarning(
                "Выдача книги",
                "Выберите читателя из списка."
            )
            return

        edition_id = get_selected_tree_id(self.edition_tree)

        if edition_id is None:
            messagebox.showwarning(
                "Выдача книги",
                "Выберите издание из списка."
            )
            return

        status = get_listbox_value(
            self.issue_status_list,
            default="Завершено"
        )

        issue_date = date.today()
        due_date = issue_date + timedelta(days=14)

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        e.quantity - COALESCE(active_loans.cnt, 0) AS available
                    FROM editions e
                    LEFT JOIN (
                        SELECT
                            edition_id,
                            COUNT(*) AS cnt
                        FROM loans
                        WHERE return_date IS NULL
                        GROUP BY edition_id
                    ) active_loans ON active_loans.edition_id = e.edition_id
                    WHERE e.edition_id = %s
                    """,
                    (edition_id,)
                )

                row = cur.fetchone()

                if row is None:
                    self.safe_rollback()
                    messagebox.showerror(
                        "Ошибка выдачи",
                        "Выбранное издание не найдено."
                    )
                    return

                available = int(row[0]) if row[0] is not None else 0

                if available <= 0:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Выдача книги",
                        "Выбранное издание сейчас недоступно."
                    )
                    return

                cur.execute(
                    """
                    INSERT INTO loans (
                        edition_id,
                        reader_id,
                        issue_date,
                        return_date,
                        due_date,
                        extensions
                    )
                    VALUES (%s, %s, %s, NULL, %s, 0)
                    RETURNING loan_id
                    """,
                    (
                        edition_id,
                        reader_id,
                        issue_date,
                        due_date
                    )
                )

                loan_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO operations (
                        loan_id,
                        operation_type,
                        status,
                        amount
                    )
                    VALUES (%s, %s, %s, NULL)
                    """,
                    (
                        loan_id,
                        "Выдача книги",
                        status
                    )
                )

            self.conn.commit()

            messagebox.showinfo(
                "Выдача книги",
                f"Книга выдана.\n\n"
                f"Номер выдачи: {loan_id}\n"
                f"Дата выдачи: {issue_date.isoformat()}\n"
                f"Срок возврата: {due_date.isoformat()}"
            )

            self.status.config(
                text=f"Выдана книга. Номер Выдачи : {loan_id}"
            )

            self.refresh_all()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # Возврат книг
    def return_book(self):
        loan_id = get_selected_tree_id(self.active_loan_tree)

        if loan_id is None:
            messagebox.showwarning(
                "Возврат книги",
                "Выберите активную выдачу из списка."
            )
            return

        status = get_listbox_value(
            self.return_status_list,
            default="Завершено"
        )

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT due_date
                    FROM loans
                    WHERE loan_id = %s
                      AND return_date IS NULL
                    FOR UPDATE
                    """,
                    (loan_id,)
                )

                row = cur.fetchone()

                if row is None:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Возврат книги",
                        "Выбранная выдача не найдена или уже закрыта."
                    )
                    return

                due_date = row[0]
                return_date = date.today()

                cur.execute(
                    """
                    UPDATE loans
                    SET return_date = %s
                    WHERE loan_id = %s
                    """,
                    (
                        return_date,
                        loan_id
                    )
                )

                cur.execute(
                    """
                    INSERT INTO operations (
                        loan_id,
                        operation_type,
                        status,
                        amount
                    )
                    VALUES (%s, %s, %s, NULL)
                    """,
                    (
                        loan_id,
                        "Возврат книги",
                        status
                    )
                )

                overdue_days = (return_date - due_date).days
                fine_added = False

                if overdue_days > 0:
                    fine_amount = Decimal(overdue_days) * OVERDUE_FINE_PER_DAY

                    answer = messagebox.askyesno(
                        "Просрочка",
                        f"Книга возвращена с просрочкой.\n"
                        f"Дней просрочки: {overdue_days}\n"
                        f"Сумма штрафа: {fine_amount} руб.\n\n"
                        "Назначить штраф за просрочку?"
                    )

                    if answer:
                        cur.execute(
                            """
                            INSERT INTO operations (
                                loan_id,
                                operation_type,
                                status,
                                amount
                            )
                            VALUES (%s, %s, %s, %s)
                            """,
                            (
                                loan_id,
                                "Штраф за просрочку",
                                "Начислено",
                                fine_amount
                            )
                        )
                        fine_added = True

            self.conn.commit()

            message = f"Книга возвращена.\n\nНомер выдачи: {loan_id}"

            if overdue_days > 0 and fine_added:
                message += f"\n\nНазначен штраф за просрочку: {fine_amount} руб."

            messagebox.showinfo(
                "Возврат книги",
                message
            )

            self.status.config(
                text=f"Возврат книги. Номер Выдачи: {loan_id}"
            )

            self.refresh_all()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # Штраф за просрочку
    def assign_overdue_fine(self):
        loan_id = get_selected_tree_id(self.overdue_tree)

        if loan_id is None:
            messagebox.showwarning(
                "Штраф за просрочку",
                "Выберите просроченную выдачу из списка."
            )
            return

        status = get_listbox_value(
            self.overdue_status_list,
            default="Начислено"
        )

        if not self.ensure_connection():
            return

        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT due_date
                    FROM loans
                    WHERE loan_id = %s
                      AND return_date IS NULL
                      AND due_date < CURRENT_DATE
                    FOR UPDATE
                    """,
                    (loan_id,)
                )

                row = cur.fetchone()

                if row is None:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Штраф за просрочку",
                        "Просроченная выдача не найдена."
                    )
                    return

                due_date = row[0]
                overdue_days = (date.today() - due_date).days

                if overdue_days <= 0:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Штраф за просрочку",
                        "По выбранной выдаче нет просрочки."
                    )
                    return

                fine_amount = Decimal(overdue_days) * OVERDUE_FINE_PER_DAY

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM operations
                    WHERE loan_id = %s
                      AND operation_type = 'Штраф за просрочку'
                    """,
                    (loan_id,)
                )

                already_exists = cur.fetchone()[0] > 0

                if already_exists:
                    answer = messagebox.askyesno(
                        "Штраф уже существует",
                        "По этой выдаче уже есть штраф за просрочку.\n\n"
                        "Добавить еще один штраф?"
                    )

                    if not answer:
                        self.safe_rollback()
                        return

                cur.execute(
                    """
                    INSERT INTO operations (
                        loan_id,
                        operation_type,
                        status,
                        amount
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        loan_id,
                        "Штраф за просрочку",
                        status,
                        fine_amount
                    )
                )

            self.conn.commit()

            messagebox.showinfo(
                "Штраф за просрочку",
                f"Штраф назначен.\n\n"
                f"Номер выдачи: {loan_id}\n"
                f"Дней просрочки: {overdue_days}\n"
                f"Сумма: {fine_amount} руб."
            )

            self.status.config(
                text=f"Назначен штраф за просрочку по номеру выдачи: {loan_id}"
            )

            self.refresh_all()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # Штраф за потерю / порчу
    def assign_loss_damage_fine(self):
        loan_id = get_selected_tree_id(self.loss_tree)

        if loan_id is None:
            messagebox.showwarning(
                "Штраф за потерю/порчу",
                "Выберите активную выдачу из списка."
            )
            return

        status = get_listbox_value(
            self.loss_status_list,
            default="Начислено"
        )

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
                      AND l.return_date IS NULL
                    """,
                    (loan_id,)
                )

                row = cur.fetchone()

                if row is None:
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Штраф за потерю/порчу",
                        "Активная выдача не найдена."
                    )
                    return

                price = row[0] if row[0] is not None else Decimal("0.00")
                fine_amount = Decimal(str(price))

                if fine_amount <= Decimal("0.00"):
                    self.safe_rollback()
                    messagebox.showwarning(
                        "Штраф за потерю/порчу",
                        "Стоимость издания равна 0.\n"
                        "Сначала укажите стоимость издания в режиме администратора."
                    )
                    return

                cur.execute(
                    """
                    INSERT INTO operations (
                        loan_id,
                        operation_type,
                        status,
                        amount
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        loan_id,
                        "Штраф за потерю/порчу",
                        status,
                        fine_amount
                    )
                )

            self.conn.commit()

            messagebox.showinfo(
                "Штраф за потерю/порчу",
                f"Штраф назначен.\n\n"
                f"Номер выдачи: {loan_id}\n"
                f"Сумма: {fine_amount} руб."
            )

            self.status.config(
                text=f"Назначен штраф за потерю/порчу по номеру выдачи: {loan_id}"
            )

            self.refresh_all()

        except Error as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка PostgreSQL", str(e))

        except Exception as e:
            self.safe_rollback()
            messagebox.showerror("Ошибка", str(e))

    # Закрытие
    def on_close(self):
        try:
            if self.conn and not self.conn.closed:
                self.conn.close()
        except Exception:
            pass

        self.destroy()

if __name__ == "__main__":
    app = StaffApp()
    app.mainloop()