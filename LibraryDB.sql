-- ================================================================
-- Схема базы данных библиотеки
-- ================================================================

DROP TABLE IF EXISTS operations CASCADE;
DROP TABLE IF EXISTS loans CASCADE;
DROP TABLE IF EXISTS editions CASCADE;
DROP TABLE IF EXISTS books CASCADE;
DROP TABLE IF EXISTS readers CASCADE;
DROP TABLE IF EXISTS authors CASCADE;
DROP TABLE IF EXISTS publishers CASCADE;

-- Издатели
CREATE TABLE publishers (
    publisher_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL
);

-- Авторы
CREATE TABLE authors (
    author_id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL
);

-- Книги
CREATE TABLE books (
    book_id SERIAL PRIMARY KEY,
    author_id INTEGER NOT NULL,
    title VARCHAR(300) NOT NULL,

    CONSTRAINT fk_books_author
        FOREIGN KEY (author_id)
        REFERENCES authors (author_id)
        ON DELETE RESTRICT
);

-- Издания книг
CREATE TABLE editions (
    edition_id SERIAL PRIMARY KEY,
    book_id INTEGER NOT NULL,
    publisher_id INTEGER NOT NULL,
    title VARCHAR(300) NOT NULL,
    publication_year INTEGER,
    storage_location VARCHAR(200),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
	price NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (price >= 0),

    CONSTRAINT fk_editions_book
        FOREIGN KEY (book_id)
        REFERENCES books (book_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_editions_publisher
        FOREIGN KEY (publisher_id)
        REFERENCES publishers (publisher_id)
        ON DELETE RESTRICT
);

-- Читатели
CREATE TABLE readers (
    reader_id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    registration_date DATE NOT NULL DEFAULT CURRENT_DATE,
    phone VARCHAR(30),
    email VARCHAR(200)
);

-- Выдачи книг
CREATE TABLE loans (
    loan_id SERIAL PRIMARY KEY,
    edition_id INTEGER NOT NULL,
    reader_id INTEGER NOT NULL,
    issue_date DATE NOT NULL,
    return_date DATE,
    due_date DATE NOT NULL,
    extensions INTEGER NOT NULL DEFAULT 0 CHECK (extensions >= 0),

    CONSTRAINT fk_loans_edition
        FOREIGN KEY (edition_id)
        REFERENCES editions (edition_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_loans_reader
        FOREIGN KEY (reader_id)
        REFERENCES readers (reader_id)
        ON DELETE RESTRICT
);

-- Операции: выдача, продление, штраф и т.п.
CREATE TABLE operations (
    operation_id SERIAL PRIMARY KEY,
    loan_id INTEGER NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    amount NUMERIC(12, 2),

    CONSTRAINT fk_operations_loan
        FOREIGN KEY (loan_id)
        REFERENCES loans (loan_id)
        ON DELETE RESTRICT
);

-- Индексы для ускорения
CREATE INDEX idx_books_author_id ON books (author_id);
CREATE INDEX idx_editions_book_id ON editions (book_id);
CREATE INDEX idx_editions_publisher_id ON editions (publisher_id);
CREATE INDEX idx_loans_edition_id ON loans (edition_id);
CREATE INDEX idx_loans_reader_id ON loans (reader_id);
CREATE INDEX idx_operations_loan_id ON operations (loan_id);