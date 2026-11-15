# Хук проверки синтаксиса (ZCode, PreToolUse Write|Edit): ДО записи .py на диск
# проверяет ИТОГОВЫЙ текст через compile():
#   - Write: tool_input.content — полный будущий текст файла;
#   - Edit:  текущий файл с диска + замена old_string -> new_string.
# Синтаксическая ошибка -> exit 2: вызов отклоняется, агент видит строку
# и текст ошибки и должен исправить текст и вызвать Write/Edit снова.
# Идея вывода с номером строки — из git-хука (githooks/pre-commit).
# exit 0 — пропуск (не .py или синтаксис ок); fail-open на любые свои сбои:
# stdin читается байтами и декодируется в UTF-8 явно (на Windows локальная
# кодировка может быть cp1251), файл с диска — строго utf-8-sig (снимает BOM,
# без errors=replace, чтобы не подставлять U+FFFD и не давать ложный deny).
import json
import sys
from pathlib import Path

TOOLS = ("Write", "Edit")


def reconstruct_edit(tool_input: dict) -> str:
    """Текст .py после Edit: файл с диска + замена old_string -> new_string."""
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
        # fail-open: вход не разобрался — не блокируем работу агента, но кричим
        sys.stderr.write(f"py_check: вход не разобран ({e}); пропускаю\n")
        return 0

    tool_name = str(data.get("tool_name") or data.get("toolName") or "")
    if tool_name and tool_name not in TOOLS:
        return 0   # чужой инструмент — не наша проверка
    tool_input = data.get("tool_input") or data.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        return 0
    path = str(tool_input.get("file_path", ""))

    # реагируем только на .py (регистр не важен — Windows пути нечувствительны)
    if not path.replace("\\", "/").lower().endswith(".py"):
        return 0

    if "content" in tool_input:                 # Write: весь текст уже в запросе
        content = str(tool_input.get("content", ""))
    elif Path(path).is_file():                  # Edit: файл существует — реконструируем
        try:
            content = reconstruct_edit(tool_input)
        except (OSError, ValueError) as e:      # чтение/декодирование не вышло — fail-open
            sys.stderr.write(f"py_check: не смог прочитать {path} ({e}); пропускаю\n")
            return 0
    else:                                       # Edit несуществующего файла: сам упадёт
        return 0

    try:
        compile(content, path, "exec")
    except SyntaxError as e:
        line = (e.text or "").strip()[:120]
        sys.stderr.write(
            f"py_check: синтаксическая ошибка {path}:{e.lineno or '?'} — {e.msg}\n"
            f"    {line}\n"
            "Исправь текст и вызови Write/Edit снова.\n"
        )
        return 2   # PreToolUse: deny — битый код не попадёт на диск
    except (ValueError, TypeError) as e:
        # не-синтаксические отказы compile (нулевые байты и т.п.) — fail-open
        sys.stderr.write(f"py_check: compile не отработал ({e}); пропускаю\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
