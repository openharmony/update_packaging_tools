import binascii
import hashlib
import struct


class ChunkParser:
    def __init__(self):
        self.chunkdata_partition_tlv_type = 0x01  # Example type
        self.chunkdata_cmd_tlv_type = 0x02  # Example type
        self.chunkdata_value_tlv_type = 0x03  # Example type
        self.chunkhash_info_tlv_type = 0x04  # Example type
        
        # Define formats for struct.pack and struct.unpack
        self.chunkdata_partiton_fmt = '<HH'
        self.chunkdata_cmd_fmt = '<HH'
        self.chunkdata_data_fmt = '<HI'
        self.chunkhash_header_fmt = '<3H'
        self.chunkhash_data_fmt = '<HH'
        self.chunksign_value_fmt = '<HI'


    def parse_chunklist(self, package_file, offset):
        print(f'start read chunklist offset:{offset}')
        package_file.seek(offset)  # Start reading from the beginning
        while True:
            # Read partition TLV
            partition_data = package_file.read(struct.calcsize(self.chunkdata_partiton_fmt))
            print(f'partition_data:{partition_data}')
            if not partition_data:
                break  # End of file
            
            partition_type, partition_length = struct.unpack(self.chunkdata_partiton_fmt, partition_data[:4])
            partition_name = package_file.read(partition_length).decode('utf-8')
            print(f"Partition Type: {partition_type}, Partition Name: {partition_name}")
            if(partition_type != 18):
                print(f'stop read chunklist')
                break
            
            # Read command TLV
            cmd_data = package_file.read(struct.calcsize(self.chunkdata_cmd_fmt))
            cmd_type, cmd_length = struct.unpack(self.chunkdata_cmd_fmt, cmd_data[:4])
            cmd_info = package_file.read(cmd_length).decode('utf-8')
            print(f"Command Type: {cmd_type}, Command Info: {cmd_info}")

            # Read data TLV
            data_data = package_file.read(struct.calcsize(self.chunkdata_data_fmt))
            print(f'self.chunkdata_data_fmt :{data_data}')
            data_type, data_length = struct.unpack(self.chunkdata_data_fmt, data_data[:6])
            data_value = package_file.read(data_length)
            print(f"Data Type: {data_type}, Data Length: {data_length}, Data Value: {data_value}")

            # Process the data based on cmd_info (extract patch or new data)
            if 'pkgdiff' in cmd_info:
                with open('new_patch.dat', 'ab') as patch_file:
                    patch_file.write(data_value)
            elif 'new' in cmd_info:
                with open('new_new.dat', 'ab') as new_file:
                    new_file.write(data_value)
            with open('new_transfer.list', 'ab') as list_file:
                list_file.write((cmd_info + '\n').encode())
                
    def parse_hash_info(self, package_file, offset):
        print(f'start read hash_info offset:{offset}')
        package_file.seek(offset)  # Start reading from the beginning
        while True:
            hash_info_data = package_file.read(struct.calcsize(self.chunkhash_header_fmt))
            if not hash_info_data:
                break  # End of file
            
            hash_type, num_images, image_number = struct.unpack(self.chunkhash_header_fmt, hash_info_data)
            print(f"Hash Type: {hash_type}, Number of Images: {num_images}, Image Number: {image_number}")
            if(hash_type != 22):
                print(f'stop read hash_info offset')
                break
                
    def parse_hash_data(self, package_file, offset):
        print(f'start read hash_data offset:{offset}')
        package_file.seek(offset)
        while True:
            partition_data = package_file.read(struct.calcsize(self.chunkdata_partiton_fmt))
            print(f'partition_data:{partition_data}')
            if not partition_data:
                break  # End of file
            
            partition_type, partition_length = struct.unpack(self.chunkdata_partiton_fmt, partition_data[:4])
            if(partition_type != 23):
                print(f'stop read hash_data offset')
                break
            partition_name = package_file.read(partition_length).decode('utf-8')
            print(f"Partition Type: {partition_type}, Partition Name: {partition_name}")
            
            hash_data = package_file.read(struct.calcsize(self.chunkhash_data_fmt))
            print(f'self.chunkdata_data_fmt :{hash_data}')
            data_type, data_length = struct.unpack(self.chunkhash_data_fmt, hash_data[:4])
            data_value = package_file.read(data_length)
            print(f"Data Type: {data_type}, Data Length: {data_length}, Data Value: {data_value}")

            large_data = package_file.read(struct.calcsize('<2HI')) 
            print(f'self.chunkdata_data_fmt :{large_data}')
            large_data_type, large_data_length, large_data_value = struct.unpack('<2HI', large_data[:8])
            print(f"image large Type: {large_data_type}, image large Length: {large_data_length}, image large Value: {large_data_value}")
            
            with open('new_hash.txt', 'ab') as file:
                file.write(data_value)
                
    def parse_full_sign(self, package_file, offset):
        print(f'start read full image sign offset:{offset}')
        package_file.seek(offset)
        while True:
            sign_data = package_file.read(struct.calcsize(self.CHUNK_SIGN_VALUE_FMT))
            print(f'self.chunkdata_data_fmt :{sign_data}')
            data_type, data_length = struct.unpack(self.CHUNK_SIGN_VALUE_FMT, sign_data[:6]) 
            data_value = package_file.read(data_length)
            print(f"Data Type: {data_type}, Data Length: {data_length}, Data Value: {data_value}")
            if(data_type != 26):
                print(f'stop read full image sign')
                break
            with open('new_sign.txt', 'ab') as file:
                hex_data = binascii.hexlify(data_value)
                file.write(hex_data + b'\n')
                
                
    def parse_full_stream(self, package_file, offset):
        print(f'start read full stream offset:{offset}')
        package_file.seek(offset)
        while True:
            partition_name = package_file.read(struct.calcsize(self.chunkdata_partiton_fmt))
            print(f'self.chunkdata_data_fmt :{partition_name}')
            partition_type, partition_length = struct.unpack(self.chunkdata_partiton_fmt, partition_name[:4])
            partiton_value = package_file.read(partition_length)
            print(f"Data Type: {partition_type}, Data Length: {partition_length}, Data Value: {partiton_value}")
            if(partition_type != 18):
                print(f'stop read full image')
                break
            cmd = package_file.read(struct.calcsize(self.chunkdata_partiton_fmt))
            print(f'self.chunkdata_data_fmt :{cmd}')
            cmd_type, cmd_length = struct.unpack(self.chunkdata_partiton_fmt, cmd[:4])
            cmd_value = package_file.read(cmd_length).decode('utf-8')
            print(f"Data Type: {cmd_type}, Data Length: {cmd_length}, Data Value: {cmd_value}")
            with open('new_full.list', 'ab') as file:
                file.write((cmd_value + '\n').encode())
            
            image_data = package_file.read(struct.calcsize(self.chunkdata_data_fmt))
            data_type, data_length = struct.unpack(self.chunkdata_data_fmt, image_data[:6])
            data_value = package_file.read(data_length)
            with open('new_iamge.img', 'ab') as file:
                file.write(data_value)


def get_file_sha256(update_package):
    sha256obj = hashlib.sha256()
    maxbuf = 8192
    with open(update_package, 'rb') as package_file:
        while True:
            buf = package_file.read(maxbuf)
            if not buf:
                break
            sha256obj.update(buf)
    hash_value_hex = sha256obj.hexdigest()
    hash_value = sha256obj.digest()
    return str(hash_value_hex).upper()

           
def calculate_file_hash(file_path):
    hash_sha256 = hashlib.sha256()  # You can change this to sha1(), md5(), etc. if needed
    with open(file_path, 'rb') as f:
        # Read the file in chunks to avoid using too much memory
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest() 
  
          
def read_update_bin(file_path):
    with open(file_path, 'rb') as f:
        return f.read()


def parse_update_bin(data, offsets):
    parsed_data = {}
    for name, (offset, length) in offsets.items():
        parsed_data[name] = data[offset:offset + length]
    return parsed_data


def reconstruct_patch(parsed_data):
    # 假设patch是一个字节串，您可以根据需要进行修改
    patch = b''
    for name in parsed_data:
        patch += parsed_data[name]
    return patch


def verify_patch(original_patch, reconstructed_patch):
    return original_patch == reconstructed_patch


def main():
    chunk_parser = ChunkParser()
    with open('update.bin', 'rb') as package_file:
        # 全量流式旧步骤说明（参数仅供历史参考),参数需要在制作包的打印信息中获取:
        # 步骤1 - parse_full_stream 偏移量 632, 使用chunk_parser.parse_full_stream(package_file, 632)
        # 步骤2 - parse_hash_info 偏移量 1975016790，使用chunk_parser.parse_hash_info(package_file, 1975016790)
        # 步骤3 - parse_hash_data 偏移量 1975016796,使用chunk_parser.parse_hash_data(package_file, 1975016796)
        # 步骤4 - parse_full_sign 偏移量 1975017344,使用chunk_parser.parse_full_sign(package_file, 1975017344)
        chunk_parser.parse_chunklist(package_file, 632)
        chunk_parser.parse_hash_info(package_file, 21590734)
        chunk_parser.parse_hash_data(package_file, 21590740)
        chunk_parser.parse_full_sign(package_file, 21590922)
    

if __name__ == "__main__":
    main()