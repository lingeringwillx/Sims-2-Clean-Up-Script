import io
import struct

class Struct:
    _endians = {'big': '>', 'little': '<'}
    _float_formats = {2: 'e', 4: 'f', 8: 'd'}
    
    def __init__(self, endian='little', encoding='utf-8', errors='ignore'):
        self.endian = endian
        self.encoding = encoding
        self.errors = errors
        
    def _get_endian(self, endian):
        if endian is None:
            return self.endian
        else:
            return endian
            
    def unpack_bool(self, b):
        if isinstance(b, int):
            return b != 0
        elif len(b) == 1:
            return b != b'\x00'
        else:
            raise ValueError('expected int or bytes object of length 1')
            
    def pack_bool(self, boolean):
        if boolean:
            return b'\x01'
        else:
            return b'\x00'
            
    def unpack_bits(self, b):
        if isinstance(b, int):
            number = b
        elif len(b) == 1:
            number = self.unpack_int(b)
        else:
            raise ValueError('expected int or bytes object of length 1')
            
        return [number >> i & 1 for i in range(8)]
        
    def pack_bits(self, bits):
        return self.pack_int(sum(bits[i] << i for i in range(8)), 1)
        
    def unpack_int(self, b, endian=None, signed=False):
        return int.from_bytes(b, self._get_endian(endian), signed=signed)
        
    def pack_int(self, number, numbytes, endian=None, signed=False):
        return number.to_bytes(numbytes, self._get_endian(endian), signed=signed)
        
    def _get_format(self, numbytes, endian=None):
        if numbytes not in self._float_formats:
            raise ValueError("float size '{}' not supported".format(numbytes))
            
        if endian not in self._endians:
            raise ValueError("endian '{}' is not recognized".format(endian))
            
        return self._endians[endian] + self._float_formats[numbytes]
        
    def unpack_float(self, b, numbytes, endian=None):
        return struct.unpack(self._get_format(numbytes, self._get_endian(endian)), b)[0]
        
    def pack_float(self, number, numbytes, endian=None):
        return struct.pack(self._get_format(numbytes, self._get_endian(endian)), number)
        
    def unpack_str(self, b):
        return b.decode(self.encoding, errors=self.errors)
        
    def pack_str(self, string):
        return string.encode(self.encoding, errors=self.errors)
        
    def _get_cstr_len(self, b, start=0):
        end = b.find(b'\x00', start)
        
        if end == -1:
            raise ValueError('null termination not found')
            
        return end - start + 1
        
    def unpack_cstr(self, b, start=0):
        length = self._get_cstr_len(b, start)
        string = self.unpack_str(b[start:(start + length - 1)])
        return string, length
        
    def pack_cstr(self, string):
        return self.pack_str(string) + b'\x00'
        
    def _get_pstr_len(self, b, numbytes, endian=None, start=0):
        return numbytes + self.unpack_int(b[start:(start + numbytes)], endian)
        
    def unpack_pstr(self, b, numbytes, endian=None, start=0):
        length = self._get_pstr_len(b, numbytes, endian, start)
        string = self.unpack_str(b[(start + numbytes):(start + length)])
        return string, length
        
    def pack_pstr(self, string, numbytes, endian=None):
        b = self.pack_str(string)
        return self.pack_int(len(b), numbytes, endian) + b
        
    def _get_7bint_len(self, b, start=0):
        i = 0
        while b[start + i] > 127:
            i += 1
            
        return i + 1
        
    def unpack_7bint(self, b, start=0):
        number = 0
        i = 0
        
        byte = b[start]
        while byte > 127:
            number += (byte & 0b01111111) << (7 * i)
            i += 1
            
            byte = b[start + i]
            
        number += byte << (7 * i)
        length = i + 1
        
        return number, length
        
    def pack_7bint(self, number):
        b = b''
        
        while number > 127:
            b += self.pack_int(number & 0b01111111 | 0b10000000, 1) 
            number >>= 7
            
        b += self.pack_int(number, 1)
        return b
        
class StructIO(io.BytesIO):
    def __init__(self, b=b'', endian='little', encoding='utf-8', errors='ignore'):
        super().__init__(b)
        self._struct = Struct(endian, encoding, errors)
        
    @property
    def buffer(self):
        return self.getvalue()
        
    @property
    def endian(self):
        return self._struct.endian
        
    @endian.setter
    def endian(self, value):
        self._struct.endian = value
        
    @property
    def encoding(self):
        return self._struct.encoding
        
    @encoding.setter
    def encoding(self, value):
        self._struct.encoding = value
        
    @property
    def errors(self):
        return self._struct.errors
        
    @errors.setter
    def errors(self, value):
        self._struct.errors = value
        
    def __len__(self):
        return len(self.getvalue())
        
    def __eq__(self, other):
        return self.getvalue() == other.getvalue()
        
    def is_eof(self):
        if self.read(1) == b'':
            return True
        else:
            self.seek(-1, 1)
            return False
            
    def copy(self):
        return StructIO(self.getvalue(), self._struct.endian, self._struct.encoding, self._struct.errors)
        
    def read_all(self):
        self.seek(0)
        return self.getvalue()
        
    def write_all(self, buffer):
        self.seek(0)
        length = self.write(buffer)
        self.truncate()
        self.seek(0)
        return length
        
    def clear(self):
        self.seek(0)
        self.truncate()
        
    def append(self, b):
        current_position = self.tell()
        return self.overwrite(current_position, current_position, b)
        
    def overwrite(self, start, end, b):
        self.seek(end)
        buffer = self.read()
        self.seek(start)
        length = self.write(b)
        self.write(buffer)
        self.truncate()
        self.seek(start + length)
        return length
        
    def delete(self, length):
        start = self.tell()
        object_length = len(self)
        
        if start + length > object_length:
            length = object_length - start
            
        self.overwrite(start, start + length , b'')
        return length
        
    def find(self, bytes_sequence, n=1):
        start = self.tell()
        content = self.getvalue()
        location = content.find(bytes_sequence, start)
        
        for i in range(1, n):
            location = content.find(bytes_sequence, location + 1)
            
            if location == -1:
                break
                
        return location
        
    def index(self, bytes_sequence, n=1):
        location = self.find(bytes_sequence, n)
        
        if location == -1:
            raise ValueError('{} not found'.format(bytes_sequence))
            
        return location
        
    def read_bool(self):
        return self._struct.unpack_bool(self.read(1))
        
    def write_bool(self, boolean):
        return self.write(self._struct.pack_bool(boolean))
        
    def append_bool(self, boolean):
        return self.append(self._struct.pack_bool(boolean))
        
    def read_bits(self):
        return self._struct.unpack_bits(self.read(1))
        
    def write_bits(self, bits):
        return self.write(self._struct.pack_bits(bits))
        
    def append_bits(self, bits):
        return self.append(self._struct.pack_bits(bits))
        
    def read_int(self, numbytes, endian=None, signed=False):
        return self._struct.unpack_int(self.read(numbytes), endian, signed)
        
    def write_int(self, number, numbytes, endian=None, signed=False):
        return self.write(self._struct.pack_int(number, numbytes, endian, signed))
        
    def append_int(self, number, numbytes, endian=None, signed=False):
        return self.append(self._struct.pack_int(number, numbytes, endian, signed))
        
    def read_float(self, numbytes, endian=None):
        return self._struct.unpack_float(self.read(numbytes), numbytes, endian)
        
    def write_float(self, number, numbytes, endian=None):
        return self.write(self._struct.pack_float(number, numbytes, endian))
        
    def append_float(self, number, numbytes, endian=None):
        return self.append(self._struct.pack_float(number, numbytes, endian))
        
    def read_str(self, length):
        return self._struct.unpack_str(self.read(length))
        
    def write_str(self, string):
        return self.write(self._struct.pack_str(string))
        
    def append_str(self, string):
        return self.append(self._struct.pack_str(string))
        
    def overwrite_str(self, string, length):
        start = self.tell()
        return self.overwrite(start, start + length, self._struct.pack_str(string))
        
    def _get_cstr_len(self):
        return self._struct._get_cstr_len(self.getvalue(), start=self.tell())
        
    def read_cstr(self):
        value, length = self._struct.unpack_cstr(self.getvalue(), start=self.tell())
        self.seek(length, 1)
        return value
        
    def write_cstr(self, string):
        return self.write(self._struct.pack_cstr(string))
        
    def append_cstr(self, string):
        return self.append(self._struct.pack_cstr(string))
        
    def overwrite_cstr(self, string):
        start = self.tell()
        return self.overwrite(start, start + self._get_cstr_len(), self._struct.pack_cstr(string))
        
    def skip_cstr(self):
        return self.seek(self._get_cstr_len(), 1)
        
    def delete_cstr(self):
        return self.delete(self._get_cstr_len())
        
    def _get_pstr_len(self, numbytes, endian=None):
        return self._struct._get_pstr_len(self.getvalue(), numbytes, endian, start=self.tell())
        
    def read_pstr(self, numbytes, endian=None):
        value, length = self._struct.unpack_pstr(self.getvalue(), numbytes, endian, start=self.tell())
        self.seek(length, 1)
        return value
        
    def write_pstr(self, string, numbytes, endian=None):
        return self.write(self._struct.pack_pstr(string, numbytes, endian))
        
    def append_pstr(self, string, numbytes, endian=None):
        return self.append(self._struct.pack_pstr(string, numbytes, endian))
        
    def overwrite_pstr(self, string, numbytes, endian=None):
        start = self.tell()
        return self.overwrite(start, start + self._get_pstr_len(numbytes, endian), self._struct.pack_pstr(string, numbytes, endian))
        
    def skip_pstr(self, numbytes, endian=None):
        return self.seek(self._get_pstr_len(numbytes, endian), 1)
        
    def delete_pstr(self, numbytes, endian=None):
        return self.delete(self._get_pstr_len(numbytes, endian))
        
    def _get_7bint_len(self):
        return self._struct._get_7bint_len(self.getvalue(), start=self.tell())
        
    def read_7bint(self):
        value, length = self._struct.unpack_7bint(self.getvalue(), start=self.tell())
        self.seek(length, 1)
        return value
        
    def write_7bint(self, number):
        return self.write(self._struct.pack_7bint(number))
        
    def append_7bint(self, number):
        return self.append(self._struct.pack_7bint(number))
        
    def overwrite_7bint(self, number):
        start = self.tell()
        return self.overwrite(start, start + self._get_7bint_len(), self._struct.pack_7bint(number))
        
    def skip_7bint(self):
        return self.seek(self._get_7bint_len(), 1)
        
    def delete_7bint(self):
        return self.delete(self._get_7bint_len())