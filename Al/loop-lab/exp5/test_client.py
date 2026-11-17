"""Тесты отказоустойчивого клиента exp5 — на фейковом транспорте.

Реального HTTP и реальных задержек нет:
- транспорт — класс-мок с очередью HTTP-статусов и счётчиком вызовов;
- задержки — записывающая заглушка (delay_func), секунды копятся в список;
- часы CircuitBreaker — фиктивные (clock инъецируется), время идёт
  только через advance().

Запуск: python -m pytest test_client.py -v
"""
import asyncio

import pytest

from client import (
    BACKOFF_BASE,
    CB_K,
    CB_TIMEOUT,
    MAX_RETRIES,
    CircuitBreaker,
    CircuitOpenError,
    FetchError,
    fetch_with_retry,
)

URL = 'http://test/flaky'  # мок URL никуда не ходит, строка условная


class FakeResponse:
    """Минимальный ответ: единственный нужный клиенту атрибут — .status."""

    def __init__(self, status: int) -> None:
        self.status = status


class FakeTransport:
    """Мок транспорта: очередь ответов и счётчик вызовов get().

    Аргументы — последовательность HTTP-статусов; get() извлекает статусы
    по одному. Если очередь опустела, возвращается последний статус
    (удобно для «вечного 503»); лишние вызовы ловит счётчик calls.
    """

    def __init__(self, *statuses: int) -> None:
        self.queue = list(statuses)
        self.calls = 0
        self._last = statuses[0] if statuses else None

    async def get(self, url: str) -> FakeResponse:
        """Единственный async-метод, который дёргает клиент."""
        self.calls += 1
        status = self.queue.pop(0) if self.queue else self._last
        return FakeResponse(status)


class DelayRecorder:
    """Заглушка вместо asyncio.sleep: записывает запрошенные задержки."""

    def __init__(self) -> None:
        self.delays = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class FakeClock:
    """Фиктивные часы для CircuitBreaker: время стоит, пока не advance()."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_retry_success_after_two_503():
    """2×503 затем 200: успех с 3-й попытки, вызовов транспорта — 3.

    Full jitter: каждая задержка лежит в [0, base*2**i]. Граничные случаи
    детерминированы: множитель 1.0 даёт ровно экспоненциальный ряд
    base*2**i, множитель 0.0 схлопывает задержки в нули.
    """

    async def scenario(rand_func):
        transport = FakeTransport(503, 503, 200)
        delays = DelayRecorder()
        response = await fetch_with_retry(
            transport, URL,
            max_retries=MAX_RETRIES, base_delay=BACKOFF_BASE,
            delay_func=delays, rand_func=rand_func)
        return transport, delays, response

    # средний множитель: значения внутри границ jitter и ровно 0.5*cap
    transport, delays, response = asyncio.run(scenario(lambda: 0.5))
    assert response.status == 200
    assert transport.calls == 3                     # успех с 3-й попытки
    caps = [BACKOFF_BASE * 2 ** i for i in range(2)]
    assert all(0 <= d <= cap for d, cap in zip(delays.delays, caps))
    assert delays.delays == [0.5 * cap for cap in caps]

    # множитель 1.0: записанные задержки — ровно экспоненциальный ряд
    transport, delays, response = asyncio.run(scenario(lambda: 1.0))
    assert delays.delays == [BACKOFF_BASE * 2 ** i for i in range(2)]

    # множитель 0.0: full jitter сжимается до нулевых задержек
    transport, delays, response = asyncio.run(scenario(lambda: 0.0))
    assert delays.delays == [0.0, 0.0]


def test_retry_exhaustion_all_503():
    """Все попытки 503: исчерпание — FetchError с последним статусом.

    Вызовов транспорта ровно max_retries; между попытками записаны
    экспоненциальные задержки (rand→1.0): base*2**0 … base*2**(n-2),
    после последней неудачи задержки нет.
    """

    async def scenario():
        transport = FakeTransport(*([503] * MAX_RETRIES))
        delays = DelayRecorder()
        with pytest.raises(FetchError) as excinfo:
            await fetch_with_retry(transport, URL, delay_func=delays,
                                   rand_func=lambda: 1.0)
        assert excinfo.value.status == 503
        assert transport.calls == MAX_RETRIES
        assert delays.delays == [BACKOFF_BASE * 2 ** i
                                 for i in range(MAX_RETRIES - 1)]

    asyncio.run(scenario())


def test_4xx_fail_fast_without_retry():
    """404: немедленный отказ — FetchError, 1 вызов транспорта, без задержек."""

    async def scenario():
        transport = FakeTransport(404)
        delays = DelayRecorder()
        with pytest.raises(FetchError) as excinfo:
            await fetch_with_retry(transport, URL, delay_func=delays)
        assert excinfo.value.status == 404
        assert transport.calls == 1
        assert delays.delays == []

    asyncio.run(scenario())


def test_breaker_opens_after_k_consecutive_failures():
    """K подряд неудачных fetch_with_retry открывают предохранитель;
    вызов в open отклоняется CircuitOpenError без обращения к транспорту."""

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=CB_K, timeout=CB_TIMEOUT, clock=clock)
        transport = FakeTransport(503)  # «вечное» 503
        for _ in range(CB_K):
            with pytest.raises(FetchError):
                await fetch_with_retry(transport, URL, breaker=breaker,
                                       max_retries=1, delay_func=DelayRecorder())
        assert breaker.state == 'open'
        assert transport.calls == CB_K

        # запрос в состоянии open: транспорт вообще не вызывается
        fresh = FakeTransport(200)
        with pytest.raises(CircuitOpenError):
            await fetch_with_retry(fresh, URL, breaker=breaker, max_retries=1)
        assert fresh.calls == 0

    asyncio.run(scenario())


def test_breaker_call_in_open_rejects_without_running_factory():
    """breaker.call при открытом предохранителе бросает CircuitOpenError,
    причём фабрика корутины (и «транспорт» внутри неё) не вызывается вовсе.
    Исключения операции считаются неудачами предохранителя."""

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=2, timeout=CB_TIMEOUT, clock=clock)
        started = []

        async def failing():
            started.append(1)
            raise RuntimeError('сеть недоступна')

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(failing)
        assert breaker.state == 'open'

        started.clear()
        with pytest.raises(CircuitOpenError):
            await breaker.call(failing)
        assert started == []  # фабрика не выполнялась

    asyncio.run(scenario())


def test_breaker_half_open_success_closes_and_resets():
    """Фиктивные часы: истёкший таймаут переводит open в half-open;
    успешная проба возвращает в closed и сбрасывает счётчик неудач."""

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=CB_K, timeout=CB_TIMEOUT, clock=clock)
        transport = FakeTransport(503)
        for _ in range(CB_K):
            with pytest.raises(FetchError):
                await fetch_with_retry(transport, URL, breaker=breaker,
                                       max_retries=1, delay_func=DelayRecorder())
        assert breaker.state == 'open'

        clock.advance(CB_TIMEOUT)  # таймаут истёк → half-open
        assert breaker.state == 'half-open'

        ok_transport = FakeTransport(200)
        response = await fetch_with_retry(ok_transport, URL, breaker=breaker,
                                          max_retries=1)
        assert response.status == 200
        assert breaker.state == 'closed'
        assert breaker.failures == 0  # счётчик неудач сброшен

    asyncio.run(scenario())


def test_breaker_half_open_failure_reopens():
    """Отказ пробы в half-open возвращает предохранитель в open;
    до нового таймаута вызовы снова отклоняются, затем — снова half-open."""

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=CB_K, timeout=CB_TIMEOUT, clock=clock)
        transport = FakeTransport(503)
        for _ in range(CB_K):
            with pytest.raises(FetchError):
                await fetch_with_retry(transport, URL, breaker=breaker,
                                       max_retries=1, delay_func=DelayRecorder())
        clock.advance(CB_TIMEOUT)
        assert breaker.state == 'half-open'

        # проба неудачна → снова open
        with pytest.raises(FetchError):
            await fetch_with_retry(transport, URL, breaker=breaker,
                                   max_retries=1, delay_func=DelayRecorder())
        assert breaker.state == 'open'

        # до истечения нового таймаута — отказ без транспорта
        fresh = FakeTransport(200)
        with pytest.raises(CircuitOpenError):
            await fetch_with_retry(fresh, URL, breaker=breaker, max_retries=1)
        assert fresh.calls == 0

        # часы идут → снова half-open
        clock.advance(CB_TIMEOUT)
        assert breaker.state == 'half-open'

    asyncio.run(scenario())


def test_breaker_half_open_allows_single_probe():
    """В half-open допускается ровно одна проба: второй вызов, пока проба
    выполняется, отклоняется CircuitOpenError; успех пробы → closed."""

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=1, timeout=CB_TIMEOUT, clock=clock)

        async def fail():
            raise RuntimeError('сбой')

        with pytest.raises(RuntimeError):
            await breaker.call(fail)  # k=1: одна неудача → open
        clock.advance(CB_TIMEOUT)
        assert breaker.state == 'half-open'

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_probe():
            started.set()
            await release.wait()
            return 'готово'

        probe = asyncio.create_task(breaker.call(slow_probe))
        await started.wait()
        with pytest.raises(CircuitOpenError):
            await breaker.call(slow_probe)  # вторая проба не пускается
        release.set()
        assert await probe == 'готово'
        assert breaker.state == 'closed'

    asyncio.run(scenario())


def test_breaker_half_open_cancelled_probe_releases_flag():
    """Отмена зависающей half-open пробы (asyncio.CancelledError) не
    заклинивает предохранитель: флаг пробы освобождается, следующая
    проба допускается.

    Отмена пробрасывается вызывающему и не считается ни успехом
    (состояние остаётся half-open), ни неудачей (снова open не происходит).
    """

    async def scenario():
        clock = FakeClock()
        breaker = CircuitBreaker(k=1, timeout=CB_TIMEOUT, clock=clock)

        async def fail():
            raise RuntimeError('сбой')

        with pytest.raises(RuntimeError):
            await breaker.call(fail)  # k=1: одна неудача → open
        clock.advance(CB_TIMEOUT)
        assert breaker.state == 'half-open'

        started = asyncio.Event()

        async def hanging_probe():
            started.set()
            await asyncio.Event().wait()  # никогда не отпустит — ждём отмены

        probe = asyncio.create_task(breaker.call(hanging_probe))
        await started.wait()  # проба началась: фабрика выполнена, флаг занят
        probe.cancel()

        # отмена доходит до вызывающего, а не превращается в результат
        with pytest.raises(asyncio.CancelledError):
            await probe
        assert breaker.state == 'half-open'  # ни closed (успех), ни open (неудача)

        # флаг пробы освобождён: следующая проба допускается
        async def ok_probe():
            return 'второй'

        assert await breaker.call(ok_probe) == 'второй'
        assert breaker.state == 'closed'
        assert breaker.failures == 0

    asyncio.run(scenario())


def test_fetch_with_open_breaker_makes_no_transport_calls():
    """Открытый брейкер + fetch_with_retry: отклонение сразу,
    ни одного вызова транспорта."""

    async def scenario():
        breaker = CircuitBreaker(k=1, timeout=CB_TIMEOUT, clock=FakeClock())

        async def fail():
            raise RuntimeError('сбой')

        with pytest.raises(RuntimeError):
            await breaker.call(fail)  # открываем предохранитель

        transport = FakeTransport(200)
        with pytest.raises(CircuitOpenError):
            await fetch_with_retry(transport, URL, breaker=breaker)
        assert transport.calls == 0

    asyncio.run(scenario())
