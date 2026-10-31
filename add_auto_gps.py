with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Import useEffect
text = text.replace("import { useCallback, useMemo, useState } from 'react'", "import { useCallback, useEffect, useMemo, useState } from 'react'")

# 2. Add automatic GPS detection on initial component load
hook_code = """
  // Automatically acquire device GPS on initial mount so voice queries immediately use true location
  useEffect(() => {
    void handleDetectAndDiscover()
  }, [])
"""

text = text.replace("    [radiusMeters, fetchForCoordinates],\n  )", "    [radiusMeters, fetchForCoordinates],\n  )\n" + hook_code)

with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print('SUCCESS HOOKED AUTO-GPS ON MOUNT')
