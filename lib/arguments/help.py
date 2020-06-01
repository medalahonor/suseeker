# Основные настройки
URL_HELP = "URL-адрес ресурса или файл с адресами для поиска"
METHOD_HELP = "Метод запроса для адресов из --url"
RAW_REQUESTS_HELP = "Файл/папка с сырым/сырыми HTTP-запросом/запросами"
OUTPUT_HELP = "Путь до файла с результатами работы"
OUTPUT_FORMAT_HELP = "Формат вывода результата: table - таблица [Адрес, Тип параметра, Параметр, Причины]; " \
                     "json - {<url>: {<param_type>: [{\"param\": <param_name>, \"reasons\": [...]}], ...}, ...}; " \
                     "light - <url>: <param_type>:<param_name>; ..."
ADDITIONAL_HEADERS_HELP = "Дополнительные хидеры к запросам, можно указывать несколько раз. Например: --header='User-Agent: Mozilla' --header='X-Forwarded-Host: test'"
ALLOW_REDIRECTS_HELP = "Позволить переходить по указанным адресам при редиректах"
DISABLE_MINING_HELP = "Выключить поиск параметров в контенте HTML страниц и скриптов"
VERBOSITY_HELP = "Уровень детализации сообщений: 0 - silent-режим (выводится только результат); 1 - INFO и SUCCESS сообщения, 2 [по умолчанию] - WARNING и ERROR сообщения, 3 - debug-режим"

# Настройки поиска хидеров
FIND_HEADERS_HELP = "Запустить сканирование скрытых хидеров в запросе"
HEADER_WORDLIST_HELP = "Словарь заголовков"
HEADER_BUCKET_HELP = "Максимальное число хидеров или параметров для поиска в запросе (количество)"
DISABLE_DYNAMIC_HEADERS_HELP = "Отключить определение максмиального размера заголовков в запросе по соотношению (размер порции)/(время ответа)"

# Настройки поиска параметров
FIND_PARAMS_HELP = "Запустить Сканирование скрытых параметров в запросе"
PARAM_WORDLIST_HELP = "Словарь параметров"
PARAM_BUCKET_HELP = "Максимальный размер порции параметров в URL или теле запроса (в байтах)"
DISABLE_DYNAMIC_PARAMS_HELP = "Отключить определение максмиального размера параметров в запросе по соотношению (размер порции)/(время ответа)"

# Настройка поиска Cookie
FIND_COOKIES_HELP = ""
COOKIE_WORDLIST_HELP = ""
COOKIE_BUCKET_HELP = ""
DISABLE_DYNAMIC_COOKIES_HELP = ""

# Настройки производительности
PROXY_HELP = "Адрес прокси-сервера (пока только http/https)"
THREADS_HELP = "Количество потоков для поиска скрытых параметров и хидеров"
RETRY_HELP = "Общее количество попыток выполнить запрос"
TIMEOUT_HELP = "Максимальное время ожидания ответа от сервера в секундах"
