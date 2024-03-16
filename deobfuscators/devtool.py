import os, traceback, base64, ast
def devtool(file_path):
        try:
            print('= development tools deobfuscator start =')
            filename = str(file_path.split('/')[-1])
            with open(file_path, 'r') as file:
                file_content = ''.join(file.readlines()[:-1])
            parsed_content = ast.parse(file_content, filename=file_path)
            global_vars = {}
            local_vars = {}
            exec(compile(parsed_content, filename=file_path, mode='exec'), global_vars, local_vars)
            trust_value = local_vars.get('trust')
            code = base64.b64decode(trust_value.encode()).decode()
            del local_vars, global_vars, parsed_content, file_content
            cleaned_filename = filename.split('.')[0]+"-cleaned.py"
            with open(cleaned_filename, 'w') as f:
                 f.write('# cleaned with de4py\n\n' + code)
                 f.close
            print(f"Saved as {cleaned_filename}")
            print('= development tools deobfuscator end =')
            return '# cleaned with de4py\n\n' + code
        except Exception as e:
            traceback.print_exc()
            return None
