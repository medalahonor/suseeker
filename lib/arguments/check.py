import argparse
import os
from urllib.parse import urlparse


def is_args_valid(arguments: argparse.Namespace) -> bool:
    """ Валидирует аргументы командной строки

    :param arguments:
    """
    if not arguments.url and not arguments.raw_requests:
        print('Требуется указать один из аргументов -u или -r')
        return False

    if arguments.url:
        addr = urlparse(arguments.url)

        if os.path.isfile(arguments.url) or (addr.scheme and addr.netloc):
            pass
        else:
            print('Некорректный формат аргумента -u')
            return False

    if arguments.raw_requests:
        if not os.path.exists(arguments.raw_requests):
            print('Указанного пути -r не существует')
            return False

    if not os.path.exists(arguments.param_wordlist):
        print(f'Файла аргумента --param-wordlist по пути {arguments.param_wordlist} не существует')
        return False

    if not os.path.exists(arguments.header_wordlist):
        print(f'Файла аргумента --header-wordlist по пути {arguments.header_wordlist} не существует')
        return False

    if not (arguments.find_headers or arguments.find_params):
        print('Не указан тип сканирования --find-headers или --find-params')
        return False

    if arguments.retry <= 0:
        print('Общее число попыток --retry выполнить запрос должно быть больше 0')
        return False

    if arguments.timeout <= 0:
        print('Время ожидания ответа --timeout должно быть больше 0')

    return True