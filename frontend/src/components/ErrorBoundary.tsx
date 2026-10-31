import { useRouteError, isRouteErrorResponse, Link } from 'react-router-dom'

export default function ErrorBoundary() {
  const error = useRouteError()

  let errorMessage = 'An unexpected error occurred in the application.'
  if (isRouteErrorResponse(error)) {
    errorMessage = `${error.status} ${error.statusText}`
  } else if (error instanceof Error) {
    errorMessage = error.message
  }

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-center">
      <div className="w-16 h-16 rounded-full bg-red-50 text-red-600 flex items-center justify-center mb-4 border border-red-100">
        <span className="material-symbols-outlined text-3xl">error_outline</span>
      </div>
      <h2 className="text-xl font-bold text-slate-900 mb-2">Something went wrong</h2>
      <p className="text-sm text-slate-600 max-w-md mb-6 bg-slate-50 p-3 rounded-lg border border-slate-200 font-mono text-xs">
        {errorMessage}
      </p>
      <div className="flex gap-3">
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs"
        >
          Reload Page
        </button>
        <Link
          to="/"
          className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-semibold"
        >
          Go to Home
        </Link>
      </div>
    </div>
  )
}

