import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import (
    ApiResponseError, ApiResponseHomeworkVerdictError, ApiResponseKeyError,
    ApiResponseStatusError, TokenError
)

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
    error_list = []
    env_dict = {
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN
    }
    for name, token in env_dict.items():
        if not token:
            error_list.append(name)
    return error_list


def send_message(bot, message):
    """Функция отправляет сообщение в чат в Телеграме."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Успешная отправка сообщения в чат.')
    except Exception as error:
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
        raise ApiResponseStatusError('HTTPStatus ответа API не OK')

    return homework_statuses.json()


def check_response(response):
    """Функция проверяет содержимое ответа API Практикум Домашка."""
    # Проверяем тип полученных данных и ключ 'homeworks'.
    if not isinstance(response, dict):

        raise TypeError(
            f'От API Практикум Домашка получен не словарь, a {type(response)}'
        )

    if 'homeworks' not in response:
        raise ApiResponseKeyError(
            'В ответе API Практикум Домашка нет ключа homeworks'
        )
    resp_homeworks = response['homeworks']
    if not isinstance(resp_homeworks, list):
        raise TypeError(
            f'Под ключом homeworks не список, a {type(resp_homeworks)}'
        )
    return True


def parse_status(homework):
    """
    Функция извлекает статус из информации о конкретной домашней работе.
    Возвращает подготовленную для отправки в Telegram строку.
    """
    # Проверяем наличие ключа homework_name.
    if (
        'homework_name' not in homework
        or 'status' not in homework
    ):
        raise ApiResponseKeyError(
            'В ответе API Практикум Домашка нет ключа homework_name'
        )

    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ApiResponseHomeworkVerdictError(
            'Неожиданный статус домашней работы в ответе API'
        )

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[homework['status']]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    # Проверяем наличие токенов. Если хоть одного нет, выходим.
    env_errors = check_tokens()
    if env_errors:
        message = f'Отсутствует {", ".join(env_errors)}.'
        logging.critical(message)
        if 'TOKEN' in message:
            raise TokenError(message)

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
