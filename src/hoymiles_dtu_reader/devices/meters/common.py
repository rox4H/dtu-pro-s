from __future__ import annotations

import logging
import struct
import time

log = logging.getLogger("hoymiles_dtu_reader")


def float32_from_words(registers: list[int], index: int, low_word_first: bool) -> float:
    """CHINT instantaneous values are IEEE-754 floats across two registers.

    Meters observed in the field send the low 16-bit word first, while the
    paper manual describes the opposite order. METER_WORD_ORDER selects which.
    """
    first = registers[index]
    second = registers[index + 1]
    if low_word_first:
        raw = (second << 16) | first
    else:
        raw = (first << 16) | second
    return struct.unpack(">f", raw.to_bytes(4, "big"))[0]


class ChintMeter:
    """Shared reader for the CHINT 0x2000 block used by DTSU666 and DDSU666.

    DTSU666 is the three-phase meter. DDSU666 is the single-phase meter
    and only publishes phase 1 of the same block.
    """

    VOLTAGE = {1: 0x2006, 2: 0x2008, 3: 0x200A}
    CURRENT = {1: 0x200C, 2: 0x200E, 3: 0x2010}
    POWER = {1: 0x2014, 2: 0x2016, 3: 0x2018}
    TOTAL_POWER = 0x2012
    POWER_FACTOR = 0x202C
    BLOCK_START = 0x2000
    BLOCK_COUNT = 50
    ENERGY_ADDRESS = 0x2048

    def __init__(
        self,
        type_name: str,
        serial_label: str,
        phases: tuple[int, ...],
        slave_id: int | None,
        candidates: tuple[int, ...],
        low_word_first: bool,
        retry_seconds: float = 60.0,
        probe_retry_seconds: float = 300.0,
        clock=time.monotonic,
    ):
        self.type_name = type_name
        self.serial_label = serial_label
        self.phases = phases
        self.slave_id = slave_id
        self.pinned = slave_id is not None
        self.candidates = candidates
        self.low_word_first = low_word_first
        self.retry_seconds = retry_seconds
        self.probe_retry_seconds = probe_retry_seconds
        self.clock = clock
        self._retry_at = 0.0
        self._last_error = ""

    def read(self, modbus) -> dict:
        """One reading. A failing meter backs off instead of stalling every cycle.

        A pinned meter is retried after `retry_seconds`; a meter that has to be
        searched for is searched again after `probe_retry_seconds`.
        """
        now = self.clock()
        if now < self._retry_at:
            return self._empty(self._last_error or "meter_not_found", slave_id=self.slave_id)
        try:
            if self.slave_id is None:
                self.slave_id = self.probe(modbus)
            if self.slave_id is None:
                self._retry_at = now + self.probe_retry_seconds
                self._last_error = "meter_not_found"
                return self._empty("meter_not_found")
            reading = self._read_slave(modbus, self.slave_id)
            self._retry_at = 0.0
            self._last_error = ""
            return reading
        except Exception as exc:
            if not self.pinned:
                self.slave_id = None
            delay = self.retry_seconds if self.pinned else self.probe_retry_seconds
            self._retry_at = now + delay
            self._last_error = str(exc)
            return self._empty(str(exc), slave_id=self.slave_id)

    def probe(self, modbus) -> int | None:
        timeout = getattr(modbus, "timeout", 1.0)
        retries = getattr(modbus, "retries", 0)
        modbus.timeout = min(float(timeout), 1.0)
        modbus.retries = 0
        try:
            for slave_id in self.candidates:
                try:
                    registers = modbus.read_holding_registers(
                        self.VOLTAGE[1],
                        2,
                        slave_id,
                    )
                    voltage = float32_from_words(registers, 0, self.low_word_first) / 10.0
                except Exception as exc:
                    log.info(
                        "%s probe slave=%s no response (%s)",
                        self.type_name,
                        slave_id,
                        exc.__class__.__name__,
                    )
                    continue
                log.info("%s probe slave=%s V=%.1f", self.type_name, slave_id, voltage)
                if 100.0 < voltage < 280.0:
                    log.info("%s found at slave %s", self.type_name, slave_id)
                    return slave_id
        finally:
            modbus.timeout = timeout
            modbus.retries = retries
        log.warning(
            "%s not found. Set %s_SLAVE_ID to the Addr shown on the meter.",
            self.type_name,
            self.type_name.upper(),
        )
        return None

    def _empty(self, error: str, slave_id: int | None = None) -> dict:
        reading = {
            "type": self.type_name,
            "error": error,
            "grid_power_w": None,
            "importing": False,
            "exporting": False,
            "serial": self.serial_label,
        }
        if slave_id is not None:
            reading["slave_id"] = slave_id
        return reading

    def _scaled(self, registers: list[int], address: int, scale: float) -> float:
        index = address - self.BLOCK_START
        return float32_from_words(registers, index, self.low_word_first) / scale

    def _read_slave(self, modbus, slave_id: int) -> dict:
        registers = modbus.read_holding_registers(
            self.BLOCK_START,
            self.BLOCK_COUNT,
            slave_id,
        )
        grid_power = self._scaled(registers, self.TOTAL_POWER, 10.0)
        reading = {
            "type": self.type_name,
            "serial": self.serial_label,
            "slave_id": slave_id,
            "grid_power_w": round(grid_power, 1),
            "grid_voltage_v": round(self._scaled(registers, self.VOLTAGE[1], 10.0), 1),
            "grid_current_a": round(self._scaled(registers, self.CURRENT[1], 1000.0), 3),
            "power_l1_w": round(self._scaled(registers, self.POWER[1], 10.0), 1),
            "importing": grid_power > 5,
            "exporting": grid_power < -5,
        }
        if 2 in self.phases:
            reading["voltage_l2_v"] = round(self._scaled(registers, self.VOLTAGE[2], 10.0), 1)
            reading["current_l2_a"] = round(self._scaled(registers, self.CURRENT[2], 1000.0), 3)
            reading["power_l2_w"] = round(self._scaled(registers, self.POWER[2], 10.0), 1)
        if 3 in self.phases:
            reading["voltage_l3_v"] = round(self._scaled(registers, self.VOLTAGE[3], 10.0), 1)
            reading["current_l3_a"] = round(self._scaled(registers, self.CURRENT[3], 1000.0), 3)
            reading["power_l3_w"] = round(self._scaled(registers, self.POWER[3], 10.0), 1)

        reading["power_factor"] = self._optional_float(
            modbus,
            slave_id,
            self.POWER_FACTOR,
            1000.0,
        )
        imported, exported = self._energy(modbus, slave_id)
        reading["energy_imported_kwh"] = imported
        reading["energy_exported_kwh"] = exported
        return reading

    def _optional_float(self, modbus, slave_id: int, address: int, scale: float) -> float:
        try:
            registers = modbus.read_holding_registers(address, 2, slave_id)
            return round(float32_from_words(registers, 0, self.low_word_first) / scale, 3)
        except Exception:
            return 0.0

    def _energy(self, modbus, slave_id: int) -> tuple[float, float]:
        """Import/export kWh as read on the existing installation.

        Two unsigned 32-bit values at 0x2048, high word first, scale 0.01.
        This is intentionally not the float map printed for other firmware.
        """
        try:
            registers = modbus.read_holding_registers(self.ENERGY_ADDRESS, 4, slave_id)
            imported = ((registers[0] << 16) | registers[1]) * 0.01
            exported = ((registers[2] << 16) | registers[3]) * 0.01
            return round(imported, 2), round(exported, 2)
        except Exception:
            return 0.0, 0.0
