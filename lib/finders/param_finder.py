import random
from math import ceil
from typing import List, Union
from urllib.parse import parse_qs, unquote

import gevent
from gevent.queue import Queue
from requests import PreparedRequest, Response

from lib.finders.base_finder import BaseFinder
from lib.utils.constants import *
from lib.utils.request_helper import RequestInfo, split_body_params
from lib.utils.workers import GuessWorker


# TODO: разделить на URLFinder и BodyFinder
class ParamFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.wordlist = self.arguments.param_wordlist

        self.max_param_value = 35
        self.min_param_name = max([len(w) for w in self.arguments.param_wordlist])
        self.min_chunk = self.min_param_name + 1 + self.max_param_value

    def add_body_params(self, request: PreparedRequest, params: List[tuple]):
        """ Добавляет в тело запроса `request` параметры `params`

        :param request: Объект типа PreparedRequest
        :param params: Список параметров вида [(name1, value1), ...]
        :return:
        """
        splitted_body = split_body_params(request.body or '')
        params = [(unquote(k), unquote(v)) for k, v in params]
        request.prepare_body(splitted_body + params, files=None)

    def add_random_body_param(self, request: PreparedRequest, param_size: int):
        """ Добавляет случайный параметр длины `param_size` в тело запроса `request`

        :param request:
        :param param_size:
        :return:
        """
        random_param = ''.join(random.choice(CACHE_BUSTER_ALF) for _ in range(param_size))
        self.add_body_params(request, [(random_param, '')])

    def add_random_url_param(self, request: PreparedRequest, param_size: int):
        # Длина параметра = param_size - [?&] - [=]
        param = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(param_size - 2)])
        request.prepare_url(request.url, param)

    def add_url_params(self, request: PreparedRequest, params: dict):
        params = {unquote(k): unquote(v) for k, v in params.items()}
        request.prepare_url(request.url, params)

    def find_body_params(self, requests_list: List[RequestInfo]):
        args_queue = Queue()
        results_queue = Queue()

        # формируем список аргументов
        for info in requests_list:
            words_chunks = self.get_wordlist_chunks(info, self.wordlist)

            for words_chunk in words_chunks:
                args_queue.put((info, words_chunk))

        # Запускаем воркеры
        self.do_work(GuessWorker, self.get_secret_body_params, args_queue, results_queue)

        # Собираем результаты в один словарь
        results = self.parse_results_queue(results_queue)

        return results

    def find_url_params(self, requests_list: List[RequestInfo]) -> dict:
        args_queue = Queue()
        results_queue = Queue()

        # формируем список аргументов
        for info in requests_list:
            words_chunks = self.get_wordlist_chunks(info, self.wordlist)

            for words_chunk in words_chunks:
                args_queue.put((info, words_chunk))

        # Запускаем воркеры
        self.do_work(GuessWorker, self.get_secret_url_params, args_queue, results_queue)

        # Собираем результаты в один словарь
        results = self.parse_results_queue(results_queue)

        return results

    def get_body_param_reasons(self, info: RequestInfo, response: Response) -> list:
        reasons = []

        self.check_status_code_reason(reasons, info, response)
        self.check_content_length_reason(reasons, info, response)
        self.check_content_type_reason(reasons, info, response)
        self.check_param_value_reflection_reason(reasons, info, response)

        return reasons

    def get_optimal_body_param_bucket(self, info: RequestInfo) -> int:
        """ Ищет оптимальный размер порции параметров в теле запроса через соотношение (Длина URL) / (время ответа)

        :param info:
        :return:
        """
        return super().get_optimal_bucket(info, self.min_chunk, self.add_random_body_param)

    def get_optimal_url_param_bucket(self, info: RequestInfo):
        """ Ищет оптимальный размер порции параметров в URL запроса через соотношение (Длина URL) / (время ответа)

        :return:
        """
        return super().get_optimal_bucket(info, self.min_chunk, self.add_random_url_param)

    def get_secret_body_params(self, info: RequestInfo, words: list) -> Union[dict, int]:
        """ Проверяет изменения в ответе для заданного списка параметров `words` в теле запроса

                :param info:
                :param words: Названия параметров
                :return:    dict([(`param`, `reasons`)]) - если найдено конкретное слово
                            int - если со словами требуется провести манипуляции
                """

        # Добавляем параметры в URL-строку
        request = info.copy_request()
        params = [(k, v) for k, v in zip(words, [info.param_value] * len(words))]
        self.add_body_params(request, params)

        response = self.do_request(request, )

        # Если не удалось получить ответ на запрос, то возвращаем слова в очередь
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция возвращена в очередь')
            return RETRY_WORDS

        reasons = self.get_body_param_reasons(info, response)

        # Если есть изменения
        if reasons:
            # Если найден конкретный заголовок, то возвращаем его вместе с причинами
            if len(words) == 1:
                self.logger.success(f'Найден body-параметр "{words[0]}" к {info.origin_url}')
                return {words[0]: {'url': info.origin_url, 'reasons': reasons, 'type': SecretType.BODY,
                                   'response': response}}
            # Иначе где-то среди слов есть искомые
            else:
                return SPLIT_WORDS
        # Иначе отбросить
        else:
            return DISCARD_WORDS

    def get_secret_url_params(self, info: RequestInfo, words: list) -> Union[dict, int]:
        """ Проверяет изменения в ответе для заданного списка параметров `words` в URL-строке

        :param info:
        :param words: Названия заголовков
        :return:    dict([(`param`, `reasons`)]) - если найдено конкретное слово
                    int - если со словами требуется провести манипуляции
        """

        # Добавляем параметры в URL-строку
        request = info.copy_request()
        params = {k: v for k, v in zip(words, [info.param_value] * len(words))}
        self.add_url_params(request, params)

        response = self.do_request(request, )

        # Если не удалось получить ответ на запрос, то возвращаем слова в очередь
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция возвращена в очередь')
            return RETRY_WORDS

        reasons = self.get_url_param_reasons(info, response)

        # Если есть изменения
        if reasons:
            # Если найден конкретный заголовок, то возвращаем его вместе с причинами
            if len(words) == 1:
                self.logger.success(f'Найден URL-параметр "{words[0]}" к {info.origin_url}')
                return {words[0]: {'url': info.origin_url, 'reasons': reasons, 'type': SecretType.URL, 'response': response}}
            # Иначе где-то среди слов есть искомые
            else:
                return SPLIT_WORDS
        # Иначе отбросить
        else:
            return DISCARD_WORDS

    def get_url_param_reasons(self, info: RequestInfo, response: Response) -> list:
        reasons = []

        self.check_status_code_reason(reasons, info, response)
        self.check_content_type_reason(reasons, info, response)
        self.check_content_length_reason(reasons, info, response)
        self.check_param_value_reflection_reason(reasons, info, response)

        return reasons

    def get_wordlist_chunks(self, info: RequestInfo, wordlist):
        chunks = []
        current_chunk = []
        current_chunk_len = 0

        wordlist = list(set(wordlist) | set(info.additional_params))

        for w in wordlist:
            # [?&]param=value
            current_chunk_len += 1 + len(w) + 1 + len(info.param_value)

            if current_chunk_len > info.url_param_bucket:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_len = 1 + len(w) + 1 + len(info.param_value)

            current_chunk.append(w)

        if len(current_chunk):
            chunks.append(current_chunk)

        return chunks

    def run(self):
        results = dict()

        self.logger.info('Запуск ParamFinder')
        # Установка характеристик параметров
        for info in self.requests_list:
            info.setup_param_properties(self.max_param_value)

        # Устанавливаем размер порций для поиска параметров в URL
        self.logger.info('Установка размера порций для поиска параметров в URL')
        self.set_url_param_buckets(self.requests_list)

        # Фильтруем запросы, для которых не удалось установить размер порции
        requests_list = self.filter_requests(self.requests_list, lambda info: info.url_param_bucket is None,
                                             'Не удалось получить размер порции параметров в URL для следующих запросов',
                                             'Не удалось получить размер порции параметров в URL для всех запросов')

        if requests_list:
            # Ищем параметры в URL
            self.logger.info('Поиск скрытых параметров в URL')
            new_results = self.find_url_params(requests_list)
            results = self.update_results(results, new_results)

        # Формируем список запросов для поиска параметров в их теле
        requests_list = []
        for info in self.requests_list:
            # Пропускаем запросы с указанными методами
            if info.request.method in {'GET', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'}:
                continue

            # Пропускаем запросы, тело которых не представлено в формате key1=value1&key2=value2&...
            if info.request.body and not len(parse_qs(info.request.body).keys()):
                continue

            requests_list.append(info)

        if not len(requests_list):
            return results

        # Устанавливаем размер порций для поиска параметров в теле запроса
        self.logger.info('Установка размера порций для поиска параметров в теле запроса')
        self.set_body_param_buckets(requests_list)

        # Фильтруем запросы, для которых не удалось установить размер порции
        requests_list = self.filter_requests(requests_list, lambda info: info.body_param_bucket is None,
                                             'Не удалось получить размер порции параметров в теле запроса для следующих запросов',
                                             'Не удалось получить размер порции параметров в теле запроса для всех запросов')

        if not requests_list:
            return results

        new_results = self.find_body_params(requests_list)
        results = self.update_results(results, new_results)
        return results

    def set_body_param_buckets(self, requests_list: List[RequestInfo]):
        if not len(requests_list):
            return

        if not self.arguments.disable_dynamic_headers:
            # Для каждого сайта выбираем первый запрос из списка
            netloc_info = dict()
            for info in requests_list:
                if netloc_info.get(info.netloc):
                    continue
                netloc_info[info.netloc] = {'request_info': info, 'body_param_bucket': None}

            # Формируем список запросов для определения размера чанков
            info_list = [value['request_info'] for _, value in netloc_info.items()]

            # Распределяем задачу между воркерами
            worker = lambda chunk: [self.get_optimal_body_param_bucket(info) for info in chunk]
            chunk_size = ceil(len(info_list) / self.threads)
            info_chunks = [info_list[i:i + chunk_size] for i in range(0, len(info_list), chunk_size)]

            # Получаем список оптимальных размеров чанков
            jobs = [gevent.spawn(worker, chunk) for chunk in info_chunks]
            gevent.joinall(jobs)
            optimal_buckets = sum([job.value for job in jobs], [])

            # Заносим полученные результаты в `netloc_info`
            for info, size in zip(info_list, optimal_buckets):
                netloc_info[info.netloc]['body_param_bucket'] = size

            # Устанавливаем их по всем остальным запросам
            for info in requests_list:
                if netloc_info[info.netloc]['body_param_bucket'] is None:
                    info.body_param_bucket = None
                else:
                    info.body_param_bucket = netloc_info[info.netloc]['body_param_bucket']
        else:
            for info in requests_list:
                info.body_param_bucket = self.arguments.param_bucket

    def set_url_param_buckets(self, requests_list: List[RequestInfo]):
        if not len(requests_list):
            return

        if not self.arguments.disable_dynamic_headers:
            # Для каждого сайта выбираем первый запрос из списка
            netloc_info = dict()
            for info in requests_list:
                if netloc_info.get(info.netloc):
                    continue
                netloc_info[info.netloc] = {'request_info': info, 'url_param_bucket': None}

            # Формируем список запросов для определения размера чанков
            info_list = [value['request_info'] for _, value in netloc_info.items()]

            # Распределяем задачу между воркерами
            worker = lambda chunk: [self.get_optimal_url_param_bucket(info) for info in chunk]
            chunk_size = ceil(len(info_list) / self.threads)
            info_chunks = [info_list[i:i + chunk_size] for i in range(0, len(info_list), chunk_size)]

            # Получаем список оптимальных размеров чанков
            jobs = [gevent.spawn(worker, chunk) for chunk in info_chunks]
            gevent.joinall(jobs)
            optimal_buckets = sum([job.value for job in jobs], [])

            # Заносим полученные результаты в `netloc_info`
            for info, size in zip(info_list, optimal_buckets):
                netloc_info[info.netloc]['url_param_bucket'] = size

            # Устанавливаем их по всем остальным запросам
            for info in requests_list:
                if netloc_info[info.netloc]['url_param_bucket'] is None:
                    info.url_param_bucket = None
                else:
                    info.url_param_bucket = netloc_info[info.netloc]['url_param_bucket']
        else:
            for info in requests_list:
                info.url_param_bucket = self.arguments.param_bucket
