import threading
from pathlib import Path
from langflow.services.settings.utils import write_secret_to_file
path = Path(r'C:\Users\Shawn\AppData\Local\LangflowConfig\secret_key_concurrent')
path.unlink(missing_ok=True)
exceptions = []

def worker(val):
    try:
        write_secret_to_file(path, val)
    except Exception as exc:
        exceptions.append(exc)

threads = [threading.Thread(target=worker, args=(f'val{i}',)) for i in range(2)]
[t.start() for t in threads]
[t.join() for t in threads]
print('exceptions:', exceptions)
