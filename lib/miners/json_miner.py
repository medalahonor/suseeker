import json

from lib.miners.abstract import AbstractMiner


class JSONMiner(AbstractMiner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_acceptable_content_types(self):
        return {'application/json'}

    def parse_resource(self, resource_dict: dict):
        # Если ресурс ранее был обработан, то пропускаем
        if self.check_resource_parsed(resource_dict['resource']):
            return

        try:
            resource = json.loads(resource_dict['resource'])
        except Exception as e:
            self.logger.error(f'JSONMiner\'у не удалось обработать ресурс: {e}')
            return

        params = list(self.get_keys(resource))
        self.logger.debug(f'Новые параметры: {params}')

        # Добавляем найденные параметры в очередь `self.param_queue`
        for param in params:
            self.add_new_param(resource_dict['netloc'], param)

    def get_keys(self, item: object) -> set:
        keys = set()

        if isinstance(item, dict):
            for key, value in item.items():
                keys.add(key)
                keys |= self.get_keys(value)
        elif isinstance(item, list):
            for value in item:
                keys |= self.get_keys(value)

        return keys
