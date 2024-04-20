import zlib, base64, re
def freecodingtools(filepath):
        lol = open(filepath, 'r').read()
        def decode_data(data):
            return zlib.decompress(base64.b64decode(data[::-1]))
        try:
            first_loop = True
            while True:
                matches = re.findall(r"b'([^']*)'", lol)
                if first_loop:
                    lol = decode_data(matches[1].encode()).decode()
                    first_loop = False
                else:
                    lol = decode_data(matches[0].encode()).decode()
        except:
            return '#cleaned with de4py\n\n'+lol