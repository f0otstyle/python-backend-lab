"""Отказоустойчивый клиент для стенда exp5.

1. Запусти стенд:   python -m uvicorn server:app --port 8000
2. Запусти клиент:  python client.py
3. Стенд на первые запросы к /flaky отвечает 503 — клиент добивается
   успеха повторными попытками с экспоненциальным backoff + full jitter,
   а предохранитель CircuitBreaker не даёт долбить лежащий сервис.

Адрес сервера можно переопределить переменной окружения LAB_URL:
LAB_URL=http://localhost:8010 python client.py

Транспорт инъецируется аргументом (любой объект с async-методом get(url),
возвращающим ответ со .status) — поэтому тесты гоняются на моке без сети.
"""
import asyncio
import os
import random
import time

import aiohttp

BASE_URL = os.environ.get('LAB_URL', 'http://localhost:8000')
COUNT = 5            # сколько запросов к /flaky в демо-сценарии
MAX_RETRIES = 5      # максимум попыток на один запрос
BACKOFF_BASE = 0.2   # база экспоненциальной задержки между попытками, c
CB_K = 3             # сколько подряд неудач открывают предохранитель
CB_TIMEOUT = 2.0     # сколько секунд предохранитель остаётся открытым, c
TIMEOUT = 60         # общий таймаут aiohttp-сессии, c


class CircuitOpenError(Exception):
    """Предохранитель открыт: вызов отклонён без обращения к транспорту."""


class FetchError(Exception):
    """Отказ запроса: 4xx без повторов или исчерпание попыток на 5xx.

    Атрибуты: url — запрошенный адрес; status — последний HTTP-статус
    (или None, если ни одного ответа не получили).
    """

    def __init__(self, url: str, status=None) -> None:
        self.url = url
        self.status = status
        if status is not None:
            super().__init__(f'{url}: HTTP-статус {status}')
        else:
            super().__init__(f'{url}: ответа нет')


class CircuitBreaker:
    """Предохранитель: closed → open (после K подряд неудач) →
    half-open (когда по часам истёк timeout) → closed (успех пробы)
    или снова open (отказ пробы).

    Аргументы:
      k — сколько ПОДРЯД неудач переводят предохранитель в open;
      timeout — сколько секунд (по часам clock) предохранитель остаётся
        открытым, после чего разрешается одна проба (half-open);
      clock — функция без аргументов, возвращающая текущее время
        (по умолчанию time.monotonic); инъекция часов нужна для тестов.

    Публичные атрибуты: state ('closed' | 'open' | 'half-open' —
    переход в half-open ленивый, вычисляется по часам), failures —
    счётчик подряд неудач (сбрасывается успехом).

    Поколения состояния: каждый переход состояния (closed → open,
    half-open → closed, half-open → open) открывает новое поколение.
    Вызов запоминает поколение на момент допуска, и его запоздалое
    завершение (успех, неудача, отмена) игнорируется, если поколение
    уже сменилось, — вызов из прежнего поколения не должен менять
    состояние нового. Флаг пробы в half-open освобождает только
    владелец пробы (вызов, допущенный пробой в текущем поколении),
    а не любой отменённый вызов.
    """

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half-open'

    def __init__(self, k=CB_K, timeout=CB_TIMEOUT, clock=time.monotonic) -> None:
        self.k = k
        self.timeout = timeout
        self.clock = clock
        self._state = self.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self._probe_running = False
        self._probe_gen = None   # поколение, в котором допущена текущая проба
        self._generation = 0     # номер поколения состояния; растёт на переходах

    @property
    def state(self) -> str:
        """Текущее состояние; открытый предохранитель, у которого истёк
        таймаут, считается half-open (проба разрешена)."""
        if (self._state == self.OPEN
                and self.clock() - self.opened_at >= self.timeout):
            return self.HALF_OPEN
        return self._state

    async def call(self, coro_factory):
        """Пропускает вызов через предохранитель.

        Аргумент: coro_factory — функция без аргументов, создающая корутину;
        она вызывается ТОЛЬКО если предохранитель пускает (в open фабрика
        не выполняется вовсе).

        Возвращает результат операции. Исключения:
          CircuitOpenError — предохранитель открыт (или проба уже идёт);
          любые исключения операции — пробрасываются дальше и засчитываются
          как неудача текущего поколения (запоздалое завершение вызова,
          допущенного в прежнем поколении, состояние не меняет);
          asyncio.CancelledError — пробрасывается вызывающему как есть
          и не считается ни успехом, ни неудачей (флаг пробы освобождает
          только владелец пробы, иначе half-open заклинивает навсегда;
          отмена вызова, допущенного в прежнем поколении, чужую пробу
          не отпускает).
        """
        gen = self._generation
        probe_gen = self._acquire()
        try:
            result = await coro_factory()
        except asyncio.CancelledError:
            # отмена — не успех и не неудача: флаг пробы освобождает только
            # владелец пробы, отмена более не допущенного в half-open вызова
            # флаг не трогает; отмену пробрасываем дальше
            if probe_gen is not None and probe_gen == self._probe_gen:
                self._probe_running = False
            raise
        except Exception:
            self._on_failure(gen)
            raise
        self._on_success(gen)
        return result

    def _acquire(self):
        """Решает, пускает ли предохранитель новый вызов.

        open — CircuitOpenError; half-open — пускает ровно одну пробу
        (второй параллельный вызов получает CircuitOpenError).
        Возвращает поколение, в котором вызов допущен пробой; для вызова
        в closed — None (он не владеет флагом пробы).
        """
        state = self.state
        if state == self.OPEN:
            raise CircuitOpenError('предохранитель открыт — вызов отклонён')
        if state == self.HALF_OPEN:
            if self._probe_running:
                raise CircuitOpenError('в half-open уже выполняется проба')
            self._probe_running = True
            self._probe_gen = self._generation
            return self._generation
        return None

    def _on_success(self, gen) -> None:
        """Успех (в том числе успех пробы) → closed, счётчик неудач сброшен.

        Вызов прежнего поколения ничего не меняет: его запоздалый успех
        не должен сбрасывать счётчик неудач нового поколения.
        """
        if gen != self._generation:
            return
        if self.state == self.HALF_OPEN:
            # успех пробы: half-open → closed, новое поколение
            self._probe_running = False
            self._state = self.CLOSED
            self.failures = 0
            self._generation += 1
            return
        self.failures = 0

    def _on_failure(self, gen) -> None:
        """Неудача: в half-open — сразу снова open; в closed — после
        K подряд неудач → open.

        Вызов прежнего поколения ничего не меняет: его запоздалая неудача
        не должна ни считаться в новом поколении, ни возвращать open
        во время чужой пробы.
        """
        if gen != self._generation:
            return
        if self.state == self.HALF_OPEN:
            # отказ пробы: half-open → open, новое поколение
            self._probe_running = False
            self._trip()
            return
        self.failures += 1
        if self.failures >= self.k:
            self._trip()

    def _trip(self) -> None:
        """Открыть предохранитель, запомнив момент (по инъецированным часам);
        открытый — новое поколение состояния."""
        self._generation += 1
        self._state = self.OPEN
        self.opened_at = self.clock()


class AiohttpTransport:
    """Живой транспорт на aiohttp для демо-сценария.

    Адаптирует aiohttp-сессию к контракту клиента: async-метод get(url),
    возвращающий объект со .status. Считает вызовы — это счётчик попыток
    для итоговой печати. Тесты этот класс не трогают (у них свой мок).
    """

    def __init__(self, session: 'aiohttp.ClientSession') -> None:
        self._session = session
        self.calls = 0

    async def get(self, url: str):
        """GET-запрос; возвращает ответ (статус читается и после release)."""
        self.calls += 1
        async with self._session.get(url) as response:
            await response.read()
            return response


async def _sleep(seconds: float) -> None:
    """Задержка по умолчанию — asyncio.sleep (в тестах инъектируется)."""
    await asyncio.sleep(seconds)


async def fetch_with_retry(transport, url, *, breaker=None,
                           max_retries=MAX_RETRIES, base_delay=BACKOFF_BASE,
                           delay_func=None, rand_func=random.random):
    """GET-запрос с повторными попытками и опциональным предохранителем.

    Аргументы:
      transport — объект с async-методом get(url), возвращающим ответ
        со .status (мок в тестах, AiohttpTransport в живом запуске);
      url — адрес запроса;
      breaker — опциональный CircuitBreaker: вся цепочка попыток
        пропускается через breaker.call, поэтому отказ (FetchError или
        исключение транспорта) засчитывается предохранителю как неудача;
        CircuitOpenError не глотается, а пробрасывается вызывающему;
      max_retries — максимум попыток;
      base_delay — база экспоненциальной задержки, c;
      delay_func — async-функция задержки (по умолчанию asyncio.sleep);
        в тестах подменяется записывающей заглушкой, реальных пауз нет;
      rand_func — источник случайности для full jitter (по умолчанию
        random.random); задержка = base_delay * 2**attempt * rand_func(),
        то есть лежит в [0, base_delay * 2**attempt].

    Логика по статусам: <400 — успех, ответ возвращается как есть;
    4xx — немедленный отказ без повторов; >=500 — повторная попытка.

    Возврат: ответ (объект со .status) при успехе.
    Исключения: FetchError — 4xx или исчерпание max_retries попыток
    (в исключении .status — последний полученный статус);
    CircuitOpenError — отказ предохранителя; прочие — исключения транспорта.
    """

    async def run_attempts():
        response = None
        for attempt in range(max_retries):
            response = await transport.get(url)
            if response.status < 400:
                return response
            if response.status < 500:
                raise FetchError(url, status=response.status)  # 4xx без ретраев
            if attempt < max_retries - 1:
                # экспоненциальная задержка с full jitter, между попытками
                await (delay_func or _sleep)(
                    base_delay * 2 ** attempt * rand_func())
        raise FetchError(url, status=response.status if response else None)

    if breaker is not None:
        return await breaker.call(run_attempts)
    return await run_attempts()


async def main() -> None:
    """Демо-сценарий: COUNT запросов к /flaky через fetch_with_retry
    с предохранителем; в конце — счётчики и итоговая строка."""
    print(f'Сервер: {BASE_URL}')
    print(f'{COUNT} запросов на /flaky '
          f'(до {MAX_RETRIES} попыток, брейкер K={CB_K}/{CB_TIMEOUT} c)')
    started = time.perf_counter()
    successes = failures = 0
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        transport = AiohttpTransport(session)
        breaker = CircuitBreaker(k=CB_K, timeout=CB_TIMEOUT)
        for num in range(1, COUNT + 1):
            try:
                response = await fetch_with_retry(
                    transport, f'{BASE_URL}/flaky', breaker=breaker)
            except (CircuitOpenError, FetchError) as exc:
                failures += 1
                print(f'  запрос №{num}: отказ ({exc})')
            else:
                successes += 1
                print(f'  запрос №{num}: /flaky -> {response.status}')
    elapsed = time.perf_counter() - started
    print(f'Попыток: {transport.calls}, успехов: {successes}, отказов: {failures}')
    print(f'Итог: {successes}/{COUNT} успешно за {elapsed:.2f} c')


if __name__ == '__main__':
    asyncio.run(main())
