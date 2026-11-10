from __future__ import annotations

import struct

from hoymiles_dtu_reader.errors import ModbusError, ModbusExceptionResponse


def registers_to_bytes(registers: list[int]) -> bytes:
    return b"".join(struct.pack(">H", register) for register in registers)


def decode_microinverter_block(data: bytes, hoymiles_type: str) -> dict | None:
    """Decode one 40-byte Hoymiles DTU-Pro microinverter slot.

    The layout is the DTU-Pro Modbus block at 0x1000 (20 registers).
    A serial of 000000000000 means there are no further inverters.
    """
    if len(data) != 40:
        raise ModbusError(f"Microinverter block has {len(data)} bytes")

    serial = data[1:7].hex().upper()
    if serial == "000000000000":
        return None

    current_scale = 100.0 if hoymiles_type == "HM" else 10.0
    return {
        "data_type": data[0],
        "serial": serial,
        "port": data[7],
        "pv_voltage_v": round(struct.unpack_from(">H", data, 8)[0] / 10.0, 1),
        "pv_current_a": round(struct.unpack_from(">H", data, 10)[0] / current_scale, 2),
        "grid_voltage_v": round(struct.unpack_from(">H", data, 12)[0] / 10.0, 1),
        "grid_freq_hz": round(struct.unpack_from(">H", data, 14)[0] / 100.0, 2),
        "pv_power_w": round(struct.unpack_from(">H", data, 16)[0] / 10.0, 1),
        "today_wh": int(struct.unpack_from(">H", data, 18)[0]),
        "total_wh": int(struct.unpack_from(">I", data, 20)[0]),
        "temperature_c": round(struct.unpack_from(">h", data, 24)[0] / 10.0, 1),
        "operating_status": int(struct.unpack_from(">H", data, 26)[0]),
        "alarm_code": int(struct.unpack_from(">H", data, 28)[0]),
        "alarm_count": int(struct.unpack_from(">H", data, 30)[0]),
        "link_status": int(data[32]),
    }


class HoymilesDTU:
    BASE_ADDRESS = 0x1000
    BLOCK_SIZE = 40
    DTU_SERIAL_ADDRESS = 0x2000

    def __init__(self, modbus, unit_id: int = 1, hoymiles_type: str = "HM", max_inverters: int = 100):
        self.modbus = modbus
        self.unit_id = unit_id
        self.hoymiles_type = hoymiles_type
        self.max_inverters = max_inverters
        # None = unknown, False = the DTU refused the register (stop asking).
        self.limit_supported: bool | None = None

    def read_dtu_serial(self) -> str:
        registers = self.modbus.read_holding_registers(
            self.DTU_SERIAL_ADDRESS,
            3,
            self.unit_id,
        )
        return registers_to_bytes(registers).hex().upper()

    def read_microinverter(self, index: int) -> dict | None:
        address = self.BASE_ADDRESS + index * self.BLOCK_SIZE
        registers = self.modbus.read_holding_registers(address, 20, self.unit_id)
        return decode_microinverter_block(
            registers_to_bytes(registers),
            self.hoymiles_type,
        )

    def read_all_microinverters(self) -> list[dict]:
        found = []
        for index in range(self.max_inverters):
            inverter = self.read_microinverter(index)
            if inverter is None:
                break
            found.append(inverter)
        return found

    def read_limit_percent(self, address: int) -> float | None:
        """Current power limit in percent, or None when it cannot be read.

        Some DTU firmware answers an illegal-function/address exception for
        this register. That is remembered so the register is not polled again
        and no made-up 0.0 is reported.
        """
        if self.limit_supported is False:
            return None
        try:
            registers = self.modbus.read_holding_registers(address, 1, self.unit_id)
        except ModbusExceptionResponse as exc:
            if exc.code in (1, 2, 3):  # illegal function / address / value
                self.limit_supported = False
                return None
            raise  # busy and other transient codes are retried next cycle
        self.limit_supported = True
        return registers[0] / 10.0
