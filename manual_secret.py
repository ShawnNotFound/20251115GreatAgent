from pathlib import Path
path = Path(r'D:\Hackathon\20251115GreatAgent\.langflow_config')
path.mkdir(parents=True, exist_ok=True)
secret = path / 'secret_key'
try:
    secret.write_text('abc', encoding='utf-8')
    print('wrote secret manually')
except Exception as e:
    print('error writing secret manually', repr(e))
