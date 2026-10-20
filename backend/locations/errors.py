class LocationError(ValueError):
    def __init__(self, message: str, *, code: str = "invalid_location"):
        super().__init__(message)
        self.code = code
