import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from requests.exceptions import RequestException
from telegram import Bot

from exceptions import ServerError, WrongAPIAnswerError

load_dotenv()

FORMAT = (
    '%(asctime)s - %(name)s - %(levelname)s - '
    '[%(filename)s:%(lineno)d] - %(funcName)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter(FORMAT))
logger.addHandler(console)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS_NAME = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщения в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f'Отправлено сообщение: "{message}"')
        return True
    except Exception as error:
        logger.error(
            f'{error}! Ошибка отправки сообщения "{message}".',
            exc_info=True
        )
        return False


def get_api_answer(current_timestamp):
    """Делает запрос к API, возвращает ответ в формате JSON."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except RequestException as error:
        raise RequestException(
            f'Ошибка соединения - {error}. '
            f'Параметры запроса {ENDPOINT}, {HEADERS}, {params}.'
        )
    if response.status_code != HTTPStatus.OK:
        raise ServerError(
            f'Ошибка доступа к серверу. Код ошибки - {response.status_code}. '
            f'Параметры запроса {ENDPOINT}, {HEADERS}, {params}.'
        )
    answer = response.json()
    if 'error' in answer:
        raise WrongAPIAnswerError(
            'Отказ API - "error": {}. Параметры запроса: {}, {}, {}.'.format(
                answer['error'], ENDPOINT, HEADERS, params)
        )
    if 'code' in answer:
        raise WrongAPIAnswerError(
            'Отказ API - "code": {}. Параметры запроса: {}, {}, {}.'.format(
                answer['code'], ENDPOINT, HEADERS, params)
        )
    return answer


def check_response(response):
    """Проверяет ответ API на корректность, возвращает список работ."""
    if len(response) == 0:
        raise WrongAPIAnswerError('Пустой ответ API.')
    if not isinstance(response, dict):
        raise TypeError(f'Некорректный тип ответа API: "{type(response)}".')
    if 'homeworks' not in response:
        raise WrongAPIAnswerError('В ответе API отсутствует ключ "homeworks".')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Объект "homeworks" не является списком')
    return homeworks


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    name = homework['homework_name']
    status = homework['status']
    verdict = VERDICTS.get(status)
    if status not in VERDICTS:
        raise ValueError(f'Неожиданный статус "{status}" домашней работы!')
    return 'Изменился статус проверки работы "{}". {}'.format(
           name, verdict)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missing_tokens = [name for name in TOKENS_NAME if globals()[name] is None]
    if len(missing_tokens) > 0:
        logger.critical('Отсутствует необходимая переменная(ые) "{}".'.format(
            ', '.join(missing_tokens)))
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError('Отсутствуют аутентификационные данные.')
    logger.info('Аутентификационные данные получены.')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info('Получен ответ от API.')
            homeworks = check_response(response)
            logger.info('Данные о домашних работах успешно извлечены.')
            previous_message = ''
            current_timestamp = response.get('current_date', int(time.time()))
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                logger.info('Нет обновленных статусов домашних работ.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'

        finally:
            if (message and message != previous_message
               and send_message(bot, message)):
                previous_message = message
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename=__file__ + '.log',
        format=FORMAT,
        filemode='w',
    )
    main()
