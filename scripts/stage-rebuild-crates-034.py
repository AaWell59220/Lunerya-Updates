#!/usr/bin/env python3
"""Rebuild the user's EXACT supplied JAR from published ZIP data. Fail closed."""
import base64
import hashlib
import io
import pathlib
import struct
import sys
import zipfile

EXPECTED = "9ab07e5a53c6d7d5657d54ddb1aec724f5da13c50d8d7ff0b17cdb3ac9fb1ba2"
BASE = "assets/luneryacrates/lang/fr_fr.json"
DATA = base64.b64decode(
 "hZPBTsMwDEDvk/YPUa9D07QLEje0SVzQTrATUmVab0RLk5EmExPig/Yd+zGaBAFe3ay3On1+ju1+"
 "jkeiewrpsHmwxu+nymu0R6gsOGyLu+7sMUXEIoVufpBXZaod/XwKrbNYxpeILsxmY1HUL342m9/"
 "eh9NfPihZfIfHBKvzSSwTCgTl1AdQxvbV6xDOORNHnJThZE460H3ZUwjnZIkjMsqwTdVbLGus3v"
 "xgZ58taOmbbG//shD/QAaukBoboyW8e27EXqzOJ9AuV8O/BKSGRObn26LcavS27MIguS1bmQ+wV"
 "7rQy0LruMzALppx3P27VTMuu90RpL2/gAZ1e+XbQefkqjTinHmSn7c8SGbLlyGcHXPk6G8cQli"
 "MR1/f"
)
HEAD = {
 BASE: bytes.fromhex(
  "504b03041400000808000000410097b32d951d0100007204000024000000"
  "6173736574732f6c756e657279616372617465732f6c616e672f66725f66722e6a736f6e"
 ),
 BASE + ".backup": bytes.fromhex(
  "504b03041400000808000000410097b32d951d010000720400002b000000"
  "6173736574732f6c756e657279616372617465732f6c616e672f66725f66722e6a736f6e2e6261636b7570"
 ),
}

def build(source, destination):
    original = pathlib.Path(source).read_bytes()
    with zipfile.ZipFile(io.BytesIO(original)) as zip_file:
        entries = sorted(
            (zip_file.getinfo(name) for name in HEAD),
            key=lambda item: item.header_offset
        )
        parts = []
        pos = 0
        deltas = []
        for entry in entries:
            start = entry.header_offset
            name_len, extra_len = struct.unpack_from("<HH", original, start + 26)
            data_start = start + 30 + name_len + extra_len
            data_end = data_start + entry.compress_size
            if entry.flag_bits & 8 or original[start:start + 4] != b"PK\x03\x04":
                raise RuntimeError("Unsupported source ZIP layout")
            parts.extend([original[pos:start], HEAD[entry.filename], DATA])
            change = len(HEAD[entry.filename]) + len(DATA) - (data_end - start)
            deltas.append((start, change))
            pos = data_end

        parts.append(original[pos:zip_file.start_dir])
        local = b"".join(parts)
        central = bytearray(original[zip_file.start_dir:])
        index = 0
        found = set()
        while (index + 46 <= len(central) and
               central[index:index + 4] == b"PK\x01\x02"):
            name_len, extra_len, comment_len = struct.unpack_from(
                "<HHH", central, index + 28
            )
            name = central[index + 46:index + 46 + name_len].decode("utf-8")
            old_offset = struct.unpack_from("<I", central, index + 42)[0]
            new_offset = old_offset + sum(
                amount for location, amount in deltas if old_offset > location
            )
            struct.pack_into("<I", central, index + 42, new_offset)
            if name in HEAD:
                struct.pack_into(
                    "<III", central, index + 16, 0x952db397, len(DATA), 1138
                )
                found.add(name)
            index += 46 + name_len + extra_len + comment_len

        if found != set(HEAD):
            raise RuntimeError("Unexpected changed entry count")
        eocd = central.find(b"PK\x05\x06", index)
        if eocd < 0:
            raise RuntimeError("End-of-central-directory missing")
        old_central_offset = struct.unpack_from("<I", central, eocd + 16)[0]
        if old_central_offset != zip_file.start_dir:
            raise RuntimeError("Unexpected source central-directory location")
        struct.pack_into(
            "<I", central, eocd + 16,
            old_central_offset + sum(amount for _, amount in deltas)
        )

        result = local + central
        actual = hashlib.sha256(result).hexdigest()
        print(f"Previous size={len(original)}, changes={deltas}, "
              f"result size={len(result)}, result SHA-256={actual}")
        if len(result) != 2666215 or actual != EXPECTED:
            raise RuntimeError(
                "Result differs from the EXACT user-supplied JAR. "
                "No binary has been published."
            )
        with zipfile.ZipFile(io.BytesIO(result)) as check:
            translation = check.read(BASE).decode("utf-8")
            if "Coffre Noxarium" not in translation or "Clé Néante" not in translation:
                raise RuntimeError("Corrected French translations not present")
        target = pathlib.Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result)
        print("VERIFIED: exact byte-for-byte user JAR reconstructed")

if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
