import base64
import ctypes
import hashlib
from os import urandom

from .pkcs7_padding import padding_size, pkcs7_padding_pad_buffer


def md5bytes(data: bytes) -> str:
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def get_type_data(ptr, index, data_type):
    if data_type == "uint64_t":
        return int.from_bytes(ptr[index * 8 : (index + 1) * 8], "little")
    else:
        raise ValueError("Invalid data type")


def set_type_data(ptr, index, data, data_type):
    if data_type == "uint64_t":
        ptr[index * 8 : (index + 1) * 8] = data.to_bytes(8, "little")
    else:
        raise ValueError("Invalid data type")


def validate(num):
    return num & 0xFFFFFFFFFFFFFFFF


def __ROR__(value: ctypes.c_ulonglong, count: int) -> ctypes.c_ulonglong:
    nbits = ctypes.sizeof(value) * 8
    count %= nbits
    low = ctypes.c_ulonglong(value.value << (nbits - count)).value
    value = ctypes.c_ulonglong(value.value >> count).value
    value = value | low
    return value


def encrypt_ladon_input(hash_table, input_data):
    data0 = int.from_bytes(input_data[:8], byteorder="little")
    data1 = int.from_bytes(input_data[8:], byteorder="little")

    for i in range(0x22):
        hash = int.from_bytes(hash_table[i * 8 : (i + 1) * 8], byteorder="little")
        data1 = validate(hash ^ (data0 + ((data1 >> 8) | (data1 << (64 - 8)))))
        data0 = validate(data1 ^ ((data0 >> 0x3D) | (data0 << (64 - 0x3D))))

    output_data = bytearray(26)
    output_data[:8] = data0.to_bytes(8, byteorder="little")
    output_data[8:] = data1.to_bytes(8, byteorder="little")

    return bytes(output_data)


def encrypt_ladon(md5hex: bytes, data: bytes, size: int):
    hash_table = bytearray(272 + 16)
    hash_table[:32] = md5hex

    temp = []
    for i in range(4):
        temp.append(int.from_bytes(hash_table[i * 8 : (i + 1) * 8], byteorder="little"))

    buffer_b0 = temp[0]
    buffer_b8 = temp[1]
    temp.pop(0)
    temp.pop(0)

    for i in range(0, 0x22):
        x9 = buffer_b0
        x8 = buffer_b8
        x8 = validate(__ROR__(ctypes.c_ulonglong(x8), 8))
        x8 = validate(x8 + x9)
        x8 = validate(x8 ^ i)
        temp.append(x8)
        x8 = validate(x8 ^ __ROR__(ctypes.c_ulonglong(x9), 61))
        set_type_data(hash_table, i + 1, x8, "uint64_t")
        buffer_b0 = x8
        buffer_b8 = temp[0]
        temp.pop(0)

    new_size = padding_size(size)

    input = bytearray(new_size)
    input[:size] = data
    pkcs7_padding_pad_buffer(input, size, new_size, 16)

    output = bytearray(new_size)
    for i in range(new_size // 16):
        output[i * 16 : (i + 1) * 16] = encrypt_ladon_input(
            hash_table, input[i * 16 : (i + 1) * 16]
        )

    return output


def ladon_encrypt(
    timestamp: int,
    license_id: int = 1611921764,
    aid: int = 1233,
    random_bytes: bytes = urandom(4),
) -> str:

    data = f"{timestamp}-{license_id}-{aid}"

    keygen = random_bytes + str(aid).encode()
    md5hex = md5bytes(keygen)

    size = len(data)
    new_size = padding_size(size)

    output = bytearray(new_size + 4)
    output[:4] = random_bytes

    encrypted = encrypt_ladon(md5hex.encode(), data.encode(), size)
    output[4:] = encrypted

    encoded = base64.b64encode(bytes(output)).decode()

    return encoded, {
        "timestamp": timestamp,
        "license_id": license_id,
        "aid": aid,
        "random_bytes": random_bytes.hex(),
        "md5_key": md5hex,
        "encrypted_bytes": encrypted.hex(),
    }


class Ladon:
    @staticmethod
    def encrypt(timestamp: int, license_id: int = 1611921764, aid: int = 1233) -> str:
        return ladon_encrypt(timestamp, license_id, aid)[0]


if __name__ == "__main__":
    key, details = ladon_encrypt(timestamp=1674223203, license_id=1611921764, aid=1233)
    print(f"Ladon Key: {key}")
    print("Details:")
    for k, v in details.items():
        print(f"  {k}: {v}")
