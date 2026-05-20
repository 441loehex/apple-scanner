"""Drive URL parsing tests — no network calls."""

from apple_caliber_scan.storage.drive import extract_drive_file_id


def test_file_d_url():
    url = "https://drive.google.com/file/d/ABC123/view?usp=sharing"
    assert extract_drive_file_id(url) == "ABC123"


def test_open_id_url():
    url = "https://drive.google.com/open?id=ABC123"
    assert extract_drive_file_id(url) == "ABC123"


def test_uc_id_url():
    url = "https://drive.google.com/uc?id=ABC123"
    assert extract_drive_file_id(url) == "ABC123"


def test_non_drive_url_returns_none():
    url = "https://example.com/file.ply"
    assert extract_drive_file_id(url) is None


def test_empty_string_returns_none():
    assert extract_drive_file_id("") is None


def test_complex_file_id():
    file_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
    url = f"https://drive.google.com/file/d/{file_id}/view"
    assert extract_drive_file_id(url) == file_id


def test_file_d_with_trailing_params():
    url = "https://drive.google.com/file/d/XYZ789/view?usp=drive_link&foo=bar"
    assert extract_drive_file_id(url) == "XYZ789"


def test_drive_id_with_dashes_underscores():
    file_id = "1A-b_C2dEFGH"
    url = f"https://drive.google.com/file/d/{file_id}/view"
    assert extract_drive_file_id(url) == file_id
