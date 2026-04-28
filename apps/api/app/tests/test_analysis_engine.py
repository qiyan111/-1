from pathlib import Path

import pytest

from app.analysis_engine import CsvFileParser, FcsFileParser, get_parser
from app.analysis_engine.exceptions import UnsupportedFileTypeError


def write_csv(tmp_path: Path) -> Path:
    file_path = tmp_path / "sample.csv"
    file_path.write_text(
        "# sample_no: S-001\n"
        "# experiment_no: EXP-001\n"
        "FSC-A,SSC-A,CD45\n"
        "1.0,2.5,10\n"
        "3.0,4.5,20\n",
        encoding="utf-8",
    )
    return file_path


def test_csv_metadata(tmp_path: Path) -> None:
    file_path = write_csv(tmp_path)

    metadata = CsvFileParser().parse_metadata(file_path)
    channels = CsvFileParser().parse_channels(file_path)
    compensation = CsvFileParser().parse_compensation(file_path)

    assert metadata.format == "CSV"
    assert metadata.file_name == "sample.csv"
    assert metadata.row_count == 2
    assert metadata.channel_count == 3
    assert metadata.attributes["comments"]["sample_no"] == "S-001"
    assert [channel.name for channel in channels] == ["FSC-A", "SSC-A", "CD45"]
    assert compensation.channel_names == ["FSC-A", "SSC-A", "CD45"]
    assert compensation.matrix == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def test_csv_events(tmp_path: Path) -> None:
    file_path = write_csv(tmp_path)

    parsed = CsvFileParser().parse(file_path)

    assert parsed.events == [
        [1.0, 2.5, 10.0],
        [3.0, 4.5, 20.0],
    ]
    assert parsed.metadata.row_count == 2
    assert parsed.channels[2].name == "CD45"


def test_unsupported_file_error(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("not supported", encoding="utf-8")

    with pytest.raises(UnsupportedFileTypeError):
        get_parser(file_path)


def test_parser_factory(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    fcs_path = tmp_path / "sample.fcs"

    assert isinstance(get_parser(csv_path), CsvFileParser)
    assert isinstance(get_parser(fcs_path), FcsFileParser)
