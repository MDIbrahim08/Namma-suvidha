import React, { useState } from 'react'

export interface CivicAiChatBarProps {
  onSubmit: (prompt: string) => Promise<string>
  placeholder?: string
}

export default function CivicAiChatBar({ onSubmit, placeholder }: CivicAiChatBarProps) {
  const [query, setQuery] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [response, setResponse] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const text = query.trim()
    if (!text || isLoading) return
    setIsLoading(true)
    setResponse(null)
    try {
      const reply = await onSubmit(text)
      setResponse(reply)
    } catch {
      setResponse('Unable to query civic database right now. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="w-full my-3 flex flex-col items-center">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl bg-white/75 backdrop-blur-xl border border-white/80 rounded-full px-4 py-2 shadow-[0_8px_30px_rgba(0,0,0,0.08)] flex items-center gap-3 transition-all hover:bg-white/90 focus-within:ring-2 focus-within:ring-[#006398]/50 focus-within:border-white"
      >
        <span className="material-symbols-outlined text-[#006398] text-[22px] flex-shrink-0">
          auto_awesome
        </span>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            placeholder ||
            "Ask Namma AI: 'Find accessible toilets near Indiranagar' or 'Western toilets near me'…"
          }
          className="flex-1 bg-transparent text-[#131b2e] placeholder:text-slate-500 text-sm md:text-base outline-none font-medium"
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
        <div className="w-full max-w-2xl mt-3 p-4 bg-white/85 backdrop-blur-xl border border-white/90 rounded-2xl shadow-[0_8px_30px_rgba(0,0,0,0.06)] animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center justify-between gap-2 mb-1.5 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs font-bold text-[#006398] uppercase tracking-wider">
                Namma Suvidha AI Response
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

