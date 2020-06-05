import argparse
import os
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

    if not os.path.isfile(arguments.param_wordlist):
        logger.error(f'Файла аргумента --param-wordlist по пути {arguments.param_wordlist} не существует')
        return False

    if not os.path.isfile(arguments.header_wordlist):
        logger.error(f'Файла аргумента --header-wordlist по пути {arguments.header_wordlist} не существует')
        return False

    if not os.path.isfile(arguments.cookie_wordlist):
        logger.error(f'Файла аргумента --cookie-wordlist по пути {arguments.cookie_wordlist} не существует')
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