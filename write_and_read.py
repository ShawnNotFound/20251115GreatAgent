from pathlib import Path
from langflow.services.settings.utils import write_secret_to_file
path = Path(r'C:\Users\Shawn\AppData\Local\LangflowConfig\secret_key_check2')
write_secret_to_file(path, 'abc123')
print('wrote file')
print('trying to read immediately:')
print(path.read_text())
