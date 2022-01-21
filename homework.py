import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import DataAPIFormatError, ServerError, WrongAPIAnswer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='w'
)
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщения в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение отправлено.')
    except Exception:
        logger.error('Ошибка отправки сообщения.')


def get_api_answer(current_timestamp):
    """Делает запрос к API, возвращает ответ в формате JSON."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    if response.status_code != HTTPStatus.OK:
        raise ServerError('Недоступен сервер API.')

    try:
        return response.json()
    except Exception:
        raise DataAPIFormatError('Не корректный формат данных API.')


def check_response(response):
    """Проверяет ответ API на корректность, возвращает список работ."""
    if len(response) == 0:
        raise WrongAPIAnswer('Пустой ответ API.')
    if type(response) is not dict:
        raise TypeError('Некорректный тип ответа API.')
    if 'homeworks' not in response:
        raise WrongAPIAnswer('В ответе API отсутствует ключ "homeworks".')

    try:
        homeworks = response.get('homeworks')
        if type(homeworks) is list:
            return homeworks
    except Exception:
        raise WrongAPIAnswer('В ответе API отсутствуют ожидаемые ключи.')


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    name = homework.get('homework_name')
    if name is None:
        raise KeyError('Ключ homework_name не найден в словаре homework!')

    status = homework.get('status')
    if status is None:
        raise KeyError('Ключ status не найден в словаре homework!')

    verdict = HOMEWORK_STATUSES.get(status)
    if verdict is None:
        raise KeyError(f'Статус "{status}" отсутствует в списке!')

    return f'Изменился статус проверки работы "{name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return(
        bool(PRACTICUM_TOKEN)
        and bool(TELEGRAM_TOKEN)
        and bool(TELEGRAM_CHAT_ID)
    )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return logger.critical('Отсутствуют аутентификационные данные.')
    logger.info('Аутентификационные данные получены.')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    previous_error = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info('Получен ответ от API.')
            homeworks = check_response(response)
            logger.info('Данные о домашних работах успешно извлечены.')
            message = ''
            if len(homeworks) != 0:
                for homework in homeworks:
                    message += parse_status(homework) + "\n"
                current_timestamp = int(time.time())
            else:
                logger.info('Нет обновленных статусов домашних работ.')
        except Exception as error:
            if (previous_error is None or type(error) != type(previous_error)
               or str(error) != str(previous_error)):
                message = f'Сбой в работе программы: {error}'

            logger.error(f'{error}')
            previous_error = str(error)
        finally:
            if message != '':
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
