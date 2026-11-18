# TASKS: exp5 (параллельные подзадачи)

Спецификация: `SPEC.md` (копия в каждом worktree). Коммиты запрещены —
файлы собираются в основную папку вручную.

## Подзадача 1: стенд

- Worktree: `D:/DEV_2/concurrency-lab/exp5-stand` (ветка `feature/exp5-stand`)
- Рабочая папка: `Al/loop-lab/exp5/` внутри worktree
- Файлы: `server.py`, `test_server.py`
- Субагент: general-purpose (TDD red→green, TestClient)

## Подзадача 2: клиент и тесты

- Worktree: `D:/DEV_2/concurrency-lab/exp5-client` (ветка `feature/exp5-client`)
- Рабочая папка: `Al/loop-lab/exp5/` внутри worktree
- Файлы: `client.py`, `test_client.py`
- Субагент: general-purpose (TDD red→green, фейковый транспорт)

## Сборка (после зелёных отчётов обоих)

Перенести 4 файла в `loop-lab/exp5/` основной папки, прогнать
`pytest` и `py_compile` на месте, отчёт пользователю.
