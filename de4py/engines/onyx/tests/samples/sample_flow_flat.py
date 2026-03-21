def calculate(a, b):
    __state = 0
    __result = None
    while True:
        if __state == 0:
            __tmp = a + b
            __state = 1
        elif __state == 1:
            __result = __tmp * 2
            __state = 2
        elif __state == 2:
            return __result
