class WrongAPIAnswerError(Exception):
    """Некорректный ответ API."""

    pass


class ServerError(Exception):
    """Недоступность API."""

    pass
