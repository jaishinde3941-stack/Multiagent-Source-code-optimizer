import { useState, useEffect, useCallback, useRef } from 'react'
import Header from './components/Header'
import CodeEditor from './components/CodeEditor'
import OutputTerminal from './components/OutputTerminal'
import ResultsPanel from './components/ResultsPanel'
import './index.css'

const DEFAULT_CODE = `#include <stdio.h>
#include <stdlib.h>

// Example: Contains multiple issues for the analyzer to find

int globalCounter;  // uninitialized global variable

int sumArray(int* arr, int n) {
    int sum;  // uninitialized local variable
    for (int i = 0; i <= n; i++) {  // off-by-one: should be i < n
        sum += arr[i];
    }
    return sum;
}

int main() {
    int data[5] = {10, 20, 30, 40, 50};

    // Nested loops with potentially redundant computation
    int result = 0;
    for (int i = 0; i < 5; i++) {
        for (int j = 0; j < 5; j++) {
            result += data[i] * data[j];
        }
    }

    printf("Sum:     %d\\n", sumArray(data, 5));
    printf("Result:  %d\\n", result);
    printf("Counter: %d\\n", globalCounter);  // uninitialized global

    // Potential division by zero
    int divisor = 0;
    printf("Ratio: %d\\n", result / divisor);

    return 0;
}
`

export default function App() {
  const [theme,        setTheme]        = useState('light')
  const [mode,         setMode]         = useState('pipeline')
  const [language,     setLanguage]     = useState('cpp')
  const [useLlm,       setUseLlm]       = useState(true)
  const [code,         setCode]         = useState(DEFAULT_CODE)
  const [messages,     setMessages]     = useState([])
  const [results,      setResults]      = useState({
    analysis: null, optimization: null, verification: null, pipeline: null,
  })
  const [isRunning,    setIsRunning]    = useState(false)
  const [ollamaStatus, setOllamaStatus] = useState(null)

  const abortRef = useRef(null)

  /* Apply theme CSS attribute to <html> */
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  /* Health-check Ollama on mount */
  useEffect(() => {
    setOllamaStatus({ checking: true })
    fetch('/api/health')
      .then(r => r.json())
      .then(d => setOllamaStatus(d.ollama))
      .catch(() => setOllamaStatus({ available: false }))
  }, [])

  /* SSE event dispatcher */
  const handleEvent = useCallback((event) => {
    const { type, data, ts } = event

    /* Forward display-worthy events to the terminal */
    if (['status', 'log', 'agent_message', 'error', 'complete'].includes(type)) {
      setMessages(prev => [...prev, { type, data, ts }])
    }

    /* Populate structured result panels */
    if (type === 'analysis_result')     setResults(r => ({ ...r, analysis:     data }))
    if (type === 'optimization_result') setResults(r => ({ ...r, optimization: data }))
    if (type === 'verification_result') setResults(r => ({ ...r, verification: data }))
    if (type === 'pipeline_result')     setResults(r => ({ ...r, pipeline:     data }))

    if (type === 'complete' || type === 'done') setIsRunning(false)
  }, [])

  /* Run / stop handler */
  const handleRun = useCallback(async () => {
    if (isRunning) {
      abortRef.current?.abort()
      setIsRunning(false)
      return
    }

    setIsRunning(true)
    setMessages([])
    setResults({ analysis: null, optimization: null, verification: null, pipeline: null })

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/stream', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ code, mode, use_llm: useLlm, language }),
        signal:  controller.signal,
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Request failed' }))
        handleEvent({ type: 'error', data: { message: err.error }, ts: new Date().toISOString() })
        setIsRunning(false)
        return
      }

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer    = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()  // keep incomplete last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            handleEvent(event)
          } catch (_) { /* ignore malformed frames */ }
        }
      }

    } catch (err) {
      if (err.name !== 'AbortError') {
        handleEvent({
          type: 'error',
          data: { message: err.message },
          ts:   new Date().toISOString(),
        })
      }
    } finally {
      setIsRunning(false)
    }
  }, [code, mode, useLlm, language, isRunning, handleEvent])

  const toggleTheme = () => setTheme(t => t === 'light' ? 'dark' : 'light')

  /* Called by ResultsPanel when user accepts the optimized code */
  const handleAcceptCode = useCallback((optimizedCode) => {
    setCode(optimizedCode)
    /* Add a terminal confirmation message */
    setMessages(prev => [...prev, {
      type: 'status',
      data: { phase: 'accepted', message: 'Optimized code applied to editor.' },
      ts:   new Date().toISOString(),
    }])
  }, [])

  return (
    <div className="app">
      <Header
        mode={mode}        setMode={setMode}
        useLlm={useLlm}   setUseLlm={setUseLlm}
        theme={theme}      toggleTheme={toggleTheme}
        ollamaStatus={ollamaStatus}
        isRunning={isRunning}
        onRun={handleRun}
      />

      <div className="main-layout">
        <div className="editor-pane">
          <CodeEditor
            code={code}        setCode={setCode}
            language={language} setLanguage={setLanguage}
            theme={theme}
          />
        </div>

        <div className="output-pane">
          <OutputTerminal messages={messages} isRunning={isRunning} />
        </div>
      </div>

      <div className="results-section">
        <ResultsPanel results={results} onAcceptCode={handleAcceptCode} messages={messages} />
      </div>
    </div>
  )
}
