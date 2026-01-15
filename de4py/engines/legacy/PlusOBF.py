from pathlib import Path
import re
import ast
import logging

logger = logging.getLogger(__name__)

def PlusOBF(file_path: str) -> str:
    path = Path(file_path)
    output_filename = path.stem + "-cleaned.py"
    
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
        regex = re.findall(r"\[(.*?)\]", content)
        if not regex:
            return "Detected PlusOBF but could not find data patterns."
            
        # Safely evaluate the bracketed content
        try:
            data = ast.literal_eval(f"[{regex[0]}]")
            # The original logic used len(i), assuming i is a string/list member
            cleaned = "".join([chr(len(str(i))) for i in data])
        except Exception as e:
            logger.error(f"PlusOBF analysis failed: {e}")
            return f"PlusOBF analysis failed: {e}"
            
        header = "# Cleaned with de4py | https://github.com/Fadi002/de4py\n"
        full_content = header + cleaned
        
        output_path = path.parent / output_filename
        output_path.write_text(full_content, encoding="utf-8")
        
        return f"Saved as {output_filename}\n\n\n{full_content}"
    except Exception as e:
        logger.error(f"PlusOBF engine encountered an error: {e}")
        return f"Engine failed: {e}"