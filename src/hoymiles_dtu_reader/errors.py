class ModbusError(Exception):
    """Modbus TCP conversation failed."""


class ModbusExceptionResponse(ModbusError):
    """The device answered with a Modbus exception frame.

    This is a valid reply, not a transport failure: the TCP connection is
    still in sync, so the client neither reconnects nor retries.
    """

    def __init__(self, function: int, code: int):
        super().__init__(f"Modbus exception FC={function} code={code}")
        self.function = function
        self.code = code
