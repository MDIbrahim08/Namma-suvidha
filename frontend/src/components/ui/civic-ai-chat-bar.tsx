import React, { useState, useEffect, useRef } from 'react'
import type { SupportedLanguage } from '../../lib/api/llm'

export interface CivicAiChatBarProps {
  onSubmit: (prompt: string, language: SupportedLanguage) => Promise<string>
  placeholder?: string
}

const LANGUAGES: { code: SupportedLanguage; label: string; placeholder: string; speechLang: string }[] = [
  { code: 'en', label: 'English', placeholder: "Ask Namma AI: 'Find accessible toilets near Indiranagar' or 'Western toilets'…", speechLang: 'en-IN' },
  { code: 'kn', label: 'ಕನ್ನಡ', placeholder: "ನಮ್ಮ AI ಗೆ ಕೇಳಿ: 'ಇಂದಿರಾನಗರ ಹತ್ತಿರ ಶೌಚಾಲಯ ಹುಡುಕಿ' ಅಥವಾ 'ಗಾಲಿಕುರ್ಚಿ ಸ್ನೇಹಿ'…", speechLang: 'kn-IN' },
  { code: 'hi', label: 'हिंदी', placeholder: "नम्मा एआई से पूछें: 'इंदिरानगर के पास शौचालय' या 'वेस्टर्न टॉयलेट'…", speechLang: 'hi-IN' },
]

export default function CivicAiChatBar({ onSubmit, placeholder }: CivicAiChatBarProps) {
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [response, setResponse] = useState<string | null>(null)
  const [language, setLanguage] = useState<SupportedLanguage>('en')
  const [isListening, setIsListening] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(true)

  const recognitionRef = useRef<any>(null)
  const currentLangObj = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0]

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

    window.speechSynthesis.cancel() // clear any queue
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
      // Automatically read aloud the answer
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
    <div className="w-full my-3 flex flex-col items-center">
      {/* Language Switcher Pills */}
      <div className="flex items-center gap-1.5 mb-2 bg-white/70 backdrop-blur-md px-2 py-1 rounded-full border border-slate-200/80 shadow-xs">
        <span className="material-symbols-outlined text-[14px] text-slate-500 ml-1">translate</span>
        <span className="text-[11px] font-semibold text-slate-600 mr-1 uppercase tracking-wider">Language:</span>
        {LANGUAGES.map((lang) => (
          <button
            key={lang.code}
            type="button"
            onClick={() => {
              setLanguage(lang.code)
              if (isSpeaking) {
                window.speechSynthesis.cancel()
                setIsSpeaking(false)
              }
            }}
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
        className="w-full max-w-2xl bg-white/80 backdrop-blur-xl border border-white/90 rounded-full px-3 sm:px-4 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.08)] flex items-center gap-2 transition-all hover:bg-white/95 focus-within:ring-2 focus-within:ring-[#006398]/50 focus-within:border-white"
      >
        <span className="material-symbols-outlined text-[#006398] text-[22px] flex-shrink-0">
          auto_awesome
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder || currentLangObj.placeholder}
          className="flex-1 bg-transparent text-[#131b2e] placeholder:text-slate-400 text-sm md:text-base outline-none font-medium min-w-0"
        />

        {/* Voice Input (Microphone) Button */}
        <button
          type="button"
          onClick={toggleListening}
          aria-label={isListening ? 'Listening… Tap to cancel' : 'Voice search'}
          className={`w-9 h-9 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
            isListening
              ? 'bg-rose-600 text-white animate-pulse shadow-md'
              : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
          }`}
          title={isListening ? 'Listening to voice...' : 'Speak your query'}
        >
          <span className="material-symbols-outlined text-[19px]">
            {isListening ? 'mic' : 'mic_none'}
          </span>
        </button>

        {/* Submit Query Button */}
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

      {/* Voice Listening Active Wave Toast */}
      {isListening && (
        <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-3 py-1.5 rounded-full animate-bounce">
          <span className="material-symbols-outlined text-sm animate-spin">graphic_eq</span>
          <span>Listening in {currentLangObj.label}... Speak now</span>
        </div>
      )}

      {/* Instant Answer Bubble with Voice Read-Aloud */}
      {response && (
        <div className="w-full max-w-2xl mt-3 p-4 bg-white/95 backdrop-blur-xl border border-white/90 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between gap-2 mb-1.5 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-[#006398] uppercase tracking-wider">
                {language === 'kn' ? 'ನಮ್ಮ ಸುವಿಧಾ AI ಪ್ರತಿಕ್ರಿಯೆ' : language === 'hi' ? 'नम्मा सुविधा AI प्रतिक्रिया' : 'Namma Suvidha AI Response'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {/* Text-To-Speech Listen Button */}
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
