# Хук качества спецификации v5: срабатывает на PreToolUse (Write|Edit).
# Проверяет ИТОГОВОЕ содержимое SPEC.md до записи на диск:
#   - Write: tool_input.content — полный будущий текст файла;
#   - Edit:  реконструкция — текущий файл с диска + замена
#            old_string -> new_string (как это сделает сам Edit).
# В SPEC.md обязательны разделы Цель, Шаги, Критерии готовности (DoD), Границы.
# Не хватает -> exit 2: вызов отклоняется (deny), агент видит причину
# и должен дополнить текст и вызвать Write/Edit снова.
# История: v3 проверял только Write; v4 добавила Edit и закрыла обход правкой.
# v5: кодировка (stdin байтами в UTF-8, диск строго utf-8-sig — снимает BOM)
# и тотальный fail-open: любой собственный сбой = пропуск, не блокировка.
import json
import sys
import re
from pathlib import Path

REQUIRED = {
    "Цель":               r"^#{1,3}\s*(Цель|Goal)\b",
    "Шаги":               r"^#{1,3}\s*Шаги\b",
    "Критерии готовности": r"^#{1,3}\s*(Критерии\s*готовности|DoD)\b",
    "Границы":            r"^#{1,3}\s*Границы\b",
}

TOOLS = ("Write", "Edit")


def reconstruct_edit(tool_input: dict) -> str:
    """Текст SPEC.md после Edit: файл с диска + замена old_string -> new_string."""
    base = Path(str(tool_input.get("file_path", ""))).read_text(
        encoding="utf-8-sig")
    old = str(tool_input.get("old_string", ""))
    new = str(tool_input.get("new_string", ""))
    if old and old in base:
        if tool_input.get("replace_all"):
            return base.replace(old, new)
        return base.replace(old, new, 1)
    return base   # замена не нашлась — Edit сам упадёт, валидируем как есть


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        # fail-open: свой баг парсинга не должен блокировать работу агента
        sys.stderr.write(f"spec_check: не смог разобрать вход ({e}); пропускаю\n")
        return 0

    tool_name = str(data.get("tool_name") or data.get("toolName") or "")
    if tool_name and tool_name not in TOOLS:
        return 0   # чужой инструмент — не наша проверка
    tool_input = data.get("tool_input") or data.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        return 0
    path = str(tool_input.get("file_path", ""))

    # Реагируем только на запись спецификации, на остальные файлы — молча пропускаем.
    # Регистр не важен (spec.md == SPEC.md); обе конвенции имён полей.
    if not path.replace("\\", "/").lower().endswith("spec.md"):
        return 0

    if "content" in tool_input:                 # Write: весь текст уже в запросе
        content = str(tool_input.get("content", ""))
    elif Path(path).is_file():                  # Edit: файл существует — реконструируем
        try:
            content = reconstruct_edit(tool_input)
        except (OSError, ValueError) as e:      # чтение/декодирование не вышло — fail-open
            sys.stderr.write(f"spec_check: не смог прочитать {path} ({e}); пропускаю\n")
            return 0
    else:                                       # Edit несуществующего файла: сам упадёт
        return 0

    missing = [name for name, rx in REQUIRED.items()
               if not re.search(rx, content, re.M | re.I)]

    if missing:
        sys.stderr.write(
            "SPEC.md не пройдёт проверку. Отсутствуют разделы: "
            + ", ".join(missing)
            + ". Обязательные: Цель, Шаги, Критерии готовности (DoD), Границы. "
            + "Дополни текст и вызови Write/Edit снова."
        )
        return 2   # PreToolUse: deny — запись не произойдёт

    return 0


if __name__ == "__main__":
    sys.exit(main())
