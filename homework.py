import http
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv
import exceptions

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot, message):
    """Функция отправляет сообщения в Телеграмбот."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except exceptions.SendMessageError as error:
        logger.error(
            f'Произошла ошибка при отправке сообщения: {error}')
    except Exception as error:
        logger.error(f'другие сбои при запросе к эндпоинт {error}')
    else:
        logger.info('Сообщение успешно отправлено')


def get_api_answer(current_timestamp):
    """Функция отправляет запрос к апи и возвращает словарь."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            params=params,
            headers=HEADERS
        )
    except Exception as error:
        message = f'Не удалось отправить запрос: {error}'
        logger.error(message)
        raise Exception(message)
    status_code = response.status_code
    if status_code == http.HTTPStatus.OK:
        return response.json()
    message = (
        f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен',
        f'Код ответа api: {status_code}')
    logger.error(message)
    raise exceptions.GetApiError(message)


def check_response(response):
    """Функция проверяет начилие изменений в работе."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип параметра')
    try:
        homework = response['homeworks']
    except exceptions.CheckHomework as error:
        message = f'Ключ "homeworks" отсутствует в словаре {error}'
        logger.error(message)
        raise exceptions.CheckHomework(message)
    if len(homework) > 0:
        return homework[0]
    message = 'В ответе нет новых статусов'
    logger.debug(message)
    raise exceptions.CheckResponseError(message)



def parse_status(homework):
    """Функция проверяет статус работы.
    Возвращает сообщение о результате проверки.
    """
    if 'homework_name' not in homework:
        raise exceptions.ParseError(
            'Отсутствуют ключ "homework_name" в ответе API')
    homework_name = homework['homework_name']
    message = 'Отсутствуют ключ "status"   в ответе API'
    if 'status' not in homework:
        raise exceptions.ParseError(message)
    homework_status = homework['status']
    try:
        verdict = HOMEWORK_VERDICTS[homework_status]
    except exceptions.VerdictError as error:
        message = f'Данного статуса нет в словаре HOMEWORK_VERDICTS: {error} '
        logger.error(message)
        raise exceptions.VerdictError(message)
    logger.info(message)
    return f'Изменился статус проверки работы "{homework_name}".{verdict}'


def check_tokens():
    """Проверяет наличие переменных окружения."""
    if not PRACTICUM_TOKEN:
        logger.critical(
            'Отсутствует обязательная переменная окружения:PRACTICUM_TOKEN')
        return False
    if not TELEGRAM_TOKEN:
        logger.critical(
            'Отсутствует обязательная переменная окружения:TELEGRAM_TOKEN')
        return False
    if not TELEGRAM_CHAT_ID:
        logger.critical(
            'Отсутствует обязательная переменная окружения:TELEGRAM_CHAT_ID')
        return False
    return True


def main():
    """Основная логика работы бота."""
    try:
        check_tokens()
    except Exception as error:
        logger.critical(
            f'Отсутствует обязательная переменная окружения:{error}')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
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
            logger.info('Cообщение об ошибке доставлено')
            time.sleep(RETRY_TIME)
        else:
            logger.info('Cообщение доставлено')


if __name__ == '__main__':
    main()
