import argparse
import os
import re

from lib.utils.logger import Logger


def prepare_param_wordlist(arguments: argparse.Namespace, logger: Logger):
    param_wordlist = set()

    wordlist_paths = re.split('\s*,\s*', arguments.param_wordlist)

    for path in wordlist_paths:
        if not os.path.exists(path):
            logger.error(f'Путь "{path}" из --param-wordlist не указывает на словарь с параметрами')
            continue

        with open(path) as file:
            param_wordlist |= set([w.strip() for w in file.readlines() if w.strip()])

    return list(param_wordlist)
