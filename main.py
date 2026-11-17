import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from library_common import load_config

from admin_app import AdminApp
from staff_app import StaffApp


class ModeSelector(tk.Tk):
    def __init__(self, admin_password):
        super().__init__()

        self.admin_password = admin_password

        self.title("Библиотека — выбор режима")
        self.geometry("480x240")
        self.resizable(False, False)

        self.create_ui()

    def create_ui(self):
        ttk_label_title = tk.Label(
            self,
            text="Выберите режим работы",
            font=("Segoe UI", 14, "bold")
        )
        ttk_label_title.pack(pady=(20, 10))

        password_frame = tk.Frame(self)
        password_frame.pack(fill="x", padx=25)

        tk.Label(
            password_frame,
            text="Пароль администратора:"
        ).pack(anchor="w")

        self.password_entry = tk.Entry(
            password_frame,
            show="*",
            width=35
        )
        self.password_entry.pack(fill="x", pady=(3, 10))
        self.password_entry.bind("<Return>", lambda event: self.open_admin())

        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)

        ttk.Button(
            button_frame,
            text="Режим администратора",
            width=22,
            command=self.open_admin
        ).pack(side="left", padx=8)

        ttk.Button(
            button_frame,
            text="Режим работника",
            width=22,
            command=self.open_staff
        ).pack(side="left", padx=8)

    def open_admin(self):
        password = self.password_entry.get()

        if password != self.admin_password:
            messagebox.showerror(
                "Ошибка входа",
                "Неверный пароль администратора."
            )
            return

        self.destroy()

        app = AdminApp()
        app.mainloop()

    def open_staff(self):
        self.destroy()

        app = StaffApp()
        app.mainloop()


def main():
    try:
        _, admin_password = load_config()
    except Exception as e:
        root = tk.Tk()
        root.withdraw()

        messagebox.showerror(
            "Ошибка конфигурации",
            f"Не удалось загрузить CONFIG.json:\n\n{e}"
        )
        return

    selector = ModeSelector(admin_password)
    selector.mainloop()

if __name__ == "__main__":
    main()