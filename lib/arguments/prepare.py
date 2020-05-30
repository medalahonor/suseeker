import argparse
import os
import random
import re
from urllib.parse import urlparse, urlunparse

from lib.utils.constants import USER_AGENTS
from lib.utils.request_helper import parse_raw_request


def prepare_raw_requests(arguments: argparse.Namespace):
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


def prepare_url(arguments: argparse.Namespace):
    raw_requests = []

    if os.path.isfile(arguments.url):
        file = open(arguments.url)

        for url in file:
            url = url.strip()
            addr = urlparse(url)

            if not (addr.scheme and addr.netloc):
                continue

            prepared_url = ('', addr.netloc, addr.path, addr.params, addr.query, addr.fragment)
            raw_request = (arguments.method, urlunparse(prepared_url).lstrip('/'),
                           {'User-Agent': random.choice(USER_AGENTS), 'Host': addr.netloc,
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate'}, '')
            raw_requests.append(raw_request)

    return raw_requests


def prepare_additional_headers(arguments: argparse.Namespace):
    headers = dict()

    for header in arguments.additional_headers:
        k, v = re.split(':\s*', header.strip(), maxsplit=1)
        headers[k] = v

    return headers


def prepare_param_wordlist(arguments: argparse.Namespace):
    with open(arguments.param_wordlist) as file:
        param_wordlist = [w.strip() for w in file.readlines() if w.strip()]

    return param_wordlist


def prepare_header_wordlist(arguments: argparse.Namespace):
    header_wordlist = []

    with open(arguments.header_wordlist) as file:
        allow_regex = '^[A-Za-z0-9_-]+$'

        for line in file:
            word = line.strip()

            if re.search(allow_regex, word):
                header_wordlist.append(word)

    return header_wordlist


def prepare_proxy(arguments: argparse.Namespace):
    url_obj = urlparse(arguments.proxy)

    if url_obj.scheme.startswith('socks'):
        proxy = {'http': arguments.proxy, 'https': arguments.proxy}
    else:
        proxy = {'http': 'http://' + url_obj.netloc, 'https': 'https://' + url_obj.netloc}

    return proxy


def prepare_args(arguments: argparse.Namespace):
    """ Подготавливает агрументы командной строки для программы """
    # --raw-request и --url
    raw_requests = []
    if arguments.raw_requests:
        raw_requests += prepare_raw_requests(arguments)

    if arguments.url:
        raw_requests += prepare_url(arguments)

    arguments.raw_requests = raw_requests

    # --header
    if arguments.additional_headers:
        arguments.additional_headers = prepare_additional_headers(arguments)

    # --param-wordlist
    if arguments.param_wordlist:
        arguments.param_wordlist = prepare_param_wordlist(arguments)

    # --header-wordlist
    if arguments.header_wordlist:
        arguments.header_wordlist = prepare_header_wordlist(arguments)

    # --proxy
    if arguments.proxy:
        arguments.proxy = prepare_proxy(arguments)
