import React, { useState, useRef } from 'react'
import './App.css'

type ScoreResult = any

function App() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const roleRef = useRef<HTMLTextAreaElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)

    const file = fileRef.current?.files?.[0]
    const roleDescription = roleRef.current?.value || undefined

    if (!file) {
      setError('Please select a PDF file to upload')
      return
    }

    const form = new FormData()
    form.append('file', file)
    if (roleDescription) form.append('role_description', roleDescription)

    try {
      setLoading(true)
      const resp = await fetch('http://localhost:8000/score', {
        method: 'POST',
        body: form,
      })

      if (!resp.ok) {
        const text = await resp.text()
        throw new Error(`Server error: ${resp.status} ${text}`)
      }

      const data = await resp.json()
      setResult(data.result)
    } catch (err: any) {
      setError(err.message || String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-root">
      <h1>Hiring Agent — Resume Scorer</h1>

      <form onSubmit={handleSubmit} className="upload-form">
        <label>
          Resume PDF
          <input ref={fileRef} type="file" accept="application/pdf" />
        </label>

        <label>
          Role description (optional)
          <textarea ref={roleRef} placeholder="Optional role description to help scoring" />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? 'Scoring...' : 'Upload & Score'}
        </button>
      </form>

      {loading && <div className="spinner">Processing — this may take a while...</div>}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="result">
          <h2>Result</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default App
