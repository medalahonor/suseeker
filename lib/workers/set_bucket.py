import gevent

from gevent.queue import Queue

from lib.utils.logger import Logger
from lib.workers.abstract import AbstractWorker


class SetBucketWorker(AbstractWorker):
    def __init__(self, args_queue: Queue, logger: Logger):
        super().__init__()

        self.args_queue = args_queue
        self.logger = logger

    def run(self):
        while not self._finish:
            try:
                work, info = self.args_queue.get(timeout=0.1)
            except gevent.queue.Empty:
                self._running = False
                continue

            self._running = True
            work(info)

        self._running = False
        self._stopped = True