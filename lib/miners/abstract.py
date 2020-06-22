import re
from argparse import Namespace
from hashlib import md5

from gevent.queue import Queue

from lib.utils.logger import Logger


class AbstractMiner:
    def __init__(self, args: Namespace, url_queue: Queue, resource_queue: Queue, param_queue: Queue, logger: Logger):
        self.args = args
        self.url_queue = url_queue
        self.resource_queue = resource_queue
        self.param_queue = param_queue
        self.logger = logger

        self.resource_hashes = set()
        self.miner_name = self.get_miner_name()

    def parse_resource(self, resource: str):
        raise NotImplementedError

    def get_acceptable_content_types(self) -> set:
        raise NotImplementedError

    def add_new_param(self, netloc: str, param_name: str):
        # Удаляем все не ASCII символы
        param_name = re.sub('[^\x00-\x7F]+', '', param_name)
        # Удаляем unicode последовательности
        param_name = re.sub(r'\\u\d{4}', '', param_name)

        self.logger.info({'netloc': netloc, 'miner_name': self.miner_name, 'param_name': param_name})
        self.param_queue.put({'netloc': netloc, 'miner_name': self.miner_name, 'param_name': param_name})

    def is_acceptable(self, content_type: str) -> bool:
        if content_type in self.get_acceptable_content_types():
            return True

        return False

    def check_resource_parsed(self, resource: str) -> bool:
        """ Проверяет, обрабатывался ли ранее данный ресурс.

         Если ресурс не обрабатывался ранее, то заносит его хэш во множество `self.resource_hashes`

        :param resource:
        :return: True, если ресурс обрабатывался, иначе False
        """
        # Если ресурс ранее был обработан, то пропускаем
        resource_hash = self.get_resource_hash(resource)
        if resource_hash in self.resource_hashes:
            return True

        # Иначе помечаем как обработанный
        self.resource_hashes.add(resource_hash)

    def get_miner_name(self):
        return self.__class__.__name__

    def get_resource_hash(self, resource: str):
        md5_hash = md5()
        md5_hash.update(resource.encode('utf8'))
        return md5_hash.hexdigest()
