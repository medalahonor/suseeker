import json
import random
from typing import List

from requests import PreparedRequest, Response

import lib.checker as checker
from lib.constants import CACHE_BUSTER_ALF, RETRY_WORDS, SPLIT_WORDS, DISCARD_WORDS, ParamType
from lib.finders.base_finder import BaseFinder
from lib.utils.request_helper import RequestInfo


class JsonFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.params_wordlist = self.arguments.param_wordlist

        self.max_json_param_name = max([len(w) for w in self.params_wordlist])
        self.max_json_param_value = 35
        self.min_json_param_chunk = self.calc_chunk_size(self.max_json_param_name,
                                                         self.max_json_param_value)  # , "param": "value"

    def add_json_params(self, request: PreparedRequest, params: List[tuple]):
        j = json.loads(request.body)

        for k, v in params:
            if k in j:
                continue

            j[k] = v

        request.prepare_body(data=None, files=None, json=j)

    def add_random_json_param(self, request: PreparedRequest, param_size: int):
        """

        :param request:
        :param param_size:
        :return:
        """
        # , "param": "" - 8 символов
        random_param = ''.join(random.choice(CACHE_BUSTER_ALF) for _ in range(param_size - 8))
        self.add_json_params(request, [(random_param, '')])

    def calc_chunk_size(self, name_len: int, value_len: int) -> int:
        return 3 + name_len + 4 + value_len + 1

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
        params = [(k, v) for k, v in zip(words, [info.json_param_value] * len(words))]
        param_type = ParamType.JSON

        self.add_json_params(request, params)

        response = self.do_request(request)

        # Если не удалось получить ответ на запрос, то убираем слова из очереди
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция удалена из учереди')
            return DISCARD_WORDS

        reasons = self.get_json_param_reasons(info, response)

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

    def get_json_param_reasons(self, info: RequestInfo, response: Response) -> list:
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
        return super().get_optimal_bucket(info, self.min_json_param_chunk, self.add_random_json_param, additional_size, self.logger)

    def get_word_chunks(self, info: RequestInfo):
        chunks = []
        current_chunk = []
        current_chunk_len = 0

        json_params = set(json.loads(info.request.body).keys())
        wordlist = list((set(self.params_wordlist) | set(info.additional_params)) - json_params)

        for w in wordlist:
            # &?param=value
            current_chunk_len += self.calc_chunk_size(len(w), len(info.json_param_value))

            if current_chunk_len > info.body_param_bucket:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_len = self.calc_chunk_size(len(w), len(info.json_param_value))

            current_chunk.append(w)

        if len(current_chunk):
            chunks.append(current_chunk)

        return chunks

    def is_info_searchable(self, info: RequestInfo):
        try:
            body = json.loads(info.request.body)
        except:
            return False

        if isinstance(body, dict):
            return True

        return False

    def set_bucket_size(self, info: RequestInfo):
        bucket_size = self.bucket_size_cache[info.netloc]['body_param_bucket'].get('size')

        if bucket_size:
            # Событие, возможное только в крайних случаях
            if bucket_size < self.min_json_param_chunk:
                bucket_size = self.min_json_param_chunk

            info.body_param_bucket = bucket_size - (len(info.request.body) if info.request.body else 0)
        else:
            info.body_param_bucket = None

    def setup_requests_info(self, info_list: List[RequestInfo]):
        for info in info_list:
            if info.json_base_param_value and info.json_param_value:
                continue

            info.json_base_param_value = ''.join(
                [random.choice(CACHE_BUSTER_ALF) for _ in
                 range(self.max_json_param_value - len(info.json_param_value_breaker))])
            info.json_param_value = info.json_base_param_value + info.json_param_value_breaker
