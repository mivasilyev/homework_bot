class TokenError(NameError):
    """Исключение для ошибок в токене Телеграм."""

    def __str__(self):
        """Возвращаем сообщение об ошибке."""
        return 'Ошибка в токене Телеграм или API Практикум Домашка.'


class ApiResponseError(Exception):
    """Исключение для ошибок ответа API Практикум Домашка."""

    def __str__(self):
        """Возвращаем сообщение об ошибке."""
        return 'Ошибка в ответе API Практикум Домашка.'


class ApiResponseStatusError(ApiResponseError):
    """Исключение для ответа API Практикум Домашка."""

    def __str__(self):
        """Возвращаем сообщение об ошибке."""
        return 'HTTPStatus ответа API не OK'


class ApiResponseKeyError(KeyError):
    """Исключение для ключей в ответе API Практикум Домашка."""

    def __str__(self):
        """Возвращаем сообщение об ошибке."""
        return (
            'В ответе API Практикум Домашка нет ключа homeworks'
            ' или homework_name.'
        )


class ApiResponseHomeworkVerdictError(ApiResponseError):
    """Исключение для неожиданного статуса вердикта ревьювера."""

    def __str__(self):
        """Возвращаем сообщение об ошибке."""
        return 'Неожиданный статус домашней работы в ответе API'
