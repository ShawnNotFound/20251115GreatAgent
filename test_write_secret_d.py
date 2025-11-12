from pathlib import Path
from langflow.services.settings.utils import write_secret_to_file
path = Path(r'D:\Hackathon\20251115GreatAgent\.langflow_config\secret_key_pytest')
path.parent.mkdir(exist_ok=True)
try:
    write_secret_to_file(path, 'abc123')
    print('write ok')
except Exception as e:
    print('write error', repr(e))
