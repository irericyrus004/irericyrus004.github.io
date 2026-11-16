"""
SCHOOL LOCK - only teachers registered by phone number can open a school's timetables on their phones.

The timetable that goes on the website is locked with the school's own key (AES-256-CTR + HMAC-SHA-256 over
zlib-compressed JSON), so the file on the website cannot be read by anybody else. The key is kept by the
PREPFIX service (Cloudflare Worker) and given only to a phone whose number is on the school's list - one phone
per number. The phone keeps the key and opens the timetables (also offline).

Pure Python (no extra packages). The phone opens it with the browser's own WebCrypto.
    new_key() -> str                     a school key (base64)
    lock(key, obj) -> dict               {"alg", "iv", "ct", "mac"}
    unlock(key, box) -> obj
    normalize_phone("0712 345 678") -> "254712345678"  (None if it is not a phone number)
    phone_hash(code, phone) -> str       what the service keeps instead of the number
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import zlib

ALG = "A256CTR-HS256-Z1"

# ---------------------------------------------------------------------------------------------------- AES-256
def _sbox():
    """The AES S-box, worked out (multiplicative inverse in GF(2^8) + affine map)."""
    s, p, q = [0] * 256, 1, 1
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)          # p * 3
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09                                                     # q / 3
        x = q ^ ((q << 1 | q >> 7) & 0xFF) ^ ((q << 2 | q >> 6) & 0xFF) ^ ((q << 3 | q >> 5) & 0xFF) ^ ((q << 4 | q >> 4) & 0xFF)
        s[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    s[0] = 0x63
    return bytes(s)


_S = _sbox()
_RC = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def _xt(a):
    a <<= 1
    return (a ^ 0x11B) & 0xFF if a & 0x100 else a


# T-tables for a quick pure-Python encryption round
_T0 = []
for _x in range(256):
    _s = _S[_x]
    _s2 = _xt(_s)
    _s3 = _s2 ^ _s
    _T0.append((_s2 << 24) | (_s << 16) | (_s << 8) | _s3)
_T1 = [((t >> 8) | (t << 24)) & 0xFFFFFFFF for t in _T0]
_T2 = [((t >> 16) | (t << 16)) & 0xFFFFFFFF for t in _T0]
_T3 = [((t >> 24) | (t << 8)) & 0xFFFFFFFF for t in _T0]


def _expand(key: bytes):
    nk = len(key) // 4
    w = [int.from_bytes(key[4 * i:4 * i + 4], "big") for i in range(nk)]
    nr = nk + 6
    for i in range(nk, 4 * (nr + 1)):
        t = w[i - 1]
        if i % nk == 0:
            t = ((t << 8) | (t >> 24)) & 0xFFFFFFFF
            t = (_S[t >> 24] << 24) | (_S[(t >> 16) & 255] << 16) | (_S[(t >> 8) & 255] << 8) | _S[t & 255]
            t ^= _RC[i // nk - 1] << 24
        elif nk > 6 and i % nk == 4:
            t = (_S[t >> 24] << 24) | (_S[(t >> 16) & 255] << 16) | (_S[(t >> 8) & 255] << 8) | _S[t & 255]
        w.append(w[i - nk] ^ t)
    return w, nr


def _block(w, nr, b: bytes) -> bytes:
    s0, s1, s2, s3 = (int.from_bytes(b[i:i + 4], "big") ^ w[i // 4] for i in (0, 4, 8, 12))
    k = 4
    for _ in range(nr - 1):
        t0 = _T0[s0 >> 24] ^ _T1[(s1 >> 16) & 255] ^ _T2[(s2 >> 8) & 255] ^ _T3[s3 & 255] ^ w[k]
        t1 = _T0[s1 >> 24] ^ _T1[(s2 >> 16) & 255] ^ _T2[(s3 >> 8) & 255] ^ _T3[s0 & 255] ^ w[k + 1]
        t2 = _T0[s2 >> 24] ^ _T1[(s3 >> 16) & 255] ^ _T2[(s0 >> 8) & 255] ^ _T3[s1 & 255] ^ w[k + 2]
        t3 = _T0[s3 >> 24] ^ _T1[(s0 >> 16) & 255] ^ _T2[(s1 >> 8) & 255] ^ _T3[s2 & 255] ^ w[k + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
        k += 4
    out = b""
    for a, bb, c, d, kk in ((s0, s1, s2, s3, w[k]), (s1, s2, s3, s0, w[k + 1]), (s2, s3, s0, s1, w[k + 2]),
                            (s3, s0, s1, s2, w[k + 3])):
        v = (_S[a >> 24] << 24) | (_S[(bb >> 16) & 255] << 16) | (_S[(c >> 8) & 255] << 8) | _S[d & 255]
        out += (v ^ kk).to_bytes(4, "big")
    return out


def _ctr(key: bytes, iv: bytes, data: bytes) -> bytes:
    w, nr = _expand(key)
    ctr = int.from_bytes(iv, "big")
    out = bytearray(len(data))
    for i in range(0, len(data), 16):
        ks = _block(w, nr, (ctr & ((1 << 128) - 1)).to_bytes(16, "big"))
        ctr += 1
        chunk = data[i:i + 16]
        out[i:i + len(chunk)] = bytes(x ^ y for x, y in zip(chunk, ks))
    return bytes(out)


# ---------------------------------------------------------------------------------------------------- lock
def _keys(key: str):
    k = base64.b64decode(key)
    return k, hashlib.sha256(k + b"|mac").digest()


def new_key() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode()


def lock(key: str, obj) -> dict:
    ek, mk = _keys(key)
    iv = secrets.token_bytes(16)
    ct = _ctr(ek, iv, zlib.compress(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    mac = hmac.new(mk, iv + ct, hashlib.sha256).digest()
    b = lambda x: base64.b64encode(x).decode()
    return {"alg": ALG, "iv": b(iv), "ct": b(ct), "mac": b(mac)}


def unlock(key: str, box: dict):
    ek, mk = _keys(key)
    iv, ct, mac = (base64.b64decode(box[k]) for k in ("iv", "ct", "mac"))
    if not hmac.compare_digest(hmac.new(mk, iv + ct, hashlib.sha256).digest(), mac):
        raise ValueError("wrong key")
    return json.loads(zlib.decompress(_ctr(ek, iv, ct)).decode("utf-8"))


# ---------------------------------------------------------------------------------------------------- phones
def normalize_phone(s) -> str | None:
    """Kenyan numbers in any usual form -> 2547XXXXXXXX / 2541XXXXXXXX. Other countries: + and the digits."""
    d = re.sub(r"\D", "", str(s or ""))
    if str(s or "").strip().startswith("+") and len(d) >= 9:
        return d if not d.startswith("2540") else "254" + d[4:]
    if d.startswith("2540"):
        d = "254" + d[4:]
    if len(d) == 10 and d[0] == "0" and d[1] in "17":
        return "254" + d[1:]
    if len(d) == 9 and d[0] in "17":
        return "254" + d
    if len(d) == 12 and d.startswith("254") and d[3] in "17":
        return d
    return None


def show_phone(norm: str) -> str:
    if norm and norm.startswith("254") and len(norm) == 12:
        return f"0{norm[3:6]} {norm[6:9]} {norm[9:]}"
    return "+" + (norm or "")


def phone_hash(code: str, phone: str) -> str:
    n = normalize_phone(phone) or ""
    return hashlib.sha256(f"prepfix|{code}|{n}".encode()).hexdigest()[:32]


def new_pin() -> str:
    """A 4-digit PIN for the school's PIN sheet (no 0000, 1234 and the like)."""
    while True:
        p = f"{secrets.randbelow(10000):04d}"
        if len(set(p)) > 1 and p not in ("1234", "4321", "0123", "1212", "2580"):
            return p


def pin_hash(code: str, phone: str, pin: str) -> str:
    """What the service keeps instead of the PIN."""
    return hashlib.sha256(f"{code}|{phone_hash(code, phone)}|{pin}".encode()).hexdigest()[:32]
