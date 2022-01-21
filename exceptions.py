class WrongAPIAnswer(Exception):
    """Некорректный ответ API."""

    pass


class ServerError(Exception):
    """Недоступность API."""

    pass


class DataAPIFormatError(Exception):
    """Невозможность преобразования ответа в формат JSON."""

    pass
