import psycopg2
from psycopg2 import Error
from decimal import Decimal


def fill_library_db():
    conn = None
    try:
        # 1. Подключение к базе данных
        conn = psycopg2.connect(
            dbname="LibraryDB",
            host="127.0.0.1",
            user="postgres",
            password="123456789",
            port="5432"
        )
        cur = conn.cursor()
        print("✅ Есть контакт! Подключение установлено.")

        # Очистка таблиц для повторного заполнения (опционально)
        tables = [
            "operations", "loans", "editions", 
            "books", "readers", "authors", "publishers"
        ]
        for table in tables:
            cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
        print("🧹 Таблицы очищены.")

        # 2. Издатели
        cur.execute("""
            INSERT INTO publishers (name) 
            VALUES ('Издательство АСТ'), ('Эксмо'), ('Азбука-Аттикус')
            RETURNING publisher_id;
        """)
        pub_ids = [row[0] for row in cur.fetchall()]
        print(f"📚 Добавлено издателей: {len(pub_ids)}")

        # 3. Авторы
        cur.execute("""
            INSERT INTO authors (full_name) 
            VALUES 
                ('Фёдор Михайлович Достоевский'), 
                ('Джоан Роулинг'), 
                ('Рэй Брэдбери')
            RETURNING author_id;
        """)
        auth_ids = [row[0] for row in cur.fetchall()]
        print(f"✍️ Добавлено авторов: {len(auth_ids)}")

        # 4. Книги
        cur.execute("""
            INSERT INTO books (author_id, title) 
            VALUES 
                (%s, 'Преступление и наказание'),
                (%s, 'Гарри Поттер и философский камень'),
                (%s, '451 градус по Фаренгейту')
            RETURNING book_id;
        """, (auth_ids[0], auth_ids[1], auth_ids[2]))
        book_ids = [row[0] for row in cur.fetchall()]
        print(f"📖 Добавлено книг: {len(book_ids)}")

        # 5. Издания
        cur.execute("""
            INSERT INTO editions (
                book_id, publisher_id, title, 
                publication_year, storage_location, quantity, price
            ) 
            VALUES 
                (%s, %s, 'Преступление и наказание (классика)', 2020, 'Стеллаж А1, Полка 2', 5, 350.00),
                (%s, %s, 'Гарри Поттер. Том 1 (иллюстрированное)', 2018, 'Стеллаж Б2, Полка 1', 3, 900.00),
                (%s, %s, '451 градус по Фаренгейту', 2022, 'Стеллаж В3, Полка 4', 10, 420.00)
            RETURNING edition_id;
        """, (
            book_ids[0], pub_ids[0],
            book_ids[1], pub_ids[1],
            book_ids[2], pub_ids[2]
        ))
        ed_ids = [row[0] for row in cur.fetchall()]
        print(f"📕 Добавлено изданий: {len(ed_ids)}")

        # 6. Читатели
        cur.execute("""
            INSERT INTO readers (full_name, registration_date, phone, email) 
            VALUES 
                ('Иванов Иван Иванович', '2023-01-15', '+79001234567', 'ivanov@mail.ru'),
                ('Петрова Мария Сергеевна', '2023-05-20', '+79007654321', 'petrova.m@gmail.com'),
                ('Сидоров Алексей', '2026-10-01', '+79112223344', NULL)
            RETURNING reader_id;
        """)
        reader_ids = [row[0] for row in cur.fetchall()]
        print(f"👤 Добавлено читателей: {len(reader_ids)}")

        # 7. Выдачи (loans)
        cur.execute("""
            INSERT INTO loans (edition_id, reader_id, issue_date, return_date, due_date, extensions) 
            VALUES 
                (%s, %s, '2026-10-01', '2026-10-15', '2026-10-15', 0),
                (%s, %s, '2026-10-20', NULL, '2026-11-03', 1),
                (%s, %s, '2026-11-01', NULL, '2026-11-15', 0),
                (%s, %s, '2026-10-01', NULL, '2026-10-20', 0)
            RETURNING loan_id;
        """, (
            ed_ids[0], reader_ids[0],
            ed_ids[1], reader_ids[1],
            ed_ids[2], reader_ids[2],
            ed_ids[0], reader_ids[2]
        ))
        loan_ids = [row[0] for row in cur.fetchall()]
        print(f"🔄 Добавлено выдач (loans): {len(loan_ids)}")

        # 8. Операции
        cur.execute("""
            INSERT INTO operations (loan_id, operation_type, status, amount) 
            VALUES 
                (%s, 'Выдача книги', 'Завершено', NULL),
                (%s, 'Продление срока', 'Завершено', NULL),
                (%s, 'Штраф за просрочку', 'Оплачено', %s),
                (%s, 'Выдача книги', 'В процессе', NULL),
                (%s, 'Штраф за просрочку', 'Начислено', %s),
                (%s, 'Штраф за потерю/порчу', 'Начислено', %s)
        """, (
            loan_ids[0],
            loan_ids[1],
            loan_ids[1], Decimal("50.00"),
            loan_ids[2],
            loan_ids[3], Decimal("160.00"),
            loan_ids[0], Decimal("350.00")
        ))
        print("💰 Добавлено операций: 6")

        conn.commit()
        print("\n✅ База данных успешно заполнена тестовыми данными!")

    except Error as e:
        print(f"❌ Ошибка при работе с PostgreSQL: {e}")
        if conn:
            conn.rollback()

    finally:
        if conn:
            cur.close()
            conn.close()
            print("🔌 Соединение с PostgreSQL закрыто.")


if __name__ == "__main__":
    fill_library_db()