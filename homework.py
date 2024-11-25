import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import ApiResponseError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

TELEGRAM_CHAT_ID = 7757155816

RETRY_PERIOD = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

was_api_call_successful = True
was_response_check_successful = True


# Глобальная конфигурация логирования.
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    level=logging.DEBUG,
    filename='program.log'
)

# Создаем и настраиваем логгер.
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Функция проверяет наличие переменных окружения."""
    if (
        not TELEGRAM_TOKEN
        or type(TELEGRAM_TOKEN) is not str
    ):
        # Логируем отсутствие токена телеграм.
        logging.critical('Отсутствует токен Телеграм.')
        sys.exit()
    if (
        not TELEGRAM_CHAT_ID
        or type(TELEGRAM_CHAT_ID) is not int
    ):
        # Логируем отсутствие ID чата.
        logging.critical('Отсутствует ID чата телеграм.')
    if (
        not PRACTICUM_TOKEN
        or type(PRACTICUM_TOKEN) is not str
    ):
        # Логируем отсутствие токена API Практикум Домашка и оповещаем.
        message = 'Отсутствует токен API Практикум Домашка.'
        logging.critical(message)
        send_log_message(message)
        sys.exit()


def send_message(bot, message):
    """Функция отправляет сообщение в чат в телеграме."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        # Логируем удачную отправку сообщения.
        logging.debug('Успешная отправка сообщения в чат.')
    except Exception as error:
        # Логируем сбой при отправке сообщения.
        logging.error(error, exc_info=True)


def send_log_message(message):
    """Функция отправляет сообщения логирования в чат."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    send_message(bot, message)


def get_api_answer(timestamp):
    """Функция запрашивает данные с API Практикум Домашка."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': timestamp}
    # Получаем доступ к переменной хранящей историю предыдущего вызова.
    global was_api_call_successful
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers,
            params=payload
        )
    except requests.RequestException as error:
        # Логируем сбои при запросе к эндпоинту.
        logging.exception(error, exc_info=True)
        # Если ошибка впервые, то сообщение в чат.
        if was_api_call_successful:
            send_log_message('Сбои при запросе к эндпойнту.')
            was_api_call_successful = False

    if homework_statuses.status_code != HTTPStatus.OK:
        message = 'HTTPStatus не OK'
        logging.error(message)
        # Если ошибка впервые, то сообщение в чат.
        if was_api_call_successful:
            send_log_message(message)
            was_api_call_successful = False
        raise ApiResponseError

    return homework_statuses.json()


def check_response(response):
    """Функция проверяет содержимое ответа API Практикум Домашка."""
    # Обеспечиваем доступ к переменной успеха предыдущего вызова.
    global was_response_check_successful
    message = 'Ответ API не соответствует требуемому формату.'
    # Проверяем тип полученных данных, ключи 'homeworks' и 'current_date'.
    if not isinstance(response, dict):
        logging.error(message)
        if was_response_check_successful:
            send_log_message(message)
            was_response_check_successful = False
        raise TypeError

    if (
        'homeworks' not in response
        or 'current_date' not in response
    ):
        # Логируем отсутствие ожидаемых ключей в ответе API.
        logging.error(message)
        if was_response_check_successful:
            send_log_message(message)
            was_response_check_successful = False
        raise ApiResponseError
    if not isinstance(response['homeworks'], list):
        logging.error(message)
        if was_response_check_successful:
            send_log_message(message)
            was_response_check_successful = False
        raise TypeError

    return True


def parse_status(homework):
    """
    Функция извлекает статус из информации о конкретной домашней работе.
    Возвращает подготовленную для отправки в Telegram строку.
    """
    # Проверяем наличие ключа homework_name.
    if 'homework_name' not in homework:
        message = ('Формат информации о домашней работе не соответствует '
                   'ожидаемому.')
        logging.error(message)
        send_log_message(message)
        raise ApiResponseError

    if homework['status'] in HOMEWORK_VERDICTS:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        # Логируем неожиданный статус домашней работы в ответе API.
        message = 'Неожиданный статус домашней работы в ответе API'
        logging.error(message)
        send_log_message(message)
        raise ApiResponseError


def main():
    """Основная логика работы бота."""
    # Проверяем наличие токенов.
    check_tokens()
    # Создаем объект класса бота.
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
        except Exception as error:
            message = f'Сбой при вызове функции get_api_answer: {error}'
            logging.error(message)

        if response:
            if check_response(response):
                # Если в ответе пришло сообщение и оно прошло проверку...
                if len(response['homeworks']) > 0:
                    latest_homework = response['homeworks'][0]
                    message = parse_status(latest_homework)
                    # Отправляем сообщение в чат.
                    send_message(bot, message)
                else:
                    # Логируем отсутствие в ответе новых статусов.
                    logging.debug('В ответе нет новых статусов')
                # Сохраняем время последнего запроса.
                timestamp = response['current_date']

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
