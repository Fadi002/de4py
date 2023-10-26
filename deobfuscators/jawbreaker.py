# NOTE : This obfuscator is outdated so 99% you can't get the source code only the hastebin url
import base64
def jawbreaker(file_path):
    data = open(file_path,'r').read()
    data = data.split('"')[1]
    file2 = base64.b64decode(base64.b32decode(base64.b16decode(data)))
    llol = ''.join(str(file2).split(";")).split("'")
    semidecoded = ''.join([sss for sss in llol if len(sss) == 1])
    decoded = base64.b64decode(base64.b32decode(base64.b16decode(semidecoded)))
    return decoded.decode()
    # real = requests.get(str(decoded).split('"')[1]).text
    # with open(filedata+'-cleaned.py','w', encoding='utf-8') as file:
    #     file.write(real)
    #     file.close()
    # print("\n"+real)