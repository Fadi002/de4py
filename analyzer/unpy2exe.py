# https://github.com/matiasb/unpy2exe/blob/master/unpy2exe.py

import imp
import logging
import marshal
import ntpath
import os
import struct
import sys
import time

import pefile
import six


IGNORE = [
    # added by py2exe
    '<bootstrap2>.pyc',
    '<install zipextimporter>.pyc',
    '<boot hacks>.pyc',
    'boot_common.py.pyc',
]

def __build_magic(magic):
    """Build Python magic number for pyc header."""
    return struct.pack(b'Hcc', magic, b'\r', b'\n')


PYTHON_MAGIC_WORDS = {
    # version magic numbers (see Python/Lib/importlib/_bootstrap_external.py)
    '1.5': __build_magic(20121),
    '1.6': __build_magic(50428),
    '2.0': __build_magic(50823),
    '2.1': __build_magic(60202),
    '2.2': __build_magic(60717),
    '2.3': __build_magic(62011),
    '2.4': __build_magic(62061),
    '2.5': __build_magic(62131),
    '2.6': __build_magic(62161),
    '2.7': __build_magic(62191),
    '3.0': __build_magic(3000),
    '3.1': __build_magic(3141),
    '3.2': __build_magic(3160),
    '3.3': __build_magic(3190),
    '3.4': __build_magic(3250),
    '3.5': __build_magic(3350),
    '3.6': __build_magic(3360),
    '3.7': __build_magic(3390),
}


def __timestamp():
    """Generate timestamp data for pyc header."""
    today = time.time()
    ret = struct.pack(b'=L', int(today))
    return ret


def __source_size(size):
    """Generate source code size data for pyc header."""
    ret = struct.pack(b'=L', int(size))
    return ret


def __current_magic():
    """Current Python magic number."""
    return imp.get_magic()


def _get_scripts_resource(pe):
    """Return the PYTHONSCRIPT resource entry."""
    res = None
    for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if entry.name and entry.name.string == b"PYTHONSCRIPT":
            res = entry.directory.entries[0].directory.entries[0]
            break
    return res


def _resource_dump(pe, res):
    """Return the dump of the given resource."""
    rva = res.data.struct.OffsetToData
    size = res.data.struct.Size

    dump = pe.get_data(rva, size)
    return dump


def _get_co_from_dump(data):
    """Return the code objects from the dump."""
    # Read py2exe header
    current = struct.calcsize(b'iiii')
    metadata = struct.unpack(b'iiii', data[:current])

    # check py2exe magic number
    # assert(metadata[0] == 0x78563412)
    logging.info("Magic value: %x", metadata[0])
    logging.info("Code bytes length: %d", metadata[3])

    arcname = ''
    while six.indexbytes(data, current) != 0:
        arcname += chr(six.indexbytes(data, current))
        current += 1
    logging.info("Archive name: %s", arcname or '-')

    code_bytes = data[current + 1:]
    # verify code bytes count and metadata info
    # assert(len(code_bytes) == metadata[3])

    code_objects = marshal.loads(code_bytes)
    return code_objects


def check_py2exe_file(pe):
    """Check file is a py2exe executable."""
    py2exe_resource = _get_scripts_resource(pe)

    if py2exe_resource is None:
        logging.info('This is not a py2exe executable.')
        if pe.__data__.find(b'pyi-windows-manifest-filename'):
            logging.info('This seems a pyinstaller executable (unsupported).')

    return bool(py2exe_resource)


def extract_code_objects(pe):
    """Extract Python code objects from a py2exe executable."""
    script_res = _get_scripts_resource(pe)
    dump = _resource_dump(pe, script_res)
    return _get_co_from_dump(dump)


def _generate_pyc_header(python_version, size):
    if python_version is None:
        version = __current_magic()
        version_tuple = sys.version_info
    else:
        version = PYTHON_MAGIC_WORDS.get(python_version[:3], __current_magic())
        version_tuple = tuple(map(int, python_version.split('.')))

    header = version + __timestamp()
    if version_tuple[0] == 3 and version_tuple[1] >= 3:
        # source code size was added to pyc header since Python 3.3
        header += __source_size(size)
    return header


def dump_to_pyc(co, python_version, output_dir):
    """Save given code_object as a .pyc file."""
    # assume Windows path information from the .exe
    pyc_basename = ntpath.basename(co.co_filename)
    pyc_name = pyc_basename + '.pyc'

    if pyc_name not in IGNORE:
        logging.info("Extracting %s", pyc_name)
        pyc_header = _generate_pyc_header(python_version, len(co.co_code))
        destination = os.path.join(output_dir, pyc_name)
        pyc = open(destination, 'wb')
        pyc.write(pyc_header)
        marshaled_code = marshal.dumps(co)
        pyc.write(marshaled_code)
        pyc.close()
    else:
        logging.info("Skipping %s", pyc_name)


def unpy2exe(filename, python_version=None, output_dir=None):
    """Process input params and produce output pyc files."""
    if output_dir is None:
        output_dir = '.'
    elif not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pe = pefile.PE(filename)

    is_py2exe = check_py2exe_file(pe)
    if not is_py2exe:
        raise ValueError('Not a py2exe executable.')

    code_objects = extract_code_objects(pe)
    for co in code_objects:
        dump_to_pyc(co, python_version, output_dir)