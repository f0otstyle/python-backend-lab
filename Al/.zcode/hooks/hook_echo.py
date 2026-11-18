# Хук-эхо: учебный первый хук. Ничего не проверяет —
# ДОПИСЫВАЕТ каждое пришедшее на stdin событие в last_event.json,
# одно событие = одна строка (формат JSONL). Файл — журнал всех
# вызовов Bash, а не снимок последнего.
# Открой файл и посмотри реальную структуру входа (прогноз → факт).
import sys
import pathlib

raw = sys.stdin.read()                     # весь вход хука приходит только через stdin
out = pathlib.Path(__file__).with_name("last_event.json")
with out.open("a", encoding="utf-8") as f:      # "a" = append: дописываем в конец
    f.write(raw.rstrip("\n") + "\n")            # rstrip: stdin мог уже прийти с \n — без него будут пустые строки между событиями
sys.exit(0)                                # 0 = пропускаем, ничего не блокируем
