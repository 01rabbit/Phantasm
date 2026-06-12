import io
import logging
import os
import re
import struct
import zipfile
from typing import Optional

LOG = logging.getLogger(__name__)

METADATA_WARNING = (
    "This file may contain metadata that could reveal source, device, "
    "location, or author information."
)
SCRUB_LIMITATION = (
    "Metadata removal is best-effort and may not remove every embedded "
    "identifier from every file format."
)
DETECTION_LIMITATION = "Metadata detection is best-effort."

_OFFICE_EXTENSIONS = (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm")

# Regex patterns for Office Open XML docProps scrubbing (bytes, case-insensitive)
_CORE_FIELDS_RE = re.compile(
    rb"(<(?:dc:creator|dc:title|dc:subject|dc:description"
    rb"|cp:lastModifiedBy|cp:keywords)[^>]*>)[^<]*(</)",
    re.IGNORECASE,
)
_APP_FIELDS_RE = re.compile(
    rb"(<(?:Application|Company|Manager|Template)[^>]*>)[^<]*(</)",
    re.IGNORECASE,
)

# JPEG APP markers to strip: APP1 (EXIF/XMP), APP13 (IPTC/Photoshop IRB)
_JPEG_STRIP_MARKERS = frozenset([0xE1, 0xED])

# PNG chunk types that carry metadata
_PNG_METADATA_CHUNKS = frozenset([b"tEXt", b"iTXt", b"zTXt", b"eXIf", b"tIME"])
_PNG_CHUNK_DESCRIPTIONS = {
    b"tEXt": "embedded text metadata",
    b"iTXt": "embedded international text metadata",
    b"zTXt": "embedded compressed text metadata",
    b"eXIf": "embedded EXIF metadata",
    b"tIME": "image timestamp",
}


def metadata_risk_report(filename, data):
    name = os.path.basename(filename or "")
    lower_name = name.lower()
    risks: list[str] = []

    if _looks_like_jpeg(data):
        if b"Exif\x00\x00" in data:
            risks.append("embedded image metadata")
        _scan_ascii_tokens(
            data,
            risks,
            {
                b"GPS": "possible location metadata",
                b"Make": "camera maker metadata",
                b"Model": "camera model metadata",
                b"Serial": "device serial-like metadata",
            },
        )

    if lower_name.endswith(".pdf") or data.startswith(b"%PDF"):
        _scan_ascii_tokens(
            data,
            risks,
            {
                b"/Author": "document author metadata",
                b"/Creator": "creator application metadata",
                b"/Producer": "creator application metadata",
                b"/Title": "document title metadata",
                b"/Subject": "document subject metadata",
            },
        )

    if _looks_like_png(data):
        risks.extend(_png_risks(data))

    if _looks_like_zip(data):
        risks.extend(_office_zip_risks(data))

    if _looks_like_text(data):
        text = data[:65536].decode("utf-8", errors="ignore")
        if re.search(r"(/Users/|/home/|[A-Za-z]:\\Users\\)", text):
            risks.append("local path leakage")
        if re.search(r"(?i)\b(author|creator|modified by|last saved by)\b", text):
            risks.append("author or modification metadata")
        if name:
            risks.append("original filename may reveal context")

    unique_risks = sorted(set(risks))
    return {
        "risk": _risk_level(unique_risks),
        "warning": METADATA_WARNING if unique_risks else "",
        "findings": unique_risks,
        "scrub_supported": _scrub_supported(lower_name, data),
        "limitation": DETECTION_LIMITATION,
    }


def scrub_metadata(filename, data):
    lower_name = os.path.basename(filename or "").lower()

    if _looks_like_jpeg(data):
        result = _scrub_jpeg(data)
        if result is not None:
            return {
                "success": True,
                "filename": "metadata_reduced_payload.bin",
                "data": result,
                "message": "Best-effort metadata removal completed.",
                "limitation": SCRUB_LIMITATION,
            }

    if _looks_like_png(data):
        result = _scrub_png(data)
        if result is not None:
            return {
                "success": True,
                "filename": "metadata_reduced_payload.bin",
                "data": result,
                "message": "Best-effort metadata removal completed.",
                "limitation": SCRUB_LIMITATION,
            }

    if _looks_like_zip(data) and lower_name.endswith(_OFFICE_EXTENSIONS):
        result = _scrub_office_zip(data)
        if result is not None:
            return {
                "success": True,
                "filename": "metadata_reduced_payload.bin",
                "data": result,
                "message": "Best-effort metadata removal completed.",
                "limitation": SCRUB_LIMITATION,
            }

    if _looks_like_text(data) and lower_name.endswith((".txt", ".md", ".csv", ".log")):
        return _scrub_text(data)

    return {
        "success": False,
        "filename": "",
        "data": b"",
        "message": "Metadata removal is not supported for this file type.",
        "limitation": SCRUB_LIMITATION,
    }


def _looks_like_jpeg(data):
    return data.startswith(b"\xff\xd8")


def _looks_like_zip(data):
    return data.startswith(b"PK\x03\x04")


def _looks_like_png(data):
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _looks_like_text(data):
    if not data:
        return True
    sample = data[:4096]
    if b"\x00" in sample:
        return False
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _scan_ascii_tokens(data, risks, token_map):
    sample = data[:262144]
    for token, description in token_map.items():
        if token in sample:
            risks.append(description)


def _png_risks(data):
    risks: list[str] = []
    pos = 8  # skip PNG signature
    limit = min(len(data), 262144)
    while pos + 8 <= limit:
        try:
            chunk_len = struct.unpack(">I", data[pos : pos + 4])[0]
            chunk_type = data[pos + 4 : pos + 8]
        except struct.error:
            break
        desc = _PNG_CHUNK_DESCRIPTIONS.get(chunk_type)
        if desc and desc not in risks:
            risks.append(desc)
        pos += 12 + chunk_len
        if chunk_type == b"IEND":
            break
    return risks


def _office_zip_risks(data):
    risks: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            for info_name in ("docProps/core.xml", "docProps/app.xml"):
                if info_name in names:
                    xml = archive.read(info_name)[:262144]
                    _scan_ascii_tokens(
                        xml,
                        risks,
                        {
                            b"creator": "document author metadata",
                            b"lastModifiedBy": "modification history metadata",
                            b"title": "document title metadata",
                            b"subject": "document subject metadata",
                            b"Application": "creator application metadata",
                        },
                    )
            if any(name.startswith("docProps/thumbnail") for name in names):
                risks.append("embedded thumbnail")
    except zipfile.BadZipFile:
        return risks
    return risks


def _scrub_jpeg(data: bytes) -> Optional[bytes]:
    """Strip APP1 (EXIF/XMP) and APP13 (IPTC) markers. Returns None on parse error."""
    try:
        out = bytearray(b"\xff\xd8")
        pos = 2
        n = len(data)
        saw_terminal_marker = False
        while pos + 3 < n:
            if data[pos] != 0xFF:
                return None
            marker = data[pos + 1]
            if marker == 0xDA:  # SOS: copy everything from here to end verbatim
                out += data[pos:]
                saw_terminal_marker = True
                break
            if marker == 0xD9:  # EOI
                out += b"\xff\xd9"
                saw_terminal_marker = True
                break
            if 0xD0 <= marker <= 0xD7:  # RST0–RST7: standalone, no length field
                out += bytes([0xFF, marker])
                pos += 2
                continue
            if pos + 4 > n:
                return None
            seg_len = struct.unpack(">H", data[pos + 2 : pos + 4])[0]
            if seg_len < 2:
                return None
            seg_end = pos + 2 + seg_len
            if seg_end > n:
                return None
            if marker not in _JPEG_STRIP_MARKERS:
                out += data[pos:seg_end]
            pos = seg_end
        if not saw_terminal_marker:
            return None
        return bytes(out)
    except (struct.error, ValueError) as exc:
        LOG.debug("jpeg metadata reduction parse failed: %s", exc)
        return None


def _scrub_png(data: bytes) -> Optional[bytes]:
    """Strip metadata chunks (tEXt, iTXt, zTXt, eXIf, tIME). Returns None on parse error."""
    _PNG_SIG = b"\x89PNG\r\n\x1a\n"
    try:
        out = bytearray(_PNG_SIG)
        pos = 8
        n = len(data)
        while pos + 8 <= n:
            chunk_len = struct.unpack(">I", data[pos : pos + 4])[0]
            chunk_type = data[pos + 4 : pos + 8]
            chunk_end = pos + 12 + chunk_len
            if chunk_end > n:
                break
            if chunk_type not in _PNG_METADATA_CHUNKS:
                out += data[pos:chunk_end]
            pos = chunk_end
            if chunk_type == b"IEND":
                break
        return bytes(out)
    except (struct.error, ValueError) as exc:
        LOG.debug("png metadata reduction parse failed: %s", exc)
        return None


def _scrub_office_zip(data: bytes) -> Optional[bytes]:
    """Blank sensitive author/title fields in docProps/core.xml and docProps/app.xml."""
    try:
        buf = io.BytesIO()
        with (
            zipfile.ZipFile(io.BytesIO(data)) as zin,
            zipfile.ZipFile(buf, "w") as zout,
        ):
            for info in zin.infolist():
                content = zin.read(info.filename)
                if info.filename == "docProps/core.xml":
                    content = _CORE_FIELDS_RE.sub(rb"\1\2", content)
                elif info.filename == "docProps/app.xml":
                    content = _APP_FIELDS_RE.sub(rb"\1\2", content)
                zout.writestr(info.filename, content)
        return buf.getvalue()
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        LOG.debug("office metadata reduction parse failed: %s", exc)
        return None


def _scrub_text(data: bytes) -> dict:
    text = data.decode("utf-8", errors="ignore")
    scrubbed = re.sub(
        r"(/Users/|/home/|[A-Za-z]:\\Users\\)[^\s]+", "[local-path]", text
    )
    scrubbed = re.sub(
        r"(?im)^(author|creator|modified by|last saved by)\s*[:=].*$",
        r"\1: [removed]",
        scrubbed,
    )
    return {
        "success": True,
        "filename": "metadata_reduced_payload.bin",
        "data": scrubbed.encode("utf-8"),
        "message": "Best-effort metadata removal completed.",
        "limitation": SCRUB_LIMITATION,
    }


def _scrub_supported(lower_name, data):
    if _looks_like_jpeg(data):
        return True
    if _looks_like_png(data):
        return True
    if _looks_like_zip(data) and lower_name.endswith(_OFFICE_EXTENSIONS):
        return True
    return _looks_like_text(data) and lower_name.endswith(
        (".txt", ".md", ".csv", ".log")
    )


def _risk_level(risks):
    if not risks:
        return "low"
    if len(risks) >= 3:
        return "high"
    return "medium"
