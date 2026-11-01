import { useEffect, useRef } from 'react'
import { Terminal, ArrowRight } from 'lucide-react'

/* ── Helpers ──────────────────────────────────────────────────────────────── */

function agentKey(sender = '') {
  const s = sender.toLowerCase()
  if (s.includes('analysis'))     return 'analysis'
  if (s.includes('optimization')) return 'optimization'
  if (s.includes('optim'))        return 'optimization'
  if (s.includes('verification')) return 'verification'
  if (s.includes('verif'))        return 'verification'
  if (s.includes('pipeline'))     return 'pipeline'
  return 'log'
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('en-GB', {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  } catch { return '' }
}

/* ── Individual terminal line renderers ──────────────────────────────────── */

function StatusLine({ data, ts }) {
  return (
    <div className="term-line">
      <span className="term-ts">{formatTime(ts)}</span>
      <span className="term-tag tag-status">INFO</span>
      <span className="term-body" style={{ color: 'var(--agent-status)' }}>
        {data?.message ?? ''}
      </span>
    </div>
  )
}

function LogLine({ data, ts }) {
  const lvl     = (data?.level ?? 'DEBUG').toUpperCase()
  const isDebug = lvl === 'DEBUG'
  const isError = lvl === 'ERROR' || lvl === 'CRITICAL'

  if (isDebug) return null  // suppress DEBUG noise by default

  return (
    <div className="term-line" style={{ opacity: isDebug ? 0.5 : 1 }}>
      <span className="term-ts">{formatTime(ts)}</span>
      <span className="term-tag tag-log">{lvl}</span>
      <span
        className="term-body"
        style={{ color: isError ? 'var(--agent-error)' : 'var(--agent-log)', fontSize: 11 }}
      >
        <span style={{ color: 'var(--text-muted)', marginRight: 6, fontSize: 10 }}>
          {data?.logger ?? ''}
        </span>
        {data?.message ?? ''}
      </span>
    </div>
  )
}

function AgentMessageLine({ data, ts }) {
  const key       = agentKey(data?.sender)
  const tagClass  = `term-tag tag-${key}`
  const typeChip  = (data?.type ?? '').toLowerCase()

  const chipStyle = {
    request:      { bg: 'rgba(59,130,246,0.10)',  color: '#3B82F6' },
    response:     { bg: 'rgba(34,197,94,0.10)',   color: '#16A34A' },
    notification: { bg: 'rgba(245,158,11,0.10)',  color: '#D97706' },
  }[typeChip] ?? { bg: 'rgba(100,116,139,0.10)', color: '#64748B' }

  const hasPayload = data?.payload_preview && Object.keys(data.payload_preview).length > 0

  return (
    <div>
      <div className="term-line">
        <span className="term-ts">{formatTime(ts)}</span>
        <span className={tagClass}>{key}</span>
        <span className="term-body">
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
            {data?.sender ?? ''}
          </span>
          <span className="term-arrow"> ──▶ </span>
          <span style={{ color: 'var(--text-secondary)' }}>{data?.receiver ?? ''}</span>
          <span
            style={{
              marginLeft: 10,
              padding: '1px 7px',
              borderRadius: 99,
              fontSize: 10,
              fontWeight: 700,
              background: chipStyle.bg,
              color: chipStyle.color,
              textTransform: 'uppercase',
              letterSpacing: '0.3px',
            }}
          >
            {typeChip}
          </span>
          {data?.msg_id && (
            <span style={{ marginLeft: 8, color: 'var(--text-muted)', fontSize: 10 }}>
              #{data.seq} id={data.msg_id}
              {data.corr_id ? ` corr=${data.corr_id}` : ''}
            </span>
          )}
        </span>
      </div>

      {hasPayload && (
        <div style={{ paddingLeft: 122 }}>
          <div className="term-payload">
            {Object.entries(data.payload_preview).map(([k, v]) => (
              <div key={k} className="term-payload-row">
                <span className="term-payload-key">{k}</span>
                <span className="term-payload-value">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ErrorLine({ data, ts }) {
  return (
    <div>
      <div className="term-line">
        <span className="term-ts">{formatTime(ts)}</span>
        <span className="term-tag tag-error">ERROR</span>
        <span className="term-body" style={{ color: 'var(--agent-error)', fontWeight: 500 }}>
          {data?.message ?? 'An unknown error occurred'}
        </span>
      </div>
      {data?.traceback && (
        <div style={{ paddingLeft: 122 }}>
          <pre style={{
            margin: '4px 0 4px 0',
            padding: '8px 12px',
            background: 'rgba(220,38,38,0.06)',
            borderLeft: '2px solid var(--agent-error)',
            borderRadius: '0 6px 6px 0',
            fontSize: 11,
            color: 'var(--agent-error)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {data.traceback}
          </pre>
        </div>
      )}
    </div>
  )
}

function CompleteLine({ data, ts }) {
  const success = data?.status === 'success'
  return (
    <div className="term-line">
      <span className="term-ts">{formatTime(ts)}</span>
      <span className={`term-tag ${success ? 'tag-analysis' : 'tag-error'}`}>
        {success ? 'DONE' : 'FAIL'}
      </span>
      <span
        className="term-body"
        style={{ color: success ? 'var(--agent-analysis)' : 'var(--agent-error)', fontWeight: 600 }}
      >
        {success ? 'Pipeline finished successfully.' : 'Pipeline finished with errors.'}
      </span>
    </div>
  )
}

/* ── Main component ──────────────────────────────────────────────────────── */

export default function OutputTerminal({ messages, isRunning }) {
  const bottomRef = useRef(null)

  /* Auto-scroll to bottom on new messages */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function renderLine(msg, idx) {
    const { type, data, ts } = msg
    switch (type) {
      case 'status':        return <StatusLine       key={idx} data={data} ts={ts} />
      case 'log':           return <LogLine          key={idx} data={data} ts={ts} />
      case 'agent_message': return <AgentMessageLine key={idx} data={data} ts={ts} />
      case 'error':         return <ErrorLine        key={idx} data={data} ts={ts} />
      case 'complete':      return <CompleteLine     key={idx} data={data} ts={ts} />
      default:              return null
    }
  }

  return (
    <>
      <div className="pane-header">
        <Terminal size={14} strokeWidth={2} style={{ color: 'var(--accent-cyan)' }} />
        <span className="pane-title">Live Output</span>
        {messages.length > 0 && (
          <span className="pane-badge">{messages.length}</span>
        )}
        {isRunning && (
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="spinner dark" />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Running…</span>
          </span>
        )}
      </div>

      <div className="terminal">
        {messages.length === 0 ? (
          <div className="terminal-empty">
            <Terminal size={32} />
            <p>Output will appear here when you run the pipeline.</p>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => renderLine(msg, i))}
            {isRunning && (
              <div className="term-line">
                <span className="term-ts" />
                <span className="cursor" />
              </div>
            )}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </>
  )
}
