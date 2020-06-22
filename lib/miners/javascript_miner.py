import gevent
from esprima import esprima
from gevent.queue import Queue

from lib.miners.abstract import AbstractMiner
from lib.utils.logger import Logger


class JavascriptMiner(AbstractMiner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_acceptable_content_types(self):
        return {'application/javascript'}

    def parse_resource(self, resource_dict: dict):
        params = set()
        # Если ресурс ранее был обработан, то пропускаем
        if self.check_resource_parsed(resource_dict['resource']):
            return

        try:
            tokens = esprima.tokenize(resource_dict['resource'])
        except:
            self.logger.error('Не удалось распарсить JS-скрипт по адресу ' + resource_dict['url'])
            return

        for token in tokens:
            if token.type == 'Identifier':
                params.add(token.value)

        params = list(params)
        self.logger.debug(f'Новые параметры: {params}')

        # Добавляем найденные параметры в очередь `self.param_queue`
        for param in params:
            self.add_new_param(resource_dict['netloc'], param)
