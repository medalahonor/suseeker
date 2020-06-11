import random
from typing import Union, List, Tuple

import requests
from requests import PreparedRequest, Response

import lib.checker as checker
from lib.constants import *
from lib.finders.base_finder import BaseFinder
from lib.utils.request_helper import RequestInfo


class HeaderFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.headers_wordlist = self.arguments.header_wordlist

        self.max_header_name = max((len(h) for h in self.headers_wordlist))
        self.max_header_value = 18
        self.min_header_chunk = 1

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

    def check_response(self, info: RequestInfo, response: Response):
        """ Проверяет ответ на наличие аномалий

        :param info:
        :param response:
        :return:
        """
        reasons = []

        checker.check_status_code_reason(reasons, info, response)
        checker.check_content_type_reason(reasons, info, response)
        checker.check_content_length_reason(reasons, info, response)
        checker.check_header_value_reflection_reason(reasons, info, response)

        return reasons

    def determine_bucket_size(self, info: RequestInfo):
        """ Определяет общее число хидеров на запрос для сайта

        :param info:
        :return:
        """
        header_bucket = self.bucket_size_cache[info.netloc]['header_bucket']

        # Если размер порции установлен либо находится в процессе определения, то пропустить
        if header_bucket.get('size') or header_bucket.get('in_progress'):
            return

        header_bucket['in_progress'] = True

        if self.arguments.disable_dynamic_params:
            header_bucket['size'] = self.arguments.header_bucket
        else:
            header_bucket['size'] = self.get_optimal_bucket(info)

    def do_request(self, prepared_request: PreparedRequest, **kwargs) -> Union[requests.Response, None]:
        """ Выполняет подготовленных запрос с отчисткой промежуточного кэша

        :param **kwargs:
        :return:    `None` - если по истечении `self.retry` попыток не удалось получить ответ от сервера
                    `requests.Response` - если удалось получить ответ от сервера
        """
        self.add_cache_buster(prepared_request)

        return super().do_request(prepared_request)

    def find_secrets(self, info: RequestInfo, words: List[str]):
        """

        :param info:
        :param words:
        :return:
        """
        request = info.copy_request()
        headers = {k: v for k, v in zip(words, [info.header_value] * len(words))}
        param_type = ParamType.HEADER

        self.add_headers(request, headers)

        response = self.do_request(request)
        # Если не удалось получить ответ на запрос, то возвращаем слова в очередь
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция возвращена в очередь')
            return RETRY_WORDS

        reasons = self.check_response(info, response)

        # Если есть изменения
        if reasons:
            # Если найден конкретный заголовок, то возвращаем его вместе с причинами
            if len(words) == 1:
                self.logger.success(f'Найден {param_type}-параметр "{words[0]}" к {info.origin_url}')
                self.logger.debug(f'{param_type}-параметр "{words[0]}": reasons={reasons}')
                return {words[0]: {'url': info.origin_url, 'reasons': reasons, 'type': param_type,
                                   'response': response}}
            # Иначе где-то среди слов есть искомые
            else:
                return SPLIT_WORDS
        # Иначе отбросить
        else:
            return DISCARD_WORDS

    def get_bucket_size(self, info: RequestInfo):
        """ Возвращает общие число хидеров в запросе """
        return info.header_bucket

    def get_optimal_bucket(self, info: RequestInfo, **kwargs) -> int:
        """ Ищет оптимальный размер числа доп. заголовков в запросе через соотношение (число заголовков) / (время ответа)

        :return:
        """
        additional_size = lambda _info: len(_info.request.headers.keys())
        return super().get_optimal_bucket(info, self.min_header_chunk, self.add_random_headers, additional_size, self.logger)

    def get_random_header(self) -> Tuple[str, str]:
        """ Генерирует случайную пару (`key`, `value`) """
        key = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.max_header_name)])
        value = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(self.max_header_value)])
        return key, value

    def get_word_chunks(self, info: RequestInfo):
        headers = set(info.request.headers.keys())

        wordlist = list((set(self.headers_wordlist) | set(info.additional_params)) - headers)
        chunk_size = info.header_bucket - len(info.request.headers.keys())

        word_chunks = [wordlist[i:i + chunk_size] for i in range(0, len(wordlist), chunk_size)]
        return word_chunks

    def set_bucket_size(self, info: RequestInfo):
        """ Устанавивает для запроса в `info` общее число хидеров """
        bucket_size = self.bucket_size_cache[info.netloc]['header_bucket'].get('size')

        if bucket_size:
            info.header_bucket = bucket_size - len(info.request.headers.keys())
        else:
            info.header_bucket = None

    def setup_requests_info(self, info_list: List[RequestInfo]):
        for info in info_list:
            info.base_header_value = ''.join(
                [random.choice(CACHE_BUSTER_ALF) for _ in
                 range(self.max_header_value - len(info.header_value_breaker))])
            info.header_value = info.base_header_value + info.header_value_breaker

    def is_info_searchable(self, info: RequestInfo):
        return True
