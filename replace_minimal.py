with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_block = """        {/* Minimal Unified Glass Card */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-2xl p-3 sm:p-4 shadow-[0_8px_30px_rgba(0,0,0,0.06)] flex flex-col gap-3">
          {/* Top: AI Assistant & Voice Input */}
          <CivicAiChatBar
            placeholder="Ask Namma AI: 'Find accessible toilets near Indiranagar' or use voice..."
            onSubmit={handleAiQuery}
          />

          {/* Integrated Minimal Control Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
            {/* View Switcher */}
            <div className="inline-flex p-1 bg-slate-100/90 rounded-full text-xs font-semibold text-slate-700">
              <button
                type="button"
                onClick={() => setActiveView('map')}
                className={`px-3 py-1 rounded-full flex items-center gap-1 transition-all ${activeView === 'map' ? 'bg-[#123C3A] text-white shadow-xs' : 'hover:text-slate-900'}`}
              >
                <span className="material-symbols-outlined text-[15px]">map</span>
                <span>Map</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveView('list')}
                className={`px-3 py-1 rounded-full flex items-center gap-1 transition-all ${activeView === 'list' ? 'bg-[#123C3A] text-white shadow-xs' : 'hover:text-slate-900'}`}
              >
                <span className="material-symbols-outlined text-[15px]">format_list_bulleted</span>
                <span>List ({filteredToilets.length})</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveView('filters')}
                className={`px-3 py-1 rounded-full flex items-center gap-1 transition-all ${activeView === 'filters' ? 'bg-[#123C3A] text-white shadow-xs' : 'hover:text-slate-900'}`}
              >
                <span className="material-symbols-outlined text-[15px]">tune</span>
                <span>Filters {activeFilterCount > 0 ? `(${activeFilterCount})` : ''}</span>
              </button>
            </div>

            {/* Quick Radius Pills */}
            <div className="flex items-center gap-1 overflow-x-auto no-scrollbar py-0.5">
              {RADIUS_OPTIONS.map((opt) => {
                const isActive = radiusMeters === opt.meters
                return (
                  <button
                    key={opt.meters}
                    type="button"
                    onClick={() => void handleRadiusChange(opt.meters)}
                    disabled={isBusy}
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${isActive ? 'bg-emerald-700 text-white shadow-xs' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`}
                  >
                    {opt.label}
                  </button>
                )
              })}
            </div>

            {/* Live GPS Action Button */}
            <button
              type="button"
              onClick={() => void handleDetectAndDiscover()}
              disabled={isBusy}
              className="px-4 py-1.5 rounded-full bg-[#123C3A] hover:bg-[#003244] text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition-all active:scale-95 disabled:opacity-50 ml-auto"
            >
              <span className="material-symbols-outlined text-[16px]">my_location</span>
              <span>{isLocating ? 'Detecting…' : userLocation ? 'Refresh GPS' : 'Use My Current Location'}</span>
            </button>
          </div>
        </div>

        {/* Geolocation Error Banner */}
        {locationError && (
          <div
            role="alert"
            className="bg-red-50 text-red-700 rounded-xl p-3 flex items-center justify-between text-xs border border-red-200"
          >
            <span>Location error: {locationError.message}</span>
            <button
              type="button"
              onClick={() => void handleDetectAndDiscover()}
              className="px-2.5 py-1 bg-red-600 text-white rounded-lg font-bold ml-2"
            >
              Retry
            </button>
          </div>
        )}

"""

final_lines = lines[:376] + [new_block] + lines[612:]

with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print('SUCCESSFULLY REPLACED WITH MINIMAL DESIGN')
