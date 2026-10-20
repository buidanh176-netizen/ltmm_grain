# ltmm_grain# Mã dòng Grain

Bài tập lớn môn Lý thuyết mật mã: cài đặt và phân tích mã dòng Grain.

## 1. Giới thiệu

Grain là mã dòng hướng phần cứng do Martin Hell, Thomas Johansson và Willi Meier đề xuất năm 2005. Grain v1 nằm trong danh mục eSTREAM (Profile 2: phần cứng). Các phiên bản sau:

| Phiên bản | Khóa | IV | Thanh ghi | Số nhịp khởi tạo | Ghi chú |
|---|---|---|---|---|---|
| Grain v1 | 80 bit | 64 bit | LFSR 80 + NFSR 80 | 160 | eSTREAM |
| Grain-128 | 128 bit | 96 bit | LFSR 128 + NFSR 128 | 256 | |
| Grain-128a | 128 bit | 96 bit | LFSR 128 + NFSR 128 | 256 | Thêm MAC |
| Grain-128AEAD | 128 bit | 96 bit | LFSR 128 + NFSR 128 | — | Chung kết NIST LWC |

## 2. Đặc tả Grain v1

```
        ┌──────────── g(·) ◄──────────┐          ┌──────────── f(·) ◄──────────┐
        │                             │          │                             │
        ▼   ┌───────────────────────┐ │          ▼   ┌───────────────────────┐ │
  ──►(⊕)──► │   NFSR  b0 ... b79    │─┘    ──►(⊕)──► │   LFSR  s0 ... s79    │─┘
     ▲  ▲   └───────────────────────┘           ▲    └───────────────────────┘
     │  └── s0 (từ LFSR)   │ 7 bit + b63         │               │ s3, s25, s46, s64
     │                     ▼                     │               ▼
     │                   ( ⊕ ) ◄──────────── h(x0..x4) ◄─────────┘
     │                     │                     │
     └───── z (chỉ khi khởi tạo) ◄───────────────┘
                           │
                           ▼  z = bit keystream
```


Ký hiệu: `s` là LFSR, `b` là NFSR, `z` là bit keystream, `^` là XOR, ghép chữ là AND.

**LFSR (hàm f):**
```
s[i+80] = s[i+62] ^ s[i+51] ^ s[i+38] ^ s[i+23] ^ s[i+13] ^ s[i]
```

**NFSR (hàm g, có cộng s[i]):**
```
b[i+80] = s[i] ^ b[i+62] ^ b[i+60] ^ b[i+52] ^ b[i+45] ^ b[i+37] ^ b[i+33] ^ b[i+28]
        ^ b[i+21] ^ b[i+14] ^ b[i+9] ^ b[i]
        ^ b[i+63]b[i+60] ^ b[i+37]b[i+33] ^ b[i+15]b[i+9]
        ^ b[i+60]b[i+52]b[i+45] ^ b[i+33]b[i+28]b[i+21]
        ^ b[i+63]b[i+45]b[i+28]b[i+9] ^ b[i+60]b[i+52]b[i+37]b[i+33]
        ^ b[i+63]b[i+60]b[i+21]b[i+15]
        ^ b[i+63]b[i+60]b[i+52]b[i+45]b[i+37] ^ b[i+33]b[i+28]b[i+21]b[i+15]b[i+9]
        ^ b[i+52]b[i+45]b[i+37]b[i+33]b[i+28]b[i+21]
```

**Hàm lọc h**, với `x0..x4 = s[i+3], s[i+25], s[i+46], s[i+64], b[i+63]`:
```
h = x1 ^ x4 ^ x0x3 ^ x2x3 ^ x3x4 ^ x0x1x2 ^ x0x2x3 ^ x0x2x4 ^ x1x2x4 ^ x2x3x4
```

**Bit đầu ra:**
```
z[i] = b[i+1] ^ b[i+2] ^ b[i+4] ^ b[i+10] ^ b[i+31] ^ b[i+43] ^ b[i+56] ^ h
```

**Khởi tạo:**
1. `b[0..79] = key`, `s[0..63] = IV`, `s[64..79] = 1`.
2. Chạy 160 nhịp, không xuất keystream. Mỗi nhịp tính `z` rồi XOR `z` vào đầu vào của **cả** LFSR và NFSR.
3. Sau đó mỗi nhịp xuất một bit `z`.

> ⚠️ **Thứ tự bit:** Grain v1 đọc bit **LSB-first** trong mỗi byte (bit thấp nhất của byte 0 là bit đầu tiên). Keystream cũng ghép thành byte theo LSB-first.

## 3. Đặc tả Grain-128

```
s[i+128] = s[i] ^ s[i+7] ^ s[i+38] ^ s[i+70] ^ s[i+81] ^ s[i+96]

b[i+128] = s[i] ^ b[i] ^ b[i+26] ^ b[i+56] ^ b[i+91] ^ b[i+96]
         ^ b[i+3]b[i+67] ^ b[i+11]b[i+13] ^ b[i+17]b[i+18] ^ b[i+27]b[i+59]
         ^ b[i+40]b[i+48] ^ b[i+61]b[i+65] ^ b[i+68]b[i+84]

h = b[i+12]s[i+8] ^ s[i+13]s[i+20] ^ b[i+95]s[i+42] ^ s[i+60]s[i+79] ^ b[i+12]b[i+95]s[i+95]

z[i] = b[i+2] ^ b[i+15] ^ b[i+36] ^ b[i+45] ^ b[i+64] ^ b[i+73] ^ b[i+89] ^ h ^ s[i+93]
```

Khởi tạo: `b = key` (128 bit), `s[0..95] = IV`, `s[96..127] = 1`, chạy 256 nhịp có XOR `z` ngược vào cả hai thanh ghi.

> ⚠️ **Thứ tự bit:** Grain-128 dùng **MSB-first** (ngược với Grain v1).

## 4. Test vector

| Thuật toán | Key (hex) | IV (hex) | Keystream (hex) |
|---|---|---|---|
| Grain v1 | `00000000000000000000` | `0000000000000000` | `dee931cf1662a72f77d0` |
| Grain v1 | `0123456789abcdef1234` | `0123456789abcdef` | `7f362bd3f7abae203664` |
| Grain-128 | `00000000000000000000000000000000` | `000000000000000000000000` | `0fd9deefeb6fad437bf43fce35849cfe` |
| Grain-128 | `0123456789abcdef123456789abcdef0` | `0123456789abcdef12345678` | `db032aff3788498b57cb894fffb6bb96` |

## 5. Cấu trúc repo

| File | Nội dung |
|---|---|
| `grain.py` | Cài đặt Grain v1 (`GrainV1`) và Grain-128 (`Grain128`) |
| `test_grain.py` | 31 test: test vector, đổi byte/bit, hàm f/g/h, mã hóa/giải mã, tấn công, kiểm tra ngẫu nhiên |
| `attack.py` | Dùng lại key+IV, khuếch tán IV khi giảm số nhịp, cube attack |
| `demo.py` | Menu: mã hóa/giải mã văn bản và file, đo tốc độ, kiểm tra ngẫu nhiên |

## 6. Phân công

| # | Thành viên | Phụ trách |
|---|---|---|
| 1 | _(tên)_ | Trưởng nhóm: `README.md`; `grain.py`: `bytes_to_bits`, `bits_to_bytes` |
| 2 | _(tên)_ | `grain.py`: `lfsr_feedback`, `lfsr128_feedback` |
| 3 | _(tên)_ | `grain.py`: `nfsr_feedback`, `nfsr128_feedback` |
| 4 | _(tên)_ | `grain.py`: `h`, `output_bit`, `output_bit128`, lớp `GrainV1`, `Grain128` |
| 5 | _(tên)_ | `attack.py`: `iv_reuse_attack`, `iv_diffusion`, `cube_attack`, `solve` |
| 6 | _(tên)_ | `test_grain.py` |
| 7 | _(tên)_ | `demo.py`: menu, mã hóa/giải mã, `benchmark`, `frequency_test`, `runs_test` |


## 8. Cách chạy

Cần Python 3.10 trở lên.

```bash
pip install pytest           # để chạy kiểm thử
pip install cryptography     # (tùy chọn) để so sánh tốc độ với AES-CTR, ChaCha20

pytest -v                    # chạy 31 test
python attack.py             # minh họa 3 tấn công (~15 giây)
python demo.py               # mở menu demo
```

Menu của `demo.py`:

```
===== DEMO MÃ DÒNG GRAIN =====
1. Mã hóa văn bản
2. Giải mã văn bản
3. Mã hóa / giải mã file
4. Đo tốc độ
5. Kiểm tra ngẫu nhiên
0. Thoát
```
