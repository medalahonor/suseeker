# Основные настройки
URL_HELP = "URL-адрес ресурса или файл с адресами для поиска"
METHOD_HELP = "Метод запроса для адресов из --url"
BODY_HELP = "Тело запроса типа x-www-form-urlencoded для запросов с пустым телом и для методов," \
            " отличных от GET, HEAD, OPTIONS, TRACE и CONNECT"
RAW_REQUESTS_HELP = "Файл/папка с сырым/сырыми HTTP-запросом/запросами"
ADDITIONAL_HEADERS_HELP = "Дополнительные хидеры к запросам, можно указывать несколько раз. Например: --header='User-Agent: Mozilla' --header='X-Forwarded-Host: test'"
ALLOW_REDIRECTS_HELP = "Позволить переходить по указанным адресам при редиректах"
DISABLE_MINING_HELP = "Выключить поиск параметров в контенте HTML страниц и скриптов"
OUTPUT_HELP = "Путь до файла с результатами работы"
OUTPUT_FORMAT_HELP = "Формат вывода результата: table - таблица [Адрес, Тип параметра, Параметр, Причины]; " \
                     "json - {<url>: {<param_type>: [{\"param\": <param_name>, \"reasons\": [...]}], ...}, ...}; " \
                     "light - <url>: <param_type>:<param_name>; ..."
VERBOSITY_HELP = "Уровень детализации сообщений: 0 - silent-режим (выводится только результат); 1 - INFO и SUCCESS сообщения, 2 [по умолчанию] - WARNING и ERROR сообщения, 3 - debug-режим"


# Настройки поиска параметров
FIND_ALL_HELP = "Запустить полное сканирование скрытых параметров и заголовков в HTTP-запросах"
FIND_HEADERS_HELP = "Запустить сканирование скрытых заголовков в запросе"
FIND_PARAMS_HELP = "Запустить сканирование скрытых параметров в запросе"
FIND_COOKIES_HELP = "Запустить сканирование скрытых параметров в Cookie-заголовке"
HEADER_WORDLIST_HELP = "Пути до словарей с названиями заголовков, разделенных через запятую (Например: --header-wordlists /path1/wordlist1,/path2/wordlist2)"
PARAM_WORDLIST_HELP = "Пути до словарей с названиями параметров, разделенных через запятую (Например: --param-wordlists /path1/wordlist1,/path2/wordlist2)"
COOKIE_WORDLIST_HELP = "Пути до словарей с названиями параметров Cookie, разделенных через запятую (Например: --cookie-wordlists /path1/wordlist1,/path2/wordlist2)"
HEADER_BUCKET_HELP = "Максимальное число хидеров или параметров для поиска в запросе (количество)"
PARAM_BUCKET_HELP = "Максимальный размер порции параметров в URL или теле запроса (в байтах)"
COOKIE_BUCKET_HELP = "Максимальный размер порции параметров Cookie-заголовке (в байтах)"
DISABLE_DYNAMIC_HEADERS_HELP = "Отключить определение оптимального размера заголовков в запросе по соотношению (размер порции)/(время ответа)"
DISABLE_DYNAMIC_PARAMS_HELP = "Отключить определение оптимального размера параметров в запросе по соотношению (размер порции)/(время ответа)"
DISABLE_DYNAMIC_COOKIES_HELP = "Отключить определение оптимального размера параметров в Cookie-заголовке запроса по соотношению (размер порции)/(время ответа)"

# Настройки производительности
PROXY_HELP = "Адрес прокси-сервера (пока только http/https)"
DELAY_HELP = "Время ожидания между запросами в одном потоке (сек)"
THREADS_HELP = "Количество потоков для поиска скрытых параметров и хидеров"
RETRY_HELP = "Общее количество попыток выполнить запрос"
TIMEOUT_HELP = "Максимальное время ожидания ответа от сервера в секундах"
