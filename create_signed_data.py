import hashlib
from build_pkcs7 import BLCOK_SIZE, sign_digest
from log_exception import UPDATE_LOGGER
from base64 import b64encode

MAX_SIGN_FILE_NUM = 32

def sign_func(sign_file, private_key_file):
    """
    sign one file with private key
    :param sign_file: path of file ready to be signed
    :param private_key_file: private key path, ex. rsa_private_key2048.pem
    :return: base64 code of the signature
    """
    hash_sha256 = hashlib.sha256()
    with open(sign_file, 'rb') as file:
        while chunk := file.read(BLCOK_SIZE):
            hash_sha256.update(chunk)
    signature = sign_digest(hash_sha256.digest(), private_key_file)
    return str(b64encode(signature).decode("ascii"))

#
# hash signed data format:
#
# name: build_tools/updater_binary
# signed-data: xxxxxxx
#
# name: build_tools/updater_binary
# signed-data: xxxxxxx
#
# ....
#
def generate_signed_data(file_lists, sign_func, private_key_file):
    """
    get hash signed data of file lists, hash signed data format:
    name: build_tools/updater_binary
    signed-data: xxxxxxx
    
    name: build_tools/updater_binary
    signed-data: xxxxxxx
    
    ....
    :param file_lists: path list of file ready to be signed, list item contains file_path and name_in_signed_data
    :param sign_func: signature function, ex. sign_func
    :param private_key_file: private key path, ex. rsa_private_key2048.pem
    :return: hash signed data of the file_lists
    """
    if not sign_func:
        UPDATE_LOGGER.print_log("please provide a sign function", log_type=UPDATE_LOGGER.ERROR_LOG)
        return None

    if len(file_lists) > MAX_SIGN_FILE_NUM:
        UPDATE_LOGGER.print_log("signed file can't be more than %d" % MAX_SIGN_FILE_NUM,
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return None
    return "\n".join([ "name: {}\nsigned-data: {}\n".format(
        name, sign_func(file, private_key_file)) for (file, name) in file_lists ])