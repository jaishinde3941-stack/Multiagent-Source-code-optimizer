import { useRef } from 'react'
import Editor from '@monaco-editor/react'
import { FileCode, Trash2, Copy, Check } from 'lucide-react'
import { useState } from 'react'

const LANGUAGES = [
  { value: 'cpp',    label: 'C++',    monaco: 'cpp'        },
  { value: 'c',      label: 'C',      monaco: 'c'          },
  { value: 'python', label: 'Python', monaco: 'python'     },
  { value: 'java',   label: 'Java',   monaco: 'java'       },
  { value: 'go',     label: 'Go',     monaco: 'go'         },
]

const MONACO_LIGHT_THEME = {
  base: 'vs',
  inherit: true,
  rules: [
    { token: 'comment',    foreground: '6B7280', fontStyle: 'italic' },
    { token: 'keyword',    foreground: '2563EB', fontStyle: 'bold'   },
    { token: 'string',     foreground: '16A34A'                       },
    { token: 'number',     foreground: 'D97706'                       },
    { token: 'type',       foreground: '7C3AED'                       },
    { token: 'function',   foreground: '0891B2'                       },
    { token: 'identifier', foreground: '1E293B'                       },
  ],
  colors: {
    'editor.background':           '#FAFBFF',
    'editor.foreground':           '#1E293B',
    'editorLineNumber.foreground': '#CBD5E1',
    'editorLineNumber.activeForeground': '#2563EB',
    'editor.lineHighlightBackground': '#EEF2FF',
    'editor.selectionBackground':  '#DBEAFE',
    'editorCursor.foreground':     '#2563EB',
    'editorIndentGuide.background':'#E2E8F0',
    'editorIndentGuide.activeBackground': '#93C5FD',
    'scrollbarSlider.background':  '#D1D9F0',
    'scrollbarSlider.hoverBackground': '#93C5FD',
  },
}

const MONACO_DARK_THEME = {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment',    foreground: '475569', fontStyle: 'italic' },
    { token: 'keyword',    foreground: '60A5FA', fontStyle: 'bold'   },
    { token: 'string',     foreground: '4ADE80'                       },
    { token: 'number',     foreground: 'FCD34D'                       },
    { token: 'type',       foreground: 'A78BFA'                       },
    { token: 'function',   foreground: '22D3EE'                       },
    { token: 'identifier', foreground: 'E2E8F6'                       },
  ],
  colors: {
    'editor.background':           '#0C1220',
    'editor.foreground':           '#E2E8F6',
    'editorLineNumber.foreground': '#1E2D4A',
    'editorLineNumber.activeForeground': '#3B82F6',
    'editor.lineHighlightBackground': '#111929',
    'editor.selectionBackground':  '#1E3A5F',
    'editorCursor.foreground':     '#3B82F6',
    'editorIndentGuide.background':'#1E2D4A',
    'editorIndentGuide.activeBackground': '#1D4ED8',
    'scrollbarSlider.background':  '#1E2D4A',
    'scrollbarSlider.hoverBackground': '#1D4ED8',
  },
}

export default function CodeEditor({ code, setCode, language, setLanguage, theme }) {
  const editorRef       = useRef(null)
  const [copied, setCopied] = useState(false)

  const monacoLang = LANGUAGES.find(l => l.value === language)?.monaco ?? 'cpp'
  const monacoThemeName = theme === 'dark' ? 'compiler-dark' : 'compiler-light'

  function handleEditorMount(editor, monaco) {
    editorRef.current = editor

    monaco.editor.defineTheme('compiler-light', MONACO_LIGHT_THEME)
    monaco.editor.defineTheme('compiler-dark',  MONACO_DARK_THEME)
    monaco.editor.setTheme(monacoThemeName)
  }

  function handleEditorWillMount(monaco) {
    monaco.editor.defineTheme('compiler-light', MONACO_LIGHT_THEME)
    monaco.editor.defineTheme('compiler-dark',  MONACO_DARK_THEME)
  }

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  function handleClear() {
    setCode('')
    editorRef.current?.focus()
  }

  return (
    <>
      <div className="pane-header">
        <FileCode size={14} strokeWidth={2} style={{ color: 'var(--primary)' }} />
        <span className="pane-title">Source Code</span>

        <div className="pane-actions">
          {/* Language selector */}
          <select
            className="lang-select"
            value={language}
            onChange={e => setLanguage(e.target.value)}
            aria-label="Select language"
          >
            {LANGUAGES.map(l => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>

          {/* Copy */}
          <button className="icon-btn" onClick={handleCopy} title="Copy code">
            {copied ? <Check size={13} strokeWidth={2.5} style={{ color: 'var(--accent-green)' }} /> : <Copy size={13} strokeWidth={2} />}
          </button>

          {/* Clear */}
          <button className="icon-btn" onClick={handleClear} title="Clear editor">
            <Trash2 size={13} strokeWidth={2} />
          </button>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Editor
          height="100%"
          language={monacoLang}
          value={code}
          onChange={val => setCode(val ?? '')}
          theme={monacoThemeName}
          beforeMount={handleEditorWillMount}
          onMount={handleEditorMount}
          options={{
            fontSize:             13,
            fontFamily:           "'JetBrains Mono', 'Fira Code', monospace",
            fontLigatures:        true,
            lineHeight:           1.7,
            minimap:              { enabled: true, scale: 0.8 },
            scrollBeyondLastLine: false,
            wordWrap:             'on',
            padding:              { top: 14, bottom: 14 },
            renderLineHighlight:  'line',
            smoothScrolling:      true,
            cursorBlinking:       'smooth',
            cursorSmoothCaretAnimation: 'on',
            bracketPairColorization: { enabled: true },
            guides: {
              bracketPairs: true,
              indentation:  true,
            },
            suggest: { showWords: true },
            renderWhitespace: 'selection',
            roundedSelection: true,
            scrollbar: {
              verticalScrollbarSize:   8,
              horizontalScrollbarSize: 8,
            },
          }}
        />
      </div>
    </>
  )
}
