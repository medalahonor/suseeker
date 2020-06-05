import argparse
import logging
import random
from collections import defaultdict
from typing import List
from urllib.parse import urlparse, urlunparse

import bs4
import esprima
import gevent
import requests
from gevent.queue import Queue

from lib.constants import USER_AGENTS
from lib.utils.request_helper import RequestInfo
from lib.workers.get_script import GetScriptsWorker


def get_src_script(netloc, src, allow_redirects: bool, timeout: int, proxies: dict, logger: logging.Logger):
    """ Возвращает контент ответа на запрос с подавлением исключений

    :param netloc: Хост(:порт)
    :param src: Адрес скрипта
    :param allow_redirects: Регулирует переход по редиректам при запросе
    :param timeout: Время ожидания ответа
    :param proxies: Словарь проксей
    :param logger: Логгер
    :return: Кортеж `(netloc, result)`
    """
    try:
        result = requests.get(src, allow_redirects=allow_redirects, verify=False, timeout=timeout,
                              proxies=proxies, headers={'User-Agent': random.choice(USER_AGENTS)}).text
    except Exception as e:
        logger.error(e)
        result = None

    return netloc, result


def parse_scripts(inline_scripts: dict):
    """ Токенизирует конктент скриптов из `inline_scripts` и возвращает токены типа "Identifier"


    :param inline_scripts: Словарь вида {netloc1: {inline_content1, inline_content2, ...}, ...}
    :return: Словарь вида {netloc1: {param1, param2, ...}, ...}
    """
    site_params = defaultdict(set)

    for netloc in inline_scripts:
        for script in list(inline_scripts[netloc]):
            try:
                for token in esprima.tokenize(script):
                    if token.type == 'Identifier':
                        site_params[netloc].add(token.value)
            except:
                continue

    return site_params


def get_params_from_html(args: argparse.Namespace, requests_list: List[RequestInfo], logger: logging.Logger) -> dict:
    """ Собирает параметры с HTML и контента скриптов и помещает их в словарь вида {netloc1: set(param1, ...), ...}

    Поиск параметров в HTML-контенте происходит путем поиска значений всех аттрибутов с именем "name". Затем со страниц
    собираются скрипты и разбиваются на группы "inline" (контент скрипта находится на странице ответа) и "src" (контент
    скрипта находится по ссылке), каждая из которых имеет вид соответственно {netloc1: set(inline_script_content1, ...),
    ...} и {netloc1: set(src1, src2, ...), ...}. Далее запускаются воркеры для получения контента скриптов из группы
    "src" в количестве `args.threads` и результат соединяется с группой "inline". И наконец контент скриптов
    токенизируется с помощью библиотеки esprima, а токены типа "Identifier" попадают в словарь `site_params`
    :param args: Аргументы командной строки
    :param requests_list: Список объектов типа `RequestInfo`
    :param logger: Логгер
    :return: Словарь `site_params` вида {netloc1: set(param1, param2, ...), ...}
    """
    site_params = defaultdict(set)

    args_queue = Queue()  # Очередь вида (netloc, src)
    results_queue = Queue()  # Очередь словарей вида {netloc: set(params)}

    src_scripts = defaultdict(set)  # Ловарь вида {netloc1: set(src1, src2, ...), ...}
    inline_scripts = defaultdict(set)  # Словарь вида {netloc1: set(inline_script_content1, ...), ...}

    # Для каждого запроса
    logger.info('Поиск HTML-аттрибутов "name"')
    for info in requests_list:
        html = bs4.BeautifulSoup(info.response.text, features='lxml')

        # Собираем все значения аттрибутов name в HTML
        for tag in html.find_all(attrs={'name': True}):
            site_params[info.netloc].add(tag.attrs.get('name'))

        scripts = html.find_all('script')

        # Разбиваем скрипты на src и inline
        for script in scripts:
            src = script.attrs.get('src')
            # TODO: фикс
            # src = /lib/test.js
            if src:
                src = urlparse(src)
                target = urlparse(info.request.url)

                src_path = urlunparse([src.scheme or target.scheme, src.netloc or target.netloc, src.path, src.params, src.query, src.fragment])
                # src = urlparse(info.request.url).scheme + '://' + src.lstrip('/') if not urlparse(src).scheme else src
                src_scripts[info.netloc].add(src_path)
            else:
                inline_scripts[info.netloc].add(script.string)

    # Заполняем очередь аргументов
    for netloc, sources in src_scripts.items():
        sources = list(sources)

        for src in sources:
            args_queue.put((netloc, src))

    logger.info('Получение контента скриптов по src')
    # Получаем контент src скриптов
    work = lambda netloc, src: get_src_script(netloc, src, args.allow_redirects, args.timeout, args.proxy, logger)
    workers = [GetScriptsWorker(work, args_queue, results_queue) for _ in range(args.threads)]

    greenlets = [gevent.spawn(worker.run) for worker in workers]

    # Ждем заверщения работы
    while all([worker.is_running() for worker in workers]) or not args_queue.empty():
        gevent.sleep(1)

    # Выключаем воркеры
    for worker in workers:
        worker.finish()

    # Ждем выключения
    while not all([worker.is_stopped() for worker in workers]):
        gevent.sleep(0.1)

    gevent.joinall(greenlets)

    # Собираем результаты в один словарь
    while results_queue.qsize():
        netloc, script_content = results_queue.get()
        inline_scripts[netloc].add(script_content)

    # Парсим скрипты на предмет идентификаторов
    logger.info('Поиск параметров в скриптах')
    return parse_scripts(inline_scripts)
