import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import *

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
# После ревью заполню докстринги к функция
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler.setFormatter(formatter)

load_dotenv()

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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except SendMessageError as error:
        logging.error(
            f'Произошла ошибка при отправке сообщения: {error}')
    except Exception as error:
        logging.error(f'другие сбои при запросе к эндпоинт {error}')
    else:
        logging.info('Сообщение успешно отправлено')


def get_api_answer(current_timestamp):
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(
        ENDPOINT,
        params=params,
        headers=HEADERS
    )
    status_code = response.status_code
    if status_code == 200:
        return response.json()
    else:
        logging.error((f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен',
                       f'Код ответа api: {status_code}'))
        raise GetApiError(f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен',
                          f'Код ответа api: {status_code}')


def check_response(response):
    if type(response) == dict:
        homework = response['homeworks']
        if len(homework) > 0:
            return homework[0]
        message = 'В ответе нет новых статусов'
        logging.debug(message)
        raise CheckResponseError(message)
    else:
        raise TypeError('неверный тип параметра')


def parse_status(homework):

    if 'homework_name' not in homework:
        raise ParseError('Отсутствуют ключь "homework_name" в ответе API')
    homework_name = homework['homework_name']
    message = 'Отсутствуют ключь "status"   в ответе API'
    if 'status' not in homework:
        raise ParseError(message)
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    logging.error(message)
    return f'Изменился статус проверки работы "{homework_name}".{verdict}'


def check_tokens():
    if not PRACTICUM_TOKEN:
        logging.critical(f'Отсутствует обязательная переменная окружения:PRACTICUM_TOKEN')
        return False
    if not TELEGRAM_TOKEN:
        logging.critical(f'Отсутствует обязательная переменная окружения:TELEGRAM_TOKEN')
        return False
    if not TELEGRAM_CHAT_ID:
        logging.critical(f'Отсутствует обязательная переменная окружения:TELEGRAM_CHAT_ID')
        return False
    return True


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except Exception as error:
        logging.critical(f'Отсутствует обязательная переменная окружения:{error}')
        return None

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())-60*60*6060
    all_errors = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            check = check_response(response)
            message = parse_status(check)
            send_message(bot, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message not in all_errors:
                send_message(bot, message)
                all_errors.append(message)
            logging.info('Cообщение об ошибке доставлено')
            time.sleep(RETRY_TIME)
            print(all_errors)
        else:
            logging.info('Cообщение доставлено')


if __name__ == '__main__':
    main()
