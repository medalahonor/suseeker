from typing import Callable

import gevent
from gevent.queue import Queue

from lib.workers.abstract import AbstractWorker


class GetScriptsWorker(AbstractWorker):
    def __init__(self, work: Callable, args_queue: Queue, results_queue: Queue):
        super().__init__()

        self.work = work
        self.args_queue = args_queue
        self.results_queue = results_queue

    def run(self):
        # Переключения контекста для запуска других воркеров
        gevent.sleep(0)

        self._running = True
        self._stopped = False

        while not self._finish:
            try:
                netloc, src = self.args_queue.get(timeout=1)
            except gevent.queue.Empty:
                self._running = False
                continue

            self._running = True

            result = self.work(netloc, src)
            self.results_queue.put(result)

        self._running = False
        self._stopped = True