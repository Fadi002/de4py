import os
def devtool(file_path):
    pycommand = 'python3 ' if os.name != 'nt' else ''
    data = open(file_path,'r').read()
    for line in data.splitlines():
        if line.startswith("eval"):
            data = data.replace(line, 'x = base64.b64decode(trust).decode()\n')
    with open(file_path+'-cleaned.py','w', encoding='utf-8') as file:
        file.write(data)
        file.write('\n')
        file.write(f"de4pyw=open('{file_path}-cleaned.py','w')\nde4pyw.write(x)\nde4pyw.close()")
        file.close()
    os.system(pycommand+file_path+'-cleaned.py')
    with open(file_path+'-cleaned.py','r', encoding='utf-8') as file:
        data = file.read()
        print(data)
        file.close()