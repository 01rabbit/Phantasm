"""SH-13: Known binary magic signatures for headerless container invariant tests.

Each entry is (name, offset, signature_bytes) where:
  - name: human-readable format name
  - offset: byte offset where the signature appears (usually 0)
  - signature_bytes: bytes object to check

Sources:
  - https://en.wikipedia.org/wiki/List_of_file_signatures
  - Gary Kessler's File Signatures Table
  - libmagic / file(1) magic database
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# (name, byte_offset, signature_bytes)
# ---------------------------------------------------------------------------

KNOWN_SIGNATURES: list[tuple[str, int, bytes]] = [
    # Archives
    ("ZIP", 0, b"PK\x03\x04"),
    ("ZIP (empty)", 0, b"PK\x05\x06"),
    ("ZIP (spanned)", 0, b"PK\x07\x08"),
    ("GZIP", 0, b"\x1f\x8b"),
    ("BZIP2", 0, b"BZh"),
    ("XZ", 0, b"\xfd7zXZ\x00"),
    ("7-Zip", 0, b"7z\xbc\xaf'\x1c"),
    ("RAR4", 0, b"Rar!\x1a\x07\x00"),
    ("RAR5", 0, b"Rar!\x1a\x07\x01\x00"),
    ("TAR (ustar)", 257, b"ustar"),
    # Executables / object files
    ("ELF", 0, b"\x7fELF"),
    ("PE/COFF", 0, b"MZ"),
    ("Mach-O 32LE", 0, b"\xce\xfa\xed\xfe"),
    ("Mach-O 64LE", 0, b"\xcf\xfa\xed\xfe"),
    ("Mach-O 32BE", 0, b"\xfe\xed\xfa\xce"),
    ("Mach-O 64BE", 0, b"\xfe\xed\xfa\xcf"),
    # Images
    ("PNG", 0, b"\x89PNG\r\n\x1a\n"),
    ("JPEG", 0, b"\xff\xd8\xff"),
    ("GIF87a", 0, b"GIF87a"),
    ("GIF89a", 0, b"GIF89a"),
    ("BMP", 0, b"BM"),
    ("TIFF LE", 0, b"II*\x00"),
    ("TIFF BE", 0, b"MM\x00*"),
    ("WEBP", 0, b"RIFF"),
    # Documents / containers
    ("PDF", 0, b"%PDF"),
    ("OLE/Office97", 0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
    ("SQLite3", 0, b"SQLite format 3\x00"),
    ("ISO 9660", 32769, b"CD001"),
    # Crypto / key formats
    ("PEM", 0, b"-----BEGIN"),
    ("OpenSSH key", 0, b"openssh-key-v1\x00"),
    # Audio / video
    ("OGG", 0, b"OggS"),
    ("FLAC", 0, b"fLaC"),
    ("MP3 ID3", 0, b"ID3"),
    ("MP4/MOV (ftyp)", 4, b"ftyp"),
    ("AVI", 0, b"RIFF"),
    ("MKV/EBML", 0, b"\x1aE\xdf\xa3"),
    # Disk images / filesystems
    ("LUKS", 0, b"LUKS\xba\xbe"),
    ("ext2/3/4", 1080, b"\x53\xef"),
    ("VeraCrypt", 0, b"\x52\x41\x49\x44"),  # Not always present, but check
    # Misc
    ("UTF-8 BOM", 0, b"\xef\xbb\xbf"),
    ("UTF-16 LE BOM", 0, b"\xff\xfe"),
    ("UTF-16 BE BOM", 0, b"\xfe\xff"),
    ("XML", 0, b"<?xml"),
    ("HTML", 0, b"<!DOCTYPE"),
    ("JSON array", 0, b"["),
    ("JSON object", 0, b"{"),
]

assert (
    len(KNOWN_SIGNATURES) >= 20
), f"known_magics.py must define at least 20 signatures, got {len(KNOWN_SIGNATURES)}"
