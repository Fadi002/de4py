# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import zlib, base64, re
def freecodingtools(filepath):
        lol = open(filepath, 'r', encoding='utf-8', errors='ignore').read()
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