with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

# Comment out unused imports & helper variables so tsc passes cleanly
text = text.replace("import CivicAiChatBar from '../../../components/ui/civic-ai-chat-bar'", "// import CivicAiChatBar from '../../../components/ui/civic-ai-chat-bar'")
text = text.replace("import { askCivicSuperLLM, type SupportedLanguage } from '../../../lib/api/llm'", "// import { askCivicSuperLLM, type SupportedLanguage } from '../../../lib/api/llm'")

# Prefix unused RADIUS_OPTIONS with _
text = text.replace("const RADIUS_OPTIONS: RadiusOption[] = [", "const _RADIUS_OPTIONS: RadiusOption[] = [")

# Prefix unused callbacks
text = text.replace("const handleRadiusChange = useCallback(", "const _handleRadiusChange = useCallback(")
text = text.replace("const handleAiQuery = useCallback(", "const _handleAiQuery = useCallback(")

with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'w', encoding='utf-8') as f:
    f.write(text)

print('CLEANED UNUSED IDENTIFIERS FOR STRICT TSC')
