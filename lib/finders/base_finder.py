import math
import re
from collections import defaultdict
from typing import Union, Callable, Tuple

import gevent
from gevent.queue import Queue
from requests import PreparedRequest, Response

from lib.utils.constants import *
from lib.utils.request_helper import RequestHelper, RequestInfo
from lib.utils.workers import GuessWorker


class BaseFinder(RequestHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_request(self, prepared_request: PreparedRequest, **kwargs) -> Union[Response, None]:
        """ Выполняет подготовленных запрос с отчисткой промежуточного кэша

        :param prepared_request:
        :return:    `None` - если по истечении `self.retry` попыток не удалось получить ответ от сервера
                    `requests.Response` - если удалось получить ответ от сервера
        """
        return super().do_request(prepared_request, self.retry, self.timeout, self.proxies,
                                  self.arguments.allow_redirects, self.logger)

    def do_work(self, worker_builder: GuessWorker, work: Callable, args_queue: Queue, results_queue: Queue):
        """ Конкурентно выполняет заданную работу `work`

        Создает воркеры ``
        :param worker_builder: Создает объекты воркеров, наследованных от `GuessWorker`
        :param work: Работа, выполняемая в рамках `worker_builder`
        :param args_queue:  Очередь аргументов для функции `work`
        :param results_queue:   Очередь с результатами работы воркеров
        :return:
        """
        # Запускаем воркеры
        workers = [worker_builder(work, args_queue, results_queue, self.logger)
                   for _ in range(self.threads)]

        greenlets = [gevent.spawn(worker.run) for worker in workers]

        # Ждем заверщения работы
        while any([worker.is_running() for worker in workers]) or args_queue.qsize():
            gevent.sleep(0)

        # Выключаем воркеры
        for worker in workers:
            worker.finish()

        # Ждем выключения
        while not all([worker.is_stopped() for worker in workers]):
            gevent.sleep(0.1)

        gevent.joinall(greenlets)

    def filter_requests(self, *args, **kwargs):
        kwargs.update({'logger': self.logger})
        return super().filter_requests(*args, **kwargs)

    def get_optimal_bucket(self, info: RequestInfo, min_chunk: int, add_random: Callable) -> int:
        """ Ищет оптимальный размер порции параметров соотношение (Длина порции) / (время ответа)

        :param info:
        :return:
        """
        left, cur, right = 1024, 2048, 4096
        left_border = 0
        right_border = math.inf

        counter = 5

        optimal_size = None
        optimal_rate = 0

        # Ограничение на число циклов
        while counter:
            counter -= 1

            # Если левая граница обнулилась
            if left == 0:
                break

            # Если диапазон неделим, то прекратить цикл
            if right - cur < 2 or cur - left < 2:
                break

            # Подготавливаем запросы
            _requests = [info.copy_request() for _ in range(3)]
            for request, length in zip(_requests, [left, cur, right]):
                add_random(request, length)

            # Отправляем
            jobs = [gevent.spawn(self.do_request, request) for request in _requests]
            gevent.joinall(jobs)
            responses = [job.value for job in jobs]

            # Получаем результаты
            results = [response.status_code == info.response.status_code if response is not None else response
                       for response in responses]

            self.logger.debug(
                f'results = {results}; l,c,r = [{left}, {cur}, {right}]; lb,rb = {left_border, right_border}')

            # Если все запросы не получили ответа от сервера, то сдвигаемся влево
            if not any(results):
                right_border = left

                right = right_border
                cur = right >> 1
                left = cur >> 1

                self.logger.debug(f'optimal_size = {optimal_size}')
                continue

            # Иначе выбираем среди ответов оптимальный
            rates = []

            for response, size, result in zip([response for response in responses], [left, cur, right], results):
                # Рассматриваем только те случаи, когда мы не вышли за границы
                elapsed = response.elapsed.total_seconds() if (response is not None and result == True) else math.inf
                rate = round(size / elapsed, 1)
                rates.append(rate)

                if rate > optimal_rate and result:
                    optimal_rate = rate
                    optimal_size = size

            self.logger.debug(f'optimal_size = {optimal_size}')

            # Cмотрим, в какую сторону развивается динамика
            max_rate = max(rates)

            # Если все запросы не превысили границу, то двигаемся в сторону динамики
            if all(results):
                # Если динамика увеличивается слева
                if rates[0] == max_rate:
                    right_border = right

                    # То смещаемся влево
                    right = left - 1
                    cur = right >> 1
                    left = cur >> 1

                    # Если левый указатель меньше левой границы
                    if left < left_border:
                        # То пересчитываем указатели в пределах границ
                        left, cur, right = self.shift_bounds(left_border, right_border)

                # Если динамика увеличивается справа
                elif rates[2] == max_rate:
                    left_border = left

                    # То смещаемся вправо
                    left = right + 1
                    cur = left << 1
                    right = cur << 1

                    # Если правый указатель вышел за пределы правой границы
                    if right > right_border:
                        # То пересчитываем указатели в пределах границ
                        left, cur, right = self.shift_bounds(left_border, right_border)

                # Иначе рассматриваем окрестности центра
                else:
                    left_border = left if left > left_border else left_border
                    right_border = right if right < right_border else right_border

                    left = (left + cur) // 2
                    right = (cur + right) // 2
            # Если результаты [True, False|None, False|None]
            elif results[0] == True and all([not r for r in results[1:]]):
                right_border = cur if cur < right_border else right_border
                # То сдвигаемся влево
                right = left - 1
                cur = right >> 1
                left = cur >> 1
            # Если результаты [True, True, False|None]
            elif results[2] in {None, False} and all([r for r in results[:2]]):
                right_border = right if right < right_border else right_border
                # То смотрим на динамику слева и посередине

                # Если динамика увеличивается слева
                if rates[0] == max_rate:
                    # То сдвигаемся влево
                    right = left - 1  # Сдвигаем рассматриваемую правую границу на 1 от ранее рассматриваемой левой
                    cur = right >> 1
                    left = cur >> 1

                    # Если левый указатель меньше левой границы
                    if left < left_border:
                        # То пересчитываем указатели в пределах границ
                        left, cur, right = self.shift_bounds(left_border, right_border)
                # Иначе копаем в пределах cur
                else:
                    right = round((cur + right) / 2)
                    left = (left + cur) // 2
            else:
                # Сдвигаемся влево
                right = left - 1  # Сдвигаем рассматриваемую правую границу на 1 от ранее рассматриваемой левой
                cur = right >> 1
                left = cur >> 1

        # Если по итогу оптимальный размер меньше минимально требуемого, то вернуть минимально требуемый требуемый
        if optimal_size and optimal_size < min_chunk:
            return min_chunk

        return optimal_size

    def check_status_code_reason(self, reasons: list, info: RequestInfo, response: Response):
        # Если изменился код ответа
        if info.response.status_code != response.status_code:
            orig_status_code = info.response.status_code
            status_code = response.status_code
            reasons.append({'reason': DIFF_STATUS_CODE, 'value': f'{status_code} ({orig_status_code})'})

    def check_content_type_reason(self, reasons: list, info: RequestInfo, response: Response):
        # Если изменился тип контента
        if info.response.headers.get('Content-Type') != response.headers.get('Content-Type'):
            orig_content_type = info.response.headers.get('Content-Type')
            content_type = response.headers.get('Content-Type')

            reasons.append(
                {'reason': DIFF_CONTENT_TYPE, 'value': f'{content_type} ({orig_content_type})'})

    def check_content_length_reason(self, reasons: list, info: RequestInfo, response: Response):
        # Если изменилась длина контента
        if info.response.headers.get('Content-Length', 0) != response.headers.get('Content-Length', 0):
            # Если оригинальный ответ - html документ
            if info.response_html_tags_count > 0:
                # То дополнительно проверяем число тэгов html запроса
                new_html_tags_count = info.count_html_tags(response.text)

                if new_html_tags_count != info.response_html_tags_count:
                    reasons.append({'reason': DIFF_HTML_TAGS_COUNT,
                                    'value': f'{new_html_tags_count} ({info.response_html_tags_count})'})
            else:
                orig_content_length = info.response.headers.get('Content-Length', 0)
                content_length = response.headers.get('Content-Length', 0)
                reasons.append({'reason': DIFF_CONTENT_LENGTH,
                                'value': f'{content_length} ({orig_content_length})'})

    def check_header_value_reflection_reason(self, reasons: list, info: RequestInfo, response: Response):
        # Если базовое значение заголовка отражается в ответе
        if info.base_header_value in response.text:
            orig_reflections = len(re.findall(info.base_header_value, info.response.text))
            reflections = len(re.findall(info.base_header_value, response.text))

            reasons.append({'reason': HEADER_VALUE_REFLECTION,
                            'value': f'{reflections} ({orig_reflections})'})

    def check_param_value_reflection_reason(self, reasons: list, info: RequestInfo, response: Response):
        # Если базовое значение параметра отражается в ответе
        if info.base_param_value in response.text:
            # То дополнительно проверяем, чтобы отраженное значение не было частью URL
            reflections = len([match for match in
                           re.findall(f'(https?://[^;\'"]+)?({info.base_param_value})', response.text) if not match[0]])

            if reflections:
                orig_reflections = len([match for match in
                           re.findall(f'(https?://[^;\'"]+)?({info.base_param_value})', info.response.text) if not match[0]])
                reasons.append({'reason': PARAM_VALUE_REFLECTION, 'value': f'{reflections} ({orig_reflections})'})

    @staticmethod
    def parse_results_queue(results_queue: Queue):
        results = defaultdict(lambda: defaultdict(list))
        while results_queue.qsize():
            result = results_queue.get()
            for param_name, value in result.items():
                url, reasons, type, response = value['url'], value['reasons'], value['type'], value['response']
                results[url][type].append({'param': param_name, 'reasons': reasons, 'response': response})

        return results

    # TODO: Вынести в класс Reporter
    @staticmethod
    def results_to_table(results):
        """ Работает, не трогай

        :param results:
        :return:
        """
        report = ''
        report_list = []

        table = ['Адрес', 'Тип параметра', 'Параметр', 'Причины']

        table_frmt = '{:^{}}'
        row_frmt = '{:^{}}'
        sep_frmt = '{:-^{}}'

        max_url, max_type, max_name, max_reason = map(len, table)
        same_url = same_type = same_name = False

        get_val = lambda val, same: '' if same else val

        for url in results:
            max_url = len(url) if len(url) > max_url else max_url

            for type in results[url]:
                max_type = len(type) if len(type) > max_type else max_type

                for param_info in results[url][type]:
                    name = param_info['param']
                    max_name = len(name) if len(name) > max_name else max_name

                    for reason_info in param_info['reasons']:
                        reason = str(reason_info['reason']) + ': ' + str(reason_info['value'])

                        max_reason = len(reason) if len(reason) > max_reason else max_reason

                        row = [get_val(url, same_url), get_val(type, same_type), get_val(name, same_name), reason]
                        report_list.append(row)

                        same_url = same_type = same_name = True

                    same_name = False
                same_type = False
            same_url = False

        sep = '\n' + '---'.join(
            [sep_frmt.format('', length) for length in [max_url, max_type, max_name, max_reason]]) + '\n'

        report += sep + ' | '.join([table_frmt.format(item, length) for item, length in
                                    zip(table, [max_url, max_type, max_name, max_reason])]) + sep

        for row in report_list:
            line = ' | '.join(
                [row_frmt.format(item, length) for item, length in zip(row, [max_url, max_type, max_name, max_reason])])
            report += ''.join([line, sep])

        return report

    @staticmethod
    def shift_bounds(left_bound: int, right_bound: int) -> Tuple[int, int, int]:
        """ Сдвигает тройку `left`, `cur`, `right` согласно новым границам `left_bound` и `right_bound` """
        cur = (left_bound + right_bound) // 2
        left = (left_bound + cur) // 2
        right = round((cur + right_bound) / 2)
        return left, cur, right

    @staticmethod
    def update_results(results: dict, new_results: dict) -> dict:
        """ Обновляет словарь `results` данными из `new_results`

        :param results:
        :param new_results:
        :return:
        """
        if not len(results.keys()):
            results = defaultdict(lambda: defaultdict(list))

        for url in new_results:
            for type in new_results[url]:
                for new_info in new_results[url][type]:
                    new_param, new_reasons, new_response = new_info['param'], new_info['reasons'], new_info['response']
                    results[url][type].append({'param': new_param, 'reasons': new_reasons, 'response': new_response})

        return results
