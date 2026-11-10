from hoymiles_dtu_reader.devices.meters.common import ChintMeter


class Dtsu666(ChintMeter):
    """CHINT DTSU666, three-phase meter on the DTU RS485 bus."""

    def __init__(self, slave_id, candidates, low_word_first: bool, **timing):
        super().__init__(
            type_name="dtsu666",
            serial_label="CHINT_DTSU666",
            phases=(1, 2, 3),
            slave_id=slave_id,
            candidates=candidates,
            low_word_first=low_word_first,
            **timing,
        )
