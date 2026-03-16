"""Tests for low-level document helper utilities."""

import base64

import pypdf  # type: ignore
import pytest

from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)
from app.utils.document.pdf_pages_to_image_data_urls import (
    pdf_pages_to_image_data_urls,
)
from app.utils.document.read_pdf_text_pages import read_pdf_text_pages
from app.utils.document.read_text_file import read_text_file


def test_read_text_file_reads_utf8_and_strips_whitespace(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("  hello world  \n", encoding="utf-8")

    assert read_text_file(str(path)) == "hello world"


def test_read_text_file_falls_back_to_latin_1(tmp_path):
    path = tmp_path / "latin1.txt"
    path.write_bytes("caf\xe9".encode("latin-1"))

    assert read_text_file(str(path)) == "café"


def test_read_text_file_raises_value_error_for_missing_file(tmp_path):
    with pytest.raises(ValueError, match="Error reading file"):
        read_text_file(str(tmp_path / "missing.txt"))


def test_read_pdf_text_pages_returns_one_entry_per_page(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as file:
        writer.write(file)

    assert read_pdf_text_pages(str(path)) == ["", ""]


def test_read_pdf_text_pages_raises_value_error_for_missing_file(tmp_path):
    with pytest.raises(ValueError, match="Error reading PDF file"):
        read_pdf_text_pages(str(tmp_path / "missing.pdf"))


def test_pdf_image_helpers_fail_softly_for_missing_file(tmp_path):
    missing = str(tmp_path / "missing.pdf")

    assert pdf_first_page_to_image_bytes(missing) is None
    assert pdf_pages_to_image_data_urls(missing) == []


class _FakePix:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self, fmt: str) -> bytes:
        assert fmt == "png"
        return self._payload


class _FakePage:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def get_pixmap(self) -> _FakePix:
        return _FakePix(self._payload)


class _FakeDoc:
    def __init__(self, payloads: list[bytes]) -> None:
        self._pages = [_FakePage(payload) for payload in payloads]
        self.closed = False

    def __len__(self) -> int:
        return len(self._pages)

    def __getitem__(self, index: int) -> _FakePage:
        return self._pages[index]

    def __iter__(self):
        return iter(self._pages)

    def close(self) -> None:
        self.closed = True


class _FakeFitz:
    def __init__(self, payloads: list[bytes], *, raises: bool = False) -> None:
        self._payloads = payloads
        self._raises = raises

    def open(self, _path: str) -> _FakeDoc:
        if self._raises:
            raise RuntimeError("boom")
        return _FakeDoc(self._payloads)


def test_pdf_first_page_to_image_bytes_returns_png_bytes_with_injected_fitz():
    payload = b"page-one"

    assert (
        pdf_first_page_to_image_bytes(
            "/tmp/example.pdf",
            fitz_module=_FakeFitz([payload]),
        )
        == payload
    )


def test_pdf_first_page_to_image_bytes_returns_none_for_empty_pdf():
    assert (
        pdf_first_page_to_image_bytes(
            "/tmp/empty.pdf",
            fitz_module=_FakeFitz([]),
        )
        is None
    )


def test_pdf_pages_to_image_data_urls_returns_one_data_url_per_page():
    payloads = [b"page-one", b"page-two"]

    result = pdf_pages_to_image_data_urls(
        "/tmp/example.pdf",
        fitz_module=_FakeFitz(payloads),
    )

    assert result == [
        f"data:image/png;base64,{base64.b64encode(payload).decode('ascii')}"
        for payload in payloads
    ]


def test_pdf_pages_to_image_data_urls_returns_empty_list_on_render_error():
    assert (
        pdf_pages_to_image_data_urls(
            "/tmp/broken.pdf",
            fitz_module=_FakeFitz([], raises=True),
        )
        == []
    )
