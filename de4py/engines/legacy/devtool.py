# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import traceback, base64, ast

from de4py.engines.onyx.safe_eval import SafeFunctionRunner, SafeEvalError


def _resolve_trust(tree: ast.Module):
    """
    Recover the module-level ``trust`` binding without running the file.

    The original implementation exec'd the whole sample to read one variable,
    which meant any file merely containing the word "trust" was executed on the
    analyst's machine. Interpreting the module under the bounded evaluator gives
    the same value for real devtool output and refuses everything else.
    """
    runner = SafeFunctionRunner({})
    env = runner.env
    for stmt in tree.body:
        if not isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            continue
        try:
            runner._exec(stmt, env)
        except (SafeEvalError, Exception):
            continue
    value = env.get('trust')
    return value if isinstance(value, (str, bytes)) else None


def devtool(file_path):
        try:
            print('= development tools deobfuscator start =')
            filename = str(file_path.split('/')[-1])
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                file_content = ''.join(file.readlines()[:-1])
            parsed_content = ast.parse(file_content, filename=file_path)
            trust_value = _resolve_trust(parsed_content)
            if not trust_value:
                return f"Error: 'trust' variable not found in {file_path}"

            if isinstance(trust_value, str):
                trust_value = trust_value.encode()
            code = base64.b64decode(trust_value).decode()
            del parsed_content, file_content
            cleaned_filename = filename.split('.')[0]+"-cleaned.py"
            with open(cleaned_filename, 'w', encoding='utf-8') as f:
                 f.write('# cleaned with de4py\n\n' + code)
                 f.close
            print(f"Saved as {cleaned_filename}")
            print('= development tools deobfuscator end =')
            return '# cleaned with de4py\n\n' + code
        except Exception:
            traceback.print_exc()
            return None
