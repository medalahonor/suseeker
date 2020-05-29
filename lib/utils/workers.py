import logging
from typing import Callable

import gevent
from gevent.queue import Queue

from lib.utils.constants import DISCARD_WORDS, RETRY_WORDS, SPLIT_WORDS


class AbstractWorker:
    def __init__(self, work: Callable, args_queue: Queue, results_queue: Queue):
        self.work = work
        self.args_queue = args_queue
        self.results_queue = results_queue

        self._running = False
        self._finish = False
        self._stopped = False

    def run(self):
        raise NotImplementedError

    def finish(self):
        self._finish = True

    def is_running(self):
        return self._running

    def is_stopped(self):
        return self._stopped


class GuessWorker(AbstractWorker):
    def __init__(self, work: Callable, args_queue: Queue, results_queue: Queue, logger: logging.Logger):
        super().__init__(work, args_queue, results_queue)

        self.logger = logger

    def run(self):
        # Переключения контекста для запуска других воркеров
        gevent.sleep(0)

        self._running = True
        self._stopped = False

        while not self._finish:
            try:
                info, words = self.args_queue.get(timeout=0.1)
            except gevent.queue.Empty:
                self._running = False
                continue

            self._running = True

            result = self.work(info, words)

            # Если среди заголовков или параметров нет секретных, то переходим к следующей пачке
            if isinstance(result, int):
                if result == DISCARD_WORDS:
                    continue
                # Если не удалось выполнить запрос, то возвращаем аргументы в очередь
                elif result == RETRY_WORDS:
                    self.args_queue.put((info, words))
                # Если среди заголовков или параметров есть секретный, то делим пачку напополам
                elif result == SPLIT_WORDS:
                    self.args_queue.put((info, words[:len(words) // 2]))
                    self.args_queue.put((info, words[len(words) // 2:]))
                else:
                    raise NotImplementedError
            # Если найден конкретный заголовок или параметр
            elif isinstance(result, dict):
                self.results_queue.put(result)
            else:
                raise NotImplementedError

        self._running = False
        self._stopped = True
