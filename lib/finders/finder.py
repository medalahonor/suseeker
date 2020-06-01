import gevent
from gevent.queue import Queue

from lib.finders.base_finder import BaseFinder
from lib.finders.body_finder import BodyFinder
from lib.finders.cookie_finder import CookieFinder
from lib.finders.header_finder import HeaderFinder
from lib.finders.url_finder import UrlFinder
from lib.workers import FindSecretsWorker, SetBucketWorker


class Finder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.header_finder = HeaderFinder(*args, **kwargs)
        self.url_finder = UrlFinder(*args, **kwargs)
        self.body_finder = BodyFinder(*args, **kwargs)
        self.cookie_finder = CookieFinder(*args, **kwargs)

        self.finders = []

    def setup_finders(self):
        if self.arguments.find_headers:
            self.finders.append(self.header_finder)

        if self.arguments.find_params:
            self.finders.append(self.url_finder)
            self.finders.append(self.body_finder)

        if self.arguments.find_cookies:
            self.finders.append(self.cookie_finder)

    def run(self):
        self.setup_finders()

        # Устанавливаем свойства запросов
        self.setup_requests_info()

        # Устанавливаем размер числа доп. заголовков для запросов
        self.logger.info('Установка размера порций для запросов')
        self.setup_bucket_sizes()

        # Запускаем поиск секретных параметров
        self.logger.info('Поиск скрытых параметров и заголовков')
        return self.find_secrets()

    def setup_requests_info(self):
        for finder in self.finders:
            finder.setup_requests_info(self.info_list)

    def setup_bucket_sizes(self):
        """ Устанавливает размер порций для всех запросов """
        args_queue = Queue()

        # Запускаем на один и тот же запрос разные работы
        for info in self.info_list:
            for finder in self.finders:
                if not finder.is_info_searchable(info):
                    continue

                args_queue.put((finder.determine_bucket_size, info))

        # Запускаем воркеры
        workers = [SetBucketWorker(args_queue, self.logger)
                   for _ in range(self.threads)]

        greenlets = [gevent.spawn(worker.run) for worker in workers]

        # Ждем заверщения работы
        while any([worker.is_running() for worker in workers]) or args_queue.qsize():
            gevent.sleep(0)

        # Выключаем воркеры
        for worker in workers:
            worker.finish()

        # Ждем выключения
        gevent.joinall(greenlets)

        # Устанавливаем размеры порций
        for info in self.info_list:
            for finder in self.finders:
                if not finder.is_info_searchable(info):
                    continue

                finder.set_bucket_size(info)
                self.logger.debug(
                    f'{finder.__class__.__name__}: {info.origin_url} - размер порции {finder.get_bucket_size(info)}')

    def find_secrets(self):
        args_queue = Queue()
        results_queue = Queue()

        # формируем список аргументов
        for finder in self.finders:
            for info in self.info_list:

                if not finder.is_info_searchable(info):
                    self.logger.debug(f'{finder.__class__.__name__} отклонил запрос {info.origin_url}')
                    continue

                # Пропускаем запросы, для которых не установлен размер порции
                if not finder.get_bucket_size(info):
                    self.logger.error(
                        f'{finder.__class__.__name__} не смог определить размер порции для запроса {info.origin_url}')
                    continue

                word_chunks = finder.get_word_chunks(info)

                for chunk in word_chunks:
                    args_queue.put((finder.find_secrets, info, chunk))

        # Запускаем воркеры
        workers = [FindSecretsWorker(args_queue, results_queue, self.logger)
                   for _ in range(self.threads)]

        greenlets = [gevent.spawn(worker.run) for worker in workers]

        # Ждем заверщения работы
        while any([worker.is_running() for worker in workers]) or args_queue.qsize():
            gevent.sleep(0)

        # Выключаем воркеры
        for worker in workers:
            worker.finish()

        # Ждем выключения
        gevent.joinall(greenlets)

        return self.parse_results_queue(results_queue)
