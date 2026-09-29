#!/usr/bin/env python3
"""Reconstruct the exact supplied LuneryaCrates JAR from the published build.
Fail CLOSED if any other byte differs. Operates only on the staging branch.
"""
import base64
import hashlib
import io
import pathlib
import struct
import sys
import zipfile
import zlib

EXPECTED = "9ab07e5a53c6d7d5657d54ddb1aec724f5da13c50d8d7ff0b17cdb3ac9fb1ba2"
EXPECTED_SIZE = 2666215
TARGET = "assets/luneryacrates/lang/fr_fr.json"
HEADER = bytes.fromhex(
    "504b03041400000808000000410097b32d951d0100007204000024000000"
    "6173736574732f6c756e657279616372617465732f6c616e672f66725f66722e6a736f6e"
)
DATA = base64.b64decode(
    "hZPBTsMwDEDvk/YPUa9D07QLEje0SVzQTrATUmVab0RLk5EmExPig/Yd+zGaBAFe3ay3On1+ju1+"
    "jkeiewrpsHmwxu+nymu0R6gsOGyLu+7sMUXEIoVufpBXZaod/XwKrbNYxpeILsxmY1HUL342m9/"
    "eh9NfPihZfIfHBKvzSSwTCgTl1AdQxvbV6xDOORNHnJThZE460H3ZUwjnZIkjMsqwTdVbLGus3v"
    "xgZ58taOmbbG//shD/QAaukBoboyW8e27EXqzOJ9AuV8O/BKSGRObn26LcavS27MIguS1bmQ+wV"
    "7rQy0LruMzALppx3P27VTMuu90RpL2/gAZ1e+XbQefkqjTinHmSn7c8SGbLlyGcHXPk6G8cQli"
    "MR1/f"
)

def reconstruct(src: str, dst: str) -> None:
    original = pathlib.Path(src).read_bytes()
    with zipfile.ZipFile(io.BytesIO(original)) as z:
        items = z.infolist()
        print("OLD_NAMES_SHA", hashlib.sha256("\\n".join(x.filename for x in items).encode()).hexdigest())
        print("OLD_SORTED_NAMES_SHA", hashlib.sha256("\\n".join(sorted(x.filename for x in items)).encode()).hexdigest())
        print("OLD_NAMES_COMPRESSED", base64.b64encode(zlib.compress("\\n".join(x.filename for x in items).encode(),9)).decode())
        old_meta = b"".join(struct.pack(">III", x.CRC, x.compress_size, x.file_size) for x in items)
        print("OLD_METADATA_B64", base64.b64encode(zlib.compress(old_meta, 9)).decode())
        fr = z.getinfo(TARGET)
        central_start = z.start_dir
        n, x = struct.unpack_from("<HH", original, fr.header_offset + 26)
        data_start = fr.header_offset + 30 + n + x
        if fr.flag_bits & 8:
            raise RuntimeError("Unexpected ZIP data descriptor")
        if len(DATA) != struct.unpack_from("<I", HEADER, 18)[0]:
            raise RuntimeError("New compressed data length invalid")

        delta = len(HEADER) + len(DATA) - (
            data_start + fr.compress_size - fr.header_offset
        )
        new_local = bytearray(
            original[:fr.header_offset] + HEADER + DATA +
            original[data_start + fr.compress_size:central_start]
        )
        new_central = bytearray(original[central_start:])
        p = 0
        found = False
        while (p + 46 <= len(new_central) and
               new_central[p:p+4] == b"PK\x01\x02"):
            name_len, extra_len, comment_len = struct.unpack_from(
                "<HHH", new_central, p + 28
            )
            name = new_central[p+46:p+46+name_len].decode("utf-8")
            offset = struct.unpack_from("<I", new_central, p + 42)[0]
            if name == TARGET:
                if offset != fr.header_offset:
                    raise RuntimeError("Unexpected translation offset")
                struct.pack_into(
                    "<III", new_central, p + 16, 0x952db397, len(DATA), 1138
                )
                found = True
            elif offset > fr.header_offset:
                struct.pack_into("<I", new_central, p + 42, offset + delta)
            p += 46 + name_len + extra_len + comment_len

        if not found:
            raise RuntimeError("Translation absent from ZIP central directory")
        eocd = new_central.find(b"PK\x05\x06", p)
        if eocd < 0:
            raise RuntimeError("Missing ZIP end marker")
        previous_central_offset = struct.unpack_from(
            "<I", new_central, eocd + 16
        )[0]
        if previous_central_offset != central_start:
            raise RuntimeError("Unexpected ZIP central directory position")
        struct.pack_into(
            "<I", new_central, eocd + 16, previous_central_offset + delta
        )

        result = bytes(new_local) + bytes(new_central)
        actual = hashlib.sha256(result).hexdigest()
        print(
            f"Published bytes={len(original)} delta={delta} "
            f"result bytes={len(result)} sha256={actual}"
        )
        if len(result) != EXPECTED_SIZE or actual != EXPECTED:
            raise RuntimeError(
                "The reconstruction does NOT match the exact user-uploaded JAR. "
                "Nothing has been published."
            )
        with zipfile.ZipFile(io.BytesIO(result)) as final:
            translation = final.read(TARGET).decode("utf-8")
            if "Coffre Noxarium" not in translation or "Clé Néante" not in translation:
                raise RuntimeError("Expected corrected translations are absent")
        target_path = pathlib.Path(dst)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(result)
        print("EXACT USER-UPLOADED JAR VERIFIED")

if __name__ == "__main__":
    reconstruct(sys.argv[1], sys.argv[2])
