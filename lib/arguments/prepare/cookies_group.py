import argparse
import os
import re

from lib.utils.logger import Logger


def prepare_cookie_wordlist(arguments: argparse.Namespace, logger: Logger):
    cookie_wordlist = set()
    bad_words = set()

    wordlist_paths = re.split('\s*,\s*', arguments.cookie_wordlist)

    for path in wordlist_paths:
        if not os.path.isfile(path):
            logger.error(f'Путь "{path}" из --cookie-wordlist не указывает на словарь с параметрами для cookie')
            continue

        with open(path) as file:
            allow_regex = '^[^=,;]*$'

            for line in file:
                word = line.strip()

                if re.search(allow_regex, word):
                    cookie_wordlist.add(word)
                else:
                    bad_words.add(word)

    if len(bad_words):
        logger.warning(f'Следующие слова для поиска cookie были исключены: ' + '"' + '", "'.join(list(bad_words)) + '"')

    return list(cookie_wordlist)