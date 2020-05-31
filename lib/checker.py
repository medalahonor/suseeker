import re

from requests import Response

from lib.constants import *
from lib.utils.request_helper import RequestInfo


def check_status_code_reason(reasons: list, info: RequestInfo, response: Response):
    # Если изменился код ответа
    if info.response.status_code != response.status_code:
        orig_status_code = info.response.status_code
        status_code = response.status_code
        reasons.append({'reason': DIFF_STATUS_CODE, 'value': f'{status_code} ({orig_status_code})'})


def check_content_type_reason(reasons: list, info: RequestInfo, response: Response):
    # Если изменился тип контента
    if info.response.headers.get('Content-Type') != response.headers.get('Content-Type'):
        orig_content_type = info.response.headers.get('Content-Type')
        content_type = response.headers.get('Content-Type')

        reasons.append(
            {'reason': DIFF_CONTENT_TYPE, 'value': f'{content_type} ({orig_content_type})'})


def check_content_length_reason(reasons: list, info: RequestInfo, response: Response):
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


def check_header_value_reflection_reason(reasons: list, info: RequestInfo, response: Response):
    # Если базовое значение заголовка отражается в ответе
    if info.base_header_value in response.text:
        orig_reflections = len(re.findall(info.base_header_value, info.response.text))
        reflections = len(re.findall(info.base_header_value, response.text))

        reasons.append({'reason': HEADER_VALUE_REFLECTION,
                        'value': f'{reflections} ({orig_reflections})'})


def check_param_value_reflection_reason(reasons: list, info: RequestInfo, response: Response):
    # Если базовое значение параметра отражается в ответе
    if info.url_base_param_value in response.text:
        # То дополнительно проверяем, чтобы отраженное значение не было частью URL
        reflections = len([match for match in
                           re.findall(f'(https?://[^;\'"]+)?({info.url_base_param_value})', response.text) if not match[0]])

        if reflections:
            orig_reflections = len([match for match in
                                    re.findall(f'(https?://[^;\'"]+)?({info.url_base_param_value})', info.response.text) if
                                    not match[0]])
            reasons.append({'reason': PARAM_VALUE_REFLECTION, 'value': f'{reflections} ({orig_reflections})'})
