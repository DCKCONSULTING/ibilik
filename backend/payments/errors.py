class PaymentError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_payload"):
        super().__init__(message)
        self.code = code
