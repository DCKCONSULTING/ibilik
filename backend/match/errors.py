class MatchError(Exception):
    def __init__(self, message: str, *, code: str = "match_error"):
        super().__init__(message)
        self.code = code
