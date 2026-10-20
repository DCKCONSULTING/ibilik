class BookingError(Exception):
    def __init__(self, message: str, *, code: str = "booking_error"):
        super().__init__(message)
        self.code = code
