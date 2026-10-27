'use client'

import React, { useState } from 'react'
import {
  ArrowRight,
  BookOpen,
  Code2,
  Database,
  Globe2,
  LineChart,
  Search,
  Wrench,
  X,
  Zap,
} from 'lucide-react'
import type { Tool, ToolCategory } from '@/lib/types'

interface ToolInspectorModalProps {
  open?: boolean
  isOpen?: boolean
  onClose: () => void
  tools: Tool[]
  onSelectPrompt?: (prompt: string) => void
  onRunExample?: (prompt: string) => void
  initialCategory?: ToolCategory | null
}

const CATEGORY_ICONS: Record<ToolCategory, React.ElementType> = {
  knowledge: BookOpen,
  web: Globe2,
  finance: LineChart,
  data: Database,
  code: Code2,
  utility: Wrench,
}

const SAMPLE_PROMPTS: Record<string, string> = {
  search_knowledge_base: 'What does the document say about AI and machine learning?',
  remember: 'Remember that my favorite tech stock is Apple',
  web_search: 'What are the latest developments in generative AI today?',
  read_url: 'Read https://en.wikipedia.org/wiki/Artificial_intelligence and summarize it',
  youtube_summary: 'Summarize this YouTube video: https://www.youtube.com/watch?v=dQw4w9WgXcQ',
  wikipedia_lookup: 'Look up Wikipedia summary for Quantum Computing',
  search_papers: 'Search recent arXiv research papers on diffusion models',
  tech_news: 'What are the top trending stories on Hacker News right now?',
  get_news: 'What is the latest breaking news about space exploration?',
  get_stock_data: 'What is the current stock price and valuation of RELIANCE.NS?',
  compare_stocks: 'Compare AAPL and RELIANCE.NS over 6 months and chart it',
  currency_convert: 'Convert 1000 USD to INR and EUR',
  crypto_price: 'What is the current price of Bitcoin and Ethereum in USD and INR?',
  analyze_data: 'Analyze my uploaded dataset: show average by category',
  make_chart: 'Create a bar chart showing quarterly sales: Q1 100, Q2 150, Q3 200, Q4 250',
  run_python: 'Run Python to compute the first 20 prime numbers',
  calculate: 'Calculate the compound interest on $50,000 at 8% for 15 years',
  get_weather: 'What is the current weather and 3-day forecast in London?',
  air_quality: 'What is the air quality and AQI health advisory in New Delhi today?',
  geocode_place: 'What are the exact GPS coordinates and address of Eiffel Tower?',
}

export function ToolInspectorModal({
  open,
  isOpen,
  onClose,
  tools,
  onSelectPrompt,
  onRunExample,
  initialCategory,
}: ToolInspectorModalProps) {
  const isModalOpen = Boolean(open ?? isOpen)
  const handleSelect = onRunExample || onSelectPrompt || (() => {})

  const [activeCategory, setActiveCategory] = useState<ToolCategory | 'all'>(
    initialCategory || 'all'
  )
  const [search, setSearch] = useState('')

  React.useEffect(() => {
    if (!isModalOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isModalOpen, onClose])

  if (!isModalOpen) return null

  const categories: (ToolCategory | 'all')[] = [
    'all',
    'knowledge',
    'web',
    'finance',
    'data',
    'code',
    'utility',
  ]

  const filtered = tools.filter((t) => {
    const matchesCat = activeCategory === 'all' || t.category === activeCategory
    const matchesSearch =
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      t.description.toLowerCase().includes(search.toLowerCase())
    return matchesCat && matchesSearch
  })

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(24, 51, 29, 0.45)',
        backdropFilter: 'blur(4px)',
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 'min(92vw, 680px)',
          maxHeight: '85vh',
          background: 'var(--panel)',
          borderRadius: 12,
          border: '1px solid var(--line)',
          boxShadow: '0 20px 50px rgba(0,0,0,0.2)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--line)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <Zap size={18} style={{ color: 'var(--green)' }} />
            <div>
              <b style={{ fontSize: 14 }}>Active Tool Directory ({tools.length})</b>
              <small style={{ display: 'block', fontSize: 10, color: 'var(--muted)' }}>
                Equipped with 20 zero-cost agent tools dynamically routed per message
              </small>
            </div>
          </div>
          <button onClick={onClose} className="icon-button" aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        {/* Filter bar */}
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid var(--line-soft)',
            display: 'flex',
            gap: 10,
            flexWrap: 'wrap',
            alignItems: 'center',
            background: 'var(--panel-2)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: 'var(--panel)',
              padding: '4px 10px',
              borderRadius: 6,
              border: '1px solid var(--line)',
              flex: '1 1 180px',
            }}
          >
            <Search size={13} style={{ color: 'var(--muted)' }} />
            <input
              type="text"
              placeholder="Search tools…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ border: 0, outline: 0, fontSize: 11, background: 'transparent', width: '100%' }}
            />
          </div>

          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => setActiveCategory(c)}
                style={{
                  fontSize: 10,
                  padding: '4px 8px',
                  borderRadius: 5,
                  border: '1px solid',
                  borderColor: activeCategory === c ? 'var(--green)' : 'var(--line)',
                  background: activeCategory === c ? 'var(--green-soft)' : 'var(--panel)',
                  color: activeCategory === c ? 'var(--green-dark)' : 'var(--muted)',
                  fontWeight: activeCategory === c ? 700 : 500,
                  cursor: 'pointer',
                }}
              >
                {c.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Tools list */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.length === 0 ? (
            <div style={{ padding: 30, textAlign: 'center', color: 'var(--muted)', fontSize: 12 }}>
              No tools match your search criteria.
            </div>
          ) : (
            filtered.map((tool) => {
              const Icon = CATEGORY_ICONS[tool.category] || Wrench
              const samplePrompt = SAMPLE_PROMPTS[tool.name] || `Use ${tool.name} to answer my question`

              return (
                <div
                  key={tool.name}
                  style={{
                    padding: 12,
                    borderRadius: 8,
                    background: 'var(--panel-2)',
                    border: '1px solid var(--line)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: 12,
                  }}
                >
                  <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: 6,
                        background: 'var(--panel)',
                        border: '1px solid var(--line)',
                        display: 'grid',
                        placeItems: 'center',
                        color: 'var(--green)',
                        flex: 'none',
                        marginTop: 2,
                      }}
                    >
                      <Icon size={14} />
                    </div>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <b style={{ fontSize: 12, fontFamily: "'DM Mono', monospace", color: 'var(--text)' }}>
                          {tool.name}
                        </b>
                        <span
                          style={{
                            fontSize: 8,
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: 'var(--panel)',
                            color: 'var(--muted)',
                            border: '1px solid var(--line-soft)',
                            textTransform: 'uppercase',
                          }}
                        >
                          {tool.category}
                        </span>
                      </div>
                      <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--muted)', lineHeight: 1.4 }}>
                        {tool.description}
                      </p>
                    </div>
                  </div>

                  <button
                    className="accent-button"
                    style={{
                      width: 'auto',
                      padding: '5px 9px',
                      fontSize: 10,
                      flex: 'none',
                      whiteSpace: 'nowrap',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      marginTop: 2,
                    }}
                    onClick={() => {
                      handleSelect(samplePrompt)
                      onClose()
                    }}
                    title={`Try asking with ${tool.name}`}
                  >
                    Try prompt <ArrowRight size={11} />
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
