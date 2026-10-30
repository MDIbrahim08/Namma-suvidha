import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <section className="space-y-3 text-center">
      <h1 className="text-2xl font-bold">404 — Page not found</h1>
      <Link to="/" className="text-teal-700 underline">
        Back to home
      </Link>
    </section>
  )
}
