import argparse
import os
import re
from urllib.parse import urlparse

from lib.utils.logger import Logger


def is_args_valid(arguments: argparse.Namespace, logger: Logger) -> bool:
    """ Валидирует аргументы командной строки

    :param arguments:
    """
    if not arguments.url and not arguments.raw_requests:
        logger.error('Требуется указать один из аргументов -u или -r')
        return False

    if arguments.url:
        addr = urlparse(arguments.url)

        if os.path.isfile(arguments.url) or (addr.scheme and addr.netloc):
            pass
        else:
            logger.error('Некорректный формат аргумента -u')
            return False

    if arguments.raw_requests:
        if not os.path.exists(arguments.raw_requests):
            logger.error('Указанного пути -r не существует')
            return False

    if arguments.param_wordlist:
        bad_paths = [path for path in re.split('\s*,\s*', arguments.param_wordlist) if not os.path.isfile(path)]

        if bad_paths:
            logger.error('Следующие пути --param-wordlists не указывают на словари: ' + '"' + '", "'.join(bad_paths) + '"')
            return False
    else:
        if arguments.find_all or arguments.find_params:
            logger.error('Требуется указать хотя бы один словарь --param-wordlists для поиска параметров')
            return False

    if arguments.header_wordlist:
        bad_paths = [path for path in re.split('\s*,\s*', arguments.header_wordlist) if not os.path.isfile(path)]

        if bad_paths:
            logger.error(
                'Следующие пути --header-wordlists не указывают на словари: ' + '"' + '", "'.join(bad_paths) + '"')
            return False
    else:
        if arguments.find_all or arguments.find_headers:
            logger.error('Требуется указать хотя бы один словарь --header-wordlists для поиска параметров')
            return False

    if arguments.cookie_wordlist:
        bad_paths = [path for path in re.split('\s*,\s*', arguments.cookie_wordlist) if not os.path.isfile(path)]

        if bad_paths:
            logger.error(
                'Следующие пути --cookie-wordlists не указывают на словари: ' + '"' + '", "'.join(bad_paths) + '"')
            return False
    else:
        if arguments.find_all or arguments.find_cookies:
            logger.error('Требуется указать хотя бы один словарь --cookie-wordlists для поиска параметров')
            return False

    if not (arguments.find_headers or arguments.find_params or arguments.find_cookies or arguments.find_all):
        logger.error('Не указан тип сканирования --find-headers / --find-params / --find-cookies / --find-all')
        return False

    if arguments.retry <= 0:
        logger.error('Общее число попыток --retry выполнить запрос должно быть больше 0')
        return False

    if arguments.timeout <= 0:
        logger.error('Время ожидания ответа --timeout должно быть больше 0')

    return True