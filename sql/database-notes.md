## Базы данных — SQL, индексы, транзакции

### Реляционная модель: таблица, строка, столбец, первичный и внешний ключ.

- Таблица -  это набор данных.
- Запись (строка) — это строка в таблице.
- Поле (столбец, колонка) — это столбец таблицы или ячейка одной записи.
- Первичный ключ - это уникальный идентификатор записи в таблице.
- Внешний ключ - это ссылка на запись в другой таблице

## Пример реляционной модели:

### Таблица `users` — пользователи сервиса

Хранит информацию о клиентах, которые заказывают такси.

|    Поле    |        Тип        |     Ограничение    |           Описание                    |
|------------|-------------------|--------------------|---------------------------------------|
|    `id`    | `UUID` / `SERIAL` |    `PRIMARY KEY`   | Уникальный идентификатор пользователя |
|   `email`  |     `VARCHAR`     | `NOT NULL, UNIQUE` |          Почта пользователя           |
|   `name`   |     `VARCHAR`     |     `NOT NULL`     |             Имя пользователя          |
| `password` |     `VARCHAR`     |     `NOT NULL`     |                 Пароль                |

---

### Таблица `drivers` — водители

Хранит информацию о водителях, которые выполняют заказы.

| Поле | Тип | Ограничение | Описание |
|------|-----|-------------|----------|
| `id` | `UUID` / `SERIAL` | `PRIMARY KEY` | Уникальный идентификатор водителя |
| `name` | `TEXT` / `VARCHAR` | `NOT NULL` | Имя водителя |
| `count` | `INT` | `DEFAULT 0` | Количество выполненных поездок |
| `estimation` | `FLOAT` | `DEFAULT 0` | Оценка водителя|
| `active` | `BOOLEAN` | `DEFAULT TRUE` | Статус водителя|

---

### Таблица `orders` — заказы

Хранит информацию о заказах такси. Связывает пользователей и водителей.

| Поле | Тип | Ограничение | Описание |
|------|-----|-------------|----------|
| `id` | `UUID` / `SERIAL` | `PRIMARY KEY` | Номер заказа |
| `user_id` | `UUID` / `SERIAL` | `FOREIGN KEY (users.id)` | Кто заказал такси |
| `driver_id` | `UUID` / `SERIAL` | `FOREIGN KEY (drivers.id)` | Водитель |
| `from_address` | `TEXT` | `NOT NULL` | Адрес отправления |
| `to_address` | `TEXT` | `NOT NULL` | Адрес назначения |
| `price` | `NUMERIC` | `NOT NULL, CHECK (price > 0)` | Стоимость поездки |
| `status` | `VARCHAR` | `NOT NULL` | Статус заказа|
| `order` | `VARCHAR` | `NOT NULL` | Дополнительная информация о заказе |

---

## Типы данных PostgreSQL: 
- `int`/`bigint` - Целые числа, но bigint до 9·10¹⁸.
- `text`/`varchar` - Строки.
- `numeric` - Точные числа.
- `float` - Приблизительные числа.
 **Почему деньги хранят в `numeric`, а не во `float`**
 - float хранит числа в двоичной системе поэтому когда мы переводим из двоичной в десятичную происходит округление поэтому для денег нужно использоавать numeric.
- `timestamptz` против `timestamp` - Оба метода применяются для времени, timestamptz может преобразовать время в часовой пояс клиента 
- `uuid` - Уникальные идентификаторы.
- `jsonb` - Бинаргный формат json.

## Что такое нормализация? Виды нормализации.

- нормализация - это процесс борьба с дублированием данных.

1. 1НФ (Первая нормальная форма) - в каждой ячейке атомарное значение.
2. 2НФ (Вторая нормальная форма) - все поля работают на первичный ключ.
3. 3НФ (Третья нормальная форма) - поля не зависят от других не ключевых полей.

### Нормализация на примере

#### Плохо: одна таблица

| id | user_name |  user_email | driver_name | driver_car  |  from_address |   to_address | price | status |
|----|-----------|-------------|-------------|-------------|---------------|--------------|-------|--------|
| 1  | Александр | alex@mail.ru|    Сергей   |     KIA     |   Ул. Пушкина | Ул. Петухова |  1200 | Active |
| 2  | Александр | alex@mail.ru|    Дмитрий  |    Haval    | Ул.Новогодняя |  Ул. Гоголя  |  500  | Active |
| 3  |   Алиса   |alisa@mail.ru|    Сергей   |     KIA     |   Ул. Ленина  |  Ул.Ватутино |  350  | Active |

**Проблемы:**
- Дублируется пользователь и почта.
- Если удалить информацию о водители удалится вся история поездок.
- Нельзя добавить нового водителя без поездки.

**Таблица `users`:**
| id | user_name |  user_email |
|----|-----------|-------------|
| 1  | Александр | alex@mail.ru|
| 2  |   Алиса   |alisa@mail.ru|

**Таблица `drivers`:**
| id |driver_name| driver_car|
|----|-----------|-----------|
| 1  |   Сергей  |    KIA    |
| 2  |   Дмитрий |   Haval   |

**Таблица `orders`:**
| id |   user_id |  driver_id  |  from_address |   to_address | price | status |
|----|-----------|-------------|---------------|------------- |-------|--------|
| 1  |     1     |      1      |   Ул. Пушкина | Ул. Петухова |  1200 | Active |
| 2  |     1     |      2      | Ул.Новогодняя |  Ул. Гоголя  |  500  | Active |
| 3  |     2     |      1      |   Ул. Ленина  |  Ул.Ватутино |  350  | Active |


## Виды JOIN: 
- INNER JOIN - включает в результирующую таблицу только те записи, в которых выполняется условие, заданное в ON
 **Пример** 
 - JOIN slogans ON video_products.slogan_id = slogans.id
- LEFT JOIN -  объединяемые таблицы условно называют «левая» и «правая». «Левая» — та, которая вызвана в блоке FROM, «правая» — та, что указана после ключевого слова JOIN. Возвращаются все строки левой таблицы и дополняются строки из правой таблицы при выполнение условия, если данные в правой части отстутсвуют то пишется `NULL`.
 **Пример**
 - LEFT JOIN slogans ON video_products.slogan_id = slogans.id
- RIGHT JOIN -  это такое же объединение, как и **LEFT JOIN**, но выводятся все записи из правой таблицы, а к ним добавляются только те данные из левой таблицы, в которых есть ключ объединения, если в правой части записей больше, то в левой части будет стоять `NULL`.
 **Пример**
 - RIGHT JOIN product_types ON video_products.type_id = product_types.id
- FULL JOIN - выводятся все записи из объединяемых таблиц (FULL JOIN == LEFT JOIN + RIGHT JOIN). Если в какой из частей отсутсвует часть записи то на ее место ставится `NULL`.
 **Пример**
 - FULL JOIN slogans ON video_products.slogan_id = slogans.id
- CROSS JOIN - возвращает декартово произведение таблиц — каждая запись левой таблицы объединится с каждой записью правой. Параметр ON при запросах CROSS JOIN не применяется.
 **Пример**
 - CROSS JOIN slogans
 
**Условие в `WHERE` против условия в `ON`**
- Условие в ON — фильтрует данные ДО соединения, условие в WHERE — фильтрует результат после соединения это приводит к потери данных на выходе.

**Порядок выполнения SQL-запроса:**
1. FROM — берем таблицу.
2. WHERE — фильтруем строки.
3. GROUP BY — группируем по условию.
4. HAVING — фильтруем группы.
5. SELECT — вычисляем выражения (например COUNT, MAX).
6. ORDER BY — сортируем по условию.
7. LIMIT — отрезаем первые N строк.

**Почему в `WHERE` нельзя использовать алиас из `SELECT`**
- По той причине что `WHERE` выполняется раньше чем `SELECT`, `WHERE` просто не видит его

**`HAVING` против `WHERE` (когда что и почему).**
- Работа HAVING во многом аналогична применению WHERE; но WHERE применяется для фильтрации строк, а HAVING — для фильтрации групп.

## Виды подзапросы:
1. Скалярные - это подзапрос в `SELECT`, `FROM`, `WHERE`, который возвращает одно значение.

**Пример**
```
SELECT name, mark, (SELECT AVG(mark) FROM Group_class) AS avg_mark
FROM Group_class
WHERE ball > (SELECT AVG(mark) FROM Group_class)
```

2. Коррелированные - это подзапрос в `SELECT`, `FROM`, `WHERE`, который ссылается на внешнюю таблицу из главного запроса, выполняется для каждой строки внешнего запроса, что делает их дорогими и сложность данного алгоритма будет 0(n * m) для 1000 элементов не кретично, но для 100 млн записей база данных просто упадет.

**Пример**
```
SELECT name, mark, (SELECT AVG(mark) 
                    FROM Group_class gl1 
                    WHERE gl1.class_id = gl2.class_id) AS avg_mark
FROM Group_class gl2
WHERE mark > (SELECT AVG(mark)
              FROM Group_class gl1 
              WHERE gl1.class_id = gl2.class_id);
```

## `EXISTS` против `IN` против `JOIN`:
1. `EXISTS` - проверяет существование строки в подзапросе. Работает быстрее IN на больших данных.
2. `IN` - используется для проверки, входит ли значение в список.
3. `JOIN` - используется, когда нужны данные из обеих таблиц.

## CTE?
- **CTE** - это обощенная табличное выражение, которая является особой формой написания именнованного подзапроса, которая позволяет использовать результат как статическая таблица (временный результирующий набор данных). Хранится он в оперативной памяти, поэтому к нему легко добраться, следовательно **CTE** существует только в течение выполнения запроса. Кроме того, повторное использование уже полученного результатов CTE может быть эффективнее, чем несколько раз выполнить один и тот же подзапрос. База данных один раз вычисляет результат CTE и затем использует его повторно, избегая избыточных вычислений.
**Пример**
```
WITH Avg_mark AS (
    SELECT AVG(mark) AS avg_val 
    FROM Group_class 
)
SELECT name
FROM Group_class
WHERE mark > (SELECT avg_val FROM Avg_mark);
```
- **Рекурсивные CTE** - позволяют выполнять рекурсивные запросы. Рекурсивные CTE состоят из двух частей: анкерной части и рекурсивной части. Анкерная часть - это начальный запрос, который возвращает базовый набор данных. Рекурсивная часть - это запрос, который ссылается на сам CTE и добавляет новые строки к результату, пока не будет достигнуто условие остановки.
**Синтаксис**
```
WITH RECURSIVE name AS (
    -- Анкерная часть
    SELECT ...
    FROM ...
    WHERE ...

    UNION ALL

    -- Рекурсивная часть
    SELECT ...
    FROM name
    WHERE ...
)
SELECT * FROM name;
```
**Пример c иерархией подчиненных для сотрудника с id = 1**
```
WITH RECURSIVE name AS (
    -- Анкерная часть
    SELECT id, name, manager_id
    FROM workers
    WHERE id = 1

    UNION ALL

    -- Рекурсивная часть
    SELECT e.id, e.name, e.manager_id
    FROM employees e
    INNER JOIN employee_hierarchy eh ON e.manager_id = eh.id
)
SELECT * FROM employee_hierarchy;
```
## Оконные функции.
1. Оконная функция в SQL - функция, которая работает с выделенным набором строк (окном, партицией) и выполняет вычисление для этого набора строк в отдельном столбце.
2. Партиции (окна из набора строк) - это набор строк, указанный для оконной функции по одному из столбцов или группе столбцов таблицы. Партиции для каждой оконной функции в запросе могут быть разделены по различным колонкам таблицы.
**Синтаксис**
```
 Function_name(colum_name) OVER (PARTITION BY column_name)
```
**Классы Оконных функций (Function_name)**
1. Агрегирующие:
 - AVG() - среднее значение
 - SUM() - сумма 
 - COUNT() - подсчет элементов
 - MIN() - минимальное значение
 - MAX() - максимальное значение
2. Ранжирующие:
 - ROW_NUMBER() - функция вычисляет последовательность ранг (порядковый номер) строк внутри партиции,
 - RANK() - функция вычисляет ранг каждой строки внутри партиции.
 - DENSE_RANK() - то же самое что и RANK, только в случае одинаковых значений DENSE_RANK не пропускает следующий числовой ранг, а идет последовательно.
3. Функции смещения:
 - LAG() - функция, возвращающая предыдущее значение столбца по порядку сортировки.
 - LEAD() - функция, возвращающая следующее значение столбца по порядку сортировки.
**Разница между `PARTITION BY` и `GROUP BY`.**
- Одно из самых главных отличий в том что `GROUP BY` сокращает количество строк в запросе с помощью их группировки, а при использовании `PARTITION BY` количество строк в запросе не уменьшается по сравнении с исходной таблицей.

**Таблица с  `GROUP BY`:**
|   name  |    object   |mark|
|---------|-------------|----|
|  Тахир  | Матеиматика |  5 |
|  Тахир  |    Физика   |  4 |
|  Тахир  |    Химия    |  5 |
| Максим  | Матеиматика |  5 |
| Максим  |    Физика   |  4 |
| Максим  |    Химия    |  5 |
```
SELECT name, AVG(mark) as avg_mark
FROM group_class
GROUP BY name;
```
|   name  |avg_mark|
|---------|--------|
|  Тахир  |  4.7   |
| Максим  |  4.7   |

**Таблица `drivers`:**
|   name  |    object   |mark|
|---------|-------------|----|
|  Тахир  | Матеиматика |  5 |
|  Тахир  |    Физика   |  4 |
|  Тахир  |    Химия    |  5 |
| Максим  | Матеиматика |  5 |
| Максим  |    Физика   |  4 |
| Максим  |    Химия    |  5 |
```
SELECT name, object, mark,
       AVG(mark) OVER (PARTITION BY name) as avg_mark
FROM group_class;
```
|   name  |    object   |mark|avg_mark|
|---------|-------------|----|--------|
|  Тахир  | Матеиматика |  5 |  4.7   |
|  Тахир  |    Физика   |  4 |  4.7   |
|  Тахир  |    Химия    |  5 |  4.7   |
| Максим  | Матеиматика |  5 |  4.7   |
| Максим  |    Физика   |  4 |  4.7   |
| Максим  |    Химия    |  5 |  4.7   |

## Что такое индексы?
- Индекс - это сущность в базе данных, которая позволяет осуществлять быстрый поиск по таблице.
**Синтаксис создания**
- CREATE INDEX idx ON name(colum)

**Как устроен B-tree индекс. Поиск по B-treee дереву**
- B-tree — это сбалансированное дерево поиска, в котором каждый узел содержит множество ключей и имеет более двух потомков.
- Поиск осуществляется сравнением искомых элементов с первым значением ключа в корневом узле дерева затем путем по левому поддереву или по правому. В В-дереве сложность поиска составляет O(log n).

## Эксперимент №1 замерим поиск записи в таблице без индекса и с индексом на таблице с 10 млн с B-tree:
**Ожидания**
- Поиск элемента по id занимает где-то 0.3-1 мс, поэтому стоит предположить что и поиск по полю с индекосм будет где-то в таком же диапазоне по той причине, что первичный ключ заиндексирован, а поиск без индекса больше на 200-400 мс.
  
  **Без индексов**

  ```
  1)
  Gather  (cost=1000.00..136417.43 rows=1 width=37) (actual time=2.856..388.012 rows=1 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   Buffers: shared hit=385 read=82949
   ->  Parallel Seq Scan on orders  (cost=0.00..135417.33 rows=1 width=37) (actual time=240.410..367.494 rows=0 loops=3)
         Filter: (value = '70dae82961365ae645094c6d198f4ff7'::text)
         Rows Removed by Filter: 3333333
         Buffers: shared hit=385 read=82949
  Planning Time: 0.065 ms
  JIT:
   Functions: 6
   Options: Inlining false, Optimization false, Expressions true, Deforming true
   Timing: Generation 0.661 ms, Inlining 0.000 ms, Optimization 0.647 ms, Emission 7.717 ms, Total 9.024 ms
  Execution Time: 388.344 ms

  2)
  Gather  (cost=1000.00..136417.43 rows=1 width=37) (actual time=2.156..343.950 rows=1 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   Buffers: shared hit=193 read=83141
   ->  Parallel Seq Scan on orders  (cost=0.00..135417.33 rows=1 width=37) (actual time=211.739..323.954 rows=0 loops=3)
         Filter: (value = '3f18c8ab61407761cd3c1b04b9d94c65'::text)
         Rows Removed by Filter: 3333333
         Buffers: shared hit=193 read=83141
  Planning Time: 0.049 ms
  JIT:
   Functions: 6
   Options: Inlining false, Optimization false, Expressions true, Deforming true
   Timing: Generation 0.719 ms, Inlining 0.000 ms, Optimization 0.606 ms, Emission 7.933 ms, Total 9.258 ms
  Execution Time: 344.141 ms

  3)
  Gather  (cost=1000.00..136417.43 rows=1 width=37) (actual time=1.992..346.997 rows=1 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   Buffers: shared hit=289 read=83045
   ->  Parallel Seq Scan on orders  (cost=0.00..135417.33 rows=1 width=37) (actual time=213.314..326.959 rows=0 loops=3)
         Filter: (value = 'cacc70d9c56d038a5540222bddd5cef7'::text)
         Rows Removed by Filter: 3333333
         Buffers: shared hit=289 read=83045
  Planning Time: 0.047 ms
  JIT:
   Functions: 6
   Options: Inlining false, Optimization false, Expressions true, Deforming true
   Timing: Generation 0.643 ms, Inlining 0.000 ms, Optimization 0.503 ms, Emission 6.866 ms, Total 8.011 ms
  Execution Time: 347.186 ms
  ```

  **С индексами**
  ```
  1)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.732..1.733 rows=1 loops=1)
  Index Cond: (value = '70dae82961365ae645094c6d198f4ff7'::text)
  Buffers: shared read=5
  Planning:
  Buffers: shared hit=73 read=27
  Planning Time: 0.691 ms
  Execution Time: 1.769 ms
  2)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.414..1.416 rows=1 loops=1)
  Index Cond: (value = '5cea12ace5976cfff6d189dff926dd4d'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.057 ms
  Execution Time: 1.430 ms
  3)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.731..1.733 rows=1 loops=1)
  Index Cond: (value = '9908f08bac57ffe46eb6c6d150e09f4a'::text)
  Buffers: shared hit=2 read=3
  Planning Time: 0.055 ms
  Execution Time: 1.747 ms
  ```

|    Запрос   | С индексом (AVG) | Без индекса (AVG) |
|-------------|------------------|-------------------|
|     1       |     1.769 ms     |     388.344 ms    |
|     2       |     1.430 ms     |     344.141 ms    |
|     3       |     1.747 ms     |     347.186 ms    |

**Вывод**
- Эксперимент показал, что использование B-tree индекса ускоряет поиск в ~200 раз по сравнению с полным сканированием таблицы. Мое ожжидание не подвердилось я ожидал поиск по индексу будет 0.3-1 мс, а на деле получил 1.769 мс, расхождение объясняется накладными расходами на планирование запроса и чтение страниц индекса с диска. Во втором эксперименте будет проведено сравнение с HASH индексом, который теоретически должен быть быстрее для точных сравнений за счёт сложности O(1). 

## Эксперимент №2 B-tree vs HASH-функции:
**Ожидания**
- Поиск с индексами через HASH должен быть быстрее так как поиск идет по ключу за время O(1), а в B-tree идет поиск по дереву и происходит сравнение элементов с O(logn). 

 - Создадим таблицу orders с полями id, order_id и заполним ее 10 млн записями и по очередно сделаем замеры с двумя типами индексов **B-tree** и **HASH**.

  **Посчитаем уровни**
  - B-tree
  1. log2(999) = x, x = 10 
  2. log2(999999) = x, x = 20
  3. log2(9999999) = x, x = 23
  - HASH
  Хеш-индекс вычисляет хеш от ключа и сразу переходит к нужной странице. Глубина всегда 1.

 ```
 1. Создаем таблицу
  CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    value TEXT NOT NULL
  );
 2. Вставляем 10 млн записей
 INSERT INTO orders (value)
 SELECT generate_series(1, 10000000)::VARCHAR;
 3. Создадим B-tree-индексы
 CREATE INDEX idx_btree_value ON orders USING BTREE (value);
 4. Удаляем B-tree индексы
 DROP INDEX idx_btree_value;
 5. Создаем HASH-индексы
 CREATE INDEX idx_hash_value ON orders USING HASH (value);
 Перед каждым запрпосом будем чистить кеш, перезаходить в контейнер, для того чтобы смотреть реальное время запроса.
 ```

 **С B-tree индексами**
   
  ```
  - 10 запусков запрос
  1)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.732..1.733 rows=1 loops=1)
  Index Cond: (value = '70dae82961365ae645094c6d198f4ff7'::text)
  Buffers: shared read=5
  Planning:
  Buffers: shared hit=73 read=27
  Planning Time: 0.691 ms
  Execution Time: 1.769 ms
  2)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.414..1.416 rows=1 loops=1)
  Index Cond: (value = '5cea12ace5976cfff6d189dff926dd4d'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.057 ms
  Execution Time: 1.430 ms
  3)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.731..1.733 rows=1 loops=1)
  Index Cond: (value = '9908f08bac57ffe46eb6c6d150e09f4a'::text)
  Buffers: shared hit=2 read=3
  Planning Time: 0.055 ms
  Execution Time: 1.747 ms
  4)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.707..1.709 rows=1 loops=1)
  Index Cond: (value = '5d2cdaa09bc693dc42f15a46e7c4b632'::text)
  Buffers: shared hit=2 read=3
  Planning Time: 0.056 ms
  Execution Time: 1.723 ms
  5)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.410..1.412 rows=1 loops=1)
  Index Cond: (value = 'bcc69e47a288fc856daaaaf0806d8e8f'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.067 ms
  Execution Time: 1.428 ms
  6)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.777..1.779 rows=1 loops=1)
  Index Cond: (value = 'cd9704256802b529b08d6e67f5fbe724'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.056 ms
  Execution Time: 1.793 ms
  7)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=4.858..4.860 rows=1 loops=1)
  Index Cond: (value = '23b0026d03ed53ba92de182abf9b9167'::text)
  Buffers: shared read=5
  Planning:
  Buffers: shared hit=73 read=27
  Planning Time: 14.615 ms
  Execution Time: 4.961 ms
  8)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=2.193..2.195 rows=1 loops=1)
  Index Cond: (value = 'cacc70d9c56d038a5540222bddd5cef7'::text)
  Buffers: shared hit=2 read=3
  Planning:
  Buffers: shared hit=110
  Planning Time: 0.465 ms
  Execution Time: 2.235 ms
  9)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.660..1.662 rows=1 loops=1)
  Index Cond: (value = '105611cd11978287f9952d04dfa3d1f9'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.057 ms
  Execution Time: 1.676 ms
  10)
  Index Scan using idx_btree_value on orders  (cost=0.56..8.58 rows=1 width=37) (actual time=1.619..1.621 rows=1 loops=1)
  Index Cond: (value = 'a09e454a0506eb05805ac20edf198994'::text)
  Buffers: shared hit=3 read=2
  Planning Time: 0.056 ms
  Execution Time: 1.635 ms
  ```

  **С HASH индексами**

  - 10 запрос
  ```
  1)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=5.171..5.175 rows=1 loops=1)
  Index Cond: (value = 'cad9e2a12a481d85624604dc795284a6'::text)
  Buffers: shared read=3
  Planning:
  Buffers: shared hit=78 read=23
  Planning Time: 10.982 ms
  Execution Time: 5.261 ms
  2)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.831..0.832 rows=1 loops=1)
  Index Cond: (value = '5cea12ace5976cfff6d189dff926dd4d'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.055 ms
  Execution Time: 0.846 ms
  3)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.768..0.769 rows=1 loops=1)
  Index Cond: (value = '9908f08bac57ffe46eb6c6d150e09f4a'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.055 ms
  Execution Time: 0.783 ms
  4)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.819..0.821 rows=1 loops=1)
  Index Cond: (value = '5d2cdaa09bc693dc42f15a46e7c4b632'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.054 ms
  Execution Time: 0.835 ms
  5)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.901..0.902 rows=1 loops=1)
  Index Cond: (value = 'bcc69e47a288fc856daaaaf0806d8e8f'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.074 ms
  Execution Time: 0.920 ms
  6)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.847..0.849 rows=1 loops=1)
  Index Cond: (value = 'cd9704256802b529b08d6e67f5fbe724'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.052 ms
  Execution Time: 0.862 ms
  7)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.832..0.834 rows=1 loops=1)
  Index Cond: (value = '23b0026d03ed53ba92de182abf9b9167'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.051 ms
  Execution Time: 0.848 ms
  8)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.812..0.814 rows=1 loops=1)
  Index Cond: (value = 'cacc70d9c56d038a5540222bddd5cef7'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.055 ms
  Execution Time: 0.829 ms
  9)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=1.043..1.061 rows=1 loops=1)
  Index Cond: (value = '105611cd11978287f9952d04dfa3d1f9'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.473 ms
  Execution Time: 1.203 ms
  10)
  Index Scan using idx_hash_value on orders  (cost=0.00..8.02 rows=1 width=37) (actual time=0.841..0.842 rows=1 loops=1)
  Index Cond: (value = 'a09e454a0506eb05805ac20edf198994'::text)
  Buffers: shared hit=1 read=1
  Planning Time: 0.072 ms
  Execution Time: 0.859 ms
  ```

  | Метрика        | B-tree      | HASH        |
  |----------------|-------------|-------------|
  | Среднее время  | 2.04 ms     | 1.27 ms     |
  | Минимум        | 1.414 ms    | 0.768 ms    |
  | Максимум       | 4.961 ms    | 5.261 ms    |
  | Медиана        | 1.735 ms    | 0.848 ms    |
  | Кол-во запросов| 10          | 10          |

**Вывод**
- эксперимент подтвердил, что использования идексов через HASH будет быстрее, но и B-tree показал достаточно хороший результат, по умолчанию если добавлять индексы будут устанавливаться B-tree индексы, они универсальныe, поддерживают сортировку и могут работать с **LIKE%**, когда hash-индексы применяются только для точного сравнения **=** и нету сортировки и **LIKE**.

**Проверим сколько памяти занимают индексы**

- Выполним команду:

```
SELECT                                                   
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
FROM pg_indexes
WHERE tablename = 'orders';
```
| Индекс | Размер |
|--------|--------|
| `idx_btree_value` | 563 MB |
| `idx_hash_value` | 256 MB |
| `orders_pkey` | 247 MB |

**Виды чтения таблиц:**

1. `Seq Scan` - Читает всю таблицу
2. `Index Scan` - Идёт по индексу, затем поднимает строку из таблицы
3. `Index Only Scan` - Читает только индекс, не заглядывая в таблицу
4. `Bitmap Heap Scan` - Строит битовую карту из индекса, затем идёт в таблицу

**Почему индекс иногда не используется:**
- `WHERE lower(email) = ...` - индекс хранит данные, а функция изменяет их перед сравнением.
- Приведение типов - не может использовать индекс, если типы данных не совпадают.
- `LIKE '%text'` - B-tree индекс работает слева направо % в начале ломает этот порядок
- Низкая селективность - индексы не используются если большое количество строк имеют одно и тоже значение.
- Слишком маленькая таблица - планировщик может выбрать `Seq Scan`, если оценка стоимости полного сканирования оказывается ниже, чем использование индекса.

**Правило левого префикса**
- Создадим базу данных и наполним ее 1 млн строк:

```
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INT,
    created_at TIMESTAMP
);

INSERT INTO orders (user_id, created_at)
SELECT 
    (random() * 10000)::INT,
    '2024-01-01'::timestamp + (random() * 365 * interval '1 day')
FROM generate_series(1, 1000000);

CREATE INDEX idx_orders_user_created ON orders (user_id, created_at);
```

1. Первый запрос с соблюдением левого префикса:

```
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders 
WHERE user_id = 5000 AND created_at BETWEEN '2024-06-01' AND '2024-06-02';
```

```
Index Scan using idx_orders_user_created on orders  (cost=0.42..8.45 rows=1 width=16) (actual time=0.032..0.033 rows=0 loops=1)
   Index Cond: ((user_id = 5000) AND (created_at >= '2024-06-01 00:00:00'::timestamp without time zone) AND (created_at <= '2024-06-02 00:00:00'::timestamp without time zone))
   Buffers: shared read=3
 Planning:
   Buffers: shared hit=30
 Planning Time: 0.171 ms
 Execution Time: 0.046 ms
```
2. Второй запрос без соблюдения левого префикса:
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders 
WHERE created_at BETWEEN '2024-06-01' AND '2024-06-02';
```
Gather  (cost=1000.00..12926.80 rows=2708 width=16) (actual time=0.452..43.271 rows=2671 loops=1)
   Workers Planned: 2
   Workers Launched: 2
   Buffers: shared hit=5406
   ->  Parallel Seq Scan on orders  (cost=0.00..11656.00 rows=1128 width=16) (actual time=0.095..33.132 rows=890 loops=3)
         Filter: ((created_at >= '2024-06-01 00:00:00'::timestamp without time zone) AND (created_at <= '2024-06-02 00:00:00'::timestamp without time zone))
         Rows Removed by Filter: 332443
         Buffers: shared hit=5406
 Planning:
   Buffers: shared hit=92
 Planning Time: 0.501 ms
 Execution Time: 43.555 ms
```
**Вывод**
- используя в запросе левый префикс ответ придет за доли секунды, а если пропущен левый префикс индекс бесполезен. PostgreSQL выполняет параллельное последовательное сканирование (Parallel Seq Scan) всей таблицы.

**Цена индекса:**

| Параметр |    Цена   |
|----------|-----------|
|  Память  |Может занимать место сколько и вся таблица|
|  INSERT  |Каждая вставка требует обновления индекса медленнее|
|  UPDATE  |Добавляется новая запись в индекс. Старая помечается как мёртвая для VACUUM. Индекс не перестраивается целиком|
|  DELETE  |Запись в индексе помечается как мёртвая для VACUUM|

### Что такое EXPLAIN ANALYZE:
- EXPLAIN ANALYZE - это инструмент PostgreSQL, который реально выполняет запрос и показывает, как он работал:

  - План выполнения (как БД собирается выполнять запрос)
  - Фактическое время (сколько реально заняло)
  - Количество строк (сколько обработано на каждом этапе)

  **Базовый синтаксис**
  - Запрос
  ```
  EXPLAIN ANALYZE SELECT * FROM users WHERE id = 1;
  ```
  - Ответ
  ```
  Index Scan using users_pkey on users  (cost=0.15..8.17 rows=1 width=36) (actual
  time=0.043..0.045 rows=1 loops=1)
   Index Cond: (id = 1)
  Planning Time: 0.109 ms
  Execution Time: 0.066 ms
  ```
  - Анализируя ответ мы видим:

  |    Параметр   |    Обозначение    |
  |---------------|-------------------|
  |cost=0.15..8.17|Примерная стоимость|
  |    rows=1     |Планировщик ожидает 1 строку|
  |actual time=0.043..0.045|Реальное время выполнение|
  |actual rows=1|Реальное количество строк|
  |loops=1|Реальное выполнение строк|
  |Planning Time|Время составления плана|
  |Execution Time|Время выполнения запроса|

  **Примечание**
  - Не во всех случаях можно использовать **EXPLAIN ANALYZE** так как он выполняет запрос и данные будут закомиченны даже если это сделано просто для теста, лучше в таких моментах использовать **EXPLAIN** мы увидим не все конечно данные о запросе, но запрос не выполнится в базе данных и это самый важный момент. Но если мы используем **SELECT** запрос то ничего страшного, но если **UPDATE/DELETE/INSERT** то база данных действительно изменится.

  **Рекомендация:**
  - Для SELECT — используйте `EXPLAIN ANALYZE` (безопасно).
  - Для UPDATE/DELETE/INSERT — используйте `EXPLAIN` или выполняйте внутри транзакции с `ROLLBACK`:

  ```
  BEGIN;
  EXPLAIN ANALYZE UPDATE users SET name = 'test' WHERE id = 1;
  ROLLBACK;
  ```

**Вывод**
- Из всего сказаного, можно сделать вывод что индексировать надо только то что мы используем для поиска и сортировки, а не все информацию, в противном случае сталкнемся с тем с медленным вставкам и раздутием БД.

## Что такое ACID и транзакции:
Транзакции - это набор SQL-запросов.

**Синтаксис:**
  - BEGIN - Начинает транзакцию.
  - ROLLBACK - Один запрос упал откатывавет назад.
  - COMMIT - Сохраняет если все хорошо.
  - SAVEPOINT - Точка сохранения.

ACID - это набор принципов о транзакциях в реалиционных базах данных: 
1. A - Атомарность - Транзакция выполняется целиком или не выполняется вообще, если какой-то запрос из транзакции не выполнился по какой-то причине то база данных не изменит свое состояние.

**Пример**
- Банковская транзакция перевод денег от одного пользователя к другому
```
BEGIN;
UPDATE balances SET amount = amount - 100 WHERE id = 1;
UPDATE balances SET amount = amount + 100 WHERE id = 2;
Далее два варианта:
COMMIT; - сохранить изменения
ИЛИ
ROLLBACK; - откатить изменения
```
2. C - Консистентность/(Согласовоность) - После транзакции данные валидны — не нарушены ограничения (CHECK и тд).

**Пример**
```
CREATE TABLE table(
    id SERIAL PRIMARY KEY,
    value INTEGER CHECK (value >= 0)
)
BEGIN;
INSERT INTO table (value) VALUES (1); - База данных сохранит
INSERT INTO table (value) VALUES (-1); - База данных не сохранит
ROLLBACK;
```
3. I - Изоляция - Транзакции выполняются так, будто они выполняются последовательно, даже если они идут параллельно.

**Аномалии**
  - Грязное чтение - Транзакция А читает данные, которые транзакция Б изменила, но ещё не подтвердила `COMMIT`. Если Б откатится, то А прочитала грязные данные.
  **Пример**
    - Транзакция А:
    ```
    BEGIN;
    SELECT * FROM table
    ```
    - Транзакция Б:
    ```
    BEGIN;
    INSERT INTO table (value) VALUES (1)
    ```
  - Неповторяющееся чтение - Транзакция А дважды читает одну и ту же строку. Между чтениями транзакция Б меняет эту строку и подтверждает `COMMIT`. А видит два разных значения.
  **Пример**
    - Транзакция А:
    ```
    BEGIN;
    SELECT balance FROM users WHERE id = 1; -> 500
    ----
    SELECT balance FROM users WHERE id = 1; -> 1000
    ```
    - Транзакция Б:
    ```
    BEGIN;
    UPDATE users SET balance = 1000 WHERE id = 1; 
    COMMIT;
    ```
  - Фантомное чтение - Транзакция А читает набор строк по условию. Транзакция Б добавляет/удаляет строки, подходящие под это условие, и подтверждает. При повторном чтении А видит другие строки.
  **Пример**
    - Транзакция А:
    ```
    BEGIN;
    SELECT COUNT(*) FROM users; -> 10
    ----
    SELECT COUNT(*) FROM users; -> 11
    ```
    - Транзакция Б:
    ```
    BEGIN;
    INSERT INTO users (name) VALUES (Саша); 
    COMMIT;
    ```
  - Потерянное обновление - Две транзакции читают одно и то же значение, изменяют его и сохраняют — последнее изменение перезаписывает первое.
  **Пример**

    - Транзакция А:
    ```
    BEGIN;
    SELECT balance FROM users WHERE id = 1; -> 100
    ----
    UPDATE users SET balance = 150 WHERE id = 1; -> 150
    ---
    COMMIT;
    ```

    - Транзакция Б:
    ```
    BEGIN;
    SELECT balance FROM users WHERE id = 1; -> 100
    ----
    UPDATE users SET balance = 120 WHERE id = 1; -> 120
    ----
    COMMIT;
    Ответ 120, первый коммит не применился
    ```

**Уровни Изоляции:**
- READ UNCOMMITTED - содержит в себе все виды аномалий и не одну из них не решает, но в PostgreSQL этот уровень изоляции эквивалентен `READ COMMITTED` и на практике `READ UNCOMMITTED` даже не применяется так как по умолчанию стоит изоляция `READ COMMITTED`.
- READ COMMITTED - решает аномалии на грязное чтение, за счет **MVCC** механизма, делает снипшот каждого **SELECT** в транзакции.
- REPEATABLE READ - решает проблемы на грязное чтение, неповторяющтеся чтение и фантомное чтение, но только в PostgreSQL, тоже под капотом есть **MVCC** механизм, делает снапшот транзакции перед первым **SELECT** и в этой транзакции не дает изменять данные, в том плане что на глабальном уровне запись в бд изменится, но в транзакцие в этой, в **Lost Update** он не решает проблему в прямом смысле, он решает конфликт между двумя транзакцями, транзакция которая первая сделала комит та и сохранится, вторая транзакция выйдет с ошибкой **ERROR:  could not serialize access due to concurrent update**, но нужно делать **retry** чтобы вторая транзакция тоже выполнилась, если **retry**.
- SERIALIZABLE - обеспечивает самую строгую изоляцию транзакций. Этот уровень эмулирует последовательное выполнение транзакций для всех зафиксированных транзакций, как если бы транзакции выполнялись одна за другой, последовательно, а не параллельно. Этот уровнь изоляции рабортает как и **REPEATABLE READ**, но дополнительно отслеживает конфликты чтения-записи. При обнаружении конфликта, который нарушил бы сериализуемость, PostgreSQL выбрасывает ошибку: **ERROR: could not serialize access due to read/write dependencies among transactions**.   

- MVCC - это механизм, управления конкурентным доступом и изоляции, устраняет конфликты между чтением и записью.
 - История - идет хранения в двух полях x_min и x_max:

   - **`xmin`** — идентификатор транзакции, которая создала эту версию строки.
   - **`xmax`** — идентификатор транзакции, которая удалила или изменила.

   Когда транзакция читает данные, она смотрит на `xmin` и `xmax` и решает, видит ли она эту версию строки:
   1. Если `xmin` уже закоммичен и виден снапшоту и `xmax` равен 0, либо не виден снапшоту то строка **видна**.
   2. Если `xmax` уже закоммичен и виден снапшоту то строка **не видна** (удалена или изменена).
   3. Если `xmin` ещё не закоммичен то строка **не видна** (грязное чтение невозможно).

   Но это только для READ COMMITTED, если мы возьмем REPEATABLE READ, то транзакция запомнинает **снапшот** в начале, в течение всей транзакции она видит **только те строки**, которые были закоммичены **до** момента начала транзакции, а строки, закоммиченные **после** начала транзакции — **не видны** и поэтому этот уровнь изоляции решает такие проблемы как неповторяющиеся чтение и фантомное чтение.

 - **Снимок (Snapshot)** - озночает что каждый SQL-запрос видит снимок данных (версию базы данных), сделанный некоторое время назад, независимо от текущего состояния базовых данных.
 - В `READ COMMITTED` — **перед каждым запросом** (`SELECT`).
 - В `REPEATABLE READ` и `SERIALIZABLE` — **один раз в начале транзакции** (перед первым `SELECT`).

### Зачем нужен MVCC:
 1. Изоляция транзакций снепшоты. Чтобы каждая транзация видела базу данных такой, какой она была на момент её начала.
 2. Чтение без блокировок. Пока одна тарнзакция обновляет строку, другая могла читать старую версию.
 3. Откат. Если сделать **UPDATE**, а потом откатить **ROLLBACK**, то PostgreSQL забудет новую версию и будет видеть старую.

### Почему читатели не блокируют писателей и наоборот.
 - Потому что MVCC вместо блокировок использует версионирование строк и пока один пользователь обновляет строку но не добавив ее в коммит, другой пользователь может читать снапшот записи и видить запись неизменненой. 

  ### Отличие SERIALIZABLE от REPEATABLE READ:
  - **REPEATABLE READ** защищает от конфликтов **запись-запись** (кто первый обновил строку — тот и сохранил).
  - **SERIALIZABLE** защищает от конфликтов **запись-запись** плюсом дополнительно защищает от конфликтов **чтение-запись**: если транзакция прочитала данные, а другая транзакция их изменила, первая не сможет закоммититься и получит ошибку (кто первый завершил транзакцию — тот и сохранил, даже если пользователь просто читает транзакцию то он все равно  может получить ошибку, если прочитанные данные были изменены другой транзакцией).

**Установка уровней изоляции:**
- SET TRANSACTION ISOLATION LEVEL уровнь_изоляции;

4. D - Надежность, что данные после коммита будут сохранены на диск в случае сбоев.

## Эксперименты с транзакциями
- Для экспериментов с транзакциями будем использовать базу данных:

|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |
| 2 |  Bob  |   500   |
| 3 |Charlie|   200   |

### Эксперимент 1 Dirty Read/Грязное чтнение

**Цель:**
 - Проверить, видит ли одна транзакция незакоммиченные данные другой.

**Ожидание:**
 - В PostgreSQL по умолчанию стоит `READ COMMITTED`, поэтому нельзя увидить те данные которые не попали в коммит.

**Выполнение**
- Транзакция А
```
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
UPDATE accounts SET balance = balance + 100 WHERE id = 1;
SELECT * FROM accounts WHERE id = 1;
```
**Результат**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1100  |

- Транзакция Б паралельно выполняется А

```
BEGIN;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;
SELECT * FROM accounts WHERE id = 1;
```
**Результат**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

**Вывод**
- Эксперимент показал что грязное чтение в PostgreSQL невозможно и мы видим только закоминченные данные, что доказывает что по умолчанию уровень изоляции `READ COMMITTED`. Причина в том что MVCC работает со снапшотами закомиченными данными, незакомиченные изменения не видны.

### Эксперимент 2 Non-Repeatable Read/неповторяемое чтение

**Цель**
- Показать, что в READ COMMITTED данные могут меняться между запросами, а в REPEATABLE READ — нет.

**Выполнение**
- Изоляция: READ COMMITTED

 - Транзакция А
```
BEGIN;
SELECT * FROM accounts WHERE id = 1;
---
SELECT * FROM accounts WHERE id = 1;
```
 **Результат №1**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

 **Результат №2**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1500  |
 - Транзакция Б паралельно выполняется А

```
BEGIN;
UPDATE accounts SET balance = balance + 500 WHERE id = 1;
COMMIT;
```
- Изоляция: REPEATABLE READ

 - Транзакция А
```
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT * FROM accounts WHERE id = 1;
---
SELECT * FROM accounts WHERE id = 1;
```
 **Результат №1**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

 **Результат №2**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |
 - Транзакция Б паралельно выполняется А

```
BEGIN;
UPDATE accounts SET balance = balance + 500 WHERE id = 1;
COMMIT;
```
**Вывод**
- Эксперимент что уровень изоляции `REPEATABLE READ` показал что данные не меняются в рамках транзакции, и `READ COMMITTED` не поможет при неповторяющимся чтение.

### Эксперимент 3  Phantom Read/фантомное чтение
**Цель**
- Проверить, появляются ли новые строки, подходящие под условие возьмем два уровня изоляции `READ COMMITTED` и `REPEATABLE READ`.

**Выполнение:**


- Изоляция: READ COMMITTED

 - Транзакция А
```
BEGIN;
SELECT * FROM balances WHERE balance > 500;
-----
SELECT * FROM balances WHERE balance > 500;
```
 **Результат №1**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

 **Результат №2**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |
| 2 | Diana |   600  |

 - Транзакция Б паралельно выполняется А

```
BEGIN;
INSERT INTO balances (name, balance) VALUES ('Diana', 600);
COMMIT;
```
**Вывод**
- `READ COMMITTED` от фантомов не спасает, так как он берет снапшоте перед каждым `SELECT`.  


- Изоляция: REPEATABLE READ

 - Транзакция А
```
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT * FROM balances WHERE balance > 500;
-----
SELECT * FROM balances WHERE balance > 500;
```
 **Результат №1**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

 **Результат №2**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1000  |

 - Транзакция Б паралельно выполняется А

```
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
INSERT INTO balances (name, balance) VALUES ('Diana', 600);
COMMIT;
```
**Вывод**
- `REPEATABLE READ` защищает таблицу от фантомного чтения, новые записи не появляются, потому что `REPEATABLE READ` использует снапшоте в начале транзакции `SELECT` и видит ее в течение всей транзакции.

### Эксперимент 4  Lost Update/потерянное обновление 

**Цель**
- Показать, как уровень изоляции REPEATABLE READ может решить проблему с аномалией потерянное обновление и посмотреть что делает `READ COMMITTED` с потерянным обновлением.

**Ожидания**
- При уровне изоляции REPEATABLE READ вторая транзакция не сможет обновить строку, изменённую первой. Вместо тихой перезаписи она получит ошибку could not serialize access due to concurrent update. Уровнь изоляции READ COMMITTED тихо перезапишет данные и потерянное обновление не решает.

**Выполнение:**

- Изоляция: REPEATABLE READ

 - Транзакция А
```
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT * FROM balances WHERE id = 1;
---
UPDATE balances SET balance = 1100 WHERE id = 1;
COMMIT;
```
 **Результат**
|id | name  | balance |
|---|-------|---------|
| 1 | Alice |   1100  |

 - Транзакция Б паралельно выполняется А

```
BEGIN;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SELECT * FROM balances WHERE id = 1;
UPDATE balances SET balance = 1500 WHERE id = 1;
COMMIT;
```
 **Результат**
 - 1-транзакция: UPDATE 1, данные сохранились, первая транзакция выиграла она выполнислась первая. 
 - 2-транзакция: во время выполнения получила ошибку ```ERROR:  could not serialize access due to concurrent update``` и проиграла.

- Изоляция: READ COMMITTED

 - Транзакция А
```
BEGIN;
SELECT * FROM balances WHERE id = 4;
---
UPDATE balances SET balance = 1100 WHERE id = 4;
COMMIT;
```
 **Результат**
|id | name  | balance |
|---|-------|---------|
| 4 |  Bob  |  1500   |

 - Транзакция Б паралельно выполняется А

```
BEGIN;
SELECT * FROM balances WHERE id = 4;
UPDATE balances SET balance = 1500 WHERE id = 4;
COMMIT;
```
**Результат**
 - 2-транзакция перезаписала данные 1-транзакции и произошла потеря данных.

**Вывод**
- Уровень изоляции REPEATABLE READ не защищает от потерянного обновления автоматически. Вместо этого он обнаруживает конфликт при параллельных UPDATE и выбрасывает ошибку: ```ERROR:  could not serialize access due to concurrent update```. Это лучше, чем тихая потеря данных и перезапись в **READ UNCOMMITTED либо READ COMMITTED**, но требует от приложения явной обработки: повторного выполнения транзакции (retry).

## Блокировки и дедлоки:

- Табличные блокировки — блокируют всю таблицу.
- Строчные блокировки — блокируют конкретные строки.

**Виды блокировок:**
 - `FOR UPDATE` - блокирует строки, чтобы никто другой не мог их изменить.
 **Пример**
 ```
 BEGIN;
 SELECT * FROM users WHERE id = 1 FOR UPDATE;
 UPDATE accounts SET balance = balance + 100 WHERE id = 1;
 COMMIT;
 ```
 - `FOR SHARE` - блокирует строку для изменений, но позволяет другим читать.

  **Пример**

 ```
 BEGIN;
 SELECT * FROM users WHERE id = 1 FOR SHARE;
 COMMIT;
 ```
 - `SELECT ... FOR UPDATE SKIP LOCKED` - это механизм для очереди, который позволяет взять следующую не заблокированную строку, игнорируя те которые взяли.

 **Пример**
 
 ```
 1-Окно

 BEGIN;
 SELECT * FROM tasks 
 WHERE status = 'pending' 
 FOR UPDATE SKIP LOCKED 
 LIMIT 1;

 UPDATE tasks 
 SET status = 'processing', assigned_to = 'Worker_1' 
 WHERE id = 1;

 COMMIT;

 2-Окно

 BEGIN;
 SELECT * FROM tasks 
 WHERE status = 'pending' 
 FOR UPDATE SKIP LOCKED 
 LIMIT 1;

 UPDATE tasks 
 SET status = 'processing', assigned_to = 'Worker_2' 
 WHERE id = 2;

 COMMIT;
 ```  

- Дедлок - это ситуация, когда несколько транзакций ждут выполнение друг друга.

**Пример**
- Транзакция А

```
BEGIN;
SELECT * FROM users WHERE id = 1 FOR UPDATE;
UPDATE accounts SET amount = amount + 100 WHERE user_id = 2;
```

- Транзакция Б

```
BEGIN;
SELECT * FROM users WHERE id = 2 FOR UPDATE;
UPDATE accounts SET amount = amount + 100 WHERE user_id = 1;
```
- PostgreSQL сам умеет их обнаруживать и отменять одну из транзакций, он выберит ту которую дешевли откатить.

##  Как исправить Lost Update:

1. Оптимистичная блокировка
```
UPDATE accounts 
SET balance = balance + 100, version = version + 1
WHERE id = 1 AND version = 1;
```
**Плюс**
- Высокая производительность.
**Минус**
- Нужно обрабатывать конфликты на уровне приложения.
2. Пессимистичная блокировка:
```
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
UPDATE accounts SET balance = 1100 WHERE id = 1;
COMMIT;
```
**Плюс**
- Гарантирует согласованность, простота.
**Минус**
- Если транзакция долго выполняется, то другие ждут.
3. Мы не читаем значение отдельно, а бд нам сама считает значение. Это атомарно и никогда не приведёт к потерянному обновлению.
```
UPDATE accounts SET balance = balance + 100 WHERE id = 1;
```
**Вывод**
- Для исправления с Lost Update, есть три способа, если логика позволяет то просто можно использовать атомарный UPDATE. Если сначала нужно прочитать данные, то можно использовать SELECT FOR UPDATE — это пессимистичная блокировка, она проста, но снижает производительность при долгих транзакциях. Также есть оптимистичная блокировка через версию строки: она не блокирует строки.