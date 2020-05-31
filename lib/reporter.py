import json
from argparse import Namespace
import shutil

from colorama import Fore, Style

from lib.constants import OutputFormats, ParamLocation


class Reporter:
    def __init__(self, arguments: Namespace, results: dict):
        self.arguments = arguments
        self.results = results

    def report(self):
        report = ''

        if self.arguments.output_format == OutputFormats.TABLE:
            report = self.results_to_table(self.results)
        elif self.arguments.output_format == OutputFormats.JSON:
            report = self.results_to_json(self.results)
        elif self.arguments.output_format == OutputFormats.LIGHT:
            report = self.results_to_light(self.results)
        else:
            raise NotImplementedError

        if self.arguments.output:
            with open(self.arguments.output, 'w') as file:
                file.write(report)
        else:
            print()
            print(report)

    @staticmethod
    def results_to_table(results):
        """ Работает, не трогай

        :param results:
        :return:
        """
        report = '\n'
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
    def results_to_json(results):
        results_copy = dict()

        for url in results:
            for type in results[url]:
                for param_info in results[url][type]:
                    name = param_info['param']
                    reasons = param_info['reasons']

                    if not results_copy.get(url):
                        results_copy[url] = dict()

                    if not results_copy[url].get(type):
                        results_copy[url][type] = list()

                    results_copy[url][type].append({'param': name, 'reasons': reasons})

        return json.dumps(results_copy)

    @staticmethod
    def results_to_light(results):
        width, _ = shutil.get_terminal_size((80, 24))
        report = ''
        current_line = ' ' * 12

        for url in results:
            report += '\n' + url + ':\n'

            for param_type in results[url]:
                for param_info in results[url][param_type]:
                    name = param_info['param']

                    if param_type == ParamLocation.HEADER:
                        type_color = Fore.YELLOW + param_type + Style.RESET_ALL
                    elif param_type == ParamLocation.BODY:
                        type_color = Fore.GREEN + param_type + Style.RESET_ALL
                    elif param_type == ParamLocation.COOKIE:
                        type_color = Fore.CYAN + param_type + Style.RESET_ALL
                    elif param_type == ParamLocation.JSON:
                        type_color = Fore.MAGENTA + param_type + Style.RESET_ALL
                    else:
                        type_color = param_type

                    pair = f'{type_color}: {name}; '

                    if len(current_line) + len(pair) > width:
                        report += current_line + '\n'
                        current_line = ' ' * 12

                    current_line += pair

            if current_line:
                report += current_line +'\n'
                current_line = ' ' * 12

        return report