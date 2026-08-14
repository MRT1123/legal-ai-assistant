import re

path = r'D:\legal-ai-assistant\backend\app\agent\nodes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 修复断行的字符串字面量：chat_history = '<换行>'.join -> chat_history = '\n'.join
fixed = re.sub(r"chat_history\s*=\s*'[\r\n]+'\.join", r"chat_history = '\\n'.join", content)

if fixed != content:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(fixed)
    print('Fixed!')
else:
    print('No match found, showing lines around 116:')
    lines = content.split('\n')
    for i in range(110, min(125, len(lines))):
        print(f'{i+1}: {repr(lines[i])}')
