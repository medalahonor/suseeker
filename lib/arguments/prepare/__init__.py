import argparse

from lib.arguments.prepare.cookies_group import *
from lib.arguments.prepare.headers_group import *
from lib.arguments.prepare.main_group import *
from lib.arguments.prepare.params_group import *
from lib.arguments.prepare.performance_group import *
from lib.utils.logger import Logger


def prepare_args(arguments: argparse.Namespace, logger: Logger):
    """ Подготавливает агрументы командной строки для программы """
    # --raw-request и --url
    raw_requests = []
    if arguments.raw_requests:
        raw_requests += prepare_raw_requests(arguments, logger)

    if arguments.url:
        raw_requests += prepare_url(arguments, logger)

    arguments.raw_requests = raw_requests

    # --header
    if arguments.additional_headers:
        arguments.additional_headers = prepare_additional_headers(arguments, logger)

    # --param-wordlist
    if arguments.param_wordlist:
        arguments.param_wordlist = prepare_param_wordlist(arguments, logger)

    # --header-wordlist
    if arguments.header_wordlist:
        arguments.header_wordlist = prepare_header_wordlist(arguments, logger)

    # --cookie-wordlist
    if arguments.cookie_wordlist:
        arguments.cookie_wordlist = prepare_cookie_wordlist(arguments, logger)

    # --proxy
    if arguments.proxy:
        arguments.proxy = prepare_proxy(arguments, logger)