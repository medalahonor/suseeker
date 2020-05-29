import __init__  # ДОЛЖЕН БЫТЬ ПЕРВЫМ ИМПОРТОМ !!!

from time import time

import sys

from lib.arguments import parse_args, is_args_valid, prepare_args
from lib.finders.base_finder import BaseFinder
from lib.finders.header_finder import HeaderFinder
from lib.finders.param_finder import ParamFinder
from lib.finders.params_miner import get_params_from_html
from lib.utils.logger import Logger
from lib.utils.request_helper import RequestHelper, RequestInfo, get_request_objects

if __name__ == '__main__':
    # Обработка аргументов командной строки
    args = parse_args()
    # Проверка переданных аргументов на валидность и достаточность
    if not is_args_valid(args):
        sys.exit(1)
    # Преобразование аргументов под вид, удобный для работы скрипта
    prepare_args(args)

    logger = Logger(args)
    logger.info('Обработка сырых запросов')

    start = time()

    # Преобразовываем сырые запросы в объекты типа `requests.PreparedRequest`
    prepared_requests, not_prepared_requests = get_request_objects(args.raw_requests, args.threads, args.retry,
                                                                   args.timeout, args.proxy, args.allow_redirects,
                                                                   logger)

    if len(prepared_requests) == 0:
        logger.error('Не удалось обработать запросы')
        sys.exit(1)

    if len(not_prepared_requests):
        logger.warning(f'Список не подготовленных запросов: {not_prepared_requests}')

    # Добавляем заголовки в запросы, переданные через командную строку
    if args.additional_headers:
        logger.info('Добавление заголовков -H к запросам')
        for request in prepared_requests:
            RequestHelper.add_headers(request, args.additional_headers)

    # Преобразуем список PreparedRequest в список RequestInfo
    requests_list = [RequestInfo(request) for request in prepared_requests]

    # Получаем эталонный ответ от сервера для каждого из запросов
    logger.info('Получение эталонного ответа от сервера для каждого из запросов')
    RequestHelper.set_origin_responses(requests_list, args.threads, args.retry, args.timeout, args.proxy,
                                       args.allow_redirects, logger)

    # Фильтруем запросы, на которые не удалость получить ответы
    requests_list = RequestHelper.filter_requests(requests_list, lambda x: x.response is None,
                                                  'Следующие запросы не получили изначальный ответ от сервера',
                                                  'Не удалось получить изначальные ответы на все запросы', logger)
    if requests_list is None:
        exit()

    # Если требуется собрать параметры со страниц
    if not args.disable_mining:
        logger.info('Поиск параметров в контенте HTML-страниц и скриптов')
        site_params = get_params_from_html(args, requests_list, logger)

        logger.debug(f'Новые параметры для поиска: {site_params}')
        for info in requests_list:
            info.additional_params = list(site_params[info.netloc])[::]
            info.additional_headers = list(site_params[info.netloc])[::]

    results = dict()

    if args.find_headers:
        secret_headers = HeaderFinder(requests_list, args, logger).run()
        results = BaseFinder.update_results(results, secret_headers)

    if args.find_params:
        secret_params = ParamFinder(requests_list, args, logger).run()
        results = BaseFinder.update_results(results, secret_params)

    stop = time()
    # временное решение
    print(BaseFinder.results_to_table(results))

    if args.verbosity >= 1:
        elapsed = round(stop - start, 2)
        print(f'Время работы: {elapsed} сек')
