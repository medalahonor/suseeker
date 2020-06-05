import argparse

from lib.utils.logger import Logger


def prepare_param_wordlist(arguments: argparse.Namespace, logger: Logger):
    with open(arguments.param_wordlist) as file:
        param_wordlist = [w.strip() for w in file.readlines() if w.strip()]

    return param_wordlist
