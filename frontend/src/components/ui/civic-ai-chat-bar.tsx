import React, { useState, useEffect, useRef } from 'react'
import type { SupportedLanguage } from '../../lib/api/llm'

export interface CivicAiChatBarProps {
  onSubmit: (prompt: string, language: SupportedLanguage) => Promise<string>
  placeholder?: string
}

const LANGUAGES: { code: SupportedLanguage; label: string; placeholder: string; speechLang: string }[] = [
  { code: 'en', label: 'English', placeholder: "Ask Namma AI: 'Find accessible toilets' or 'Western toilets'…", speechLang: 'en-IN' },
  { code: 'kn', label: 'ಕನ್ನಡ', placeholder: "ನಮ್ಮ AI ಗೆ ಕೇಳಿ: 'ಇಂದಿರಾನಗರ ಹತ್ತಿರ ಶೌಚಾಲಯ ಹುಡುಕಿ'…", speechLang: 'kn-IN' },
  { code: 'hi', label: 'हिंदी', placeholder: "ನಮ್ಮ AI: 'इंदिरानगर के पास शौचालय'…", speechLang: 'hi-IN' },
]

export default function CivicAiChatBar({ onSubmit, placeholder }: CivicAiChatBarProps) {
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [response, setResponse] = useState<string | null>(null)
  const [language, setLanguage] = useState<SupportedLanguage>('en')
  const [langMenuOpen, setLangMenuOpen] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(true)

  const recognitionRef = useRef<any>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const currentLangObj = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0]

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setLangMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Setup Web Speech Recognition
  useEffect(() => {
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      setSpeechSupported(false)
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = false
      recognition.lang = currentLangObj.speechLang

      recognition.onstart = () => {
        setIsListening(true)
      }

      recognition.onresult = (event: any) => {
        const transcript = event.results?.[0]?.[0]?.transcript
        if (transcript) {
          setQuery(transcript)
          void triggerSubmit(transcript, language)
        }
        setIsListening(false)
      }

      recognition.onerror = (e: any) => {
        console.warn('Speech recognition error:', e)
        setIsListening(false)
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognition
    } catch (e) {
      console.warn('Speech init warning:', e)
      setSpeechSupported(false)
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort()
        } catch {}
      }
    }
  }, [language, currentLangObj.speechLang])

  const toggleListening = () => {
    if (!speechSupported || !recognitionRef.current) {
      alert('Speech recognition is not supported in this browser. Please try Google Chrome or Safari.')
      return
    }

    if (isListening) {
      try {
        recognitionRef.current.stop()
      } catch {}
      setIsListening(false)
    } else {
      try {
        recognitionRef.current.lang = currentLangObj.speechLang
        recognitionRef.current.start()
      } catch (err) {
        console.warn('Speech start error:', err)
        setIsListening(false)
      }
    }
  }

  // Text-To-Speech (Read Aloud Response)
  const speakResponse = (text: string) => {
    if (!('speechSynthesis' in window)) return

    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      return
    }

    window.speechSynthesis.cancel()
    const cleanText = text.replace(/[*#_~]/g, '')
    const utterance = new SpeechSynthesisUtterance(cleanText)
    utterance.lang = currentLangObj.speechLang
    utterance.rate = 1.0

    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)

    window.speechSynthesis.speak(utterance)
  }

  const triggerSubmit = async (text: string, lang: SupportedLanguage) => {
    if (!text.trim() || isLoading) return
    setIsLoading(true)
    setResponse(null)
    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
    }
    try {
      const reply = await onSubmit(text.trim(), lang)
      setResponse(reply)
      speakResponse(reply)
    } catch {
      setResponse(
        lang === 'kn'
          ? 'ನಾಗರಿಕ ಡೇಟಾಬೇಸ್ ಸಂಪರ್ಕಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಪ್ರಯತ್ನಿಸಿ.'
          : lang === 'hi'
          ? 'नागरिक डेटाबेस से कनेक्ट नहीं हो सका। कृपया पुनः प्रयास करें।'
          : 'Unable to query civic database right now. Please try again.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void triggerSubmit(query, language)
  }

  return (
    <div className="w-full flex flex-col items-center">
      <form
        onSubmit={handleSubmit}
        className="w-full bg-white/95 backdrop-blur-xl border border-white/90 rounded-full px-2 sm:px-3 py-1.5 shadow-[0_4px_20px_rgba(0,0,0,0.06)] flex items-center gap-1.5 sm:gap-2 transition-all hover:bg-white focus-within:ring-2 focus-within:ring-[#006398]/50 focus-within:border-white"
      >
        {/* Custom Language Dropdown Pill */}
        <div ref={dropdownRef} className="relative flex-shrink-0">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              setLangMenuOpen(!langMenuOpen)
            }}
            className="flex items-center gap-1 bg-slate-100/90 hover:bg-slate-200 text-slate-800 px-2.5 py-1 rounded-full text-xs font-bold transition-all border border-slate-200/80 active:scale-95"
            aria-expanded={langMenuOpen}
            aria-label="Select Language"
          >
            <span className="material-symbols-outlined text-[15px] text-slate-600">translate</span>
            <span>{currentLangObj.label}</span>
            <span className="material-symbols-outlined text-[14px] text-slate-500">
              {langMenuOpen ? 'expand_less' : 'expand_more'}
            </span>
          </button>

          {/* Dropdown Menu Popover */}
          {langMenuOpen && (
            <div className="absolute top-full left-0 mt-1.5 z-50 bg-white border border-slate-200 rounded-xl shadow-xl py-1 w-32 animate-in fade-in zoom-in-95 duration-150">
              {LANGUAGES.map((l) => (
                <button
                  key={l.code}
                  type="button"
                  onClick={() => {
                    setLanguage(l.code)
                    setLangMenuOpen(false)
                    if (isSpeaking) {
                      window.speechSynthesis.cancel()
                      setIsSpeaking(false)
                    }
                  }}
                  className={`w-full text-left px-3 py-1.5 text-xs font-semibold flex items-center justify-between transition-colors ${
                    language === l.code
                      ? 'bg-emerald-50 text-emerald-800 font-bold'
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <span>{l.label}</span>
                  {language === l.code && (
                    <span className="material-symbols-outlined text-sm text-emerald-600">check</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Input Text Field */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder || currentLangObj.placeholder}
          className="flex-1 bg-transparent text-[#131b2e] placeholder:text-slate-400 text-xs sm:text-sm md:text-base outline-none font-medium min-w-0 px-1"
        />

        {/* Voice Input (Microphone) Button */}
        <button
          type="button"
          onClick={toggleListening}
          aria-label={isListening ? 'Listening… Tap to cancel' : 'Voice search'}
          className={`w-8 h-8 sm:w-9 sm:h-9 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
            isListening
              ? 'bg-rose-600 text-white animate-pulse shadow-md'
              : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
          }`}
          title={isListening ? 'Listening to voice...' : 'Speak your query'}
        >
          <span className="material-symbols-outlined text-[18px] sm:text-[19px]">
            {isListening ? 'mic' : 'mic_none'}
          </span>
        </button>

        {/* Submit Query Button */}
        <button
          type="submit"
          disabled={!query.trim() || isLoading}
          aria-label="Send Query"
          className="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#123C3A] hover:bg-[#003244] disabled:opacity-40 text-white flex items-center justify-center transition-transform active:scale-95 flex-shrink-0 shadow-sm"
        >
          {isLoading ? (
            <span className="material-symbols-outlined text-[17px] animate-spin">progress_activity</span>
          ) : (
            <span className="material-symbols-outlined text-[17px]">arrow_upward</span>
          )}
        </button>
      </form>

      {/* Voice Listening Active Wave Toast */}
      {isListening && (
        <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded-full animate-bounce">
          <span className="material-symbols-outlined text-sm animate-spin">graphic_eq</span>
          <span>Listening in {currentLangObj.label}... Speak now</span>
        </div>
      )}

      {/* Instant Answer Bubble with Voice Read-Aloud */}
      {response && (
        <div className="w-full mt-2.5 p-3.5 sm:p-4 bg-white/95 backdrop-blur-xl border border-white/90 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between gap-2 mb-1.5 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-[#006398] uppercase tracking-wider">
                {language === 'kn' ? 'ನಮ್ಮ ಸುವಿಧಾ AI ಪ್ರತಿಕ್ರಿಯೆ' : language === 'hi' ? 'ನಮ್ಮ AI प्रतिक्रिया' : 'Namma Suvidha AI Response'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => speakResponse(response)}
                className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full font-bold transition-all ${
                  isSpeaking
                    ? 'bg-emerald-600 text-white animate-pulse'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
                title={isSpeaking ? 'Stop speaking' : 'Read aloud'}
              >
                <span className="material-symbols-outlined text-[15px]">
                  {isSpeaking ? 'volume_up' : 'volume_mute'}
                </span>
                <span>{isSpeaking ? 'Speaking...' : 'Listen'}</span>
              </button>

              <button
                onClick={() => {
                  if (isSpeaking) {
                    window.speechSynthesis.cancel()
                    setIsSpeaking(false)
                  }
                  setResponse(null)
                }}
                className="text-slate-400 hover:text-slate-600 text-xs flex items-center p-1"
                aria-label="Close"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
              </button>
            </div>
          </div>
          <p className="text-xs md:text-sm text-slate-800 leading-relaxed font-medium">
            {response}
          </p>
        </div>
      )}
    </div>
  )
}
