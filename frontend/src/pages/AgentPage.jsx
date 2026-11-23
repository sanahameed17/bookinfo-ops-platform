import { Bot, Loader2, Send, ShieldCheck, User, Wrench } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Card, ErrorState, Notice, PageHeader } from '../components/ui'
import { useApi } from '../hooks/useApi'

const EXAMPLES = [
  'Which Bookinfo Pod is using the most CPU?',
  'Which microservice has the highest memory usage?',
  'Are any Pods unhealthy?',
  'Which service has restarted containers?',
  'What is the current status of the Reviews service?',
  'Why is productpage showing high CPU usage?',
  'Compare CPU utilization of reviews-v1 and reviews-v3.',
  'Are all microservices healthy?',
  'Which Pods have failed readiness checks?',
]

function Evidence({ tools }) {
  if (!tools?.length) return <p className="mt-2 text-[11px] text-slate-400">No tool was called for this answer.</p>
  return (
    <details className="mt-2 rounded-lg border border-slate-200 bg-slate-50">
      <summary className="flex cursor-pointer items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-600">
        <Wrench className="h-3.5 w-3.5" aria-hidden="true" /> Evidence: {tools.length} tool call{tools.length > 1 ? 's' : ''} ({tools.map((t) => t.tool).join(', ')})
      </summary>
      <ol className="space-y-2 px-3 pb-3">
        {tools.map((t, i) => (
          <li key={i} className="text-xs">
            <p className="font-mono font-semibold text-slate-800">
              {i + 1}. {t.tool}({JSON.stringify(t.input)}) <span className="font-normal text-slate-400">· {t.duration_ms} ms</span>
            </p>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-900 p-2 font-mono text-[11px] text-slate-100">{t.output_preview}</pre>
          </li>
        ))}
      </ol>
    </details>
  )
}

export default function AgentPage() {
  const config = useApi(() => api.config())
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages, busy])

  async function ask(text) {
    const question = (text ?? input).trim()
    if (!question || busy) return
    setInput('')
    setError(null)
    const history = messages.slice(-6).map((m) => ({ role: m.role, content: m.content.slice(0, 3900) }))
    setMessages((m) => [...m, { role: 'user', content: question }])
    setBusy(true)
    try {
      const res = await api.chat(question, history)
      setMessages((m) => [...m, { role: 'assistant', content: res.answer, tools: res.tools_used, meta: `${res.model} · ${(res.duration_ms / 1000).toFixed(1)} s` }])
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const notConfigured = config.data && !config.data.llm_configured

  return (
    <>
      <PageHeader title="AI OpsAgent" description="Ask questions in plain language. The agent (LangChain ReAct, reused from Lab 3) answers only from read-only Kubernetes and Prometheus tools and shows the tool calls as evidence.">
        {config.data && (
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs text-slate-600 ring-1 ring-slate-200">
            <ShieldCheck className="h-4 w-4 text-emerald-600" aria-hidden="true" /> Read-only · {config.data.llm_provider} / {config.data.llm_model}
          </span>
        )}
      </PageHeader>

      {notConfigured && (
        <div className="mb-4"><Notice>The LLM is not configured. Put <code>LLM_API_KEY</code>, <code>LLM_BASE_URL</code> and <code>LLM_MODEL</code> in the <code>.env</code> file and restart the backend.</Notice></div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1fr_300px]">
        <Card bodyClass="flex h-[calc(100vh-260px)] min-h-[420px] flex-col">
          <div className="flex-1 space-y-5 overflow-y-auto p-5" aria-live="polite">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center text-slate-500">
                <Bot className="h-10 w-10 text-indigo-500" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-slate-700">Ask about pods, CPU, memory, restarts or health.</p>
                <p className="mt-1 text-xs">Pick an example on the right, or type your own question.</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className="flex gap-3">
                <span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${m.role === 'user' ? 'bg-slate-200 text-slate-700' : 'bg-indigo-600 text-white'}`}>
                  {m.role === 'user' ? <User className="h-4 w-4" aria-hidden="true" /> : <Bot className="h-4 w-4" aria-hidden="true" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-slate-500">{m.role === 'user' ? 'You' : 'OpsAgent'}{m.meta && <span className="ml-2 font-normal text-slate-400">{m.meta}</span>}</p>
                  <p className="mt-0.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-900">{m.content}</p>
                  {m.role === 'assistant' && <Evidence tools={m.tools} />}
                </div>
              </div>
            ))}
            {busy && (
              <p className="flex items-center gap-2 text-sm text-slate-500" role="status">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Agent is calling tools and thinking… (can take 10–60 s)
              </p>
            )}
            {error && <ErrorState error={error} compact />}
            <div ref={endRef} />
          </div>
          <form
            className="flex gap-2 border-t border-slate-200 p-3"
            onSubmit={(e) => {
              e.preventDefault()
              ask()
            }}
          >
            <label htmlFor="agent-input" className="sr-only">Question</label>
            <input id="agent-input" className="input flex-1" placeholder="e.g. Which pod is using the most memory?" value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} disabled={busy} />
            <button type="submit" className="btn-primary" disabled={busy || !input.trim()}>
              <Send className="h-3.5 w-3.5" aria-hidden="true" /> Ask
            </button>
          </form>
        </Card>

        <Card title="Example questions">
          <ul className="space-y-1.5">
            {EXAMPLES.map((q) => (
              <li key={q}>
                <button type="button" onClick={() => ask(q)} disabled={busy} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-xs text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50 disabled:opacity-50">
                  {q}
                </button>
              </li>
            ))}
          </ul>
          {messages.length > 0 && (
            <button type="button" className="btn-secondary mt-4 w-full justify-center" onClick={() => { setMessages([]); setError(null) }}>
              Clear conversation
            </button>
          )}
        </Card>
      </div>
    </>
  )
}
