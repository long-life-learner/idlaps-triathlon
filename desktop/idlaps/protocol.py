"""Electron EL-UHF-RC4 framing. Based on protocol v1.1, not packet boundaries."""
from dataclasses import dataclass


def checksum(data: bytes) -> bytes:
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0x8408 if value & 1 else value >> 1
    return value.to_bytes(2, "big")


def command(code: int, data: bytes = b"", address: int = 0xFF) -> bytes:
    if len(data) > 255:
        raise ValueError("Data perintah terlalu panjang")
    frame = bytes([0xCF, address]) + code.to_bytes(2, "big") + bytes([len(data)]) + data
    return frame + checksum(frame)


@dataclass(frozen=True)
class Frame:
    address: int
    command: int
    status: int
    data: bytes


class Parser:
    def __init__(self):
        self.buffer = bytearray()
        self.corrupt = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            try:
                start = self.buffer.index(0xCF)
            except ValueError:
                self.buffer.clear()
                break
            del self.buffer[:start]
            if len(self.buffer) < 5:
                break
            length = self.buffer[4]
            if length < 1:
                del self.buffer[0]
                self.corrupt += 1
                continue
            size = 7 + length
            if len(self.buffer) < size:
                break
            raw = bytes(self.buffer[:size])
            if checksum(raw[:-2]) != raw[-2:]:
                del self.buffer[0]
                self.corrupt += 1
                continue
            del self.buffer[:size]
            frames.append(Frame(raw[1], int.from_bytes(raw[2:4], "big"), raw[5], raw[6:-2]))
        return frames


def tag_from_frame(frame: Frame) -> dict | None:
    if frame.command != 1 or frame.status != 0:
        return None
    p = frame.data
    if len(p) < 5 or not p[4] or len(p) != p[4] + 5:
        raise ValueError("Panjang EPC tidak sesuai respons reader")
    return {"epc": p[5:].hex().upper(), "rssi": int.from_bytes(p[:2], "big", signed=True) / 10,
            "antenna": p[2], "channel": p[3]}
