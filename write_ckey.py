from pathlib import Path
path = Path(r'C:\Users\Shawn\AppData\Local\LangflowConfig\secret_key')
path.write_text('abc', encoding='utf-8')
