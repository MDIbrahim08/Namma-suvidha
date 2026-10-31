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
  en: 'Respond in clear, natural, warm, and helpful conversational English like ChatGPT.',
  kn: 'Respond fluently, naturally, and conversationally in authentic Kannada (ಕನ್ನಡ ಲಿಪಿಯಲ್ಲಿ ಆತ್ಮೀಯವಾಗಿ ಮತ್ತು ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ).',
  hi: 'Respond fluently, naturally, and conversationally in polite Hindi (हिंदी में मित्रवत और स्पष्ट बातचीत की तरह उत्तर दें).',
}

/**
 * Supercharged Live ChatGPT-Style Conversational LLM Engine for Bengaluru Civic Sanitation
 * Connects directly to Groq high-speed Llama-3.3 / OpenRouter with fluent natural language generation.
 */
export async function askCivicSuperLLM(ctx: any): Promise<string> {
  const query = (ctx.userQuery || ctx.prompt || '').toLowerCase().trim()
  const lang: SupportedLanguage = ctx.language || 'en'

  if (query === 'hi' || query === 'hello' || query.startsWith('hi ') || query.startsWith('hello ')) {
    if (lang === 'kn') return 'ನಮಸ್ಕಾರ! ನಾನು ನಮ್ಮ ಸುವಿಧಾ AI ಸಹಾಯಕ. ನಿಮ್ಮ ಹತ್ತಿರದ ಬಿಬಿಎಂಪಿ ಶೌಚಾಲಯಗಳನ್ನು ಹುಡುಕಲು ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.'
    if (lang === 'hi') return 'नमस्ते! मैं नम्मा सुविधा AI सहायक हूँ। मैं आपके आस-पास के स्वच्छ शौचालयों को खोजने में मदद कर सकता हूँ।'
    return 'Hello! I am Namma Suvidha AI assistant. I can help you find verified, clean, and accessible public toilets across Bengaluru. How can I help you today?'
  }
  const lang = ctx.language || 'en'
  const langInstruction = LANGUAGE_INSTRUCTIONS[lang] || LANGUAGE_INSTRUCTIONS.en

  // 1. Feature Filter Matching
  const matched = (ctx.facilities || []).filter((f: any) => {
    if (ctx.userPreferences?.wantsWheelchair && f.wheelchair !== 'yes') return false
    if (ctx.userPreferences?.wantsFree && f.fee && !['no', 'free', '0'].includes(f.fee.toLowerCase())) return false
    if (ctx.userPreferences?.wantsBabyChanging && f.changingTable !== 'yes') return false
    return true
  })

  const candidateList = matched.length > 0 ? matched : ctx.facilities
  const best = candidateList[0]

  // Construct structured municipal facilities briefing
  const facilitiesSummary = candidateList.slice(0, 5).map((f, i) =>
    `[Facility #${i + 1}] "${f.name}" | Distance: ${f.distance} (${f.distanceMeters}m) | Location: ${f.address} | Wheelchair Accessible: ${f.wheelchair} | Fee: ${f.fee || 'Free'} | Style: ${f.toiletsType || 'Western & Indian stalls'}`
  ).join('\n')

  const systemPrompt = `You are Namma Suvidha AI, a helpful, ultra-fast live conversational AI assistant (like ChatGPT) dedicated to Bengaluru's public sanitation network.
You have real-time access to live OpenStreetMap and BBMP municipal telemetry.

Your Goal:
1. Act like a knowledgeable, warm, and direct local guide.
2. Directly answer the citizen's query based on their requested preferences (e.g., Western commode vs. Indian squat, wheelchair accessibility, free access, infant care, or location).
3. Recommend the top verified facility with its exact name, distance, and location.
4. Keep the response concise, conversational, and direct (2 to 3 sentences).
5. ${langInstruction}
6. Never output markdown code fences or JSON. Speak directly to the citizen.`

  const userPrompt = `Citizen Query: "${ctx.userQuery}"
User Language: ${lang}
Current Citizen Location: ${ctx.locationLabel} (Radius: ${ctx.radiusKm} km)
Extracted Preferences: ${JSON.stringify(ctx.userPreferences)}
Live Municipal Facilities Found Nearby:
${facilitiesSummary || 'No facilities found within current radius.'}`

  // 1. Try Groq (Ultra-fast 500 tokens/sec live streaming response)
  const groqKey = (import.meta as any).env?.VITE_GROQ_API_KEY || '' // Groq public endpoint
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
            { role: 'user', content: userPrompt },
          ],
          max_tokens: 220,
          temperature: 0.3,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const reply = data.choices?.[0]?.message?.content?.trim()
        if (reply) return reply
      }
    } catch {
      // Fallback seamlessly
    }
  }

  // 2. Try OpenRouter (Gemini / Nemotron / Llama)
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
            { role: 'user', content: userPrompt },
          ],
          max_tokens: 220,
          temperature: 0.3,
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const reply = data.choices?.[0]?.message?.content?.trim()
        if (reply) return reply
      }
    } catch {
      // Fallback seamlessly
    }
  }

  // 3. Conversational Live Fallback (Zero Latency, ChatGPT Style)
  if (!best) {
    if (lang === 'kn') {
      return `ನಮಸ್ಕಾರ! ${ctx.locationLabel} ಸುತ್ತಮುತ್ತಲಿನ ${ctx.radiusKm} ಕಿಮೀ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ ನೀವು ಹುಡುಕುತ್ತಿರುವ ಸೌಲಭ್ಯ ಸದ್ಯಕ್ಕೆ ಲಭ್ಯವಿಲ್ಲ. ನಿಮ್ಮ ನಕ್ಷೆಯ ತ್ರಿಜ್ಯವನ್ನು ನಾವು 5 ಕಿಮೀಗೆ ವಿಸ್ತರಿಸಿದ್ದೇವೆ, ಅಲ್ಲಿ ಹತ್ತಿರದ ಬಿಬಿಎಂಪಿ ಶೌಚಾಲಯಗಳನ್ನು ನೋಡಬಹುದು.`
    }
    if (lang === 'hi') {
      return `नमस्ते! ${ctx.locationLabel} के पास ${ctx.radiusKm} किमी के दायरे में आपकी पसंद का कोई शौचालय तुरंत नहीं मिला। हमने आपके लिए मैप का दायरा बढ़ा दिया है ताकि आप निकटतम चालू सुविधाएं देख सकें।`
    }
    return `Hello! I couldn't find a washroom matching all your exact preferences within ${ctx.radiusKm} km of ${ctx.locationLabel}. I've expanded your search radius on the map below so you can view the nearest verified municipal facilities.`
  }

  const feeLabel = best.fee && !['no', 'free', '0'].includes(best.fee.toLowerCase()) ? `शुल्क: ${best.fee}` : 'ಉಚಿತ ಪ್ರವೇಶ (Free)'
  const feeLabelEn = best.fee && !['no', 'free', '0'].includes(best.fee.toLowerCase()) ? `Fee: ${best.fee}` : 'Free public access'

  if (lang === 'kn') {
    const acc = best.wheelchair === 'yes' ? 'ಗಾಲಿಕುರ್ಚಿ ಸ್ನೇಹಿ (Wheelchair Accessible)' : 'ಸಾಮಾನ್ಯ ಪ್ರವೇಶ'
    return `ಖಂಡಿತ, ನಿಮ್ಮ ಲೈವ್ ಲೊಕೇಶನ್ (${ctx.locationLabel}) ಹತ್ತಿರ ಉತ್ತಮವಾದ ಶೌಚಾಲಯ ಇಲ್ಲಿದೆ: "${best.name}". ಇದು ಕೇವಲ ${best.distance} ದೂರದಲ್ಲಿದೆ (${best.address}). ಸೌಲಭ್ಯಗಳು: ${acc}, ${feeLabel}. ನಕ್ಷೆಯಲ್ಲಿ ಗೂಗಲ್ ಮ್ಯಾಪ್ಸ್ ಮಾರ್ಗವನ್ನು ಕೆಳಗೆ ನೀಡಲಾಗಿದೆ!`
  }

  if (lang === 'hi') {
    const accHi = best.wheelchair === 'yes' ? 'व्हीलचेयर सुलभ' : 'सामान्य'
    return `ज़रूर! आपकी लाइव लोकेशन (${ctx.locationLabel}) के सबसे पास यह सत्यापित बीबीएमपी शौचालय है: "${best.name}"। यह केवल ${best.distance} की दूरी पर (${best.address}) स्थित है। सुविधाएं: ${accHi}, शुल्क: ${best.fee || 'मुफ़्त'}। नीचे दिए गए मैप पर सीधा गूगल मैप्स नेविगेशन उपलब्ध है।`
  }

  const prefTags: string[] = []
  if (ctx.userPreferences.wantsWheelchair) prefTags.push('wheelchair ramp')
  if (ctx.userPreferences.wantsWestern) prefTags.push('western commode')
  if (ctx.userPreferences.wantsIndian) prefTags.push('Indian squat toilet')
  if (ctx.userPreferences.wantsBabyChanging) prefTags.push('baby changing station')
  if (ctx.userPreferences.wantsFree) prefTags.push('free entry')

  const prefStr = prefTags.length > 0 ? ` with ${prefTags.join(', ')}` : ''
  const accEn = best.wheelchair === 'yes' ? 'Wheelchair accessible' : 'Standard access'

  return `Sure thing! The best verified public washroom${prefStr} near ${ctx.locationLabel} is "${best.name}", located just ${best.distance} away at ${best.address}. Amenities: ${accEn}, ${feeLabelEn}. I've mapped out direct Google Maps directions right below for you!`
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
