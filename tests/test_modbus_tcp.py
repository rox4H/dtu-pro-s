from __future__ import annotations

import pytest

from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse
from hoymiles_dtu_reader.transport.modbus_tcp import ModbusTCP


def client_for(server, **kwargs) -> ModbusTCP:
    kwargs.setdefault("timeout", 1.0)
    kwargs.setdefault("retries", 1)
    return ModbusTCP("127.0.0.1", server.port, **kwargs)


def test_reads_holding_registers(fake_dtu):
    fake_dtu.units[1] = {0x10: 111, 0x11: 222, 0x12: 65535}
    modbus = client_for(fake_dtu)
    try:
        assert modbus.read_holding_registers(0x10, 3, unit_id=1) == [111, 222, 65535]
        assert modbus.stats["requests"] == 1
        assert modbus.stats["connections"] == 1
    finally:
        modbus.close()


def test_reuses_the_connection_between_requests(fake_dtu):
    fake_dtu.units[1] = {0: 1, 1: 2}
    modbus = client_for(fake_dtu)
    try:
        modbus.read_holding_registers(0, 1, 1)
        modbus.read_holding_registers(1, 1, 1)
        assert modbus.stats["connections"] == 1
        assert modbus.stats["requests"] == 2
    finally:
        modbus.close()


def test_exception_response_is_raised_and_not_retried(fake_dtu):
    fake_dtu.units[1] = {}
    modbus = client_for(fake_dtu, retries=3)
    try:
        with pytest.raises(ModbusExceptionResponse) as caught:
            modbus.read_holding_registers(0x500, 1, unit_id=1)
        assert caught.value.code == 0x02
        assert caught.value.function == 3
        assert modbus.stats["exceptions"] == 1
        assert modbus.stats["requests"] == 1
        assert modbus.sock is not None
    finally:
        modbus.close()


def test_dropped_connection_is_retried_then_reported(fake_dtu):
    fake_dtu.units[1] = {0: 1}
    fake_dtu.drop_connections = True
    modbus = client_for(fake_dtu, retries=1)
    try:
        with pytest.raises(ModbusError):
            modbus.read_holding_registers(0, 1, 1)
        assert modbus.stats["requests"] == 2
        assert modbus.stats["errors"] >= 2
    finally:
        modbus.close()


def test_connection_refused_raises_modbus_error(free_port):
    modbus = ModbusTCP("127.0.0.1", free_port, timeout=0.5, retries=0)
    with pytest.raises(ModbusError):
        modbus.read_holding_registers(0, 1, 1)


@pytest.mark.parametrize("quantity", [0, 126])
def test_rejects_invalid_read_quantity(quantity):
    with pytest.raises(ValueError):
        ModbusTCP("127.0.0.1", 1).read_holding_registers(0, quantity, 1)


def test_transaction_id_wraps_around():
    modbus = ModbusTCP("127.0.0.1", 1)
    modbus.transaction_id = 65535
    assert modbus._next_transaction_id() == 1
