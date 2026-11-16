"""
School licences, signed by Cyrus Ireri.

Cyrus's edition holds a private signing key. Each school copy carries a licence (school name, code and the
school's own GitHub account) signed with that key. The matching public key is published on Cyrus's website,
so a school copy checks its licence against Cyrus's website and nobody can change the school's name.

Pure Python (no extra packages): RSA-2048, PKCS#1 v1.5 with SHA-256.
"""
from __future__ import annotations

import hashlib
import json
import secrets

_SMALL_PRIMES = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _is_probable_prime(n: int, rounds: int = 40) -> bool:
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(bits: int) -> int:
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_probable_prime(c):
            return c


def new_key(bits: int = 2048) -> dict:
    e = 65537
    while True:
        p, q = _prime(bits // 2), _prime(bits // 2)
        if p == q:
            continue
        phi = (p - 1) * (q - 1)
        if phi % e == 0:
            continue
        n = p * q
        d = pow(e, -1, phi)
        return {"n": format(n, "x"), "e": e, "d": format(d, "x")}


def public(key: dict) -> dict:
    return {"n": key["n"], "e": key["e"], "alg": "RSA-SHA256", "what": "Ireri Timetables licence key (public)"}


_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def _encode(message: bytes, k: int) -> int:
    t = _DIGEST_INFO + hashlib.sha256(message).digest()
    return int.from_bytes(b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t, "big")


def canonical(lic: dict) -> bytes:
    body = {k: v for k, v in lic.items() if k != "sig"}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign(lic: dict, key: dict) -> dict:
    n, d = int(key["n"], 16), int(key["d"], 16)
    k = (n.bit_length() + 7) // 8
    out = dict(lic)
    out["sig"] = format(pow(_encode(canonical(lic), k), d, n), "x")
    return out


def verify(lic: dict, pub: dict) -> bool:
    try:
        n, e = int(pub["n"], 16), int(pub["e"])
        k = (n.bit_length() + 7) // 8
        return pow(int(lic["sig"], 16), e, n) == _encode(canonical(lic), k)
    except Exception:
        return False
