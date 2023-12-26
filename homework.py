import logging
import os
import time
import sys
import exceptions
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig( 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)
stdout_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stdout_handler)


def check_tokens():
    """Проверяем наличие всех токенов."""
    source = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    for token in source:
        if not globals()[token]:
            missing_token = ', '.join(token)
            logger.critical(f'Отсутствует токен: {missing_token}')
            raise exceptions.EmptyToken(
                f'Отсутствует токен: {missing_token}'
                )


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
    except telegram.TelegramError as error:
        logger.error(f'Сообщене не отправлено. Причина: {error}')


def get_api_answer(timestamp):
    """Проверяем статус ответа АПИ."""
    from_date = {}
    from_date['from_date'] = timestamp
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=from_date)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            f'Запрос к {ENDPOINT} с параметрами {timestamp} '
            f'провалился с ошибкой {error}'
            )
    if response.status_code != HTTPStatus.OK:
        raise ValueError(f'Ошибка ответа API: {response.reason}')
    return response.json()


def check_response(response):
    """Проверяем что в ответ пришли данные ожидаемого вида."""
    logger.info('Начало проверки запроса к API')
    if type(response) is not dict:
        raise TypeError(f'Неверный тип ответа API {type(response)}')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks в ответе API')
    if type(response.get('homeworks')) is not list:
        raise TypeError('Неверный тип ответа API')
    if response.get('current_date') is None:
        raise KeyError('Отсутствует ключ current_date в ответе API')
    logger.info('Проверка успешно пройдена')
    return response.get('homeworks')


def parse_status(homework):
    """Проверяем статус проверки и результат ревью."""
    if homework['status'] is None:
        raise KeyError('Отсутствует ключ status в ответе API')
    if homework['status'] not in HOMEWORK_VERDICTS:
        status = homework['status']
        raise ValueError(
            f'Нечитаемый статус домашнего задания {status}'
            )
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ homework_name в ответе API')
    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 604800
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                last_message = message
            else:
                logging.debug('Статус домашнего задания не изменился')
            timestamp = response['current_date']

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
