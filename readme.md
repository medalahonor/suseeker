# Suseeker

Утилита для поиска скрытых параметров в URL, HTTP-заголовках, теле запроса и Cookie-заголовке

[![asciicast](https://asciinema.org/a/imfUtcwE5tQStFJ2umTFrl8l5.svg)](https://asciinema.org/a/imfUtcwE5tQStFJ2umTFrl8l5)

## Особенности
* Поиск в **URL**, **Headers**, **Body** (x-www-form-urlencoded и json) и **Cookie**-заголовке
* Поиск **дополнительных параметров** в **HTML**, **JS**, **JSON** контенте и посредством SDX api **web.archive.org**
* Конкурентность посредством использования **Greenlets**
* Возможность использования **множества** HTTP-запросов (сырых и импортированных из Burp Suite) и URL-адресов
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
python3 suseeker.py -u <url or file> -m GET -r <raw_request or folder> --follow -fa -t 10 --timeout 15 --retry 2
```

## Todo
* Удалять из запросов заголовки If-Modified-Since, If-None-Match и т.п.
* Группировать запросы с одинаковыми host и url (отдельный параметр)
* Добавить майнинг параметров из archive.org (параметры, части путей url, скрипты)
* Выводить по окончанию список выполненных проверок для запросов (отдельный параметр)
* Перепроверка параметров в словарях при нахождении новых
* Сохранять найденные параметры модулем Miner (только при указании пути)
* Сохранять сырые ответы для найденных параметров?
* Добавить проверку отражения названия параметров в ответе?
* Рендерить ответы (https://github.com/psf/requests-html)?