import random
from math import ceil
from typing import Tuple, Union, List

import gevent
import requests
from gevent.queue import Queue
from requests import PreparedRequest, Session, Response

from lib.finders.base_finder import BaseFinder
from lib.utils.constants import *
from lib.utils.request_helper import RequestInfo
from lib.utils.workers import GuessWorker


class HeaderFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.wordlist = self.arguments.header_wordlist

        self.max_header_name = max((len(h) for h in self.wordlist))
        self.max_header_value = 18

        self.random_param_name_len = 10
        self.random_param_value_len = 10

    def add_cache_buster(self, request: PreparedRequest):
        """ Добавляет случайные данные в строку запроса для обнуления кэширования """
        key = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.random_param_name_len)])
        value = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.random_param_value_len)])

        request.prepare_url(request.url, f'{key}={value}')

    def add_random_headers(self, request: PreparedRequest, count: int) -> None:
        """ Добавляет случайные заголовки в `request` в количестве `count`

        :param request: Объект типа requests.PreparedRequest
        :param count: Число случайных заголовков
        """
        if count == 0:
            return
        # Генерируем список уникальных заголовков, для исключения аномальных ответов
        headers = dict()
        while len(headers) != count:
            key, value = self.get_random_header()
            headers[key] = value

        self.add_headers(request, headers)
        request.headers.update(headers)

    def check_header_count(self, info: RequestInfo, headers_count: int) -> Union[bool, None]:
        """ Проверяет, допустимо ли заданное число `header_count` заголовков в запросе

        :param info:
        :param headers_count: Число случайных заголовков
        """
        request = info.copy_request()
        self.add_random_headers(request, headers_count)

        response = self.do_request(request, )
        if response is None:
            return None

        if response.status_code != info.response.status_code:
            return False

        return True

    def check_secret_headers(self, info: RequestInfo, words: list):
        """ Проверяет изменения в ответе для заданного списка заголовков `words`

        :param info:
        :param words: Названия заголовков
        :return:    dict([(`header`, `reasons`)]) - если найдено конкретное слово
                    int - если со словами требуется провести манипуляции
        """

        # Добавляем заголовки в запрос
        request = info.copy_request()
        headers = {k: v for k, v in zip(words, [info.header_value] * len(words))}
        self.add_headers(request, headers)

        response = self.do_request(request, )
        # Если не удалось получить ответ на запрос, то возвращаем слова в очередь
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция возвращена в очередь')
            return RETRY_WORDS

        reasons = self.get_header_finder_reasons(info, response)

        # Если есть изменения
        if reasons:
            # Если найден конкретный заголовок, то возвращаем его вместе с причинами
            if len(words) == 1:
                self.logger.success(f'Найден заголовок "{words[0]}" к {info.origin_url}')
                return {words[0]: {'url': info.origin_url, 'reasons': reasons, 'type': SecretType.HEADER,
                                   'response': response}}
            # Иначе где-то среди слов есть искомые
            else:
                return SPLIT_WORDS
        # Иначе отбросить
        else:
            return DISCARD_WORDS

    def do_request(self, prepared_request: PreparedRequest, **kwargs) -> Union[requests.Response, None]:
        """ Выполняет подготовленных запрос с отчисткой промежуточного кэша

        :param **kwargs:
        :return:    `None` - если по истечении `self.retry` попыток не удалось получить ответ от сервера
                    `requests.Response` - если удалось получить ответ от сервера
        """
        self.add_cache_buster(prepared_request)

        return super().do_request(prepared_request, )

    def find_secret_headers(self, requests_list: List[RequestInfo]):
        args_queue = Queue()
        results_queue = Queue()

        # формируем список аргументов
        for info in requests_list:
            wordlist = list(set(self.wordlist) | set(info.additional_headers))
            words_chunks = [wordlist[i:i + info.header_bucket] for i in
                            range(0, len(wordlist), info.header_bucket)]
            for words_chunk in words_chunks:
                args_queue.put((info, words_chunk))

        # Запускаем воркеры
        self.do_work(GuessWorker, self.check_secret_headers, args_queue, results_queue)

        return self.parse_results_queue(results_queue)

    def get_header_finder_reasons(self, info: RequestInfo, response: Response) -> list:
        reasons = []

        self.check_status_code_reason(reasons, info, response)
        self.check_content_type_reason(reasons, info, response)
        self.check_content_length_reason(reasons, info, response)
        self.check_header_value_reflection_reason(reasons, info, response)

        return reasons

    def get_optimal_headers_bucket(self, info: RequestInfo) -> int:
        """ Ищет оптимальный размер числа доп. заголовков в запросе через соотношение (число заголовков) / (время ответа)

        :return:
        """
        return super().get_optimal_bucket(info, 1, self.add_random_headers)

    def get_random_header(self) -> Tuple[str, str]:
        """ Генерирует случайную пару (`key`, `value`) """
        key = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.max_header_name)])
        value = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.max_header_value)])
        return key, value

    def make_session(self, **kwargs) -> Session:
        """ Создаёт сессию для отправки подготовленных запросов """
        return super().make_session(self.proxies)

    def run(self):
        self.logger.info('Запуск HeaderFinder')

        # Устанавливаем базовое значение всех заголовков
        for info in self.requests_list:
            info.setup_header_properties(self.max_header_value)

        # Устанавливаем размер числа доп. заголовков для запросов
        self.logger.info('Установка числа доп. заголовков для запросов')
        self.set_headers_bucket(self.requests_list)

        # TODO: Проверка и корректировка header_bucket при отсутствии --dynamic-header-bucket
        # Фильтруем запросы, для которых размер доп. заголовков установить не удалось
        requests_list = self.filter_requests(self.requests_list, lambda x: x.header_bucket is None,
                                                  'Для следующих запросов не удалось установить размер доп. заголовков',
                                                  'Не удалось установить размер доп. заголовков на все запросы')
        if requests_list is None:
            return dict()

        self.logger.info('Поиск скрытых заголовков')
        # Находим секретные заголовки
        return self.find_secret_headers(requests_list)

    def set_headers_bucket(self, requests_list: List[RequestInfo]):
        # Если требуется для каждого веб-приложения выбрать оптимальное значение `header_bucket`
        if not self.arguments.disable_dynamic_headers:
            # Для каждого сайта выбираем первый запрос из списка
            netloc_info = dict()
            for info in requests_list:
                if netloc_info.get(info.netloc):
                    continue
                netloc_info[info.netloc] = {'request_info': info, 'header_bucket': None}

            # Формируем список запросов для определения размера чанков
            info_list = [value['request_info'] for _, value in netloc_info.items()]

            # Распределяем задачу между воркерами
            worker = lambda chunk: [self.get_optimal_headers_bucket(info) for info in chunk]
            chunk_size = ceil(len(info_list) / self.threads)
            info_chunks = [info_list[i:i + chunk_size] for i in range(0, len(info_list), chunk_size)]

            # Получаем список оптимальных размеров чанков
            jobs = [gevent.spawn(worker, chunk) for chunk in info_chunks]
            gevent.joinall(jobs)
            optimal_buckets = sum([job.value for job in jobs], [])

            # Заносим полученные результаты в `netloc_info`
            for info, size in zip(info_list, optimal_buckets):
                netloc_info[info.netloc]['header_bucket'] = size

            # Устанавливаем их по всем остальным запросам
            for info in requests_list:

                if netloc_info[info.netloc]['header_bucket'] is None:
                    info.header_bucket = None
                else:
                    info.header_bucket = netloc_info[info.netloc]['header_bucket'] - len(info.request.headers)
        # Иначе выставляем всем одинаковое
        else:
            for info in requests_list:
                info.header_bucket = self.arguments.header_bucket - len(info.request.headers)
