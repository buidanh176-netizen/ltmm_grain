
"""
attack.py - Minh họa 3 tấn công lên Grain v1 (người số 5).

Chạy: python attack.py   (khoảng 15 giây)
"""


import itertools 
import os 
import random
import sys 

import grain 

# ============ 1. Dùng lại khóa + IV ============
#
# C1 = P1 ^ K  và  C2 = P2 ^ K  (cùng keystream K)
# => C1 ^ C2 = P1 ^ P2. Biết P1 thì tính được P2 = C1 ^ C2 ^ P1, không cần khóa.

def xor(a,b):
    return bytes(x^y for x, y in zip(a,b))  

def iv_reuse_attack():
    key, iv = os.urandom(10), os.urandom(8)
    p1 = b"Chuyen khoan 1.000.000 VND den tai khoan A"   # kẻ tấn công biết tin này
    p2 = b"Mat khau dang nhap moi la: Grain_2026!!!!!"   # tin bí mật
    c1 = grain.GrainV1(key, iv).encrypt(p1)
    c2 = grain.GrainV1(key, iv).encrypt(p2)

    recovered = xor(xor(c1, c2), p1)
    return p2, recovered


# ============ 2. Giảm số nhịp khởi tạo ============
#
# Lật 1 bit IV rồi đếm xem bao nhiêu % bit keystream bị đổi.
# Mã tốt: khoảng 50%. Khởi tạo quá ngắn: thấp hơn nhiều -> phân biệt được với ngẫu nhiên.

def count_ones(data):
    return sum(bin(byte).count("1") for byte in data)


def flip_bit(data, i):
    """Đảo bit thứ i của data."""
    result = bytearray(data)
    result[i // 8] ^= 1 << (i % 8)
    return bytes(result)


def iv_diffusion(init_clocks, trials=200):
    changed = 0
    for _ in range(trials):
        key = os.urandom(10)
        iv1 = os.urandom(8)
        iv2 = flip_bit(iv1, random.randrange(64))
        ks1 = grain.GrainV1(key, iv1, init_clocks).keystream(8)
        ks2 = grain.GrainV1(key, iv2, init_clocks).keystream(8)
        changed += count_ones(xor(ks1, ks2))
    return changed / (trials * 64)

#3.CubeAttack
# Mỗi bit keystream là một đa thức theo bit khóa k và bit IV v.
# Chọn vài bit IV (gọi là "cube"), cho chúng chạy qua mọi giá trị 0/1, các bit IV khác = 0,
# rồi XOR tất cả bit keystream thu được. Kết quả chỉ còn phụ thuộc vào khóa ("superpoly").
# Nếu superpoly có dạng  c ^ k_a ^ k_b ^ ...  (tuyến tính) thì ta có 1 phương trình về khóa.
#
#   Bước 1 (offline): dùng khóa tự chọn để tìm các phương trình như vậy.
#   Bước 2 (online) : với khóa bí mật, chỉ cần chọn IV và xem keystream -> tính vế phải.
#   Bước 3          : giải hệ phương trình -> biết được một phần khóa.

CUBE_CLOCKS =32 #số nhịp khởi tạo của grain  rút gọn 
CUBE_SIZE = 2 # số bit IV cần xét 
NUM_CUBES = 200 # số cube thử 
OUT_BITS = 32 # dùng 32 bit keystream đầu tiên -> mỗi cube cho 32 superpoly
CHECKS = 32 # số khóa ngâu nhiên để kiểm tra superpoly tuyến tính 

def cube_sum(cube, key_bits):
    """XOR keystream (OUT_BITS bit đầu) trên mọi giá trị của các bit IV trong cube."""
    key = grain.bits_to_bytes(key_bits)
    total = [0] * OUT_BITS
    for values in itertools.product([0, 1], repeat=len(cube)):
        iv_bits = [0] * 64
        for pos, v in zip(cube, values):
            iv_bits[pos] = v
        cipher = grain.GrainV1(key, grain.bits_to_bytes(iv_bits), CUBE_CLOCKS)
        for t in range(OUT_BITS):
            total[t] ^= cipher.next_bit()
    return total


def find_equations():
    """Bước 1. Trả về danh sách (cube, t, các bit khóa, hằng số)."""
    zero_key = [0] * 80
    equations = []
    found = set()
    for _ in range(NUM_CUBES):
        cube = sorted(random.sample(range(64), CUBE_SIZE))
        const = cube_sum(cube, zero_key)

        # Nếu tuyến tính thì: k_j có mặt trong phương trình <=> superpoly(e_j) != superpoly(0)
        with_bit = [cube_sum(cube, [int(i == j) for i in range(80)]) for j in range(80)]
        variables = [{j for j in range(80) if with_bit[j][t] != const[t]} for t in range(OUT_BITS)]

        # Kiểm tra với nhiều khóa ngẫu nhiên: superpoly phải đúng bằng  const ^ XOR(k_j)
        ok = [True] * OUT_BITS
        for _ in range(CHECKS):
            key = [random.randrange(2) for _ in range(80)]
            real = cube_sum(cube, key)
            for t in range(OUT_BITS):
                predicted = const[t] ^ (sum(key[j] for j in variables[t]) % 2)
                if real[t] != predicted:
                    ok[t] = False

        for t in range(OUT_BITS):
            eq = frozenset(variables[t])
            if ok[t] and eq and eq not in found:
                found.add(eq)
                equations.append((cube, t, eq, const[t]))
    return equations


def solve(equations):
    """Khử Gauss trên GF(2). Mỗi phương trình là (tập bit khóa, vế phải).

    Trả về {bit: (tập bit khóa, vế phải)}, mỗi phương trình còn lại có 1 bit "đại diện" riêng.
    """
    pivots = {}
    for variables, rhs in equations:
        variables = set(variables)
        # Loại các bit đại diện đã có ra khỏi phương trình mới
        for p, (p_vars, p_rhs) in pivots.items():
            if p in variables:
                variables ^= p_vars
                rhs ^= p_rhs
        if not variables:
            continue   # phương trình thừa (suy ra được từ các phương trình trước)
        p = min(variables)
        # Loại bit p ra khỏi các phương trình cũ
        for q, (q_vars, q_rhs) in pivots.items():
            if p in q_vars:
                pivots[q] = (q_vars ^ variables, q_rhs ^ rhs)
        pivots[p] = (variables, rhs)
    return pivots

def cube_attack():
    equations = find_equations()

    # Bước 2: khóa bí mật. Kẻ tấn công chỉ chọn IV và quan sát keystream (trong cube_sum).
    secret_key = os.urandom(10)
    secret_bits = grain.bytes_to_bits(secret_key)
    sums = {}
    system = []
    for cube, t, variables, const in equations:
        if tuple(cube) not in sums:
            sums[tuple(cube)] = cube_sum(cube, secret_bits)
        system.append((variables, sums[tuple(cube)][t] ^ const))

    # Bước 3
    pivots = solve(system)
    known_bits = {p: rhs for p, (variables, rhs) in pivots.items() if variables == {p}}

    # Đối chiếu với khóa thật (chỉ để kiểm chứng)
    correct = sum(sum(secret_bits[j] for j in variables) % 2 == rhs
                  for variables, rhs in pivots.values())

    return {
        "equations": len(equations),
        "independent": len(pivots),
        "correct": correct,
        "known_bits": known_bits,
        "secret": secret_key,
    }


# ============ Chạy tất cả ============

def main():
    sys.stdout.reconfigure(encoding="utf-8")   # để console Windows in được tiếng Việt
    random.seed(1)

    print("=== 1. Dùng lại khóa + IV ===")
    p2, recovered = iv_reuse_attack()
    print("Tin bí mật     :", p2.decode())
    print("Tin khôi phục  :", recovered.decode())
    print("Thành công     :", recovered == p2)
    print()

    print("=== 2. Lật 1 bit IV: bao nhiêu % bit keystream bị đổi? (lý tưởng 50%) ===")
    for clocks in [0, 16, 32, 48, 64, 96, 160]:
        print(f"{clocks:4} nhịp khởi tạo: {iv_diffusion(clocks):6.1%}")
    print()

    print(f"=== 3. Cube attack lên Grain v1 rút gọn còn {CUBE_CLOCKS} nhịp ===")
    print("Đang tính (khoảng 15 giây)...")
    r = cube_attack()
    bits = ", ".join(f"k{j}={v}" for j, v in sorted(r["known_bits"].items()))
    print("Số phương trình tìm được :", r["equations"], f"({r['independent']} phương trình độc lập)")
    print("Đúng với khóa thật       :", f"{r['correct']}/{r['independent']}")
    print("Khóa bí mật              :", r["secret"].hex())
    print("Bit khóa biết chắc chắn  :", bits or "(không có)")
    print("Không gian vét cạn       :", f"2^80 -> 2^{80 - r['independent']}")


if __name__ == "__main__":
    main()