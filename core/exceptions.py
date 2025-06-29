class ProductError(Exception):
    def __init__(self, message, errors=None):
        self.message = message
        self.errors = errors or []

    def __str__(self):
        return self.message
