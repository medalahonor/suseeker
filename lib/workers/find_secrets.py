import gevent

from gevent.queue import Queue

from lib.constants import DISCARD_WORDS, RETRY_WORDS, SPLIT_WORDS
from lib.utils.logger import Logger
from lib.workers.abstract import AbstractWorker


class FindSecretsWorker(AbstractWorker):
    def __init__(self, args_queue: Queue, results_queue: Queue, logger: Logger):
        super().__init__()

        self.args_queue = args_queue
        self.results_queue = results_queue
        self.logger = logger

    def run(self):
        while not self._finish:
            try:
                work, info, words = self.args_queue.get(timeout=0.1)
            except gevent.queue.Empty:
                self._running = False
                continue

            self._running = True
            result = work(info, words)

            # Если среди заголовков или параметров нет секретных, то переходим к следующей пачке
            if isinstance(result, int):
                if result == DISCARD_WORDS:
                    continue
                # Если не удалось выполнить запрос, то возвращаем аргументы в очередь
                elif result == RETRY_WORDS:
                    self.args_queue.put((work, info, words))
                # Если среди заголовков или параметров есть секретный, то делим пачку напополам
                elif result == SPLIT_WORDS:
                    self.args_queue.put((work, info, words[:len(words) // 2]))
                    self.args_queue.put((work, info, words[len(words) // 2:]))
                else:
                    raise NotImplementedError
            # Если найден конкретный заголовок или параметр
            elif isinstance(result, dict):
                self.results_queue.put(result)
            else:
                raise NotImplementedError

        self._running = False
        self._stopped = True
