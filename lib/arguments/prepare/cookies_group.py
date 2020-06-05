import argparse
import re

from lib.utils.logger import Logger


def prepare_cookie_wordlist(arguments: argparse.Namespace, logger: Logger):
    cookie_wordlist = []

    with open(arguments.cookie_wordlist) as file:
        allow_regex = '^[^=,;]*$'

        for line in file:
            word = line.strip()

            if re.search(allow_regex, word):
                cookie_wordlist.append(word)

    return cookie_wordlist