class ToolCallException(Exception):
    """
    Exception raised when a tool call fails.
    """

    def __init__(self, message: str):
        super().__init__(message)
