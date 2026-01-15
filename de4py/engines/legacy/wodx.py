def wodx(file_path):
    file_name = file_path.split('/')[-1].split('.')[0]
    data = open(file_path,'r').read()
    data = data.replace('exec', 'input')
    with open(file_name+'-cleaned.py','w', encoding='utf-8') as file:
        file.write("# Cleaned with de4py | https://github.com/Fadi002/de4py\n"+data)
    return "now you need to run "+file_name+'-cleaned.py'+" to get the cleaned code"