import re, lzma, base64, lzma, codecs, marshal, io, dis, sys
def get_bytes(text):
    return re.search(r"b'(.+)'", text).group(1)
def decompressing(payload):
    return lzma.decompress(codecs.escape_decode(get_bytes(payload.decode()))[0]).decode()
def BlankOBF(file_path):
    return disasm(decompressing(lzma.decompress(base64.b64decode(get_bytes(open(file_path,'r',encoding='utf-8').read())))))
def disasm(text):
    matches = re.findall(r'\b(_{4,9})\b="(.*?)"', text, re.DOTALL)
    variable_content = {name: content for name, content in matches}
    variable_list = []
    for name, content in variable_content.items():
        variable_list.append((name, content))
    disassembly_output = io.StringIO()
    original_stdout = sys.stdout
    try:
        sys.stdout = disassembly_output
        marshal_code=(base64.b64decode(codecs.decode(variable_list[0][1], 'rot13')+variable_list[2][1]+variable_list[3][1][::-1]+variable_list[1][1]))
        try:
            dis.dis(marshal.loads(marshal_code))
        except:
            print("failed to dis marshal code so heres the marshal code only:\n")
            print(marshal_code)
    finally:
        sys.stdout = original_stdout
    disassembly_text = disassembly_output.getvalue()
    return disassembly_text
