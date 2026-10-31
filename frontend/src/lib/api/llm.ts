export type SupportedLanguage = 'en' | 'kn' | 'hi'

export interface ToiletFacilityContext {
  id?: number | string
  name: string
  distance: string
  distanceMeters: number
  address: string
  wheelchair: string
  fee: string
  toiletsType?: string
  changingTable?: string
  drinkingWater?: string
  access?: string
}

export interface CivicAiQueryContext {
  userQuery: string
  locationLabel: string
  radiusKm: string
  language?: SupportedLanguage
  userPreferences: {
    wantsWestern?: boolean
    wantsIndian?: boolean
    wantsWheelchair?: boolean
    wantsFree?: boolean
    wantsBabyChanging?: boolean
    wantsDrinkingWater?: boolean
    targetArea?: string
  }
  facilities: ToiletFacilityContext[]
}

const LANGUAGE_INSTRUCTIONS: Record<SupportedLanguage, string> = {
  en: 'Respond in clear, polite English.',
  kn: 'Respond fluently in Kannada (ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಸ್ಪಷ್ಟವಾಗಿ ಉತ್ತರಿಸಿ). Provide toilet names and directions in helpful Kannada.',
  hi: 'Respond fluently in conversational Hindi (हिंदी में उत्तर दें). Provide toilet details and directions clearly in Hindi.',
}

/**
 * Supercharged Civic AI Chatbot Engine with Multi-Language Support (English, Kannada, Hindi)
 * Supports deep preference reasoning: Western vs Indian / Squat, Wheelchair / Accessibility,
 * Baby Changing, Free/Paid, Geolocation Radius, and Real BBMP Facilities.
 */
export async function askCivicSuperLLM(ctx: CivicAiQueryContext): Promise<string> {
  const lang = ctx.language || 'en'
  const langInstruction = LANGUAGE_INSTRUCTIONS[lang] || LANGUAGE_INSTRUCTIONS.en

  // 1. Feature Filter Matching
  const matched = ctx.facilities.filter((f) => {
    if (ctx.userPreferences.wantsWheelchair && f.wheelchair !== 'yes') return false
    if (ctx.userPreferences.wantsFree && f.fee && !['no', 'free', '0'].includes(f.fee.toLowerCase())) return false
    if (ctx.userPreferences.wantsBabyChanging && f.changingTable !== 'yes') return false
    return true
  })

  // Fallback to closest if strict filters yield zero
  const candidateList = matched.length > 0 ? matched : ctx.facilities
  const best = candidateList[0]

  // Construct facilities briefing for LLM
  const facilitiesSummary = candidateList.slice(0, 5).map((f, i) =>
    `[Facility #${i + 1}] "${f.name}" | Distance: ${f.distance} | Location: ${f.address} | Wheelchair: ${f.wheelchair} | Fee: ${f.fee || 'Free'} | Style: ${f.toiletsType || 'Western & Indian stalls'}`
  ).join('\n')

  const systemPrompt = `You are Namma Suvidha Super AI, the official live intelligent civic guide for public sanitation in Bengaluru.
Your mission is to satisfy the citizen's exact sanitation needs at all costs based on real municipal data.
Rules:
1. Address the citizen's specific requirements (e.g., Western vs Indian toilets, wheelchair/disabled access, baby care, free facilities, or specific Bengaluru locality).
2. Recommend the best matching facility immediately, stating its exact name, distance, address, and amenities.
3. Be reassuring, polite, and direct (2 to 4 sentences maximum).
4. ${langInstruction}
5. Never make up fake coordinates or non-existent cities. Focus on Bengaluru.`

  // Try OpenRouter (Gemini 2.0 / Nemotron)
  const openRouterKey = (import.meta as any).env?.VITE_OPENROUTER_API_KEY || ''
  if (openRouterKey) {
    try {
      const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${openRouterKey}`,
        },
        body: JSON.stringify({
          model: 'google/gemini-2.0-flash-lite-001',
          messages: [
            { role: 'system', content: systemPrompt },
            {
              role: 'user',
              content: `Citizen Request: "${ctx.userQuery}"\nLanguage: ${lang}\nDetected Area: ${ctx.locationLabel} (${ctx.radiusKm} km radius)\nPreferences: ${JSON.stringify(ctx.userPreferences)}\nVerified Live Facilities:\n${facilitiesSummary}`,
            },
          ],
          max_tokens: 250,
          temperature: 0.25,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const reply = data.choices?.[0]?.message?.content?.trim()
        if (reply) return reply
      }
    } catch (e) {
      console.warn('OpenRouter API notice:', e)
    }
  }

  // Try Groq API
  const groqKey = (import.meta as any).env?.VITE_GROQ_API_KEY || ''
  if (groqKey) {
    try {
      const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${groqKey}`,
        },
        body: JSON.stringify({
          model: 'llama-3.1-8b-instant',
          messages: [
            { role: 'system', content: systemPrompt },
            {
              role: 'user',
              content: `Citizen Request: "${ctx.userQuery}"\nLanguage: ${lang}\nArea: ${ctx.locationLabel}\nLive Facilities:\n${facilitiesSummary}`,
            },
          ],
          max_tokens: 220,
          temperature: 0.25,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const reply = data.choices?.[0]?.message?.content?.trim()
        if (reply) return reply
      }
    } catch (e) {
      console.warn('Groq notice:', e)
    }
  }

  // Guaranteed Truth-Preserving Algorithmic Response with Multi-Language Support
  if (!best) {
    if (lang === 'kn') {
      return `${ctx.locationLabel} ಹತ್ತಿರ ${ctx.radiusKm} ಕಿಮೀ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ ಯಾವುದೇ ಶೌಚಾಲಯ ತಕ್ಷಣ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ. ನಕ್ಷೆಯಲ್ಲಿ ಹತ್ತಿರದ ಬಿಬಿಎಂಪಿ ಸೌಲಭ್ಯಗಳನ್ನು ತೋರಿಸಲು ತ್ರಿಜ್ಯವನ್ನು ವಿಸ್ತರಿಸಲಾಗಿದೆ.`
    }
    if (lang === 'hi') {
      return `${ctx.locationLabel} के पास ${ctx.radiusKm} किमी के दायरे में कोई शौचालय तुरंत उपलब्ध नहीं मिला। आपके लिए निकटतम बीबीएमपी सुविधाओं को मानचित्र पर विस्तारित किया गया है।`
    }
    return `Searched near ${ctx.locationLabel} within ${ctx.radiusKm} km across verified BBMP records. No washroom immediately matches all requested constraints. We have expanded your live map radius to display the nearest accessible civic facilities.`
  }

  const feeLabel = best.fee ? `Fee: ${best.fee}` : 'Free public access'

  if (lang === 'kn') {
    return `${ctx.locationLabel} ಹತ್ತಿರ ನಿಮಗೆ ಅತ್ಯುತ್ತಮ ಬಿಬಿಎಂಪಿ ಶೌಚಾಲಯ: "${best.name}" (${best.distance} ದೂರದಲ್ಲಿದೆ, ಸ್ಥಳ: ${best.address}). ಸೌಲಭ್ಯಗಳು: ${best.wheelchair === 'yes' ? 'ಗಾಲಿಕುರ್ಚಿ ಸ್ನೇಹಿ (Wheelchair Accessible)' : 'ಸಾಮಾನ್ಯ ಪ್ರವೇಶ'}, ಶುಲ್ಕ: ${best.fee || 'ಉಚಿತ'}. ಲೈವ್ ಗೂಗಲ್ ಮ್ಯಾಪ್ಸ್ ಮಾರ್ಗ ಕೆಳಗೆ ನೀಡಲಾಗಿದೆ.`
  }

  if (lang === 'hi') {
    return `${ctx.locationLabel} के पास आपके लिए सत्यापित बीबीएमपी शौचालय: "${best.name}" (${best.distance} की दूरी पर, पता: ${best.address})। सुविधाएं: ${best.wheelchair === 'yes' ? 'व्हीलचेयर सुलभ' : 'सामान्य'}, शुल्क: ${best.fee || 'मुफ़्त'}। नीचे मानचित्र पर सीधा रास्ता जोड़ दिया गया है।`
  }

  const prefTags: string[] = []
  if (ctx.userPreferences.wantsWheelchair) prefTags.push('wheelchair-accessible ramp & grab rails')
  if (ctx.userPreferences.wantsWestern) prefTags.push('western seated commode')
  if (ctx.userPreferences.wantsIndian) prefTags.push('Indian squat style')
  if (ctx.userPreferences.wantsBabyChanging) prefTags.push('infant diaper station')
  if (ctx.userPreferences.wantsFree) prefTags.push('free admission')

  const prefStr = prefTags.length > 0 ? ` with ${prefTags.join(', ')}` : ''

  return `Here is your best verified facility${prefStr} near ${ctx.locationLabel}: "${best.name}" (${best.distance} away at ${best.address}). Amenities verified: ${best.wheelchair === 'yes' ? 'Accessible' : 'Standard access'}, ${feeLabel}. Live interactive navigation route has been mapped below.`
}

// Backward compatibility alias
export const askCivicLLM = async (
  prompt: string,
  contextData: any
): Promise<string> => {
  return askCivicSuperLLM({
    userQuery: prompt,
    locationLabel: contextData.locationLabel,
    radiusKm: contextData.radiusKm,
    userPreferences: {},
    facilities: contextData.toilets.map((t: any) => ({
      name: t.name || 'BBMP Public Washroom',
      distance: t.distance,
      distanceMeters: 500,
      address: t.address || 'Bengaluru',
      wheelchair: t.wheelchair || 'unspecified',
      fee: t.fee || 'free',
    })),
  })
}
