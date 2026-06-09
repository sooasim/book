"""stdlib-only 래스터 PNG 표지 테스트."""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from ebook_polisher.cover import cover_png, write_cover_png

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _iter_chunks(data: bytes):
    """PNG 바이트열을 (type, data) 청크로 순회한다."""
    pos = len(PNG_SIG)
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        cdata = data[pos + 8 : pos + 8 + length]
        yield ctype, cdata
        pos += 8 + length + 4  # length + type + data + crc


class CoverPngTest(unittest.TestCase):
    def test_signature(self):
        data = cover_png("Hello")
        self.assertTrue(data.startswith(PNG_SIG))

    def test_contains_chunks(self):
        data = cover_png("Hello")
        self.assertIn(b"IHDR", data)
        self.assertIn(b"IDAT", data)
        self.assertIn(b"IEND", data)

    def test_deterministic_same_args(self):
        self.assertEqual(cover_png("My Title", "Me"), cover_png("My Title", "Me"))

    def test_different_titles_differ(self):
        self.assertNotEqual(cover_png("Title A"), cover_png("Title B"))

    def test_ihdr_dimensions(self):
        w, h = 321, 654
        data = cover_png("Dim", width=w, height=h)
        # IHDR 데이터는 시그니처(8) + 길이(4) + 타입(4) = 16 바이트 뒤에서 시작.
        (pw,) = struct.unpack(">I", data[16:20])
        (ph,) = struct.unpack(">I", data[20:24])
        self.assertEqual((pw, ph), (w, h))

    def test_write_creates_png_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "nested" / "cover.png"
            ret = write_cover_png(str(out), "Persisted", "Author")
            self.assertEqual(ret, str(out))
            self.assertTrue(out.exists())
            blob = out.read_bytes()
            self.assertGreater(len(blob), 0)
            self.assertTrue(blob.startswith(PNG_SIG))

    def test_idat_decompresses_to_raw_size(self):
        w, h = 40, 60
        data = cover_png("Raw Size", width=w, height=h)
        idat = b"".join(d for t, d in _iter_chunks(data) if t == b"IDAT")
        raw = zlib.decompress(idat)
        self.assertEqual(len(raw), w * h * 3 + h)


if __name__ == "__main__":
    unittest.main()
