import json
def a1(b2, c3):
    d4 = json.loads(b2)
    e5 = list(d4.keys())
    f6 = len(e5)
    for g7 in e5:
        h8 = d4[g7]
        print(g7, h8)
    return f6

def zz(OO0, II1):
    lI1 = open(OO0, 'r')
    lll = lI1.readlines()
    lI1.close()
    return lll
