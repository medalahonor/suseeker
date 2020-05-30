import argparse

from lib.arguments.help import *


epilog = ''' Примеры:

python3 suseeker.py -r requests/ --follow -fh -fp -t 6 --timeout 15 --retry 2
    -r requests/ - папка с сырыми запросами (можно указать файл)
    --follow - следовать редиректам
    -fh - запуск модуля по поиску HTTP-заголовков 
    -fp - запуск модуля по поиску параметров
    -t 6 - число воркеров на каждое задание
    --timeout 15 - время ожидания ответа в секундах
    --retry 2 - Число повторов запроса в случае ошибки (первый запрос + 1 дополнительный)

'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    main_group = parser.add_argument_group('Основные настройки')
    main_group.add_argument('-u', '--url', dest='url', help=URL_HELP)
    main_group.add_argument('-m', '--method', dest='method', default='GET', help=METHOD_HELP)
    main_group.add_argument('-r', '--raw-requests', dest='raw_requests', help=RAW_REQUESTS_HELP)
    main_group.add_argument('-H', '--header', dest='additional_headers', type=list, action='append',
                            help=ADDITIONAL_HEADERS_HELP)
    main_group.add_argument('--follow', dest='allow_redirects', default=False, action='store_true',
                            help=ALLOW_REDIRECTS_HELP)
    main_group.add_argument('-dm', '--disable-mining', dest='disable_mining', default=False, action='store_true',
                            help=DISABLE_MINING_HELP)
    main_group.add_argument('-v', dest='verbosity', default=2, type=int, choices=[0, 1, 2, 3], help=VERBOSITY_HELP)

    headers_group = parser.add_argument_group('Настройки поиска хидеров')
    headers_group.add_argument('-fh', '--find-headers', dest='find_headers', action='store_true', default=False,
                               help=FIND_HEADERS_HELP)
    headers_group.add_argument('-hw', '--header-wordlist', dest='header_wordlist', default='wordlists/headers.txt',
                               help=HEADER_WORDLIST_HELP)
    headers_group.add_argument('-hb', '--header-bucket', dest='header_bucket', type=int, default=2048,
                               help=HEADER_BUCKET_HELP)
    headers_group.add_argument('-ddh', '--disable-dynamic-headers', dest="disable_dynamic_headers", action="store_true",
                               default=False, help=DISABLE_DYNAMIC_HEADERS_HELP)

    parameters_group = parser.add_argument_group('Настройки поиска параметров')
    parameters_group.add_argument('-fp', '--find-params', dest='find_params', action='store_true', default=False,
                                  help=FIND_PARAMS_HELP)
    parameters_group.add_argument('-pw', '--param-wordlist', dest='param_wordlist', default='wordlists/params.txt',
                                  help=PARAM_WORDLIST_HELP)
    parameters_group.add_argument('-pb', '--param-bucket', dest='param_bucket', type=int, default=2048,
                                  help=PARAM_BUCKET_HELP)
    parameters_group.add_argument('-ddp', '--disable-dynamic-params', dest='disable_dynamic_params', action='store_true',
                                  default=False, help=DISABLE_DYNAMIC_PARAMS_HELP)

    cookies_group = parser.add_argument_group('Настройка поиска cookies')

    performance_group = parser.add_argument_group('Настройки производительности')
    performance_group.add_argument('--proxy', dest='proxy', default=None, help=PROXY_HELP)
    performance_group.add_argument('-t', '--threads', dest='threads', default=7, type=int, help=THREADS_HELP)
    performance_group.add_argument('--retry', dest='retry', default=2, type=int, help=RETRY_HELP)
    performance_group.add_argument('--timeout', dest='timeout', default=13, type=int, help=TIMEOUT_HELP)

    return parser.parse_args()
