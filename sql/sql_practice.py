import sqlite3

con = sqlite3.connect('db.sqlite')


cur = con.cursor()


query_create = '''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at DATETIME
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    category TEXT NOT NULL,
    stock INT NOT NULL DEFAULT 0 CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    order_date DATETIME,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    price_at_order NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id)
);
'''

query = '''
    INSERT INTO users (name, email) VALUES
    ('Алексей Иванов', 'alex@mail.ru'),
    ('Мария Петрова', 'maria@mail.ru'),
    ('Иван Смирнов', 'ivan@mail.ru'),
    ('Екатерина Кузнецова', 'ekaterina@mail.ru'),
    ('Дмитрий Соколов', 'dmitry@mail.ru'),
    ('Ольга Попова', 'olga@mail.ru');

    INSERT INTO products (name, price, category, stock) VALUES
    ('Ноутбук', 85000, 'Электроника', 10),
    ('Смартфон', 45000, 'Электроника', 25),
    ('Наушники', 4500, 'Аксессуары', 50),
    ('Клавиатура', 2500, 'Аксессуары', 30),
    ('Монитор', 22000, 'Электроника', 8),
    ('Мышь', 1200, 'Аксессуары', 100),
    ('Планшет', 35000, 'Электроника', 15),
    ('Чехол для телефона', 800, 'Аксессуары', 200);

    INSERT INTO orders (user_id, status, order_date) VALUES
    (1, 'delivered', '2025-01-10 10:00:00+03'),
    (1, 'paid', '2025-01-15 14:30:00+03'),
    (2, 'delivered', '2025-01-12 09:00:00+03'),
    (2, 'cancelled', '2025-01-20 16:00:00+03'),
    (3, 'pending', '2025-02-01 11:00:00+03'),
    (1, 'delivered', '2025-02-14 12:00:00+03'),
    (2, 'delivered', '2025-02-15 10:00:00+03'),
    (3, 'delivered', '2025-02-20 15:00:00+03'),
    (4, 'delivered', '2025-03-01 09:00:00+03'),
    (5, 'delivered', '2025-03-10 14:00:00+03');

    INSERT INTO order_items (order_id, product_id, quantity, price_at_order) VALUES
    (1, 1, 1, 85000),
    (1, 3, 2, 4500),
    (2, 2, 1, 45000),
    (3, 4, 1, 2500),
    (3, 5, 2, 22000),
    (4, 2, 1, 45000),
    (5, 6, 5, 1200),
    (6, 2, 1, 45000),
    (6, 3, 3, 4500),
    (7, 1, 1, 85000),
    (8, 7, 2, 35000),
    (9, 8, 10, 800),
    (10, 5, 1, 22000);
'''

print('№ 1 Топ-10 пользователей по сумме заказов.')
results = cur.execute('''
    SELECT
        u.id,
        u.name,
        SUM(oi.quantity * oi.price_at_order) AS total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    JOIN order_items oi ON o.id = oi.order_id
    GROUP BY u.id, u.name
    ORDER BY total DESC
    LIMIT 10;
    ''')

for result in results:
    print(result)


print('№ 2 Пользователи, у которых нет ни одного заказа.')
results = cur.execute('''
   SELECT users.id, users.name, orders.id
   FROM users
   LEFT JOIN orders ON users.id = orders.user_id
   WHERE orders.id is NULL;
''')

for result in results:
    print(result)

print('№ 3 Количество заказов по месяцам за последний год')
results = cur.execute('''
   SELECT COUNT(*)
   FROM orders
   WHERE order_date < datetime('now', '-1 year');
''')

for result in results:
    print(result)

print('№ 4 Средний чек по каждому пользователю, только для тех, у кого больше 5 заказов.')
results = cur.execute('''
   SELECT
        users.id,
        users.name,
        AVG(order_items.quantity * order_items.price_at_order) AS total
   FROM users
   JOIN orders ON users.id = orders.user_id
   JOIN order_items ON orders.id = order_items.order_id
   WHERE orders.status = 'delivered'
   HAVING COUNT(orders.id) > 5;
''')

for result in results:
    print(result)

print('№ 5 Товары, которые ни разу не заказывали.')
results = cur.execute('''
    SELECT p.name
    FROM products p
    JOIN order_items oi ON p.id = oi.product_id
    WHERE oi.product_id IS NULL;
    ''')

for result in results:
    print(result)

con.commit()
con.close()
