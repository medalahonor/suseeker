import random
import re
from typing import List
from urllib.parse import parse_qs, unquote

from requests import PreparedRequest, Response

import lib.checker as checker
from lib.constants import CACHE_BUSTER_ALF, RETRY_WORDS, SPLIT_WORDS, DISCARD_WORDS, ParamType
from lib.finders.base_finder import BaseFinder
from lib.utils.request_helper import RequestInfo


class BodyFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.params_wordlist = self.arguments.param_wordlist

        self.max_body_param_name = max([len(w) for w in self.params_wordlist])
        self.max_body_param_value = 35
        self.min_body_param_chunk = 1 + self.max_body_param_name + 1 + self.max_body_param_value

    def add_body_params(self, request: PreparedRequest, params: List[tuple]):
        """ Добавляет в тело запроса `request` параметры `params`

        :param request: Объект типа PreparedRequest
        :param params: Список параметров вида [(name1, value1), ...]
        :return:
        """
        splitted_body = self.split_body_params(request.body or '')
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

    def determine_bucket_size(self, info: RequestInfo):
        """ Определяет общий размер тела запроса для сайта в байтах

        :param info:
        :return:
        """
        body_param_bucket = self.bucket_size_cache[info.netloc]['body_param_bucket']

        # Если размер порции установлен либо находится в процессе определения, то пропустить
        if body_param_bucket.get('size') or body_param_bucket.get('in_progress'):
            return

        body_param_bucket['in_progress'] = True

        if self.arguments.disable_dynamic_params:
            body_param_bucket['size'] = self.arguments.param_bucket
        else:
            body_param_bucket['size'] = self.get_optimal_bucket(info)

    def find_secrets(self, info: RequestInfo, words: List[str]):
        """ Проверяет изменения в ответе для заданного списка параметров `words` в теле запроса

                :param info:
                :param words: Названия параметров
                :return:    dict([(`param`, `reasons`)]) - если найдено конкретное слово
                            int - если со словами требуется провести манипуляции
                """
        # Добавляем параметры в URL-строку
        request = info.copy_request()
        params = [(k, v) for k, v in zip(words, [info.body_param_value] * len(words))]
        param_type = ParamType.BODY

        self.add_body_params(request, params)

        response = self.do_request(request)

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

    def get_body_param_reasons(self, info: RequestInfo, response: Response) -> list:
        reasons = []

        checker.check_status_code_reason(reasons, info, response)
        checker.check_content_length_reason(reasons, info, response)
        checker.check_content_type_reason(reasons, info, response)
        checker.check_param_value_reflection_reason(reasons, info, response)

        return reasons

    def get_bucket_size(self, info: RequestInfo):
        return info.body_param_bucket

    def get_optimal_bucket(self, info: RequestInfo, **kwargs):
        additional_size = lambda _info: len(info.request.body) if info.request.body else 0
        return super().get_optimal_bucket(info, self.min_body_param_chunk, self.add_random_body_param, additional_size, self.logger)

    def get_word_chunks(self, info: RequestInfo):
        chunks = []
        current_chunk = []
        current_chunk_len = 0

        body_params = set([k for k, v in self.split_body_params(info.request.body or '')])
        wordlist = list((set(self.params_wordlist) | set(info.additional_params)) - body_params)

        for w in wordlist:
            # &?param=value
            current_chunk_len += 1 + len(w) + 1 + len(info.body_param_value)

            if current_chunk_len > info.body_param_bucket:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_len = 1 + len(w) + 1 + len(info.body_param_value)

            current_chunk.append(w)

        if len(current_chunk):
            chunks.append(current_chunk)

        return chunks

    def is_info_searchable(self, info: RequestInfo):
        if info.request.method in {'GET', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'}:
            return False

        # Пропускаем запросы, тело которых не представлено в формате key1=value1&key2=value2&...
        if info.request.body and not len(parse_qs(info.request.body).keys()):
            return False

        return True

    def split_body_params(self, body: str) -> List[tuple]:
        return [(match[0], match[2]) for match in re.findall('([^?:&=$]+)(=([^?:&=$]+))?', body)]

    def set_bucket_size(self, info: RequestInfo):
        bucket_size = self.bucket_size_cache[info.netloc]['body_param_bucket'].get('size')

        if bucket_size:
            info.body_param_bucket = bucket_size - (len(info.request.body) if info.request.body else 0)
        else:
            info.body_param_bucket = None

    def setup_requests_info(self, info_list: List[RequestInfo]):
        for info in info_list:
            if info.body_base_param_value and info.body_param_value:
                continue

            info.body_base_param_value = ''.join(
                [random.choice(CACHE_BUSTER_ALF) for _ in
                 range(self.max_body_param_value - len(info.body_param_value_breaker))])
            info.body_param_value = info.body_base_param_value + info.body_param_value_breaker
