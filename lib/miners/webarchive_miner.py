import re
from urllib.parse import urlparse

from lib.miners.abstract import AbstractMiner


class WebArchiveMiner(AbstractMiner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_acceptable_content_types(self):
        return {'webarchive/download', 'webarchive/result'}

    def parse_resource(self, resource_dict: dict):
        # Если требуется сформировать запрос к sdx серверу webarchive
        netloc = resource_dict['netloc']
        resource = resource_dict['resource']

        if resource_dict['content_type'] == 'webarchive/download':
            domain = re.sub(':\d+$', '', netloc)
            url = f'http://web.archive.org/cdx/search/cdx?url={domain}&collapse=urlkey&matchType=prefix&fl=original&limit=-1000'

            self.url_queue.put({'netloc': netloc, 'url': url, 'force_content_type': 'webarchive/result'})
        else:
            urls = re.split('\n', resource)

            for url in urls:
                if not url:
                    continue

                url_obj = urlparse(url)

                if url_obj.query:
                    params = [match[0] for match in re.findall('([^?:&=$]+)(=([^?:&=$]+))?', url_obj.query)]
                    self.logger.debug(f'Новые параметры: {params}')

                    for param in params:
                        self.add_new_param(netloc, param)

                self.url_queue.put({'netloc': netloc, 'url': url})
