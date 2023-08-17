from structio import Struct, StructIO
import string as strlib
import ctypes
import os
import sys

"""
Package:
contains Header and Entry

Header:
major_version = int #1
minor_version = int #1
major_user_version = int #0
minor_user_version = int #0
flags = int #unknown
created_date = int #not important
modified_date = int #not important
index_major_version = int #7
index_entry_count = int #number of entries in file
index_location = int #location of file index
index_size = int #length of index
hole_index_entry_count = int #number oh holes in file
hole_index_location = int #location of hole index
hole_index_size = int #length of hole index
index_minor_version = int #index version, between 0 and 2
remainder = 32 bytes #what remains of the header

Entry:
type: int #entry type
group: int #entry group
instance: int #entry instance
resource: int #entry resource, only exists if the index minor version is 2
compressed = bool #indicates whether the entry is compressed or not
name = str #name of entry
"""

if sys.platform != 'win32':
    raise Exception('The dbpf library currently only works in Windows')
    
if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 2):
    raise Exception('The dbpf library requires Python 3.2 or higher')
    
named_types = {0x42434F4E, 0x42484156, 0x4E524546, 0x4F424A44, 0x53545223, 0x54544142, 0x54544173, 0x424D505F, 0x44475250, 0x534C4F54, 0x53505232}
named_rcol_types = {0xFB00791E, 0x4D51F042, 0xE519C933, 0xAC4F8687, 0x7BA3838C, 0xC9C81B9B, 0xC9C81BA3, 0xC9C81BA9, 0xC9C81BAD, 0xED534136, 0xFC6EB1F7, 0x49596978, 0x1C4A276C}
named_cpf_types = {0x2C1FD8A1, 0x0C1FE246, 0xEBCF3E27}
lua_types = {0x9012468A, 0x9012468B}

is_64bit = sys.maxsize > 2 ** 32

if is_64bit:
    clib = ctypes.cdll.LoadLibrary(os.path.join(os.path.dirname(__file__),'dbpf64.dll'))
else:
    clib = ctypes.cdll.LoadLibrary(os.path.join(os.path.dirname(__file__),'dbpf32.dll'))
    
clib.decompress.restype = ctypes.c_bool

class RepeatKeyError(Exception): pass
class CompressionError(Exception): pass
class NotSupportedError(Exception): pass

class ExtendedStruct(Struct):
    def _get_7bstr_len(self, b, start=0):
        str_len, int_len = self.unpack_7bint(b, start)
        return int_len + str_len
        
    def unpack_7bstr(self, b, start=0):
        str_len, int_len = self.unpack_7bint(b, start)
        string = self.unpack_str(b[(start + int_len):(start + int_len + str_len)])
        return string, int_len + str_len
        
    def pack_7bstr(self, string):
        b = self.pack_str(string)
        return self.pack_7bint(len(b)) + b
        
class MemoryIO(StructIO):
    def __init__(self, b=b'', endian='little'):
        super().__init__(b)
        self._struct = ExtendedStruct(endian)
        
    def copy(self):
        return MemoryIO(self.getvalue(), self._struct.endian)
        
    def _get_7bstr_len(self):
        return self._struct._get_7bstr_len(self.getvalue(), start=self.tell())
        
    def read_7bstr(self):
        value, length = self._struct.unpack_7bstr(self.getvalue(), start=self.tell())
        self.seek(length, 1)
        return value
        
    def write_7bstr(self, string):
        return self.write(self._struct.pack_7bstr(string))
        
    def append_7bstr(self, string):
        return self.append(self._struct.pack_7bstr(string))
        
    def overwrite_7bstr(self, string):
        start = self.tell()
        return self.overwrite(start, start + self._get_7bstr_len(), self._struct.pack_7bstr(string))
        
    def skip_7bstr(self):
        return self.seek(self._get_7bstr_len(), 1)
        
    def delete_7bstr(self):
        return self.delete(self._get_7bstr_len())
        
class Header:
    def __init__(self):
        self.major_version = 1
        self.minor_version = 1
        self.major_user_version = 0
        self.minor_user_version = 0
        self.flags = 0
        self.created_date = 0
        self.modified_date = 0
        self.index_major_version = 7
        self.index_entry_count = 0
        self.index_location = 0
        self.index_size = 0
        self.hole_index_entry_count = 0
        self.hole_index_location = 0
        self.hole_index_size = 0
        self.index_minor_version = 2
        self.remainder = b'\x00' * 32
        
    def __str__(self):
        display = 'Header:\n'
        display += 'major version: {}\n'.format(self.major_version)
        display += 'minor version: {}\n'.format(self.minor_version)
        display += 'major user version: {}\n'.format(self.major_user_version)
        display += 'minor user version: {}\n'.format(self.minor_user_version)
        display += 'flags: {}\n'.format(self.flags)
        display += 'created date: {}\n'.format(self.created_date)
        display += 'modified date: {}\n'.format(self.modified_date)
        display += 'index major version: {}\n'.format(self.index_major_version)
        display += 'index entry count: {}\n'.format(self.index_entry_count)
        display += 'index location: {}\n'.format(self.index_location)
        display += 'index size: {}\n'.format(self.index_size)
        display += 'hole index entry count: {}\n'.format(self.hole_index_entry_count)
        display += 'hole index location: {}\n'.format(self.hole_index_location)
        display += 'hole index size: {}\n'.format(self.hole_index_size)
        display += 'index minor version: {}'.format(self.index_minor_version)
        
        return display
        
    def copy(self):
        header_copy = Header()
        for key, value in vars(self).items():
            setattr(header_copy, key, value)
            
        return header_copy
        
class Entry(MemoryIO):
    def __init__(self, type_id, group_id, instance_id, resource_id=None, name='', content=b'', compressed=False):
        super().__init__(content)
        self.type = type_id
        self.group = group_id
        self.instance = instance_id
        
        if resource_id is not None:
            self.resource = resource_id
            
        self.name = name
        self.compressed = compressed
        
    def __contains__(self, key):
        return hasattr(self, key)
        
    def __str__(self):
        if self.name == '':
            name_display = ''
        else:
            name_display = '{}\n'.format(self.name)
            
        if hasattr(self, 'resource'):
            return name_display + 'Type: 0x{:08X}, Group: 0x{:08X}, Instance: 0x{:08X}, Resource: 0x{:08X}'.format(self.type, self.group, self.instance, self.resource)
        else:
            return name_display + 'Type: 0x{:08X}, Group: 0x{:08X}, Instance: 0x{:08X}'.format(self.type, self.group, self.instance)
            
    def copy(self):
        if hasattr(self, 'resource'):
            return Entry(self.type, self.group, self.instance, self.resource, self.name, self.buffer, self.compressed)
        else:
            return Entry(self.type, self.group, self.instance, name=self.name, content=self.buffer, compressed=self.compressed)
            
    #using C++ library from moreawesomethanyou   
    def compress(self):
        if self.compressed or self.type == 0xE86B1EEF:
            return self
            
        else:
            src = self.buffer
            src_len = len(src)
            dst = ctypes.create_string_buffer(src_len)
            
            dst_len = clib.try_compress(src, src_len, dst)
            
            if dst_len > 0:
                self.write_all(dst.raw[:dst_len])
                self.compressed = True
                
                return self
                
    #using C++ library from moreawesomethanyou 
    def decompress(self):
        if self.compressed:
            src = self.buffer
            compressed_size = len(src)
            
            self.seek(6)
            uncompressed_size = self.read_int(3, 'big')
            
            dst = ctypes.create_string_buffer(uncompressed_size)
            success = clib.decompress(src, compressed_size, dst, uncompressed_size, False)
            
            self.seek(0)
            
            if success:
                self.write_all(dst.raw)
                self.compressed = False
                
                return self
                
            else:
                raise CompressionError('Could not decompress the file')
                
        else:
            return self
        
    def read_name(self):
        try:
            if self.type in named_types:
                self.name = partial_decompress(self, 64).read().rstrip(b'x\00').decode('utf-8', errors='ignore')
                
            elif self.type in named_rcol_types:
                file = partial_decompress(self)
                location = file.find(b'cSGResource')
                
                if location != -1:
                    file.seek(location + 19)
                    self.name = file.read_7bstr()
                    
            elif self.type in named_cpf_types:
                file = partial_decompress(self)
                location = file.find(b'\x18\xea\x8b\x0b\x04\x00\x00\x00name')
                
                if location != -1:
                    file.seek(location + 12)
                    self.name = file.read_pstr(4)
                    
            elif self.type in lua_types:
                file = partial_decompress(self)
                file.seek(4)
                self.name = file.read_pstr(4)        
                
            else:
                self.name = ''
                
        except:
            self.name = ''
            
        return self.name
        
    def write_name(self, name):
        was_compressed = self.compressed
        
        if self.type in named_types:
            if self.compressed:
                self.decompress()
                
            if len(name) <= 64:
                self.seek(0)
                self.write_str(name)
                self.write_int(0, 64 - len(name))
                self.seek(0)
                self.name = name
            else:
                raise ValueError("file name '{}' is longer than expected".format(name))
                
        elif self.type in named_rcol_types:
            if self.compressed:
                self.decompress()
                
            location = self.find(b'cSGResource')
            
            if location != -1:
                self.seek(location + 19)
                self.overwrite_7bstr(name)
                self.seek(0)
                self.name = name
                
        elif self.type in named_cpf_types:
            if self.compressed:
                self.decompress()
                
            location = self.find(b'\x18\xea\x8b\x0b\x04\x00\x00\x00name')
            
            if location != -1:
                self.seek(location + 12)
                self.overwrite_pstr(name, 4)
                self.seek(0)
                self.name = name
                
        elif self.type in lua_types:
            if self.compressed:
                self.decompress()
                
            self.seek(4)
            self.overwrite_pstr(name, 4)
            self.seek(0)
            self.name = name
            
        else:
            raise NotSupportedError('naming format 0x{:08X} is not supported'.format(self.type))
            
        if was_compressed:
            self.compress()
            
class Package:
    def __init__(self):
        self.header = Header()
        self.entries = []
        
    def copy(self):
        package_copy = Package()
        package_copy.header = self.header.copy()      
        package_copy.entries = [entry.copy() for entry in self.entries]
        
        return package_copy
        
    def unpack(file_path, decompress=False):
        with open(file_path, 'rb') as fs:
            file = MemoryIO(fs.read())
            
        self = Package()
        
        self.file_name = os.path.basename(file_path)
        
        #read header
        file.seek(4)
        self.header.major_version = file.read_int(4)
        self.header.minor_version = file.read_int(4)
        self.header.major_user_version = file.read_int(4)
        self.header.minor_user_version = file.read_int(4)
        self.header.flags = file.read_int(4)
        self.header.created_date = file.read_int(4)
        self.header.modified_date = file.read_int(4)
        self.header.index_major_version = file.read_int(4)
        self.header.index_entry_count = file.read_int(4)
        self.header.index_location = file.read_int(4)
        self.header.index_size = file.read_int(4)
        self.header.hole_index_entry_count = file.read_int(4)
        self.header.hole_index_location = file.read_int(4)
        self.header.hole_index_size = file.read_int(4)
        self.header.index_minor_version = file.read_int(4)
        self.header.remainder = file.read(32)
        
        #read index
        self.entries = []
        
        file.seek(self.header.index_location)
        for i in range(self.header.index_entry_count):
            #using int.from_bytes and file.read instead of read_int to avoid the function call overhead
            type_id = int.from_bytes(file.read(4), 'little')
            group_id = int.from_bytes(file.read(4), 'little')
            instance_id = int.from_bytes(file.read(4), 'little')
            
            if self.header.index_minor_version == 2:
                resource_id = int.from_bytes(file.read(4), 'little')
            else:
                resource_id = None
                
            location = int.from_bytes(file.read(4), 'little')
            size = int.from_bytes(file.read(4), 'little')
            
            position = file.tell()
            file.seek(location)
            content = file.read(size)
            file.seek(position)
            
            self.entries.append(Entry(type_id, group_id, instance_id, resource_id, content=content))
            
        #make list of index entries
        #the entries list is for checking if the file is compressed later, just for increasing execution speed
        #so that we don't need to spend time converting the CLST entries to integers
        index_entries = []
        
        if self.header.index_minor_version == 2:
            size = 16
        else:
            size = 12
            
        file.seek(self.header.index_location)
        for i in range(self.header.index_entry_count):
            index_entries.append(file.read(size))
            file.seek(8, 1)
            
        #read CLST
        #using a set for speed
        clst_entries = set()
        results = search(self.entries, 0xE86B1EEF, get_first=True)
        
        if len(results) > 0:
            clst = results[0]
            file_size = len(clst)
            
            if self.header.index_minor_version == 2:
                entry_size = 20
                tgi_size = 16
            else:
                entry_size = 16
                tgi_size = 12
            
            clst.seek(0)
            for i in range(file_size // entry_size):
                entry = clst.read(tgi_size)
                
                if entry not in clst_entries:
                    clst_entries.add(entry)
                else:
                    raise RepeatKeyError('Two entries with matching type, group, and instance found')
                    
                clst.seek(4, 1)
                
            clst.seek(0)
            
        #check if compressed
        for index_entry, entry in zip(index_entries, self.entries):
            entry.compressed = False
            
            if index_entry in clst_entries:
                entry.seek(4)
                
                #entries can be in the CLST file even if they're not compressed
                #so a second check for compression would be good
                if entry.read(2) == b'\x10\xfb':
                    entry.compressed = True
                    
                entry.seek(0)
                
        #decompress entries
        if decompress:
            for entry in self.entries:
                try:
                    entry.decompress()
                except CompressionError:
                    pass
                    
        #read file names
        for entry in self.entries:
            try:
                #print(entry)
                entry.read_name()
            except CompressionError:
                pass
                
        return self 
        
    def pack_into(self, file_path, compress=False):
        #compress entries
        if compress:
            compressed_entries = {} #for checking if the a compressed entry with the same TGI already exists
            for i, entry in enumerate(self.entries):
                if 'resource' in entry:
                    tgi = (entry.type, entry.group, entry.instance, entry.resource)
                else:
                    tgi = (entry.type, entry.group, entry.instance)
                    
                if tgi in compressed_entries:
                    i = compressed_entries[tgi]
                    self.entries[i].decompress()
                    
                else:
                    entry.compress()
                    compressed_entries[tgi] = i
                    
        #only check for repeated compressed entries
        else:
            compressed_entries = set()
            for entry in self.entries:
                if entry.compressed:
                    if 'resource' in entry:
                        tgi = (entry.type, entry.group, entry.instance, entry.resource)
                    else:
                        tgi = (entry.type, entry.group, entry.instance)
                        
                    if tgi in compressed_entries:
                        raise RepeatKeyError('Repeat compressed entry found in package')
                    else:
                        compressed_entries.add(tgi)
                        
        #use index minor version 2?
        if self.header.index_minor_version != 2:
            for entry in self.entries:
                if 'resource' in entry:
                    self.header.index_minor_version = 2
                    break
                    
        file = MemoryIO()
        
        #write header
        file.write(b'DBPF')
        file.write_int(self.header.major_version, 4)
        file.write_int(self.header.minor_version, 4)
        file.write_int(self.header.major_user_version, 4)
        file.write_int(self.header.minor_user_version, 4)
        file.write_int(self.header.flags, 4)
        file.write_int(self.header.created_date, 4)
        file.write_int(self.header.modified_date, 4)
        file.write_int(self.header.index_major_version, 4)
        file.write_int(self.header.index_entry_count, 4)
        file.write_int(self.header.index_location, 4)
        file.write_int(self.header.index_size, 4)
        file.write_int(self.header.hole_index_entry_count, 4)
        file.write_int(self.header.hole_index_location, 4)
        file.write_int(self.header.hole_index_size, 4)
        file.write_int(self.header.index_minor_version, 4)
        
        file.write(self.header.remainder)
        
        #make CLST
        results = search(self.entries, 0xE86B1EEF, get_first=True)
        compressed_files = [entry for entry in self.entries if entry.compressed]
        
        if len(results) > 0:
            self.entries.remove(results[0])
            
        if len(compressed_files) > 0:
            clst = Entry(0xE86B1EEF, 0xE86B1EEF, 0x286B1F03)
            
            if self.header.index_minor_version == 2:
                clst.resource = 0x00000000
                
            for compressed_file in compressed_files:
                clst.write_int(compressed_file.type, 4)
                clst.write_int(compressed_file.group, 4)
                clst.write_int(compressed_file.instance, 4)
                
                if self.header.index_minor_version == 2:
                    if 'resource' in compressed_file:
                        clst.write_int(compressed_file.resource, 4)
                    else:
                        clst.write_int(0, 4)
                        
                #uncompressed size is written in big endian?
                compressed_file.seek(6)
                uncompressed_size = compressed_file.read_int(3, 'big')
                clst.write_int(uncompressed_size, 4)
                
            self.entries.append(clst)
            
        #write entries
        for entry in self.entries:
            #get new location to put in the index later
            entry.location = file.tell()
            
            file.write(entry.buffer)
            
            #get new file size to put in the index later
            entry.size = file.tell() - entry.location
            
        #write index
        index_start = file.tell()
        
        for entry in self.entries:
            file.write_int(entry.type, 4)
            file.write_int(entry.group, 4)
            file.write_int(entry.instance, 4)
            
            if self.header.index_minor_version == 2:
                if 'resource' in entry:
                    file.write_int(entry.resource, 4)
                else:
                    file.write_int(0, 4)
                    
            file.write_int(entry.location, 4)
            file.write_int(entry.size, 4)
            
        index_end = file.tell()
        
        file.truncate()
        
        #update header index info, clear holes index info
        file.seek(36)
        file.write_int(len(self.entries), 4) #index entry count
        file.write_int(index_start, 4) #index location
        file.write_int(index_end - index_start, 4) #index size
        file.write_int(0, 12) #hole index entries
        
        with open(file_path, 'wb') as fs:
            fs.write(file.buffer)
            
def partial_decompress(entry, size=-1):
    if entry.compressed:
        src = entry.buffer  
        compressed_size = len(src)
        
        entry.seek(6)
        uncompressed_size = entry.read_int(3, 'big')
        
        if size == -1 or size >= uncompressed_size:
            size = uncompressed_size
            
        dst = ctypes.create_string_buffer(size)
        success = clib.decompress(src, compressed_size, dst, size, True)
        
        entry.seek(0)
        
        if success:
            return MemoryIO(dst.raw)
        else:
            raise CompressionError('Could not decompress the file')
            
    else:
        entry.seek(0)
        buffer = entry.read(size)
        entry.seek(0)
        return MemoryIO(buffer)
        
def search(entries, type_id=-1, group_id=-1, instance_id=-1, resource_id=-1, entry_name='', get_first=False):
    entry_name = entry_name.lower()
    
    results = []
    for entry in entries:
        if type_id != -1 and type_id != entry.type:
            continue
            
        if group_id != -1 and group_id != entry.group:
            continue
            
        if instance_id != -1 and instance_id != entry.instance:
            continue
            
        if resource_id != -1 and resource_id != entry.resource:
            continue
            
        if entry_name != '' and entry_name not in entry.name.lower():
            continue
            
        results.append(entry)
        
        if get_first:
            return results
            
    return results
    
#for faster searching
def build_index(entries):
    index = {}
    index['types'] = {}
    index['groups'] = {}
    index['instances'] = {}
    index['resources'] = {}
    index['names index'] = {}
    index['names list'] = []
    
    for c in strlib.printable:
        index['names index'][c] = set()
        
    for i, entry in enumerate(entries):
        if entry.type not in index['types']:
            index['types'][entry.type] = set()
            
        index['types'][entry.type].add(i)
        
        if entry.group not in index['groups']:
            index['groups'][entry.group] = set()
            
        index['groups'][entry.group].add(i)
            
        if entry.instance not in index['instances']:
            index['instances'][entry.instance] = set()
            
        index['instances'][entry.instance].add(i)
            
        if 'resource' in entry:
            if entry.resource not in index['resources']:
                index['resources'][entry.resource] = set()
                
            index['resources'][entry.resource].add(i)
            
        name = entry.name.lower()
        index['names list'].append(name)
        
        if name != '':
            for char in name:
                index['names index'][char].add(i)
                
    return index
    
#faster search
def index_search(entries, index, type_id=-1, group_id=-1, instance_id=-1, resource_id=-1, entry_name=''):
    results = []
    keys = ['types', 'groups', 'instances', 'resources']
    values = [type_id, group_id, instance_id, resource_id]
    
    for key, value in zip(keys, values):
        if value == -1:
            pass
        elif value in index[key]:
            results.append(index[key][value])
        else:
            return []
        
    if len(results) > 0:
        results = set.intersection(*results)
        
    if entry_name != '':
        entry_name = entry_name.lower()
        names_set = (index['names index'][char] for char in entry_name)
        
        if len(results) > 0:
            results = results.intersection(*names_set)
        else:
            results = set.intersection(*names_set)
            
        if len(entry_name) > 1:
            results = [i for i in results if entry_name in index['names list'][i]]
            
    return [entries[i] for i in results]
