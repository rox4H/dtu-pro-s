from hoymiles_dtu_reader.devices.meters.common import ChintMeter


class Ddsu666(ChintMeter):
    """CHINT / Hoymiles DDSU666 single-phase meter.

    Typically installed as the grid meter. It uses phase 1 of the same
    0x2000 block as the three-phase DTSU666. The Modbus address is the
    Addr shown on the meter, not the DTU slave id and not 101.
    """

    def __init__(self, slave_id, candidates, low_word_first: bool, **timing):
        super().__init__(
            type_name="ddsu666",
            serial_label="CHINT_DDSU666",
            phases=(1,),
            slave_id=slave_id,
            candidates=candidates,
            low_word_first=low_word_first,
            **timing,
        )
