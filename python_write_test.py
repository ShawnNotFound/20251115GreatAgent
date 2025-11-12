from pathlib import Path
path = Path(r'D:\Hackathon\20251115GreatAgent\python_test.txt')
try:
    path.write_text('hello')
    print('wrote test file ok')
except Exception as e:
    print('error writing test', repr(e))
