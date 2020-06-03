# Suseeker

Утилита для поиска скрытых параметров в URL, HTTP-заголовках, теле запроса и Cookie-заголовке

[![asciicast](https://asciinema.org/a/gOc8mdz0JecaHrrAuBvUUvwE8.svg)](https://asciinema.org/a/gOc8mdz0JecaHrrAuBvUUvwE8)

## Особенности
* Поиск в **URL**, **Headers**, **Body** (только application/x-www-form-urlencoded) и **Cookie**-заголовке
* Конкурентность посредством использования **Greenlets**
* Возможность использования **множества** сырых HTTP-запросов и URL-адресов
* Использование очереди с приоритетами для **распределения нагрузки** среди указанных запросов
* Определение **оптимального** числа хидеров и параметров в запросе
с помощью бинарного поиска вместе с анализом динамики времени ожидания ответа от сервера
  по соотношению 
  <sup>Размер порции</sup>&frasl;<sub>Время ответа</sub>
* Определение скрытых параметров по изменению **числа тэгов**, **длины контента**,
 **типа контента**, **кода состояния** и **отражений значения** в ответе
* Поиск **дополнительных параметров** в HTML-страницах и скриптах 


## Требования
* Python 3.6
* Не пытаться ломать логику намеренно

## Установка
```
git clone https://github.com/medalahonor/suseeker.git
cd suseeker 
python3 -m venv .
source bin/activate
pip install -r requirements.txt
```

## Запуск
``` 
python3 suseeker.py -u https://example.com -m GET -r <raw_request or folder> --follow -fh -fp -t 6 --timeout 15 --retry 2
```

## Todo
* Скорректировать breaker'ы для значений в хидерах, параметрах и cookie
* Добавить майнинг параметров из archive.org
* Добавить обработку запросов из сохраненного burp suite файла
* Добавить проверку отражения названия параметров в ответе?
* Поиск параметров в Json
* Отправлять запросы через PhantomJS либо найти способ рендерить сырые ответы
* Выводить по окончанию список выполненных проверок для запросов (отдельный параметр)
* Сохранять сырые ответы для найденных параметров
* Перепроверка параметров в словарях при нахождении новых
