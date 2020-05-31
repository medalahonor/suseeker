import math
from collections import defaultdict
from typing import Union, Callable, Tuple, List

import gevent
from gevent.queue import Queue
from requests import PreparedRequest, Response

from lib.utils.request_helper import RequestHelper, RequestInfo


class BaseFinder(RequestHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bucket_size_cache = defaultdict(dict)

    def determine_bucket_size(self, info: RequestInfo):
        raise NotImplementedError

    def find_secrets(self, info: RequestInfo, words: List[str]):
        raise NotImplementedError

    def get_bucket_size(self, info: RequestInfo):
        """ Возвращает общие число хидеров в запросе """
        raise NotImplementedError

    def get_word_chunks(self, info: RequestInfo):
        raise NotImplementedError

    def is_info_searchable(self, info: RequestInfo):
        raise NotImplementedError

    def set_bucket_size(self, info: RequestInfo):
        """ Устанавивает для запроса в `info` общее число хидеров """
        raise NotImplementedError

    def setup_requests_info(self, info_list: List[RequestInfo]):
        raise NotImplementedError

    def do_request(self, prepared_request: PreparedRequest, **kwargs) -> Union[Response, None]:
        """ Выполняет подготовленных запрос с отчисткой промежуточного кэша

        :param prepared_request:
        :return:    `None` - если по истечении `self.retry` попыток не удалось получить ответ от сервера
                    `requests.Response` - если удалось получить ответ от сервера
        """
        return super().do_request(prepared_request, self.retry, self.timeout, self.proxies,
                                  self.arguments.allow_redirects, self.logger)

    def filter_requests(self, *args, **kwargs):
        kwargs.update({'logger': self.logger})
        return super().filter_requests(*args, **kwargs)

    def get_optimal_bucket(self, info: RequestInfo, min_chunk: int, add_random: Callable,
                           additional_size: Callable) -> Union[int, None]:
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

            # Если все запросы не получили ответа от сервера, то сдвигаемся влево
            if not any(results):
                right_border = left

                right = right_border
                cur = right >> 1
                left = cur >> 1

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
        if optimal_size is not None:
            if optimal_size < min_chunk < right_border:
                return min_chunk + additional_size(info)

            return optimal_size + additional_size(info)

        return optimal_size

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
