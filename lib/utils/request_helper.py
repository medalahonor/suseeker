import argparse
import logging
import random
import re
from typing import List, Union, Callable, Tuple
from urllib.parse import urlparse, quote_plus

import gevent
import lxml.html
import math
import requests
from bs4 import BeautifulSoup
from requests import PreparedRequest, Response, Session
from requests.cookies import cookiejar_from_dict
from requests.utils import super_len

from lib.constants import CACHE_BUSTER_ALF
from lib.utils.logger import Logger


class RequestInfo:
    def __init__(self, request: PreparedRequest):
        self.request = request

        self._response: Response = None
        self.origin_url = request.url
        self.netloc = urlparse(request.url).netloc
        self.response_html_tags_count: int = None

        self.additional_params: list = []  # Список дополнительных параметров для данного запроса

        self.url_param_bucket: int = None  # Размер порции искомых параметров в URL (в байтах)
        self.url_param_value_breaker = quote_plus('\'"`%${{|\\')
        self.url_base_param_value: str = None  # Базовое значение всех значений URL параметров
        self.url_param_value: str = None  # Актуальное значение всех значений URL параметров

        self.body_param_bucket: int = None  # Размер порции искомых параметров в теле запроса (в байтах)
        self.body_param_value_breaker = quote_plus('\'"`%${{|\\')
        self.body_base_param_value: str = None  # Базовое значение всех значений body параметров
        self.body_param_value: str = None  # Актуальное значение всех значений body параметров

        self.json_param_value_breaker = '\'"`%${{|\\'
        self.json_base_param_value: str = None  # Базовое значение всех значений body параметров
        self.json_param_value: str = None  # Актуальное значение всех значений body параметров

        self.header_bucket: int = None  # Размер порции проверяемых хидеров (количество)
        self.header_value_breaker = '\'"`%${{|\\'  # Суффикс `self.base_header_value` для определения аномалий
        self.base_header_value: str = None  # Базовое значение всех заголовков
        self.header_value: str = None  # Актуальное значение всех заголовков

        self.cookie_bucket: int = None  # Размер порции проверяемых параметров в Cookie (в байтах)
        self.cookie_value_breaker = '\'"`%${{|\\'  # кодировать символы ,;
        self.base_cookie_value: str = None
        self.cookie_value: str = None

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value: Response):
        if isinstance(value, Response):
            self._response = value
            self.response_html_tags_count: int = self.count_html_tags(value.text)

    def copy_request(self):
        return self.request.copy()

    def count_html_tags(self, html: str) -> int:
        """ Возвращает число тэгов в HTML странице `html`

        :param html: Контент HTML страницы
        :return: int
        """
        try:
            if lxml.html.fromstring(html).find('.//*') is None:
                return 0

            soup = BeautifulSoup(html, features='lxml')
            return len(soup.find_all())
        except Exception as e:
            return 0

    def setup_header_properties(self, max_header_value):
        """ Устанавливает свойства `self.base_header_value` и `self.header_value` """
        self.base_header_value = ''.join(
            [random.choice(CACHE_BUSTER_ALF) for _ in range(max_header_value - len(self.header_value_breaker))])
        self.header_value = self.base_header_value + self.header_value_breaker

    def setup_param_properties(self, max_param_value):
        """ Устанавливает свойства `self.url_base_param_value` и `self.url_param_value` """
        self.url_base_param_value = ''.join(
            [random.choice(CACHE_BUSTER_ALF) for _ in range(max_param_value - len(self.url_param_value_breaker))])
        self.url_param_value = self.url_base_param_value + self.url_param_value_breaker


class RequestHelper:
    def __init__(self, info_list: List[RequestInfo], arguments: argparse.Namespace, logger: logging.Logger):
        self.info_list = info_list
        self.arguments = arguments
        self.logger = logger

        self.allow_redirects = self.arguments.allow_redirects
        self.timeout = self.arguments.timeout
        self.threads = self.arguments.threads
        self.proxies = self.arguments.proxy
        self.delay = self.arguments.delay
        self.retry = self.arguments.retry

    @staticmethod
    def add_headers(request: PreparedRequest, headers: dict):
        # Через request.prepare_headers пропадают заголовки
        request.headers.update(headers)

    @staticmethod
    def do_request(prepared_request: PreparedRequest, retry: int, timeout: int, delay: int, proxies: dict, allow_redirects: bool,
                   logger: Logger, propagate_exceptions: bool = False) -> Union[Response, None]:
        """ Выполняет подготовленных запрос

        :return:    `None` - если по истечении `retry` попыток не удалось получить ответ от сервера
                    `Response` - если удалось получить ответ от сервера
        """
        # Создается объект сессии, через которых отправляются PreparedRequest'ы
        with RequestHelper.make_session(proxies) as session:
            # Пытаемся получить ответ в течении `retry` раз
            while retry:
                retry -= 1

                try:
                    gevent.sleep(delay)
                    response = session.send(prepared_request, allow_redirects=allow_redirects, timeout=timeout)
                    return response
                except Exception as e:
                    # В случае дебаг режима выводим текст ошибки в stdout
                    # Поднимаем исключение "вверх"
                    if propagate_exceptions:
                        raise e

                    continue

        return None

    @staticmethod
    def make_session(proxies=None) -> Session:
        """ Создаёт сессию для отправки подготовленных запросов """
        session = Session()
        session.verify = False

        if proxies:
            session.proxies = proxies

        return session

    @staticmethod
    def get_origin_response(origin_request: PreparedRequest, retry: int, timeout: int, delay: int, proxies: dict,
                            allow_redirects: bool, logger: Logger) -> Union[
        Response, None]:
        """ Получает ответ на оригинальный запрос

        :return:    None - если по истечении `retry` попыток не удалось получить ответ от сервера
                    Response - если удалось получить ответ от сервера
        """

        return RequestHelper.do_request(origin_request.copy(), retry, timeout, delay, proxies, allow_redirects, logger)

    @staticmethod
    def set_origin_responses(requests_list: List[RequestInfo], threads: int, retry: int, timeout: int, delay: int,
                             proxies: dict, allow_redirects: bool, logger: Logger):
        """ Помещает изначальные ответы от сервера в соответствующие объекты из `info_list` """
        worker = lambda chunk: [
            RequestHelper.get_origin_response(request, retry, timeout, delay, proxies, allow_redirects, logger) for
            request in chunk]
        prepared_requests = [info.request for info in requests_list]

        chunk_size = math.ceil(len(prepared_requests) / threads)
        request_chunks = [prepared_requests[i:i + chunk_size] for i in
                          range(0, len(prepared_requests), chunk_size)]

        jobs = [gevent.spawn(worker, request_chunk) for request_chunk in request_chunks]
        gevent.joinall(jobs)

        origin_responses = sum([job.value for job in jobs], [])
        for request_info, origin_response in zip(requests_list, origin_responses):
            request_info.response = origin_response

    @staticmethod
    def filter_requests(requests_list: List[RequestInfo], bad_condition: Callable,
                        warning_message: str = None, error_message: str = None, logger: Logger = None):
        """

        :param requests_list:
        :param bad_condition:
        :param warning_message:
        :param error_message:
        :param logger:
        :return:
        """
        bad_requests = []
        filtered_requests = []

        for info in requests_list:
            if bad_condition(info):
                bad_requests.append(info.request.method + ' ' + info.origin_url)
                continue
            filtered_requests.append(info)

        if not len(filtered_requests):
            if error_message and logger:
                logger.error(error_message)
            return None

        if bad_requests and warning_message and logger:
            logger.warning(f'{warning_message}: {bad_requests}')

        return filtered_requests


def parse_raw_request(raw_request: str) -> list:
    """ Парсит сырой запрос и вычленяет из него метод, url-адрес, заголовки и тело запроса

    :return: Список `[method, url, headers, body]`
    """
    if not re.search('\r?\n\r?\n', raw_request):
        head, headers = re.split('\r?\n', raw_request, maxsplit=1)
        body = ''
    else:
        other, body = re.split('\r?\n\r?\n', raw_request, maxsplit=1)
        head, headers = re.split('\r?\n', other, maxsplit=1)

    body = body.strip() if body is not None else ''

    method, uri, *other = head.split(' ')
    host = re.search('Host:\s*(.+?)\r?\n', headers).group(1)
    url = host + '/' + uri.lstrip('/')
    headers = {key: value for key, value in
               [re.split('\s*:\s*', line.strip(), maxsplit=1) for line in re.split('\r?\n', headers.strip())]}

    return [method, url, headers, body]


def get_request_object(method: str, url: str, headers: dict, body: str, retry: int, timeout: int, delay: int,
                       proxies: dict, allow_redirects: bool, logger: Logger) -> Union[requests.PreparedRequest, None]:
    """ Формирует из кортежа `(method, url, headers, body)` объект класса PreparedRequest

    Для определения схемы HTTP(S) отправляется HEAD HTTP-запрос и коду ответа решается данный вопрос
    """
    scheme = 'https'
    cookies = cookiejar_from_dict(dict(re.findall('([^=,;]*)=([^,;]*)', headers.get('Cookie', ''))))

    prepared_request = requests.Request('GET', scheme + '://' + url.lstrip('/'), headers, data=body,
                                        cookies=cookies).prepare()

    prepared_request.headers['Content-Length'] = super_len(body)

    try:
        RequestHelper.do_request(prepared_request, retry, timeout, delay, proxies, allow_redirects, logger, True)
    except requests.exceptions.SSLError:
        scheme = 'http'
    except requests.exceptions.ConnectionError:
        return None

    prepared_request = requests.Request(method, scheme + '://' + url, headers, data=body, cookies=cookies).prepare()
    prepared_request.headers['Content-Length'] = super_len(body)

    return prepared_request


def get_request_objects(parsed_requests: list, arguments: argparse.Namespace, logger: Logger) -> Tuple:
    """ Применяет функцию `get_request_object` на запросы из `parsed_requests` с числом потоков `threads`

    :param parsed_requests:
    :param arguments:
    :param logger:

    :return:    Кортеж `(prepared_requests, not_prepared_requests)`, где prepared_requests - список объектов класса
                `requests.PreparedRequest`, а not_prepared_requests - список неподготовленных URL'ов типа `str`
    """
    threads = arguments.threads
    retry = arguments.retry
    timeout = arguments.timeout
    delay = arguments.delay
    proxies = arguments.proxy
    allow_redirects = arguments.allow_redirects

    def worker(requests_chunk):
        return [get_request_object(*parsed_request, retry=retry, timeout=timeout, delay=delay, proxies=proxies,
                                   allow_redirects=allow_redirects, logger=logger) for parsed_request in
                requests_chunk]

    # Если требуется установить тело запроса
    if arguments.body is not None:
        _parsed_requests = []

        for parsed_request in parsed_requests:
            # Если метод запроса не отвечает за "действие", то пропускаем
            if parsed_request[0].upper() in {'GET', 'HEAD', 'OPTIONS', 'TRACE', 'CONNECT'}:
                _parsed_requests.append(parsed_request)
                continue

            # Если тело запроса установлено, то пропускаем
            if parsed_request[3]:
                _parsed_requests.append(parsed_request)
                continue

            # Иначе меняем тело запроса и тип контента
            parsed_request[3] = arguments.body
            parsed_request[2]['Content-Type'] = 'application/x-www-form-urlencoded'

            _parsed_requests.append(parsed_request)

        parsed_requests = _parsed_requests

    # Создаем порции с распаршенными запросами
    chunk_size = math.ceil(len(parsed_requests) / threads)
    req_chunks = [parsed_requests[i:i + chunk_size] for i in range(0, len(parsed_requests), chunk_size)]

    # Запускаем воркеры
    jobs = [gevent.spawn(worker, chunk) for chunk in req_chunks]
    gevent.joinall(jobs)

    # Получаем результаты
    _requests = sum([job.value for job in jobs], [])

    prepared_requests = []
    not_prepared_requests = []

    # Разбиваем запросы на подготовленные и неподготовленные
    for prepared_request, parsed_request in zip(_requests, parsed_requests):
        if prepared_request is None:
            not_prepared_requests.append(parsed_request[1])
        else:
            prepared_requests.append(prepared_request)

    return prepared_requests, not_prepared_requests
