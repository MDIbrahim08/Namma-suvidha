with open('frontend/src/lib/api/llm.ts', 'r', encoding='utf-8') as f:
    code = f.read()

import re
code = re.sub(r"const groqKey =[\s\S]*?'gsk_[^']*'", "const groqKey = (import.meta as any).env?.VITE_GROQ_API_KEY || ''", code)

with open('frontend/src/lib/api/llm.ts', 'w', encoding='utf-8') as f:
    f.write(code)

print('SUCCESS CLEANED TOKEN VIA SCRIPT')

