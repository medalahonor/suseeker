import argparse
from urllib.parse import urlparse

from lib.utils.logger import Logger


def prepare_proxy(arguments: argparse.Namespace, logger: Logger):
    if arguments.proxy is None:
        return None

    url_obj = urlparse(arguments.proxy)

    if url_obj.scheme.startswith('socks'):
        proxy = {'http': arguments.proxy, 'https': arguments.proxy}
    else:
        proxy = {'http': 'http://' + url_obj.netloc, 'https': 'https://' + url_obj.netloc}

    return proxy