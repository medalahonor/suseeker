import argparse
import os
import random
import re
from urllib.parse import urlparse

from lib.utils.constants import USER_AGENTS
from lib.utils.request_helper import parse_raw_request


def prepare_args(arguments: argparse.Namespace):
    """ Подготавливает параметры для программы """
    # --raw-request
    if arguments.raw_requests:
        raw_requests = []
        if os.path.isfile(arguments.raw_requests):
            with open(arguments.raw_request) as file:
                content = file.read()
                if content: raw_requests.append(parse_raw_request(file.read()))
        else:
            for path, _, files in os.walk(arguments.raw_requests):
                for filename in files:
                    file = open(os.path.join(path, filename))
                    content = file.read()
                    if content: raw_requests.append(parse_raw_request(content))
                    file.close()
    else:
        raw_requests = (
        'GET', arguments.url, {'User-Agent': random.choice(USER_AGENTS), 'Host': urlparse(arguments.url).netloc})
    arguments.raw_requests = raw_requests

    # --header
    if arguments.additional_headers:
        headers = dict()
        for header in arguments.additional_headers:
            k, v = re.split(':\s*', header.strip(), maxsplit=1)
            headers[k] = v
        arguments.additional_headers = headers

    # --param-wordlist
    if arguments.param_wordlist:
        with open(arguments.param_wordlist) as file:
            arguments.param_wordlist = [w.strip() for w in file.readlines() if w.strip()]

    # --header-wordlist
    if arguments.header_wordlist:
        header_wordlist = []
        bad_header_wordlist = []

        with open(arguments.header_wordlist) as file:
            allow_regex = '^[A-Za-z0-9_-]+$'

            for line in file:
                word = line.strip()

                if not re.search(allow_regex, word):
                    bad_header_wordlist.append(word)
                else:
                    header_wordlist.append(word)

        if len(bad_header_wordlist):
            print(f'Следующие хидеры были убраны их словаря {arguments.header_wordlist}: {bad_header_wordlist}')

        arguments.header_wordlist = header_wordlist

    if arguments.proxy:
        url_obj = urlparse(arguments.proxy)

        if url_obj.scheme.startswith('socks'):
            arguments.proxy = {'http': arguments.proxy, 'https': arguments.proxy}
        else:
            arguments.proxy = {'http': 'http://' + url_obj.netloc, 'https': 'https://' + url_obj.netloc}