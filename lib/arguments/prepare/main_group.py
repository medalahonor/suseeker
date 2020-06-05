import argparse
import os
import random
import re
from base64 import b64decode
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from lib.constants import USER_AGENTS
from lib.utils.logger import Logger
from lib.utils.request_helper import parse_raw_request


def prepare_additional_headers(arguments: argparse.Namespace, logger: Logger):
    headers = dict()

    for header in arguments.additional_headers:
        k, v = re.split(':\s*', header.strip(), maxsplit=1)
        headers[k] = v

    return headers


def _prepare_burp_requests(content: str, logger: Logger) -> list:
    root = BeautifulSoup(content, 'html.parser')
    items = root.find('items')

    raw_requests = []

    for item in items.find_all('item'):
        request = item.find('request')

        if not request:
            continue

        if request['base64'] == 'true':
            raw_requests.append(parse_raw_request(b64decode(request.text).decode('utf8')))
        else:
            raw_requests.append(parse_raw_request(request.text))

    return raw_requests


def prepare_raw_requests(arguments: argparse.Namespace, logger: Logger):
    raw_requests = []

    # Если путь - файл
    if os.path.isfile(arguments.raw_requests):
        file = open(arguments.raw_requests)
        content = file.read()

        if not content:
            file.close()
            return raw_requests

        if content.startswith('<?xml version="1.0"?>'):
            raw_requests += _prepare_burp_requests(content, logger)
        else:
            raw_requests.append(parse_raw_request(content))

        file.close()
    # Иначе директория
    else:
        for path, _, files in os.walk(arguments.raw_requests):
            for filename in files:
                file = open(os.path.join(path, filename))
                content = file.read()

                if not content:
                    file.close()
                    continue

                if re.match('<\?xml.*\?>', content):
                    raw_requests += _prepare_burp_requests(content, logger)
                else:
                    raw_requests.append(parse_raw_request(content))

                file.close()

    return raw_requests


def prepare_url(arguments: argparse.Namespace, logger: Logger) -> list:
    raw_requests = []

    urls = []
    if os.path.isfile(arguments.url):
        file = open(arguments.url)
        for url in file:
            urls.append(url.strip())
        file.close()
    else:
        urls.append(arguments.url)

    for url in urls:
        addr = urlparse(url)

        if not (addr.scheme and addr.netloc):
            continue

        prepared_url = ('', addr.netloc, addr.path, addr.params, addr.query, addr.fragment)
        raw_request = [arguments.method, urlunparse(prepared_url).lstrip('/'),
                       {'User-Agent': random.choice(USER_AGENTS), 'Host': addr.netloc,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5', 'Accept-Encoding': 'gzip, deflate'}, '']
        raw_requests.append(raw_request)

    return raw_requests