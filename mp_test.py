from multiprocessing import Process
from pathlib import Path
from langflow.services.settings.utils import write_secret_to_file
path = Path(r'C:\Users\Shawn\AppData\Local\LangflowConfig\secret_key_mp')
path.unlink(missing_ok=True)

def worker(i):
    write_secret_to_file(path, f'val{i}')

procs = [Process(target=worker, args=(i,)) for i in range(2)]
[p.start() for p in procs]
[p.join() for p in procs]
print('done')
