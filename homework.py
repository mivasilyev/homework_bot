import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (ApiResponseError, ApiResponseHomeworkVerdictError,
                        ApiResponseKeyError, ApiResponseStatusError,
                        TokenError)

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


def check_tokens():
    """Функция проверяет наличие переменных окружения."""
    tg_token_error = False
    tg_chat_id_error = False
    practicum_token_error = False

    if (
        not TELEGRAM_TOKEN
        or type(TELEGRAM_TOKEN) is not str
    ):
        tg_token_error = True
        # Логируем отсутствие токена телеграм.
        logging.critical('Отсутствует токен Телеграм.')
    if (
        not TELEGRAM_CHAT_ID
        or type(TELEGRAM_CHAT_ID) is not int
    ):
        tg_chat_id_error = True
        # Логируем отсутствие ID чата.
        logging.critical('Отсутствует ID чата телеграм.')
    if (
        not PRACTICUM_TOKEN
        or type(PRACTICUM_TOKEN) is not str
    ):
        practicum_token_error = True
        # Логируем отсутствие токена API Практикум Домашка.
        message = 'Отсутствует токен API Практикум Домашка.'
        logging.critical(message)

    if (
        not tg_token_error
        and not tg_chat_id_error
        and practicum_token_error
    ):
        bot = TeleBot(token=TELEGRAM_TOKEN)
        send_message(bot, message)

    elif tg_token_error or practicum_token_error:
        raise TokenError  # Сообщение в кастомном исключении.


def send_message(bot, message):
    """Функция отправляет сообщение в чат в Телеграме."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Успешная отправка сообщения в чат.')
    except Exception as error:
        # Логируем сбой при отправке сообщения.
        logging.error(error, exc_info=True)


def get_api_answer(timestamp):
    """Функция запрашивает данные с API Практикум Домашка."""
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers,
            params=payload
        )
    except requests.RequestException as error:
        raise ApiResponseError(error)

    if homework_statuses.status_code != HTTPStatus.OK:
        raise ApiResponseStatusError  # Сообщение в кастомном исключении.

    return homework_statuses.json()


def check_response(response):
    """Функция проверяет содержимое ответа API Практикум Домашка."""
    # Проверяем тип полученных данных и ключ 'homeworks'.
    if not isinstance(response, dict):
        raise TypeError('От API Практикум Домашка получен не словарь')

    elif 'homeworks' not in response:
        raise ApiResponseKeyError  # Сообщение в кастомном исключении.

    elif not isinstance(response['homeworks'], list):
        raise TypeError('Под ключом homeworks не список')

    else:
        return True


def parse_status(homework):
    """
    Функция извлекает статус из информации о конкретной домашней работе.
    Возвращает подготовленную для отправки в Telegram строку.
    """
    # Проверяем наличие ключа homework_name.
    if 'homework_name' not in homework:
        raise ApiResponseKeyError  # Сообщение в кастомном исключении.

    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ApiResponseHomeworkVerdictError  # Сообщ-е в кастомном исключ-и.

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    # Проверяем наличие токенов.
    check_tokens()
    # Создаем объект класса бота.
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    latest_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                # Если в ответе пришло сообщение и оно прошло проверку...
                if response['homeworks']:
                    latest_homework = response['homeworks'][0]
                    message = parse_status(latest_homework)
                    # Отправляем сообщение в чат.
                    if message != latest_message:
                        send_message(bot, message)
                        latest_message = message
                else:
                    # Логируем отсутствие в ответе новых статусов.
                    logging.debug('В ответе нет новых статусов')
                # Сохраняем время последнего запроса.
                timestamp = response['current_date']

        except Exception as error:
            message = f'Сбой при вызове функции: {error}'
            logging.error(message)
            if latest_message != message:
                send_message(message)
                latest_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
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
    main()
