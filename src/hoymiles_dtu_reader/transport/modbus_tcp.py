from __future__ import annotations

import socket
import struct
import threading
import time

from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse


class ModbusTCP:
    """Small, read-only Modbus TCP client for the Hoymiles DTU."""

    def __init__(self, host: str, port: int = 502, timeout: float = 3.0, retries: int = 2):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries
        self.sock = None
        self.transaction_id = 0
        self.lock = threading.RLock()
        self.stats = {
            "connections": 0,
            "requests": 0,
            "errors": 0,
            "exceptions": 0,
            "bytes_rx": 0,
            "bytes_tx": 0,
        }

    def _next_transaction_id(self) -> int:
        self.transaction_id = self.transaction_id % 65535 + 1
        return self.transaction_id

    def connect(self) -> None:
        if self.sock is not None:
            return
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self.sock.settimeout(self.timeout)
            self.stats["connections"] += 1
        except OSError as exc:
            self.sock = None
            self.stats["errors"] += 1
            raise ModbusError(f"Connection failed: {exc}") from exc

    def close(self) -> None:
        sock, self.sock = self.sock, None
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def _recv_exact(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise ModbusError("DTU closed TCP connection")
            data.extend(chunk)
        self.stats["bytes_rx"] += len(data)
        return bytes(data)

    def _read_request(self, address: int, quantity: int, unit_id: int) -> bytes:
        with self.lock:
            last_error: Exception | None = None
            for attempt in range(self.retries + 1):
                try:
                    self.connect()
                    transaction_id = self._next_transaction_id()
                    payload = struct.pack(">BHH", 3, address, quantity)
                    header = struct.pack(">HHHB", transaction_id, 0, len(payload) + 1, unit_id)
                    packet = header + payload
                    self.sock.sendall(packet)
                    self.stats["bytes_tx"] += len(packet)
                    self.stats["requests"] += 1

                    response = self._recv_exact(7)
                    response_id, protocol_id, _length, response_unit = struct.unpack(">HHHB", response)
                    if response_id != transaction_id:
                        raise ModbusError(f"Transaction mismatch {response_id} != {transaction_id}")
                    if protocol_id != 0:
                        raise ModbusError("Invalid Modbus protocol ID")
                    if response_unit != unit_id:
                        raise ModbusError(f"Unit mismatch {response_unit} != {unit_id}")

                    function = self._recv_exact(1)[0]
                    if function & 0x80:
                        code = self._recv_exact(1)[0]
                        raise ModbusExceptionResponse(function & 0x7F, code)
                    if function != 3:
                        raise ModbusError(f"Unexpected function {function}")

                    byte_count = self._recv_exact(1)[0]
                    return self._recv_exact(byte_count)
                except ModbusExceptionResponse:
                    # A Modbus exception is a complete reply; retrying it is pointless.
                    self.stats["exceptions"] += 1
                    raise
                except (TimeoutError, ConnectionError, OSError, ModbusError) as exc:
                    last_error = exc
                    self.stats["errors"] += 1
                    self.close()
                    if attempt < self.retries:
                        time.sleep(0.15 * (attempt + 1))
            raise ModbusError(str(last_error))

    def read_holding_registers(self, address: int, quantity: int, unit_id: int = 1) -> list[int]:
        if not 1 <= quantity <= 125:
            raise ValueError("Quantity must be 1..125")
        body = self._read_request(address, quantity, unit_id)
        expected = quantity * 2
        if len(body) != expected:
            raise ModbusError(f"Expected {expected} bytes, got {len(body)}")
        return list(struct.unpack(">" + ("H" * quantity), body))
