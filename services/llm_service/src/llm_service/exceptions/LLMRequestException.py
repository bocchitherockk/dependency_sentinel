class LLMRequestException(Exception):
    """Exception raised when the LLM request fails."""

    def __init__(self, message: str):
        super().__init__(message)
