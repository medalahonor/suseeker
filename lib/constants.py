CACHE_BUSTER_ALF = 'qwertyuiopasdfghjklzxcvbnm1234567890'

# ...
DISCARD_WORDS = 1
RETRY_WORDS = 2
SPLIT_WORDS = 3

# Причины определения заколовков или параметров как скрытых
DIFF_HTML_TAGS_COUNT = 'diff_html_tags_count'
DIFF_CONTENT_LENGTH = 'diff_content_length'
DIFF_STATUS_CODE = 'diff_status_code'
DIFF_CONTENT_TYPE = 'diff_content_type'
HEADER_VALUE_REFLECTION = 'header_value_reflection'
PARAM_VALUE_REFLECTION = 'param_value_reflection'

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_4) AppleWebKit/605.1.15 (KHTML, like Gecko)',
    'Mozilla/5.0 (iPad; CPU OS 9_3_5 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Mobile/13G36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows 98)',
    'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36 Edge/15.15063',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.18363',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 12_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36',
    'Mozilla/5.0 (Windows NT 5.1; rv:36.0) Gecko/20100101 Firefox/36.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/603.3.8 (KHTML, like Gecko)'
]


class ParamLocation:
    URL = "URL param"
    HEADER = "Header"
    BODY = "Body"
    JSON = "Json"


class OutputFormats:
    TABLE = 'table'
    JSON = 'json'
    LIGHT = 'light'

    @staticmethod
    def get_list():
        return [OutputFormats.__dict__[attr] for attr in OutputFormats.__dict__ if
                not attr.startswith('_') and isinstance(OutputFormats.__dict__[attr], str)]
