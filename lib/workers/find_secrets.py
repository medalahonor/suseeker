import heapq

import gevent

from lib.constants import DISCARD_WORDS, RETRY_WORDS, SPLIT_WORDS
from lib.structures import PrioritizedItem
from lib.utils.logger import Logger
from lib.workers.abstract import AbstractWorker


class FindSecretsWorker(AbstractWorker):
    def __init__(self, args_heapq: list, results: list, logger: Logger):
        super().__init__()

        self.args_heapq = args_heapq
        self.results = results
        self.logger = logger

    def run(self):
        while not self._finish:
            try:
                item = heapq.heappop(self.args_heapq)
                priority = item.priority
                work, info, words = item.item
            except IndexError:
                self._running = False
                gevent.sleep(0.1)
                continue

            self._running = True

            result = work(info, words)
            # Переключаем контекст после выполненной работы
            gevent.sleep(0)

            # Если среди заголовков или параметров нет секретных, то переходим к следующей пачке
            if isinstance(result, int):
                if result == DISCARD_WORDS:
                    continue
                # Если не удалось выполнить запрос, то возвращаем аргументы в очередь
                elif result == RETRY_WORDS:
                    # Увеличиваем приоритет, чтобы не задерживать остальные запросы
                    heapq.heappush(self.args_heapq, PrioritizedItem(priority + 1, (work, info, words)))
                # Если среди заголовков или параметров есть секретный, то делим пачку напополам
                elif result == SPLIT_WORDS:
                    heapq.heappush(self.args_heapq, PrioritizedItem(priority + 1, (work, info, words[:len(words) // 2])))
                    heapq.heappush(self.args_heapq, PrioritizedItem(priority + 2, (work, info, words[len(words) // 2:])))
                else:
                    raise NotImplementedError
            # Если найден конкретный заголовок или параметр
            elif isinstance(result, dict):
                self.results.append(result)
            else:
                raise NotImplementedError

        self._running = False
        self._stopped = True
