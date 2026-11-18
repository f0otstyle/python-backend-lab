#!/usr/bin/env bash
# Проверка pre-commit хука «синтаксис staged-версии, а не рабочей копии» —
# воспроизводимая из дерева: скрипт сам создаёт временный учебный репозиторий,
# подключает хук из ../githooks через core.hooksPath и прогоняет оба сценария
# частичного staging на пути с пробелами и кириллицей.
#
# Сценарий 1: сломано в индексе, исправлено в рабочей копии → коммит
#             блокируется хуком (проверяется staged blob: git show :путь).
# Сценарий 2: исправлено в индексе, сломано в рабочей копии → коммит проходит.
#
# Запуск: bash run_checks.sh (из любой точки; в PATH должны быть git и python).
# Код выхода: 0 — оба сценария совпали с ожиданием; 1 — расхождение
# (в этом случае временный репозиторий не удаляется, путь печатается для разбора).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHOOKS_DIR="$(cd "$SCRIPT_DIR/../githooks" && pwd)"

if [ ! -f "$GITHOOKS_DIR/pre-commit" ]; then
    echo "run_checks: хук не найден: $GITHOOKS_DIR/pre-commit" >&2
    exit 1
fi

# Вывод хука (python) форсируем в UTF-8, чтобы grep по кириллице не зависел
# от ANSI-кодировки: на Windows python пишет в pipe в локальной кодировке.
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

LAB="$(mktemp -d "${TMPDIR:-/tmp}/precommit-lab.XXXXXX")"
REPO="$LAB/repo"
# путь с пробелами и кириллицей: именно такой путь хук должен разобрать (-z)
PYREL="учебные файлы/модуль с пробелами.py"
PYFILE="$REPO/$PYREL"

failures=0

cleanup() {
    if [ "$failures" -eq 0 ]; then
        rm -rf "$LAB"
    else
        echo "run_checks: есть расхождения, временный репозиторий оставлен: $LAB"
    fi
}
trap cleanup EXIT

git init -q "$REPO" >/dev/null 2>&1
git -C "$REPO" config user.email "lab@example.com"
git -C "$REPO" config user.name "precommit-lab"
git -C "$REPO" config core.hooksPath "$GITHOOKS_DIR"
git -C "$REPO" config core.autocrlf false   # без warning про LF→CRLF в выводе
mkdir -p "$(dirname "$PYFILE")"
git -C "$REPO" commit -q --allow-empty -m "init" >/dev/null 2>&1

# --- сценарий 1: сломано в индексе, исправлено в рабочей копии ---
printf 'def ок():\n    return 1 +\n' > "$PYFILE"     # сломано → в индекс
git -C "$REPO" add "$PYREL"
printf 'def ок():\n    return 1\n' > "$PYFILE"       # исправлено в рабочей копии

head_before="$(git -C "$REPO" rev-parse HEAD)"
if out="$(git -C "$REPO" commit -m "сломано в индексе" 2>&1)"; then
    echo "СЦЕНАРИЙ 1: ПРОВАЛ — коммит прошёл, ожидалась блокировка хуком"
    printf '%s\n' "$out"
    failures=$((failures + 1))
else
    head_after="$(git -C "$REPO" rev-parse HEAD)"
    if [ "$head_before" = "$head_after" ] && printf '%s\n' "$out" | grep -q "Коммит отменён"; then
        echo "СЦЕНАРИЙ 1: OK — коммит заблокирован хуком (staged-версия сломана, рабочая копия исправлена)"
        printf '%s\n' "$out" | grep "Коммит отменён"
    else
        echo "СЦЕНАРИЙ 1: ПРОВАЛ — коммит не прошёл, но не по выводу хука (или HEAD изменился)"
        printf '%s\n' "$out"
        failures=$((failures + 1))
    fi
fi

# --- сценарий 2: исправлено в индексе, сломано в рабочей копии ---
printf 'def ок():\n    return 1\n' > "$PYFILE"       # исправлено → в индекс
git -C "$REPO" add "$PYREL"
printf 'def сломано(:\n    return 1 +\n' > "$PYFILE" # сломано в рабочей копии

if out="$(git -C "$REPO" commit -m "исправлено в индексе" 2>&1)"; then
    if printf '%s\n' "$out" | grep -q "Синтаксис OK"; then
        echo "СЦЕНАРИЙ 2: OK — коммит прошёл, хук проверил staged-версию (индекс исправлен, рабочая копия сломана)"
        printf '%s\n' "$out" | grep "Синтаксис OK"
    else
        echo "СЦЕНАРИЙ 2: ПРОВАЛ — коммит прошёл, но вывод хука без «Синтаксис OK»:"
        printf '%s\n' "$out"
        failures=$((failures + 1))
    fi
else
    echo "СЦЕНАРИЙ 2: ПРОВАЛ — коммит заблокирован, ожидался проход:"
    printf '%s\n' "$out"
    failures=$((failures + 1))
fi

if [ "$failures" -eq 0 ]; then
    echo "ИТОГ: оба сценария воспроизведены — хук проверяет staged blob, а не рабочую копию."
fi
[ "$failures" -eq 0 ]
