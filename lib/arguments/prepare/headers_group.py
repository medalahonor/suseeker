import argparse
import re

from lib.utils.logger import Logger


def prepare_header_wordlist(arguments: argparse.Namespace, logger: Logger):
    header_wordlist = []

    with open(arguments.header_wordlist) as file:
        allow_regex = '^[A-Za-z0-9_-]+$'

        for line in file:
            word = line.strip()

            if re.search(allow_regex, word):
                header_wordlist.append(word)

    return header_wordlist