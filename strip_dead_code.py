with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

import re

# Remove unused RADIUS_OPTIONS completely
code = re.sub(r'const _?RADIUS_OPTIONS: RadiusOption\[\] = \[[\s\S]*?\];\n', '', code)
code = re.sub(r'interface RadiusOption \{[\s\S]*?\}\n', '', code)

# Remove _handleRadiusChange and _handleAiQuery completely
code = re.sub(r'  const _handleRadiusChange = useCallback\([\s\S]*?\n  \)\n', '', code)
code = re.sub(r'  const _handleAiQuery = useCallback\([\s\S]*?\n  \)\n', '', code)

with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'w', encoding='utf-8') as f:
    f.write(code)

print('SUCCESS STRIPPED DEAD CODE')
