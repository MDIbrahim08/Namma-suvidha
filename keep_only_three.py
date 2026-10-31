with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Replace the control card to only keep the pure 3 pills: Map, List, Filters
old_pattern = r'\{/\* Minimal Unified Glass Card[\s\S]*?\{/\* Geolocation Error Banner \*/\}'

new_minimal_bar = '''{/* Clean Minimal Controls: Map, List, Filters */}
        <div className="flex items-center justify-center my-2">
          <div className="inline-flex p-1 bg-white/90 backdrop-blur-md rounded-full text-xs font-bold text-slate-700 border border-slate-200/80 shadow-sm">
            <button
              type="button"
              onClick={() => setActiveView('map')}
              className={`px-4 py-1.5 rounded-full flex items-center gap-1.5 transition-all ${
                activeView === 'map'
                  ? 'bg-[#123C3A] text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <span className="material-symbols-outlined text-[17px]">map</span>
              <span>Map</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveView('list')}
              className={`px-4 py-1.5 rounded-full flex items-center gap-1.5 transition-all ${
                activeView === 'list'
                  ? 'bg-[#123C3A] text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <span className="material-symbols-outlined text-[17px]">format_list_bulleted</span>
              <span>List ({filteredToilets.length})</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveView('filters')}
              className={`px-4 py-1.5 rounded-full flex items-center gap-1.5 transition-all ${
                activeView === 'filters'
                  ? 'bg-[#123C3A] text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <span className="material-symbols-outlined text-[17px]">tune</span>
              <span>Filters {activeFilterCount > 0 ? `(${activeFilterCount})` : ''}</span>
            </button>
          </div>
        </div>

        {/* Geolocation Error Banner */}'''

text, count = re.subn(old_pattern, new_minimal_bar, text, count=1)
if count > 0:
    with open('frontend/src/features/citizen/pages/CitizenHome.tsx', 'w', encoding='utf-8') as f:
        f.write(text)
    print('SUCCESS KEPT ONLY MAP, LIST, FILTERS')
else:
    print('PATTERN NOT MATCHED')
