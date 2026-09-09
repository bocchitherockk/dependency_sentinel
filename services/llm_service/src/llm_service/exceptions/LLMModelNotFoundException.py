class LLMModelNotFoundException(Exception):
    """Exception raised when a requested LLM model is not found."""

    def __init__(self, message: str):
        super().__init__(message)
