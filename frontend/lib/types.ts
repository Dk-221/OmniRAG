export type ToolCategory = 'knowledge' | 'web' | 'finance' | 'data' | 'code' | 'utility'

export type Tool = {
  name: string
  description: string
  category: ToolCategory
}

export type DocumentItem = {
  filename: string
  chunks: number
}

export type DatasetItem = {
  filename: string
  size_bytes: number
}

export type MemoryItem = {
  id: string
  fact: string
  created_at?: string
}

export type HealthInfo = {
  status: string
  provider: string
  model: string
  fallback_model: string
  documents_indexed: number
  api_key_configured: boolean
  verify_answers?: boolean
  router_max_tools?: number
  message?: string | null
}

export type CandleItem = {
  date: string
  open: number
  high: number
  low: number
  close: number
  raw_open?: number
  raw_high?: number
  raw_low?: number
  raw_close?: number
}

export type ChartArtifactData = {
  chart_type: 'bar' | 'line' | 'pie' | 'area' | 'candle' | 'candlestick'
  title: string
  labels: string[]
  series: { name: string; data: number[] }[]
  candles?: Record<string, CandleItem[]>
}

export type TableArtifactData = {
  columns: string[]
  rows: (string | number)[][]
}

export type StockArtifactData = {
  ticker: string
  price: number | null
  change_pct: number | null
  day_low: number | null
  day_high: number | null
  currency: string
}

export type WeatherArtifactData = {
  city: string
  current_temp: number | null
  condition: string
  forecast: { day: string; min: number | null; max: number | null; condition: string }[]
}

export type NewsArtifactData = {
  items: { title: string; source: string; published: string; url: string }[]
}

export type CodeArtifactData = {
  code: string
  stdout: string
  error?: string | null
}

export type Artifact = {
  kind: 'chart' | 'table' | 'stock' | 'weather' | 'news' | 'code' | string
  tool_call_id: string
  data: any
}

export type PlanStep = {
  id: number
  text: string
  status: 'pending' | 'running' | 'done'
}

export type ToolCallRecord = {
  id: string
  name: string
  args: Record<string, any>
  summary?: string
  ok?: boolean
  artifact_ref?: string
  status: 'running' | 'done' | 'error'
  duration?: string
  startTime?: number
}

export type SourceItem = {
  type: string
  title: string
  ref: string
  page?: number
}

export type VerificationResult = {
  verdict: 'supported' | 'partial' | 'unsupported'
  notes: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  plan?: { steps: PlanStep[] }
  toolCalls?: ToolCallRecord[]
  artifacts?: Artifact[]
  sources?: SourceItem[]
  verification?: VerificationResult
  createdAt: Date
}

export type TraceItem = {
  id: string
  kind: 'router' | 'plan' | 'tool' | 'check' | 'artifact'
  title: string
  detail: string
  status: 'done' | 'running' | 'pending'
  duration?: string
}
