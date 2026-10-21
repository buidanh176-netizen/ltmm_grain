"""
test_grain.py

Chạy: pytest -v
"""

import os

import pytest

import attack
import demo
import grain


# ============ Test vector chính thức: (khóa, IV, keystream) ============

VECTORS_V1 = [
    ("00000000000000000000", "0000000000000000", "dee931cf1662a72f77d0"),
    ("0123456789abcdef1234", "0123456789abcdef", "7f362bd3f7abae203664"),
]

VECTORS_128 = [
    ("00000000000000000000000000000000", "000000000000000000000000",
     "0fd9deefeb6fad437bf43fce35849cfe"),
    ("0123456789abcdef123456789abcdef0", "0123456789abcdef12345678",
     "db032aff3788498b57cb894fffb6bb96"),
]


@pytest.mark.parametrize("key, iv, expected", VECTORS_V1)
def test_grain_v1_vector(key, iv, expected):
    cipher = grain.GrainV1(bytes.fromhex(key), bytes.fromhex(iv))
    assert cipher.keystream(len(expected) // 2).hex() == expected


@pytest.mark.parametrize("key, iv, expected", VECTORS_128)
def test_grain128_vector(key, iv, expected):
    cipher = grain.Grain128(bytes.fromhex(key), bytes.fromhex(iv))
    assert cipher.keystream(len(expected) // 2).hex() == expected


# ============ Đổi byte <-> bit ============

def test_bytes_to_bits():
    assert grain.bytes_to_bits(b"\x01") == [1, 0, 0, 0, 0, 0, 0, 0]
    assert grain.bytes_to_bits(b"\x01", lsb_first=False) == [0, 0, 0, 0, 0, 0, 0, 1]


def test_bits_to_bytes_reverses_bytes_to_bits():
    data = os.urandom(32)
    for lsb_first in [True, False]:
        bits = grain.bytes_to_bits(data, lsb_first)
        assert grain.bits_to_bytes(bits, lsb_first) == data


# ============ Hàm f, g, h ============

def bits_at(*positions, n=80):
    """Danh sách n bit, bằng 1 tại các vị trí cho trước."""
    return [1 if i in positions else 0 for i in range(n)]


def test_lfsr_feedback():
    for tap in [0, 13, 23, 38, 51, 62]:
        assert grain.lfsr_feedback(bits_at(tap)) == 1
    assert grain.lfsr_feedback(bits_at(1)) == 0    # 1 không phải tap


def test_nfsr_feedback():
    assert grain.nfsr_feedback(bits_at(), s0=1) == 1      # chỉ có s0
    assert grain.nfsr_feedback(bits_at(62), s0=0) == 1    # số hạng tuyến tính b62
    # b63 = b60 = 1: các số hạng có mặt là b60 và b63*b60  ->  1 ^ 1 = 0
    assert grain.nfsr_feedback(bits_at(63, 60), s0=0) == 0


def test_h_examples():
    assert grain.h(0, 0, 0, 0, 0) == 0
    assert grain.h(0, 1, 0, 0, 0) == 1    # x1
    assert grain.h(1, 0, 0, 1, 0) == 1    # x0x3
    assert grain.h(1, 1, 1, 1, 1) == 0


def test_h_is_balanced():
    """h cho ra bit 1 với đúng một nửa (16/32) số đầu vào."""
    ones = 0
    for v in range(32):
        x = [(v >> i) & 1 for i in range(5)]
        ones += grain.h(*x)
    assert ones == 16


    # ============ Mã hóa / giải mã ============

@pytest.mark.parametrize("cls", [grain.GrainV1, grain.Grain128])
@pytest.mark.parametrize("data", [b"", b"a", b"Xin chao Grain", os.urandom(1000)])
def test_decrypt_gives_back_plaintext(cls, data):
    key, iv = os.urandom(cls.KEY_BYTES), os.urandom(cls.IV_BYTES)
    ciphertext = cls(key, iv).encrypt(data)
    assert len(ciphertext) == len(data)
    assert cls(key, iv).decrypt(ciphertext) == data


def test_different_iv_gives_different_keystream():
    key = os.urandom(10)
    ks1 = grain.GrainV1(key, bytes(8)).keystream(16)
    ks2 = grain.GrainV1(key, b"\x01" + bytes(7)).keystream(16)
    assert ks1 != ks2


def test_keystream_continues_between_calls():
    key, iv = os.urandom(10), os.urandom(8)
    c = grain.GrainV1(key, iv)
    assert c.keystream(4) + c.keystream(4) == grain.GrainV1(key, iv).keystream(8)


@pytest.mark.parametrize("cls, key_len, iv_len", [
    (grain.GrainV1, 9, 8), (grain.GrainV1, 10, 7),
    (grain.Grain128, 10, 12), (grain.Grain128, 16, 8),
])
def test_wrong_key_or_iv_length(cls, key_len, iv_len):
    with pytest.raises(ValueError):
        cls(bytes(key_len), bytes(iv_len))

# ============ attack.py ============

def test_iv_reuse_attack():
    p2, recovered = attack.iv_reuse_attack()
    assert recovered == p2


def test_iv_diffusion():
    assert attack.iv_diffusion(0, trials=50) < 0.3             # khởi tạo 0 nhịp: yếu
    assert 0.4 < attack.iv_diffusion(160, trials=50) < 0.6     # đủ 160 nhịp: ~50%


def test_solve():
    # k0 ^ k1 = 1  và  k1 = 1   =>   k0 = 0, k1 = 1
    pivots = attack.solve([({0, 1}, 1), ({1}, 1)])
    assert pivots == {0: ({0}, 0), 1: ({1}, 1)}


def test_cube_attack_equations_are_correct(monkeypatch):
    # Chạy bản nhỏ cho nhanh
    monkeypatch.setattr(attack, "CUBE_CLOCKS", 16)
    monkeypatch.setattr(attack, "CUBE_SIZE", 1)
    monkeypatch.setattr(attack, "NUM_CUBES", 20)
    r = attack.cube_attack()
    assert r["independent"] > 0
    assert r["correct"] == r["independent"]


# ============ demo.py ============

def test_frequency_test():
    assert demo.frequency_test([0, 1] * 500) > 0.99    # cân bằng hoàn hảo
    assert demo.frequency_test([1] * 1000) < 0.01      # toàn bit 1


def test_runs_test():
    assert demo.runs_test([0, 1] * 500) < 0.01             # đổi bit liên tục
    assert demo.runs_test([0] * 500 + [1] * 500) < 0.01    # 2 đoạn dài


def test_keystream_looks_random():
    bits = grain.bytes_to_bits(grain.GrainV1(os.urandom(10), os.urandom(8)).keystream(2000))
    assert demo.frequency_test(bits) >= 0.001
    assert demo.runs_test(bits) >= 0.001
