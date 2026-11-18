"""Базовые статистические функции для числовых последовательностей.

Учебный модуль exp4: только стандартная библиотека, без зависимостей.
"""


def mean(numbers):
    """Среднее арифметическое элементов последовательности.

    Аргумент:
        numbers: список или кортеж чисел (int/float).

    Возвращает:
        float — сумма элементов, делённая на их количество.

    Исключение:
        ValueError: если последовательность пуста.
    """
    if not numbers:
        raise ValueError("mean(): последовательность не должна быть пустой")
    return sum(numbers) / len(numbers)


def max_diff(numbers):
    """Максимальная абсолютная разность соседних элементов.

    Аргумент:
        numbers: список или кортеж чисел (int/float) длиной не меньше 2.

    Возвращает:
        Число — максимум из abs(numbers[i+1] - numbers[i]) по всем парам.

    Исключение:
        ValueError: если в последовательности меньше двух элементов.
    """
    if len(numbers) < 2:
        raise ValueError("max_diff(): нужно не меньше двух элементов")
    return max(abs(numbers[i + 1] - numbers[i]) for i in range(len(numbers) - 1))


if __name__ == "__main__":
    demo = [1, 2, 3, 4]
    print("mean([1, 2, 3, 4]) =", mean(demo))          # 2.5
    print("max_diff([2, 10, 3]) =", max_diff([2, 10, 3]))  # 8

    try:
        mean([])
    except ValueError as e:
        print("mean([]) ->", e)
    try:
        max_diff([5])
    except ValueError as e:
        print("max_diff([5]) ->", e)
