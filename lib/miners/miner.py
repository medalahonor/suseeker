import random
import re
from collections import defaultdict
from typing import List, Tuple, Union, Dict
from urllib.parse import urlparse

import gevent
import requests
from gevent.queue import Queue

from lib.miners.html_miner import HTMLMiner
from lib.miners.javascript_miner import JavascriptMiner
from lib.miners.json_miner import JSONMiner
from lib.miners.webarchive_miner import WebArchiveMiner
from lib.utils.logger import Logger
from lib.utils.request_helper import RequestInfo
from lib.workers.abstract import AbstractWorker
from lib.constants import USER_AGENTS


class DownloadWorker(AbstractWorker):
    def __init__(self, url_queue: Queue, resource_queue: Queue, proxies: dict, logger: Logger):
        super().__init__()

        self.url_queue = url_queue
        self.resource_queue = resource_queue
        self.logger = logger
        self.proxies = proxies

    def run(self):
        # Переключения контекста для запуска других воркеров
        gevent.sleep(0)

        self._running = True
        self._stopped = False

        while not self._finish:
            try:
                d = self.url_queue.get(timeout=1)
                netloc, url, force_content_type = d['netloc'], d['url'], d.get('force_content_type')
                self._running = True
            except gevent.queue.Empty:
                self._running = False
                continue
            except Exception as e:
                self.logger.error(e)
                continue

            try:
                content_type, resource = self.download(url, force_content_type)
                self.logger.debug(f'Загружен ресурс {url} типа {content_type}')
            except Exception as e:
                self.logger.error(f'Не удалось загрузить ресурс {url} типа {content_type}: {e}')
                continue

            if not content_type or not resource:
                continue

            self.resource_queue.put({'netloc': netloc, 'content_type': content_type, 'resource': resource, 'url': url})

        self._running = False
        self._stopped = True

    def is_url_blacklisted(self, url: str):
        extentions = {'jpg', 'jpeg', 'bmp', 'font', 'gif', 'ico', 'css', 'png', '7z', 'gz', 'jar', 'rar', 'tar', 'zip',
                      'pdf', 'psd', 'doc', 'docx', 'ttf', 'ttc', 'psb', 'tif', 'tiff', 'svg', 'flac', 'torrent',
                      'ogv', 'xz', 'apk', 'flv', 'wav', 'mpeg', 'avi', 'm4a', 'woff', 'mp4', 'ogg', 'mkv', 'epub',
                      'otf', 'swf', 'wmv', 'mpg', 'mic', 'aud', 'flac16', 'flac24', 'mp3', 'm3u', 'm4b'}

        ext = re.search('\.([a-zA-Z0-9]+)$', urlparse(url).path)

        if not ext or ext.group(1).lower() not in extentions:
            return False

        return True

    def download(self, url: Union[str, requests.PreparedRequest], force_content_type: str = None) -> Tuple[str, str]:
        """ Загружает ресурс согласно заданному аргументу `url`

        В случае, если url - это объект класса requests.PreparedRequest, он отправляется как есть, иначе используются
        дефолтные настройки, выданные сессии методом `self.get_session`

        :param url: URL-адрес или объект класса requests.PreparedRequest
        :param force_content_type: Перезаписывает `content_type`
        :return: Кортеж `(content_type, resource)`
        """
        session = self.get_session()

        if isinstance(url, requests.PreparedRequest):
            response = session.send(url, allow_redirects=True)
        elif isinstance(url, str):
            if self.is_url_blacklisted(url):
                return '', ''

            response = session.get(url, allow_redirects=True)
        else:
            raise TypeError(f'Тип аргумента url "{type(url)}" не соответствует Union[str, requests.PreparedRequest]')

        if force_content_type:
            content_type = force_content_type
        else:
            content_type = re.search('[^\s/]+/[^\s;]+', response.headers.get('Content-Type', ''))
            content_type = content_type.group(0) if content_type else 'unknown'

        return content_type, response.text

    def get_session(self) -> requests.Session:
        """ Создает сессионный объект с предустановленными настройками

        :return:
        """
        session = requests.Session()

        session.verify = False
        session.proxies = self.proxies
        session.headers.update({'User-Agent': random.choice(USER_AGENTS),
                                'Accept': '*/*',
                                'Accept-Language': 'en-US;q=0.5,en;q=0.3',
                                'Accept-Encoding': 'gzip, deflate',
                                'Cache-Control': 'no-cache',
                                'Connection': 'close'})

        return session


class Miner:
    def __init__(self, args, info_list: List[RequestInfo], logger: Logger):
        self.args = args
        self.info_list = info_list
        self.logger = logger

        self.miners = []

        # {'netloc': str, 'url': Union[str, requests.PreparedRequest], 'force_content_type': str}
        self.url_queue: Queue = None
        # {'netloc': str, 'content_type': str, 'resource': str, 'url': str}
        self.resource_queue: Queue = None
        # {'netloc': str, 'miner_name': str, 'param_name': str}
        self.param_queue: Queue = None

    def run(self) -> Tuple[Dict[str, set], Dict[str, int]]:
        """ Запускает майнеры параметров

        :return: Кортеж `(params, miner_statistics)`, где `params` - словарь параметров по каждому `netloc`,
                 `miner_statistict` - словарь со статистикой по числу найденных параметров майнерами
        """
        self.setup_queues()
        self.setup_miners()

        self.logger.info('Поиск параметров для заданных запросов модулями: {}'.format(
            ', '.join([m.miner_name for m in self.miners])))

        # Запуск загрузчиков ресурсов
        loaders = [DownloadWorker(self.url_queue, self.resource_queue, self.args.proxy, self.logger) for _ in
                   range(self.args.threads)]
        jobs = [gevent.spawn(loader.run) for loader in loaders]

        while True:
            # Пытаемся получить ресурс и его тип из очереди
            try:
                resource_dict = self.resource_queue.get(timeout=1)
            # Если очередь пуста
            except gevent.queue.Empty:
                # И если загрузчики не работают и очередь url-адресов пуста
                if all([loader.is_running() == False for loader in loaders]) and not self.url_queue.qsize():
                    # То выключаем очередь
                    break
                # Иначе ждём ресурсы от загрузчиков
                continue

            self.logger.debug('Получен новый ресурс типа ' + resource_dict['content_type'])

            is_resource_accepted = False

            # Предлагаем каждому зарегистрированному майнеру обработать ресурс
            for miner in self.miners:
                if miner.is_acceptable(resource_dict['content_type']):
                    self.logger.debug(f'Майнер {miner.miner_name} принял ресурс')

                    is_resource_accepted = True
                    miner.parse_resource(resource_dict)

            if not is_resource_accepted:
                self.logger.debug('Ресурс типа {} не обработан'.format(resource_dict['content_type']))

        # Завершаем загрузчики
        for loader in loaders:
            loader.finish()

        # Ждем завершения
        gevent.joinall(jobs)
        self.logger.debug('Майнеры завершили работу')

        params = defaultdict(set)
        miner_statistics = defaultdict(int)

        while self.param_queue.qsize():
            d = self.param_queue.get()
            netloc, miner_name, param_name = d['netloc'], d['miner_name'], d['param_name']

            if param_name not in params[netloc]:
                miner_statistics[miner_name] += 1
                params[netloc].add(param_name)

        self.logger.debug('Обработка результатов завершена')

        return params, miner_statistics

    def setup_miners(self):
        """ Регистрирует майнеры

        :return:
        """
        builders = [HTMLMiner, JavascriptMiner, JSONMiner, WebArchiveMiner]

        for builder in builders:
            self.miners.append(builder(self.args, self.url_queue, self.resource_queue, self.param_queue, self.logger))

    def setup_queues(self):
        """ Инициализирует очереди для майнеров

        :return:
        """
        self.url_queue = Queue()
        self.resource_queue = Queue()
        self.param_queue = Queue()

        domains = set()
        for info in self.info_list:
            domain = re.sub(':\d+$', '', info.netloc)

            # Добавляется ресурс специально для WebArchiveMiner
            if domain not in domains:
                domains.add(domain)
                self.resource_queue.put({'netloc': info.netloc, 'content_type': 'webarchive/download', 'resource': domain})

            self.url_queue.put({'netloc': info.netloc, 'url': info.origin_url})
