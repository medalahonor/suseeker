import random
from typing import List
from urllib.parse import unquote, urlparse

from requests import PreparedRequest

import lib.checker as checker
from lib.constants import CACHE_BUSTER_ALF, RETRY_WORDS, SPLIT_WORDS, DISCARD_WORDS, ParamLocation
from lib.finders.base_finder import BaseFinder
from lib.utils.request_helper import RequestInfo


class UrlFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.params_wordlist = self.arguments.param_wordlist

        self.max_url_param_name = max([len(w) for w in self.arguments.param_wordlist])
        self.max_url_param_value = 35
        self.min_url_param_chunk = 1 + self.max_url_param_name + 1 + self.max_url_param_value

        self.random_param_name_len = 10
        self.random_param_value_len = 10

    def add_random_url_param(self, request: PreparedRequest, param_size: int):
        # Длина параметра = param_size - [?&] - [=]
        param = ''.join([random.choice(CACHE_BUSTER_ALF) for _ in range(param_size - 2)])
        request.prepare_url(request.url, param)

    def add_url_params(self, request: PreparedRequest, params: dict):
        params = {unquote(k): unquote(v) for k, v in params.items()}
        request.prepare_url(request.url, params)

    def determine_bucket_size(self, info: RequestInfo):
        """ Определяет общий размер URL параметров в байтах

        :param info:
        :return:
        """
        if self.bucket_size_cache[info.netloc].get('bucket') or self.bucket_size_cache[info.netloc].get('in_progress'):
            return

        self.bucket_size_cache[info.netloc]['in_progress'] = True

        if self.arguments.disable_dynamic_params:
            self.bucket_size_cache[info.netloc]['bucket'] = self.arguments.param_bucket
        else:
            self.bucket_size_cache[info.netloc]['bucket'] = self.get_optimal_bucket(info)

    def get_url_param_reasons(self, info, response) -> List:
        reasons = []

        checker.check_status_code_reason(reasons, info, response)
        checker.check_content_type_reason(reasons, info, response)
        checker.check_content_length_reason(reasons, info, response)
        checker.check_param_value_reflection_reason(reasons, info, response)

        return reasons

    def find_secrets(self, info: RequestInfo, words: List[str]):
        """ Проверяет изменения в ответе для заданного списка параметров `words` в URL-строке

                :param info:
                :param words: Названия заголовков
                :return:    dict([(`param`, `reasons`)]) - если найдено конкретное слово
                            int - если со словами требуется провести манипуляции
                """

        # Добавляем параметры в URL-строку
        request = info.copy_request()
        params = {k: v for k, v in zip(words, [info.url_param_value] * len(words))}
        self.add_url_params(request, params)

        response = self.do_request(request)

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
                return {words[0]: {'url': info.origin_url, 'reasons': reasons, 'type': ParamLocation.URL,
                                   'response': response}}
            # Иначе где-то среди слов есть искомые
            else:
                return SPLIT_WORDS
        # Иначе отбросить
        else:
            return DISCARD_WORDS

    def get_optimal_bucket(self, info: RequestInfo, **kwargs):
        additional_size = lambda _info: len(urlparse(_info.origin_url).query)
        return super().get_optimal_bucket(info, self.min_url_param_chunk, self.add_random_url_param, additional_size)

    def get_bucket_size(self, info: RequestInfo):
        return info.url_param_bucket

    def get_word_chunks(self, info: RequestInfo):
        chunks = []
        current_chunk = []
        current_chunk_len = 0

        wordlist = list(set(self.params_wordlist) | set(info.additional_params))

        for w in wordlist:
            # [?&]param=value
            current_chunk_len += 1 + len(w) + 1 + len(info.url_param_value)

            if current_chunk_len > info.url_param_bucket:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_len = 1 + len(w) + 1 + len(info.url_param_value)

            current_chunk.append(w)

        if len(current_chunk):
            chunks.append(current_chunk)

        return chunks

    def is_info_searchable(self, info: RequestInfo):
        return True

    def set_bucket_size(self, info: RequestInfo):
        bucket_size = self.bucket_size_cache[info.netloc].get('bucket')

        if bucket_size:
            info.url_param_bucket = bucket_size - len(urlparse(info.origin_url).query)
        else:
            info.url_param_bucket = None

    def setup_requests_info(self, info_list: List[RequestInfo]):
        for info in info_list:
            if info.url_base_param_value and info.url_param_value:
                continue

            info.url_base_param_value = ''.join(
                [random.choice(CACHE_BUSTER_ALF) for _ in
                 range(self.max_url_param_value - len(info.url_param_value_breaker))])
            info.url_param_value = info.url_base_param_value + info.url_param_value_breaker
