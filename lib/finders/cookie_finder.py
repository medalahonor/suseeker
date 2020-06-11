import random
import re
from typing import List

from requests import PreparedRequest, Response

import lib.checker as checker
from lib.constants import CACHE_BUSTER_ALF, RETRY_WORDS, SPLIT_WORDS, DISCARD_WORDS, ParamType
from lib.finders.base_finder import BaseFinder
from lib.utils.request_helper import RequestInfo


class CookieFinder(BaseFinder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cookie_wordlist = self.arguments.cookie_wordlist

        self.max_cookie_param_name = max([len(w) for w in self.cookie_wordlist])
        self.max_cookie_param_value = 30
        # ; cookie_name=cookie_value
        self.min_cookie_param_chunk = 2 + self.max_cookie_param_name + 1 + self.max_cookie_param_value

    def add_cookies(self, request: PreparedRequest, cookies: List[tuple]):
        cookies_str = '; '.join(['='.join(cookie) if cookie[1] else cookie[0] for cookie in cookies])
        if not cookies_str:
            return

        if request.headers.get('Cookie'):
            request.headers['Cookie'] += '; ' + cookies_str
        else:
            request.headers['Cookie'] = cookies_str

    def add_random_cookie(self, request: PreparedRequest, cookie_size: int):
        random_cookie = ''.join(random.choice(CACHE_BUSTER_ALF) for _ in range(cookie_size))
        self.add_cookies(request, [(random_cookie, '')])

    def determine_bucket_size(self, info: RequestInfo):
        """ Определяет общий размер параметров в Cookie-заголовке запроса для сайта в байтах

        :param info:
        :return:
        """
        # Если размер порции установлен либо находится в процессе определения, то пропустить
        if self.bucket_size_cache[info.netloc].get('bucket') or self.bucket_size_cache[info.netloc].get('in_progress'):
            return

        self.bucket_size_cache[info.netloc]['in_progress'] = True

        if self.arguments.disable_dynamic_params:
            self.bucket_size_cache[info.netloc]['bucket'] = self.arguments.cookie_bucket
        else:
            self.bucket_size_cache[info.netloc]['bucket'] = self.get_optimal_bucket(info)

    def get_optimal_bucket(self, info: RequestInfo, **kwargs):
        additional_size = lambda _info: len(info.request.headers.get('Cookie', ''))
        return super().get_optimal_bucket(info, self.min_cookie_param_chunk, self.add_random_cookie, additional_size,
                                          self.logger)

    def find_secrets(self, info: RequestInfo, words: List[str]):
        """ Проверяет изменения в ответе для заданного списка параметров `words` в теле запроса

                :param info:
                :param words: Названия параметров
                :return:    dict([(`param`, `reasons`)]) - если найдено конкретное слово
                            int - если со словами требуется провести манипуляции
                """
        # Добавляем параметры в URL-строку
        request = info.copy_request()
        cookies = [(k, v) for k, v in zip(words, [info.cookie_value] * len(words))]
        param_type = ParamType.COOKIE

        self.add_cookies(request, cookies)

        response = self.do_request(request)

        # Если не удалось получить ответ на запрос, то возвращаем слова в очередь
        if response is None:
            self.logger.error(
                f'[{info.origin_url}] Ошибка при выполнении запроса, '
                'порция возвращена в очередь')
            return RETRY_WORDS

        reasons = self.get_cookie_reasons(info, response)

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
        return info.cookie_bucket

    def get_cookie_reasons(self, info: RequestInfo, response: Response) -> list:
        reasons = []

        checker.check_content_length_reason(reasons, info, response)
        checker.check_cookie_value_reflection_reason(reasons, info, response)
        checker.check_status_code_reason(reasons, info, response)
        checker.check_content_type_reason(reasons, info, response)

        return reasons

    def get_word_chunks(self, info: RequestInfo):
        chunks = []
        current_chunk = []
        current_chunk_len = 0

        cookie_params = set(self.split_cookie_params(info.request.headers.get('Cookie', '')))
        wordlist = list((set(self.cookie_wordlist) | set(info.additional_params)) - cookie_params)

        for w in wordlist:
            # ; param=value
            current_chunk_len += 2 + len(w) + 1 + len(info.cookie_value)

            if current_chunk_len > info.cookie_bucket:
                chunks.append(current_chunk)
                current_chunk = []
                current_chunk_len = 1 + len(w) + 1 + len(info.cookie_value)

            current_chunk.append(w)

        if len(current_chunk):
            chunks.append(current_chunk)

        return chunks

    def is_info_searchable(self, info: RequestInfo):
        return True

    def set_bucket_size(self, info: RequestInfo):
        bucket_size = self.bucket_size_cache[info.netloc].get('bucket')

        if bucket_size:
            info.cookie_bucket = bucket_size - len(info.request.headers.get('Cookie', ''))
        else:
            info.cookie_bucket = None

    def setup_requests_info(self, info_list: List[RequestInfo]):
        for info in info_list:
            if info.base_cookie_value and info.cookie_value:
                continue

            info.base_cookie_value = ''.join(
                [random.choice(CACHE_BUSTER_ALF) for _ in
                 range(self.max_cookie_param_value - len(info.cookie_value_breaker))])
            info.cookie_value = info.base_cookie_value + info.cookie_value_breaker

    def split_cookie_params(self, params: str):
        return re.findall('\s*([^=;]+)=([^;]+)', params)
