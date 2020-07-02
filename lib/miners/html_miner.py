from urllib.parse import urlparse, urlunparse

import bs4
from gevent.queue import Queue

from lib.miners.abstract import AbstractMiner
from lib.utils.logger import Logger


class HTMLMiner(AbstractMiner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_acceptable_content_types(self):
        return {'text/html'}

    def parse_resource(self, resource_dict: dict):
        params = set()

        # Если ресурс ранее был обработан, то пропускаем
        if self.check_resource_parsed(resource_dict['resource']):
            return

        html = bs4.BeautifulSoup(resource_dict['resource'], features='lxml')

        # Собираем все значения аттрибутов name в HTML
        for tag in html.find_all(attrs={'name': True}):
            params.add(tag.attrs.get('name'))

        params = list(params)
        self.logger.debug(f'Новые параметры: {params}')

        # Добавляем найденные параметры в очередь `self.param_queue`
        for param in params:
            self.add_new_param(resource_dict['netloc'], param)

        scripts = html.find_all('script')

        # Разбиваем скрипты на src и inline
        for script in scripts:
            src = script.attrs.get('src')

            # Если указан адрес скрипта
            if src:
                # То приводим его к общему виду
                src = urlparse(src)
                target = urlparse(resource_dict['url'])

                src_path = urlunparse(
                    [src.scheme or target.scheme, src.netloc or target.netloc, src.path, src.params, src.query,
                     src.fragment])

                # И добавляем в очередь `self.url_queue` на загрузку
                self.url_queue.put({'netloc': resource_dict['netloc'], 'url': src_path})
            # Иначе добавляем в очередь ресурсов `self.resource_queue`
            else:
                self.resource_queue.put(
                    {'netloc': resource_dict['netloc'], 'content_type': 'application/javascript', 'resource': script.string,
                     'url': resource_dict['url']})