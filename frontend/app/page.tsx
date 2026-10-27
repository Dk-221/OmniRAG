'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Brain,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock3,
  Code2,
  Copy,
  Database,
  ExternalLink,
  FileText,
  FolderOpen,
  Globe2,
  Info,
  LineChart,
  Loader2,
  Menu,
  MoreHorizontal,
  Newspaper,
  Paperclip,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
  Settings2,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Sun,
  Moon,
  Table2,
  Trash2,
  Upload,
  X,
  Zap,
} from 'lucide-react'

import {
  API_BASE,
  fetchDatasets,
  fetchDocuments,
  fetchHealth,
  fetchMemories,
  fetchTools,
  uploadDataset,
  uploadDocument,
  reindexDocuments,
  deleteMemory,
  streamChat,
} from '@/lib/api'

import type {
  ChatMessage,
  DatasetItem,
  DocumentItem,
  HealthInfo,
  MemoryItem,
  SourceItem,
  Tool,
  ToolCategory,
  TraceItem,
  VerificationResult,
} from '@/lib/types'

import { ArtifactView } from '@/components/ArtifactView'
import { PlanCard } from '@/components/PlanCard'
import { MarkdownContent } from '@/components/MarkdownContent'
import { DocumentViewerModal } from '@/components/DocumentViewerModal'
import { SettingsModal } from '@/components/SettingsModal'
import { ToolInspectorModal } from '@/components/ToolInspectorModal'

const EXAMPLES = [
  'Compare AAPL and RELIANCE.NS over 6 months and chart it',
  'Summarize this YouTube video: https://youtu.be/demo',
  'Latest arXiv papers on agentic RAG',
  'Convert 5000 INR to USD and show the BTC price',
  "What's the weather and air quality in Rajkot today?",
  'Read this article and give me 5 key points: https://example.com',
  'Analyze my uploaded CSV: average by category as a bar chart',
  'Write Python to compute compound interest for 10 years and plot it',
]

function Logo({ theme = 'dark' }: { theme?: 'light' | 'dark' }) {
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png'
  return (
    <div className="flex items-center gap-2.5">
      <div className="logo-mark">
        <img src={logoSrc} alt="OmniRag" className="logo-img" />
      </div>
      <div>
        <div className="brand-name">
          Omni<span>Rag</span>
        </div>
        <div className="brand-sub">RESEARCH CONSOLE</div>
      </div>
    </div>
  )
}

function IconButton({
  label,
  children,
  onClick,
  active,
}: {
  label: string
  children: React.ReactNode
  onClick?: () => void
  active?: boolean
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`icon-button ${active ? 'active' : ''}`}
    >
      {children}
    </button>
  )
}

function ToolIconByCategory({ category }: { category: ToolCategory | string }) {
  switch (category) {
    case 'finance':
      return <LineChart size={14} />
    case 'web':
      return <Globe2 size={14} />
    case 'data':
      return <Table2 size={14} />
    case 'code':
      return <Code2 size={14} />
    case 'knowledge':
      return <BookOpen size={14} />
    default:
      return <Zap size={14} />
  }
}

export default function Page() {
  // Navigation & Modals
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [traceOpen, setTraceOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [toolInspectorOpen, setToolInspectorOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<ToolCategory | null>(null)
  const [docModal, setDocModal] = useState<{ open: boolean; filename: string; page: number }>({
    open: false,
    filename: '',
    page: 1,
  })

  // Theme State ('light' | 'dark')
  const [theme, setTheme] = useState<'light' | 'dark'>('dark')

  useEffect(() => {
    try {
      const saved = localStorage.getItem('omnirag-theme') as 'light' | 'dark' | null
      if (saved === 'light' || saved === 'dark') {
        setTheme(saved)
        document.documentElement.setAttribute('data-theme', saved)
      } else {
        setTheme('dark')
        document.documentElement.setAttribute('data-theme', 'dark')
      }
    } catch {
      document.documentElement.setAttribute('data-theme', 'dark')
    }
  }, [])

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark'
      try {
        localStorage.setItem('omnirag-theme', next)
      } catch {}
      document.documentElement.setAttribute('data-theme', next)
      const iconLink = document.querySelector("link[rel*='icon']") as HTMLLinkElement
      if (iconLink) {
        iconLink.href = next === 'dark' ? '/logo-dark.png' : '/logo-light.png'
      }
      return next
    })
  }

  // Live Backend Data
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [tools, setTools] = useState<Tool[]>([])
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [memories, setMemories] = useState<MemoryItem[]>([])
  const [loadingInitial, setLoadingInitial] = useState(true)

  // Status & Notifications
  const [reindexing, setReindexing] = useState(false)
  const [uploadingDoc, setUploadingDoc] = useState(false)
  const [uploadingData, setUploadingData] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null)

  // Chat & Stream State
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [generating, setGenerating] = useState(false)
  const [traceItems, setTraceItems] = useState<TraceItem[]>([])

  const docInputRef = useRef<HTMLInputElement>(null)
  const dataInputRef = useRef<HTMLInputElement>(null)
  const composerInputRef = useRef<HTMLTextAreaElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(timer)
  }, [toast])

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type })
  }, [])

  // Initial Data Fetching from Live Backend
  const refreshAll = useCallback(async () => {
    try {
      const [h, t, d, f, m] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchTools().catch(() => []),
        fetchDocuments().catch(() => []),
        fetchDatasets().catch(() => []),
        fetchMemories().catch(() => []),
      ])
      if (h) setHealth(h)
      if (t?.length) setTools(t)
      if (d) setDocuments(d)
      if (f) setDatasets(f)
      if (m) setMemories(m)
    } finally {
      setLoadingInitial(false)
    }
  }, [])

  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  // Scroll chat to bottom on new events
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, generating])

  // Handlers for File Uploads
  const handleDocUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploadingDoc(true)
    showToast(`Uploading ${files[0].name}...`, 'info')
    try {
      const result = await uploadDocument(files[0])
      showToast(`Indexed "${result.filename}" (${result.chunks} chunks)`, 'success')
      const updatedDocs = await fetchDocuments().catch(() => [])
      setDocuments(updatedDocs)
      const updatedHealth = await fetchHealth().catch(() => null)
      if (updatedHealth) setHealth(updatedHealth)
    } catch (err: any) {
      showToast(err.message || 'Upload failed', 'error')
    } finally {
      setUploadingDoc(false)
      if (docInputRef.current) docInputRef.current.value = ''
    }
  }

  const handleDatasetUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    setUploadingData(true)
    showToast(`Uploading dataset ${files[0].name}...`, 'info')
    try {
      const result = await uploadDataset(files[0])
      showToast(`Uploaded dataset "${result.filename}" (${result.size_bytes} bytes)`, 'success')
      const updatedDatasets = await fetchDatasets().catch(() => [])
      setDatasets(updatedDatasets)
    } catch (err: any) {
      showToast(err.message || 'Dataset upload failed', 'error')
    } finally {
      setUploadingData(false)
      if (dataInputRef.current) dataInputRef.current.value = ''
    }
  }

  const handleReindex = async () => {
    setReindexing(true)
    showToast('Re-indexing all knowledge base documents...', 'info')
    try {
      const res = await reindexDocuments()
      showToast(`Re-indexed ${res.documents} files (${res.chunks} total chunks)`, 'success')
      const [updatedDocs, updatedHealth] = await Promise.all([
        fetchDocuments().catch(() => []),
        fetchHealth().catch(() => null),
      ])
      setDocuments(updatedDocs)
      if (updatedHealth) setHealth(updatedHealth)
    } catch (err: any) {
      showToast(err.message || 'Re-indexing failed', 'error')
    } finally {
      setReindexing(false)
    }
  }

  const handleDeleteMemory = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      await deleteMemory(id)
      setMemories(prev => prev.filter(m => m.id !== id))
      showToast('Memory forgotten', 'info')
    } catch (err: any) {
      showToast(err.message || 'Failed to delete memory', 'error')
    }
  }

  // Open Citation
  const handleOpenCitation = (source: SourceItem) => {
    if (source.type === 'memory' || source.title === 'Stored Memory' || source.ref === 'Memory Store') {
      showToast('Source: Persistent Long-Term Memory', 'info')
      return
    }
    if (source.page !== undefined && source.ref) {
      setDocModal({
        open: true,
        filename: source.ref,
        page: source.page,
      })
    } else if (source.ref?.startsWith('http')) {
      window.open(source.ref, '_blank', 'noreferrer')
    } else if (source.title) {
      // Look up document by title or ref
      setDocModal({
        open: true,
        filename: source.ref || source.title,
        page: 1,
      })
    }
  }

  // Stop current generation
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setGenerating(false)
    showToast('Generation cancelled', 'info')
  }

  // Clear conversation
  const handleClear = () => {
    handleStop()
    setMessages([])
    setTraceItems([])
    setInput('')
    showToast('Conversation cleared', 'info')
  }

  // Ask prompt handler
  const handleSend = async (textToSend?: string) => {
    const query = (textToSend ?? input).trim()
    if (!query || generating) return

    setInput('')
    if (composerInputRef.current) {
      composerInputRef.current.style.height = 'auto'
    }

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      createdAt: new Date(),
    }

    const assistantMsgId = `asst-${Date.now()}`
    const assistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      toolCalls: [],
      artifacts: [],
      createdAt: new Date(),
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setGenerating(true)

    // Build history for backend
    const historyPayload = messages.map(m => ({
      role: m.role,
      content: m.content,
    }))

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    // Add query start to trace
    setTraceItems(prev => [
      ...prev,
      {
        id: `query-${Date.now()}`,
        kind: 'plan',
        title: 'Query dispatched',
        detail: query,
        status: 'running',
      },
    ])

    await streamChat(
      query,
      historyPayload,
      (event: any) => {
        const evtType = event.type || event.event
        const evtData = event.data !== undefined ? event.data : event

        if (evtType === 'plan') {
          const rawSteps = evtData.steps || []
          const steps = rawSteps.map((s: any, idx: number) => {
            const stepText =
              typeof s === 'string'
                ? s
                : typeof s?.text === 'string'
                ? s.text
                : typeof s?.description === 'string'
                ? s.description
                : JSON.stringify(s)
            const stepId = typeof s?.id === 'number' ? s.id : idx + 1
            return {
              id: stepId,
              text: stepText,
              status: idx === 0 ? ('running' as const) : ('pending' as const),
            }
          })
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, plan: { steps } } : m
            )
          )
          setTraceItems(prev => [
            ...prev,
            {
              id: `plan-${Date.now()}`,
              kind: 'plan',
              title: 'Multi-step plan generated',
              detail: `${steps.length} coordinated steps`,
              status: 'done',
            },
          ])
        } else if (evtType === 'plan_step') {
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantMsgId || !m.plan) return m
              const steps = m.plan.steps.map(s => {
                if (s.id === evtData.step) {
                  return {
                    ...s,
                    status: (evtData.status === 'running' ? 'running' : 'done') as any,
                  }
                }
                return s
              })
              return { ...m, plan: { steps } }
            })
          )
        } else if (evtType === 'tool_call') {
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantMsgId) return m
              const existing = m.toolCalls || []
              return {
                ...m,
                toolCalls: [
                  ...existing,
                  {
                    id: evtData.id,
                    name: evtData.name,
                    args: evtData.args || {},
                    status: 'running',
                    startTime: Date.now(),
                  },
                ],
              }
            })
          )
          setTraceItems(prev => [
            ...prev,
            {
              id: `tool-${evtData.id}-${Date.now()}`,
              kind: 'tool',
              title: `Tool: ${evtData.name}`,
              detail: JSON.stringify(evtData.args || {}),
              status: 'running',
            },
          ])
        } else if (evtType === 'tool_result') {
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantMsgId) return m
              const existing = m.toolCalls || []
              const idx = existing.findIndex(t => t.id === evtData.id)
              if (idx >= 0) {
                const updated = [...existing]
                const dur = updated[idx].startTime
                  ? `${((Date.now() - updated[idx].startTime!) / 1000).toFixed(1)}s`
                  : '1.1s'
                updated[idx] = {
                  ...updated[idx],
                  ok: evtData.ok,
                  summary: evtData.summary,
                  status: 'done',
                  duration: dur,
                }
                return { ...m, toolCalls: updated }
              }
              return m
            })
          )
          setTraceItems(prev => [
            ...prev,
            {
              id: `res-${evtData.id}-${Date.now()}`,
              kind: 'tool',
              title: `Result: ${evtData.name}`,
              detail: evtData.summary || (evtData.ok ? 'Success' : 'Error'),
              status: 'done',
            },
          ])
        } else if (evtType === 'artifact') {
          const kind = event.kind || evtData.kind || (evtData.chart_type ? 'chart' : 'data')
          const tool_call_id = event.tool_call_id || evtData.tool_call_id || `call-${Date.now()}`
          const artData = event.kind && event.data ? event.data : (evtData.data || evtData)
          const art = {
            kind,
            tool_call_id,
            data: artData,
          }
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantMsgId) return m
              const existing = m.artifacts || []
              return { ...m, artifacts: [...existing, art] }
            })
          )
          setTraceItems(prev => [
            ...prev,
            {
              id: `art-${Date.now()}`,
              kind: 'artifact',
              title: `Artifact: ${art.kind}`,
              detail: art.data?.title || `${art.kind} payload received`,
              status: 'done',
            },
          ])
        } else if (evtType === 'token') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, content: m.content + (evtData.text || '') } : m
            )
          )
        } else if (evtType === 'sources') {
          const rawItems = evtData.items || evtData.sources || []
          const mapped: SourceItem[] = rawItems.map((s: any) => ({
            type: s.type || 'web',
            title: s.title || s.ref || 'Source',
            ref: s.ref || s.url || '',
            page: s.page,
          }))
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId ? { ...m, sources: mapped } : m
            )
          )
        } else if (evtType === 'verification') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    verification: {
                      verdict: evtData.verdict,
                      notes: evtData.notes,
                    },
                  }
                : m
            )
          )
          setTraceItems(prev => [
            ...prev,
            {
              id: `verif-${Date.now()}`,
              kind: 'check',
              title: `Self-check: ${evtData.verdict}`,
              detail: evtData.notes || 'Verification finished',
              status: 'done',
            },
          ])
        } else if (evtType === 'error') {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content:
                      m.content + `\n\n> ⚠️ **Error:** ${evtData.message || 'An error occurred during agent processing.'}`,
                  }
                : m
            )
          )
          showToast(evtData.message || 'Stream error', 'error')
        } else if (evtType === 'done') {
          setGenerating(false)
          setMessages(prev =>
            prev.map(m => {
              if (m.id !== assistantMsgId || !m.plan) return m
              const steps = m.plan.steps.map(s => ({ ...s, status: 'done' as const }))
              return { ...m, plan: { steps } }
            })
          )
        }
      },
      (err: Error) => {
        setGenerating(false)
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content:
                    m.content ||
                    `*Could not connect to the backend agent at \`${API_BASE}\`. Ensure the FastAPI server is running on port 8000.*`,
                }
              : m
          )
        )
        showToast(err.message, 'error')
      },
      abortController.signal
    )
    setGenerating(false)
  }

  // Copy assistant response
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    showToast('Copied response to clipboard', 'success')
  }

  // Regenerate last response
  const handleRegenerate = () => {
    const lastUserMsg = [...messages].reverse().find(m => m.role === 'user')
    if (lastUserMsg) {
      handleSend(lastUserMsg.content)
    }
  }

  // Group tools by category
  const toolGroups: [ToolCategory, string][] = [
    ['knowledge', 'Knowledge'],
    ['web', 'Web intelligence'],
    ['finance', 'Finance'],
    ['data', 'Data'],
    ['code', 'Code'],
    ['utility', 'Utility'],
  ]

  // Sidebar accordion open state
  const [openAccordions, setOpenAccordions] = useState<string[]>([
    'knowledge',
    'datasets',
    'memory',
    'tools',
  ])
  const toggleAccordion = (key: string) =>
    setOpenAccordions(v => (v.includes(key) ? v.filter(x => x !== key) : [...v, key]))

  return (
    <div className="app-shell">
      {/* Hidden File Inputs */}
      <input
        ref={docInputRef}
        type="file"
        accept=".pdf,.txt,.md,.json"
        className="hidden"
        style={{ display: 'none' }}
        onChange={handleDocUpload}
      />
      <input
        ref={dataInputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.json"
        className="hidden"
        style={{ display: 'none' }}
        onChange={handleDatasetUpload}
      />

      {/* Floating Status Notification Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -20, scale: 0.95 }}
            className={`fixed top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2.5 px-4 py-2.5 rounded-lg shadow-xl text-xs font-medium border backdrop-blur-md ${
              toast.type === 'error'
                ? 'bg-red-950/90 text-red-200 border-red-800'
                : toast.type === 'success'
                ? 'bg-emerald-950/90 text-emerald-200 border-emerald-800'
                : 'bg-stone-900/90 text-stone-100 border-stone-700'
            }`}
          >
            {toast.type === 'error' ? (
              <ShieldAlert size={14} className="text-red-400" />
            ) : toast.type === 'success' ? (
              <Check size={14} className="text-emerald-400" />
            ) : (
              <Info size={14} className="text-sky-400" />
            )}
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="ml-2 opacity-60 hover:opacity-100 text-current"
            >
              <X size={13} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Top Navigation Bar */}
      <header className="topbar">
        <div className="mobile-logo">
          <IconButton label="Open sidebar" onClick={() => setSidebarOpen(true)}>
            <Menu size={18} />
          </IconButton>
          <Logo theme={theme} />
        </div>
        <div className="desktop-brand">
          {sidebarCollapsed && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <IconButton
                label="Expand sidebar"
                onClick={() => setSidebarCollapsed(false)}
              >
                <Menu size={18} />
              </IconButton>
              <Logo theme={theme} />
            </div>
          )}
        </div>

        <div className="topbar-actions">
          {/* Status Badge -> opens SettingsModal */}
          <button
            className="status-badge"
            onClick={() => setSettingsOpen(true)}
            title="Backend status & configuration (Click to inspect)"
          >
            <span
              className={`online-dot ${health?.status === 'ok' ? '' : 'bg-amber-400'}`}
              style={{
                backgroundColor: health?.status === 'ok' ? '#33a852' : '#f59e0b',
              }}
            />
            <span>{health?.provider || 'groq'}</span>
            <span className="status-divider">·</span>
            <span className="mono">{health?.model?.split('/')[1] || health?.model || 'gpt-oss-20b'}</span>
            <ChevronDown size={13} />
          </button>

          {/* Live Trace Button */}
          <button
            className={`trace-toggle ${traceOpen ? 'bg-emerald-50 text-emerald-800 border-emerald-300' : ''}`}
            onClick={() => setTraceOpen(v => !v)}
            title="Toggle Live Agent Trace Panel"
          >
            <Activity size={15} />
            <span>Live trace</span>
            <span className="trace-pulse" />
          </button>

          {/* Theme Toggle Button */}
          <button
            className="theme-toggle-badge"
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            {theme === 'dark' ? (
              <>
                <Moon size={13} style={{ color: '#4ade80' }} />
                <span>Dark</span>
              </>
            ) : (
              <>
                <Sun size={13} style={{ color: '#f59e0b' }} />
                <span>Light</span>
              </>
            )}
          </button>

          {/* Clear Chat Button */}
          <IconButton label="Clear chat" onClick={handleClear}>
            <Trash2 size={16} />
          </IconButton>

          {/* Settings Button */}
          <IconButton label="Settings" onClick={() => setSettingsOpen(true)}>
            <Settings2 size={16} />
          </IconButton>
        </div>
      </header>

      {/* Mobile Backdrop Overlay - rendered outside workspace grid so it never shifts columns */}
      <div
        className={`mobile-overlay ${sidebarOpen || traceOpen ? 'visible' : ''}`}
        onClick={() => {
          setSidebarOpen(false)
          setTraceOpen(false)
        }}
      />

      {/* Main Workspace Layout */}
      <div
        className={`workspace ${traceOpen ? 'has-trace' : ''} ${
          sidebarCollapsed ? 'sidebar-collapsed' : ''
        }`}
      >
        {/* Sidebar */}
        <div
          className={`sidebar-wrap ${sidebarOpen ? 'mobile-open' : ''} ${
            sidebarCollapsed ? 'collapsed' : ''
          }`}
        >
          <aside className="sidebar">
            <div className="sidebar-top">
              <Logo theme={theme} />
              <IconButton
                label="Collapse sidebar"
                onClick={() => {
                  setSidebarOpen(false)
                  setSidebarCollapsed(true)
                }}
              >
                <ChevronLeft size={16} />
              </IconButton>
            </div>

            <div className="sidebar-scroll">
              {/* Knowledge Base Accordion */}
              <div className="accordion-block">
                <button
                  className="accordion-head"
                  onClick={() => toggleAccordion('knowledge')}
                >
                  <span>
                    <BookOpen size={15} />
                    Knowledge base
                  </span>
                  <ChevronDown
                    className={openAccordions.includes('knowledge') ? 'rotate' : ''}
                    size={15}
                  />
                </button>

                {openAccordions.includes('knowledge') && (
                  <div className="accordion-content">
                    {/* Dropzone with real click-to-upload */}
                    <div
                      className="dropzone cursor-pointer hover:border-emerald-400 transition"
                      onClick={() => docInputRef.current?.click()}
                    >
                      {uploadingDoc ? (
                        <>
                          <Loader2 size={16} className="animate-spin text-emerald-400" />
                          <span>Uploading & chunking...</span>
                        </>
                      ) : (
                        <>
                          <Upload size={16} />
                          <span>Drop PDF, TXT or MD</span>
                          <small>Click to browse files</small>
                        </>
                      )}
                    </div>

                    {/* Document List with click-to-view */}
                    {documents.length === 0 ? (
                      <div className="text-[10px] text-stone-400 py-2 text-center">
                        No documents indexed yet.
                      </div>
                    ) : (
                      documents.map(d => (
                        <div
                          className="file-row cursor-pointer hover:bg-white/10 rounded px-1.5 transition"
                          key={d.filename}
                          onClick={() =>
                            setDocModal({
                              open: true,
                              filename: d.filename,
                              page: 1,
                            })
                          }
                          title="Click to view document content"
                        >
                          <FileText size={15} />
                          <div>
                            <b>{d.filename}</b>
                            <small>{d.chunks} chunks indexed</small>
                          </div>
                          <EyeIcon />
                        </div>
                      ))
                    )}

                    {/* Re-index Button */}
                    <button
                      className="quiet-button hover:text-emerald-300 w-full"
                      onClick={handleReindex}
                      disabled={reindexing}
                    >
                      <RefreshCw
                        size={13}
                        className={reindexing ? 'animate-spin' : ''}
                      />
                      {reindexing ? 'Re-indexing store...' : 'Re-index all'}
                    </button>
                  </div>
                )}
              </div>

              {/* Datasets Accordion */}
              <div className="accordion-block">
                <button
                  className="accordion-head"
                  onClick={() => toggleAccordion('datasets')}
                >
                  <span>
                    <Database size={15} />
                    Datasets <em>{datasets.length}</em>
                  </span>
                  <ChevronDown
                    className={openAccordions.includes('datasets') ? 'rotate' : ''}
                    size={15}
                  />
                </button>

                {openAccordions.includes('datasets') && (
                  <div className="accordion-content">
                    {/* Dataset Upload Trigger */}
                    <div
                      className="dataset-strip cursor-pointer hover:bg-white/10 transition"
                      onClick={() => dataInputRef.current?.click()}
                      title="Upload CSV or XLSX for DuckDB analysis"
                    >
                      {uploadingData ? (
                        <>
                          <Loader2 size={16} className="animate-spin text-emerald-400" />
                          <span>Uploading table...</span>
                        </>
                      ) : (
                        <>
                          <BarChart3 size={16} />
                          <span>Upload CSV / XLSX</span>
                          <Plus size={15} />
                        </>
                      )}
                    </div>

                    {/* Datasets List */}
                    {datasets.map(f => (
                      <div
                        className="file-row cursor-pointer hover:bg-white/10 rounded px-1.5 transition"
                        key={f.filename}
                        onClick={() => {
                          setInput(
                            `Analyze dataset "${f.filename}" using duckdb_query: show summary stats and generate a chart`
                          )
                          composerInputRef.current?.focus()
                          setSidebarOpen(false)
                        }}
                        title="Click to query this dataset"
                      >
                        <Table2 size={15} />
                        <div>
                          <b>{f.filename}</b>
                          <small>
                            {(f.size_bytes / 1024).toFixed(1)} KB · Ready for DuckDB
                          </small>
                        </div>
                        <ArrowUpRight size={13} className="opacity-60" />
                      </div>
                    ))}

                    {/* Ask about this data Button */}
                    <button
                      className="accent-button"
                      onClick={() => {
                        const target = datasets[0]?.filename || 'your uploaded CSV'
                        setInput(
                          `Analyze dataset "${target}" with duckdb_query: compute average by category and chart it as a bar chart`
                        )
                        composerInputRef.current?.focus()
                        setSidebarOpen(false)
                      }}
                    >
                      <Sparkles size={13} /> Ask about this data
                    </button>
                  </div>
                )}
              </div>

              {/* Memory Accordion */}
              <div className="accordion-block">
                <button
                  className="accordion-head"
                  onClick={() => toggleAccordion('memory')}
                >
                  <span>
                    <Brain size={15} />
                    Memory <em>{memories.length}</em>
                  </span>
                  <ChevronDown
                    className={openAccordions.includes('memory') ? 'rotate' : ''}
                    size={15}
                  />
                </button>

                {openAccordions.includes('memory') && (
                  <div className="accordion-content">
                    <p className="memory-hint">
                      Tell OmniRag in chat: <strong>&quot;remember that ...&quot;</strong>
                    </p>

                    {memories.length === 0 ? (
                      <div className="text-[10px] text-stone-400 py-2 text-center">
                        No memories saved yet.
                      </div>
                    ) : (
                      memories.map(m => (
                        <div className="memory-row group" key={m.id}>
                          <span title={m.fact}>{m.fact}</span>
                          <button
                            onClick={e => handleDeleteMemory(m.id, e)}
                            title="Delete memory"
                            className="text-stone-400 hover:text-red-400 p-1 transition"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* Tools Directory Accordion */}
              <div className="accordion-block tools-block">
                <button
                  className="accordion-head"
                  onClick={() => toggleAccordion('tools')}
                >
                  <span>
                    <Zap size={15} />
                    Tools <em>{tools.length || 20}</em>
                  </span>
                  <ChevronDown
                    className={openAccordions.includes('tools') ? 'rotate' : ''}
                    size={15}
                  />
                </button>

                {openAccordions.includes('tools') && (
                  <div className="tool-orbit">
                    {toolGroups.map(([key, label]) => {
                      const count = tools.filter(t => t.category === key).length
                      return (
                        <div
                          className={`orbit-node ${key} cursor-pointer hover:bg-white/10 transition`}
                          key={key}
                          onClick={() => {
                            setSelectedCategory(key)
                            setToolInspectorOpen(true)
                          }}
                          title={`View ${label} tools`}
                        >
                          <span className="node-dot" />
                          <div>
                            <b>{label}</b>
                            <small>
                              {count || (key === 'finance' ? 3 : key === 'web' ? 4 : key === 'knowledge' ? 3 : 2)}{' '}
                              tools active
                            </small>
                          </div>
                          <ArrowUpRight size={13} />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Sidebar Footer */}
            <div className="sidebar-footer">
              <div
                className="user-chip cursor-pointer hover:bg-white/10 rounded p-1 transition"
                onClick={() => setSettingsOpen(true)}
                title="Workspace settings"
              >
                <div className="avatar">OR</div>
                <span>OmniRag Workspace</span>
                <Settings2 size={14} />
              </div>
            </div>
          </aside>
        </div>

        {/* Center Chat Panel */}
        <main className="chat-panel">
          {/* Chat Toolbar */}
          <div className="chat-toolbar">
            <div>
              <span className="live-label">
                <span className="online-dot" /> SYSTEM READY
              </span>
              <span className="toolbar-divider" />
              <span className="muted">
                {tools.length || 20} tools · {documents.length} docs · Groq {health?.model || 'gpt-oss-20b'}
              </span>
            </div>
            <div className="chat-toolbar-actions">
              <button
                onClick={() => setToolInspectorOpen(true)}
                className="hover:text-emerald-700 transition"
              >
                <Zap size={14} /> Tools ({tools.length || 20})
              </button>
              <button
                onClick={() => setTraceOpen(v => !v)}
                className="hover:text-emerald-700 transition"
              >
                <Activity size={14} /> Trace
              </button>
              <button
                onClick={handleClear}
                className="hover:text-red-600 transition"
              >
                <Trash2 size={14} /> Clear
              </button>
            </div>
          </div>

          {/* Chat Messages Scroll */}
          <div className="chat-scroll">
            {messages.length === 0 ? (
              <EmptyState onAsk={q => handleSend(q)} theme={theme} />
            ) : (
              <div className="space-y-6">
                {messages.map(msg => (
                  <div key={msg.id} className="chat-message-row">
                    {msg.role === 'user' ? (
                      <div className="user-message">
                        <div className="user-bubble">{msg.content}</div>
                      </div>
                    ) : (
                      <div className="assistant-message">
                        <div className="message-mark">
                          <img
                            src={theme === 'dark' ? '/logo-dark.png' : '/logo-light.png'}
                            alt="OmniRag"
                            className="message-mark-img"
                          />
                        </div>
                        <div className="message-content">
                          {/* Live Query Plan */}
                          {msg.plan && <PlanCard plan={msg.plan} />}

                          {/* Parallel Tool Call Badges */}
                          {msg.toolCalls && msg.toolCalls.length > 0 && (
                            <div className="trace-inline">
                              {msg.toolCalls.map(tc => (
                                <div
                                  key={tc.id}
                                  className={`tool-call ${getCategoryTone(tc.name)}`}
                                >
                                  <div className="tool-icon">
                                    <ToolIconByName name={tc.name} />
                                  </div>
                                  <div className="tool-copy">
                                    <div>
                                      <b>{tc.name}</b>
                                      {tc.status === 'running' ? (
                                        <span className="running-label">
                                          <Loader2 size={11} className="animate-spin" /> running
                                        </span>
                                      ) : (
                                        <span className="success-label">
                                          <Check size={11} /> complete
                                        </span>
                                      )}
                                    </div>
                                    <small>
                                      {tc.summary || JSON.stringify(tc.args || {})}
                                    </small>
                                  </div>
                                  {tc.duration && (
                                    <span className="duration">
                                      <Clock3 size={12} /> {tc.duration}
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Streamed Assistant Content */}
                          {msg.content ? (
                            <MarkdownContent content={msg.content} />
                          ) : generating ? (
                            <div className="flex items-center gap-2 text-stone-400 text-xs py-2">
                              <Loader2 size={14} className="animate-spin text-emerald-600" />
                              <span>Thinking & executing tools...</span>
                            </div>
                          ) : null}

                          {/* Interactive Artifacts */}
                          {msg.artifacts && msg.artifacts.length > 0 && (
                            <div className="artifacts-container my-3 space-y-3">
                              {msg.artifacts.map((art, idx) => (
                                <ArtifactView key={`${art.tool_call_id}-${idx}`} artifact={art} />
                              ))}
                            </div>
                          )}

                          {/* Sources & Verification Footer */}
                          {(msg.sources?.length || msg.verification) && (
                            <div className="message-footer">
                              {msg.sources && msg.sources.length > 0 && (
                                <div className="source-chips">
                                  {msg.sources.map((src, i) => (
                                    <button
                                      key={i}
                                      onClick={() => handleOpenCitation(src)}
                                      title={src.ref || src.title}
                                      className="hover:border-emerald-500 transition"
                                    >
                                      {src.type === 'memory' || src.title === 'Stored Memory' ? (
                                        <>
                                          <Brain size={12} className="text-emerald-400" /> Stored Memory
                                        </>
                                      ) : src.page !== undefined ? (
                                        <>
                                          <FileText size={12} /> {src.ref || src.title}{' '}
                                          <span>p. {src.page}</span>
                                        </>
                                      ) : (
                                        <>
                                          <Globe2 size={12} /> {src.title || src.ref}
                                        </>
                                      )}
                                    </button>
                                  ))}
                                </div>
                              )}

                              {msg.verification && (
                                <div
                                  className={`verify-badge ${msg.verification.verdict || 'supported'}`}
                                  title={msg.verification.notes}
                                >
                                  {msg.verification.verdict === 'supported' ? (
                                    <ShieldCheck size={13} />
                                  ) : (
                                    <ShieldAlert size={13} />
                                  )}
                                  <span className="capitalize">{msg.verification.verdict}</span>
                                  <CircleHelp size={12} className="opacity-60" />
                                </div>
                              )}
                            </div>
                          )}

                          {/* Actions: Copy & Regenerate */}
                          <div className="message-tools">
                            <button
                              onClick={() => handleCopy(msg.content)}
                              className="hover:text-emerald-700 transition"
                            >
                              <Copy size={13} /> Copy
                            </button>
                            <button
                              onClick={handleRegenerate}
                              className="hover:text-emerald-700 transition"
                            >
                              <RefreshCw size={13} /> Regenerate
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={chatBottomRef} />
              </div>
            )}
          </div>

          {/* Chat Composer */}
          <div className="composer-shell">
            <div className="composer">
              <textarea
                ref={composerInputRef}
                value={input}
                onChange={e => {
                  setInput(e.target.value)
                  e.target.style.height = 'auto'
                  e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`
                }}
                onKeyDown={e => {
                  if (
                    e.key === 'Enter' &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing &&
                    e.keyCode !== 229
                  ) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                placeholder="Ask OmniRag anything (e.g. Compare AAPL and RELIANCE, read web page, query dataset)..."
                aria-label="Ask OmniRag anything"
                rows={1}
              />

              <div className="composer-bottom">
                <div>
                  <IconButton
                    label="Attach files (PDF, TXT, CSV, XLSX)"
                    onClick={() => docInputRef.current?.click()}
                  >
                    <Paperclip size={16} />
                  </IconButton>
                  <span className="composer-hint">Shift + Enter for new line</span>
                </div>

                {generating ? (
                  <button className="stop-button" onClick={handleStop}>
                    <Square size={13} /> Stop
                  </button>
                ) : (
                  <button
                    className="send-button"
                    onClick={() => handleSend()}
                    disabled={!input.trim()}
                  >
                    <Send size={15} />
                  </button>
                )}
              </div>
            </div>

            <div className="composer-meta">
              <span>
                <ShieldCheck size={12} /> Answers include real-time sources & verification
              </span>
              <span className="mono">
                {health?.status === 'ok' ? 'CONNECTED · GROQ CLOUD' : 'CONNECTING...'}
              </span>
            </div>
          </div>
        </main>

        {/* Live Agent Trace Panel */}
        <aside className={`trace-panel ${traceOpen ? 'trace-open' : ''}`}>
          <div className="trace-head">
            <div>
              <div className="eyebrow">
                <Activity size={12} /> LIVE AGENT TRACE
              </div>
              <h2>Working memory & routing</h2>
            </div>
            <IconButton label="Close trace" onClick={() => setTraceOpen(false)}>
              <X size={16} />
            </IconButton>
          </div>

          <div className="trace-status">
            <span className="trace-pulse" />
            {generating
              ? 'Agent is reasoning & dispatching tools...'
              : `${traceItems.length || 5} steps completed · model: ${health?.model || 'gpt-oss-20b'}`}
          </div>

          <div className="timeline">
            {traceItems.length === 0 ? (
              <>
                <div className="timeline-item done">
                  <span className="timeline-dot">
                    <Check size={11} />
                  </span>
                  <div>
                    <b>System ready</b>
                    <small>All 20 tools registered & router warm</small>
                    <time>0.0s</time>
                  </div>
                </div>
                <div className="timeline-item done">
                  <span className="timeline-dot">
                    <Check size={11} />
                  </span>
                  <div>
                    <b>ChromaDB vector store initialized</b>
                    <small>{documents.length} knowledge base documents indexed</small>
                    <time>0.1s</time>
                  </div>
                </div>
              </>
            ) : (
              traceItems.map(item => (
                <div key={item.id} className={`timeline-item ${item.status}`}>
                  <span className="timeline-dot">
                    {item.status === 'running' ? (
                      <Loader2 size={11} className="animate-spin text-emerald-600" />
                    ) : (
                      <Check size={11} />
                    )}
                  </span>
                  <div>
                    <b>{item.title}</b>
                    <small>{item.detail}</small>
                    {item.duration && <time>{item.duration}</time>}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="trace-footer">
            <button
              onClick={() => {
                const traceJson = JSON.stringify(traceItems, null, 2)
                navigator.clipboard.writeText(traceJson)
                showToast('Trace diagnostic log copied', 'success')
              }}
            >
              <FolderOpen size={14} /> Copy diagnostic trace
            </button>
          </div>
        </aside>
      </div>

      {/* Interactive Modals */}
      <DocumentViewerModal
        isOpen={docModal.open}
        filename={docModal.filename}
        initialPage={docModal.page}
        onClose={() => setDocModal(prev => ({ ...prev, open: false }))}
      />

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        health={health}
        onRefresh={refreshAll}
      />

      <ToolInspectorModal
        isOpen={toolInspectorOpen}
        tools={tools}
        initialCategory={selectedCategory}
        onClose={() => setToolInspectorOpen(false)}
        onRunExample={prompt => {
          setToolInspectorOpen(false)
          setInput(prompt)
          handleSend(prompt)
        }}
      />
    </div>
  )
}

function EyeIcon() {
  return <ArrowUpRight size={13} className="opacity-60" />
}

function EmptyState({ onAsk, theme = 'dark' }: { onAsk: (q: string) => void; theme?: 'light' | 'dark' }) {
  const logoSrc = theme === 'dark' ? '/logo-dark.png' : '/logo-light.png'
  return (
    <div className="empty-state">
      <div className="signal-ring">
        <div className="signal-core">
          <img src={logoSrc} alt="OmniRag" className="signal-logo-img" />
        </div>
      </div>
      <div className="empty-kicker">YOUR RESEARCH CO-PILOT</div>
      <h1>
        Ask once.<br />
        <em>Search everything.</em>
      </h1>
      <p>
        OmniRag orchestrates your local documents, live web intelligence, finance charts,
        and code sandboxes into one verifiable answer.
      </p>

      <div className="example-grid">
        {EXAMPLES.map((ex, i) => (
          <button key={ex} onClick={() => onAsk(ex)}>
            <span>0{i + 1}</span>
            <span className="truncate">{ex}</span>
            <ArrowUpRight size={14} />
          </button>
        ))}
      </div>
    </div>
  )
}

function getCategoryTone(toolName: string): string {
  if (toolName.includes('stock') || toolName.includes('crypto') || toolName.includes('currency') || toolName.includes('sec_edgar')) {
    return 'finance'
  }
  if (toolName.includes('web') || toolName.includes('news') || toolName.includes('arxiv') || toolName.includes('wikipedia') || toolName.includes('youtube')) {
    return 'web'
  }
  if (toolName.includes('duckdb') || toolName.includes('dataset')) {
    return 'data'
  }
  if (toolName.includes('python')) {
    return 'code'
  }
  return 'knowledge'
}

function ToolIconByName({ name }: { name: string }) {
  if (name.includes('stock') || name.includes('crypto') || name.includes('currency')) {
    return <LineChart size={14} />
  }
  if (name.includes('news')) {
    return <Newspaper size={14} />
  }
  if (name.includes('web') || name.includes('read_url')) {
    return <Globe2 size={14} />
  }
  if (name.includes('duckdb')) {
    return <Table2 size={14} />
  }
  if (name.includes('python')) {
    return <Code2 size={14} />
  }
  if (name.includes('knowledge') || name.includes('doc')) {
    return <BookOpen size={14} />
  }
  return <Zap size={14} />
}
