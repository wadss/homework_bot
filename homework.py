import logging
import os

from dotenv import load_dotenv

import requests
import time

import telegram

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
    level=logging.INFO)


def check_tokens():
    """Проверяем наличие всех токенов."""
    if not (PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        logging.critical('Отсутствует один из токенов')
        return False
    else:
        return True


def send_message(bot, message):
    """Отправляем сообщение."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('Сообщение отправлено')


def get_api_answer(timestamp):
    """Проверяем статус ответа АПИ."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        if response.status_code != 200:
            raise ValueError(f'Ошибка ответа API: {response.status_code}')
        else:
            return response.json()
    except requests.exceptions.RequestException as error:
        logging.error(f'Ошибка ответа API: {error}')


def check_response(response):
    """Проверяем что в ответ пришли данные ожидаемого вида."""
    if type(response) is not dict:
        raise TypeError('Неверный тип ответа API')
    elif type(response.get('homeworks')) is not list:
        raise TypeError('Неверный тип ответа API')
    elif response.get('current_date') is None:
        raise ValueError('Неверная дата в ответе от API')
    elif response.get('homeworks') is None:
        raise ValueError('В ответе от API отсутствует список домашних заданий')
    else:
        return response.get('homeworks')


def parse_status(homework):
    """Проверяем статус проверки и результат ревью."""
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError('Нечитаемый статус домашнего задания')
    else:
        verdict = HOMEWORK_VERDICTS[homework['status']]
    if 'homework_name' not in homework:
        raise ValueError('Проверяемая домашняя работа не обнаружена')
    else:
        homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = {'from_date': int(time.time()) - 604800}
    response = get_api_answer(timestamp)
    last_message = ''

    while check_tokens():
        try:
            get_api_answer(timestamp)
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
