import re
def PlusOBF(file_path):
    try:
        filename = file_path.split('/')[-1].split('.')[0]
        lines = open(file_path,'r',encoding='utf-8').read()
        regex = re.findall("\[(.*?)\]", "".join(lines))
        cleaned = "".join([chr(len(i)) for i in eval(f'{"[" + regex[0] + "]"}')])
        with open(filename+"-cleaned.py", "w") as file:
            file.write("# Cleaned with de4py | https://github.com/Fadi002/de4py\n"+cleaned)
        return "Saved as "+filename+'-cleaned.py\n\n\n'+"# Cleaned with de4py | https://github.com/Fadi002/de4py\n"+cleaned
    except Exception as e:
        return 'Detected PlusOBF but Failed to deobfuscate\n'+e