import base64, zlib
def _a(_b, _c=42):
    _d = base64.b64decode('SGVsbG8gV29ybGQ=').decode()
    _e = chr(87)+chr(111)+chr(114)+chr(108)+chr(100)
    _f = [_x ^ _c for _x in [112, 121, 116, 104, 111, 110]]
    __state = 0
    while True:
        if __state == 0:
            _g = _d + _e
            __state = 1
        elif __state == 1:
            _h = bytes(_f).decode()
            __state = 2
        elif __state == 2:
            return _g + _h
