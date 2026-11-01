import { Sun, Moon, Play, Square, Cpu, Search, Zap, ShieldCheck, GitBranch, Brain, Code2 } from 'lucide-react'

const MODES = [
  { id: 'pipeline', label: 'Full Pipeline', icon: GitBranch },
  { id: 'analyze',  label: 'Analyze',       icon: Search    },
  { id: 'optimize', label: 'Optimize',       icon: Zap       },
  { id: 'verify',   label: 'Verify',         icon: ShieldCheck },
]

export default function Header({
  mode, setMode,
  useLlm, setUseLlm,
  theme, toggleTheme,
  ollamaStatus,
  isRunning, onRun,
}) {
  /* Ollama status indicator */
  const dotClass = ollamaStatus?.checking
    ? 'checking'
    : ollamaStatus?.available
      ? 'online'
      : 'offline'

  const dotLabel = ollamaStatus?.checking
    ? 'Checking…'
    : ollamaStatus?.available
      ? `LLM Online (${ollamaStatus.model ?? 'unknown'})`
      : 'LLM Offline'

  return (
    <header className="header">
      {/* Logo */}
      <div className="header-logo">
        <div className="logo-icon">
          <Cpu size={17} strokeWidth={2.5} />
        </div>
        <div>
          <div className="logo-text">CompilerAI</div>
          <div className="logo-sub">Optimization Studio</div>
        </div>
      </div>

      <div className="header-divider" />

      {/* Mode tabs */}
      <nav className="mode-tabs" aria-label="Pipeline mode">
        {MODES.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`mode-tab${mode === id ? ' active' : ''}`}
            onClick={() => setMode(id)}
            aria-pressed={mode === id}
          >
            <Icon size={13} strokeWidth={2} />
            {label}
          </button>
        ))}
      </nav>

      <div className="header-divider" />

      {/* LLM toggle */}
      <div className="llm-toggle" role="group" aria-label="Inference mode">
        <button
          className={`llm-btn${useLlm ? ' active' : ''}`}
          onClick={() => setUseLlm(true)}
          title="Use Qwen 2.5 Coder via Ollama for enhanced analysis"
        >
          <Brain size={12} strokeWidth={2} />
          LLM
        </button>
        <button
          className={`llm-btn${!useLlm ? ' active' : ''}`}
          onClick={() => setUseLlm(false)}
          title="Use rule-based heuristics and regex patterns only"
        >
          <Code2 size={12} strokeWidth={2} />
          Heuristics
        </button>
      </div>

      <div className="header-spacer" />

      {/* Ollama status */}
      <div className="ollama-status" title={ollamaStatus?.base_url ?? ''}>
        <span className={`status-dot ${dotClass}`} />
        {dotLabel}
      </div>

      {/* Theme toggle */}
      <button
        className="theme-toggle"
        onClick={toggleTheme}
        aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        title={theme === 'light' ? 'Dark mode (black & blue)' : 'Light mode (white & blue)'}
      >
        {theme === 'light' ? <Moon size={15} strokeWidth={2} /> : <Sun size={15} strokeWidth={2} />}
      </button>

      {/* Run / Stop button */}
      <button
        className={`run-btn${isRunning ? ' running' : ''}`}
        onClick={onRun}
        aria-label={isRunning ? 'Stop pipeline' : 'Run pipeline'}
      >
        {isRunning ? (
          <>
            <span className="spinner" />
            Stop
          </>
        ) : (
          <>
            <Play size={13} strokeWidth={2.5} fill="white" />
            Run
          </>
        )}
      </button>
    </header>
  )
}
