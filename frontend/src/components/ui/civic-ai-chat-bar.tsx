import React, { useState } from 'react'
import type { SupportedLanguage } from '../../lib/api/llm'

export interface CivicAiChatBarProps {
  onSubmit: (prompt: string, language: SupportedLanguage) => Promise<string>
  placeholder?: string
}

const LANGUAGES: { code: SupportedLanguage; label: string; placeholder: string }[] = [
  { code: 'en', label: 'English', placeholder: "Ask Namma AI: 'Find accessible toilets near Indiranagar' or 'Western toilets'…" },
  { code: 'kn', label: 'ಕನ್ನಡ', placeholder: "ನಮ್ಮ AI ಗೆ ಕೇಳಿ: 'ಇಂದಿರಾನಗರ ಹತ್ತಿರ ಶೌಚಾಲಯ ಹುಡುಕಿ' ಅಥವಾ 'ಗಾಲಿಕುರ್ಚಿ ಸ್ನೇಹಿ'…" },
  { code: 'hi', label: 'हिंदी', placeholder: "नम्मा एआई से पूछें: 'इंदिरानगर के पास शौचालय' या 'वेस्टर्न टॉयलेट'…" },
]

export default function CivicAiChatBar({ onSubmit, placeholder }: CivicAiChatBarProps) {
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [response, setResponse] = useState<string | null>(null)
  const [language, setLanguage] = useState<SupportedLanguage>('en')

  const currentLangObj = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = query.trim()
    if (!text || isLoading) return
    setIsLoading(true)
    setResponse(null)
    try {
      const reply = await onSubmit(text, language)
      setResponse(reply)
    } catch {
      setResponse(
        language === 'kn'
          ? 'ನಾಗರಿಕ ಡೇಟಾಬೇಸ್ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸಿ.'
          : language === 'hi'
          ? 'नागरिक डेटाबेस से कनेक्ट नहीं हो सका। कृपया पुनः प्रयास करें।'
          : 'Unable to query civic database right now. Please try again.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="w-full my-3 flex flex-col items-center">
      {/* Language Switcher Pills */}
      <div className="flex items-center gap-1.5 mb-2 bg-white/70 backdrop-blur-md px-2 py-1 rounded-full border border-slate-200/80 shadow-xs">
        <span className="material-symbols-outlined text-[14px] text-slate-500 ml-1">translate</span>
        <span className="text-[11px] font-semibold text-slate-600 mr-1 uppercase tracking-wider">Language:</span>
        {LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            type="button"
            onClick={() => setLanguage(lang.code)}
            className={`px-2.5 py-0.5 rounded-full text-xs font-bold transition-all ${
              language === lang.code
                ? 'bg-[#123C3A] text-white shadow-xs scale-105'
                : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            {lang.label}
          </button>
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl bg-white/80 backdrop-blur-xl border border-white/90 rounded-full px-4 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.08)] flex items-center gap-2.5 transition-all hover:bg-white/95 focus-within:ring-2 focus-within:ring-[#006398]/50 focus-within:border-white"
      >
        <span className="material-symbols-outlined text-[#006398] text-[22px] flex-shrink-0">
          auto_awesome
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder || currentLangObj.placeholder}
          className="flex-1 bg-transparent text-[#131b2e] placeholder:text-slate-400 text-sm md:text-base outline-none font-medium"
        />
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          aria-label="Send Query"
          className="w-9 h-9 rounded-full bg-[#123C3A] hover:bg-[#003244] disabled:opacity-40 text-white flex items-center justify-center transition-transform active:scale-95 flex-shrink-0 shadow-sm"
        >
          {isLoading ? (
            <span className="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
          ) : (
            <span className="material-symbols-outlined text-[18px]">arrow_upward</span>
          )}
        </button>
      </form>

      {/* Instant Answer Bubble */}
      {response && (
        <div className="w-full max-w-2xl mt-3 p-4 bg-white/90 backdrop-blur-xl border border-white/90 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between gap-2 mb-1.5 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-[#006398] uppercase tracking-wider">
                {language === 'kn' ? 'ನಮ್ಮ ಸುವಿಧಾ AI ಪ್ರತಿಕ್ರಿಯೆ' : language === 'hi' ? 'नम्मा सुविधा AI प्रतिक्रिया' : 'Namma Suvidha AI Response'}
              </span>
            </div>
            <button
              onClick={() => setResponse(null)}
              className="text-slate-400 hover:text-slate-600 text-xs flex items-center"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
          <p className="text-xs md:text-sm text-slate-800 leading-relaxed font-medium">
            {response}
          </p>
        </div>
      )}
    </div>
  )
}
