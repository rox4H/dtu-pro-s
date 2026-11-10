# Modbus register layouts

These layouts were observed on real devices and are **not vendor-guaranteed**; firmware versions differ. Automated tests use synthetic frames, not real hardware. Run `hoymiles-dtu-reader scan-meter` to inspect a meter on the bus.

The reader uses Modbus TCP function 3 (read holding registers) only. Responses are parsed using the PDU byte count rather than the MBAP length because some DTU firmware reports a wrong length.

## Hoymiles DTU-Pro (unit id `DTU_SLAVE_ID`, default 1)

| What | Address | Size |
| --- | --- | --- |
| Microinverter port slot *i* | `0x1000 + 40 * i` | 20 registers (40 bytes) |
| DTU serial | `0x2000` | 3 registers, shown as upper-case hex |
| Power limit (optional) | `LIMIT_REGISTER_ADDRESS`, default 257 | 1 register; value / 10 = percent |

The reader reads slots from *i* = 0 upward and stops at the first slot whose serial is `000000000000` or after `MAX_MICROINVERTERS` slots.

### Slot layout (40 bytes, big-endian)

| Byte offset | Type | Field | Scale / unit |
| --- | --- | --- | --- |
| 0 | u8 | `data_type` | |
| 1-6 | 6 bytes | `serial` | hex |
| 7 | u8 | `port` | |
| 8 | u16 | `pv_voltage_v` | / 10 V |
| 10 | u16 | `pv_current_a` | / 100 A for `HM`, / 10 A for `MI` |
| 12 | u16 | `grid_voltage_v` | / 10 V |
| 14 | u16 | `grid_freq_hz` | / 100 Hz |
| 16 | u16 | `pv_power_w` | / 10 W |
| 18 | u16 | `today_wh` | Wh |
| 20 | u32 | `total_wh` | Wh |
| 24 | i16 | `temperature_c` | / 10 °C |
| 26 | u16 | `operating_status` | raw code |
| 28 | u16 | `alarm_code` | raw code |
| 30 | u16 | `alarm_count` | |
| 32 | u8 | `link_status` | 0 = not linked |

Bytes 33-39 are not decoded. If the DTU does not support the power-limit register, its API value is `null`.

## CHINT DDSU666 (single phase) and DTSU666 (three phase)

The meters sit on the DTU's RS485 bus and are reached through the DTU's Modbus TCP gateway. The unit id is the meter's configured *Addr*, not the DTU's id. The reader reads 50 registers from `0x2000` in one request. Instantaneous values are IEEE-754 float32 spread over two registers.

| Value | Address | Divisor applied to the float |
| --- | --- | --- |
| Voltage L1 / L2 / L3 | `0x2006` / `0x2008` / `0x200A` | 10 -> V |
| Current L1 / L2 / L3 | `0x200C` / `0x200E` / `0x2010` | 1000 -> A |
| Total active power (`grid_power_w`) | `0x2012` | 10 -> W |
| Power L1 / L2 / L3 | `0x2014` / `0x2016` / `0x2018` | 10 -> W |
| Power factor | `0x202C` | 1000 |

The DDSU666 publishes only phase 1. Positive total power is import from the grid; negative is export. The reader flags import above +5 W and export below -5 W.

### Energy counters

Two unsigned 32-bit values at `0x2048` (import) and `0x204A` (export), high word first, scaled by 0.01 to kWh. This layout was observed on field devices and may differ on other firmware.

### Word order

The meters seen in the field publish the low 16-bit word of each float first, opposite to some manuals. `METER_WORD_ORDER=low` (default) selects that; use `high` for the other order.

### Finding the meter

With the meter slave ID unset, the reader probes `CHINT_CANDIDATES` (default `2,3,4,11,22,101`), skipping the DTU's own ID. It accepts the first address reporting a voltage between 100 and 280 V.
