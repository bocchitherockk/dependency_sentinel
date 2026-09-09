class MCPListToolsException(Exception):
    """
    Exception raised when there is an error related to the MCP list tools.
    """

    def __init__(self, message: str):
        super().__init__(message)
