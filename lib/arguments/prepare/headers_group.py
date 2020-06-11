import argparse
import os
import re


from lib.utils.logger import Logger


def prepare_header_wordlist(arguments: argparse.Namespace, logger: Logger):
    header_wordlist = set()

    wordlist_paths = re.split('\s*,\s*', arguments.header_wordlist)

    for path in wordlist_paths:
        if not os.path.isfile(path):
            logger.error(f'Путь "{path}" из --header-wordlist не указывает на словарь с заголовками')
            continue

        with open(path) as file:
            allow_regex = '^[A-Za-z0-9_-]+$'

            for line in file:
                word = line.strip()

                if re.search(allow_regex, word):
                    header_wordlist.add(word)

    return list(header_wordlist)