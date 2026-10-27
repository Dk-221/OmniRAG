'use client'

import React, { useState, useMemo } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  ArrowUpRight,
  CandlestickChart,
  Check,
  ChevronRight,
  Cloud,
  Code2,
  Copy,
  ExternalLink,
  LineChart as LineChartIcon,
  Newspaper,
  Sun,
  Table as TableIcon,
  Terminal,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import type { Artifact } from '@/lib/types'
import { FloatingCandleChart } from '@/components/FloatingCandleChart'

const PALETTE = ['#33a852', '#f39b2f', '#29a9c7', '#9bcb55', '#a855f7', '#ec4899']

function parseCleanNumber(val: any): number | null {
  if (val === null || val === undefined) return null
  if (typeof val === 'number') return isNaN(val) ? null : val
  if (typeof val === 'string') {
    const cleaned = val.replace(/[^0-9.-]/g, '')
    const num = parseFloat(cleaned)
    return isNaN(num) ? null : num
  }
  return null
}

function formatYTick(val: number) {
  if (val === undefined || val === null || isNaN(val)) return ''
  if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
  if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(1)}k`
  if (Math.abs(val) < 10 && !Number.isInteger(val)) return val.toFixed(2)
  return String(val)
}

function ChartArtifact({
  data,
  copied,
  onCopy,
}: {
  data: any
  copied: boolean
  onCopy: (text: string) => void
}) {
  const chartType = (data.chart_type || 'line').toLowerCase()
  const title = data.title || 'Data Chart'
  const labels: string[] = data.labels || []
  const series: any[] = data.series || []
  const candles = data.candles

  const isStockLike =
    chartType === 'candle' ||
    chartType === 'candlestick' ||
    Boolean(candles) ||
    /stock|price|ticker|aapl|reliance|nifty|sensex|nasdaq|crypto|btc|eth/i.test(title)

  const [mode, setMode] = useState<'candle' | 'line'>(() => {
    return isStockLike ? 'candle' : 'line'
  })

  const isCandleView = isStockLike && mode === 'candle'

  // Normalize series to ensure robust keys and numeric values
  const normalizedSeries = useMemo(() => {
    if (!Array.isArray(series)) return []
    if (series.length > 0 && typeof series[0] === 'number') {
      return [{
        name: 'Value',
        data: (series as unknown as any[]).map(parseCleanNumber),
      }]
    }
    return series.map((s: any, idx: number) => {
      const sName = String(s?.name || `Series ${idx + 1}`).trim()
      const rawData = Array.isArray(s?.data) ? s.data : []
      return {
        name: sName,
        data: rawData.map(parseCleanNumber),
      }
    })
  }, [series])

  const chartData = useMemo(() => {
    return labels.map((label, idx) => {
      const entry: Record<string, any> = { label: String(label) }
      normalizedSeries.forEach((s) => {
        entry[s.name] = s.data[idx] !== undefined ? s.data[idx] : null
      })
      return entry
    })
  }, [labels, normalizedSeries])

  return (
    <div className="artifact chart-artifact">
      <div className="artifact-head">
        <div>
          <span className="eyebrow">
            {isCandleView ? (
              <>
                <CandlestickChart size={12} /> FLOATING CANDLES ARTIFACT
              </>
            ) : (
              <>
                <LineChartIcon size={12} /> {chartType.toUpperCase()} ARTIFACT
              </>
            )}
          </span>
          <h4>{title}</h4>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {isStockLike && (
            <div
              style={{
                display: 'inline-flex',
                background: 'var(--panel-2)',
                padding: '2px',
                borderRadius: '6px',
                border: '1px solid var(--line)',
                gap: 2,
              }}
            >
              <button
                type="button"
                onClick={() => setMode('candle')}
                style={{
                  fontSize: 10,
                  padding: '2px 8px',
                  borderRadius: 4,
                  border: 'none',
                  background: mode === 'candle' ? 'var(--green)' : 'transparent',
                  color: mode === 'candle' ? '#fff' : 'var(--muted)',
                  cursor: 'pointer',
                  fontWeight: mode === 'candle' ? 700 : 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 0.15s',
                }}
                title="View Floating Candlesticks"
              >
                <CandlestickChart size={11} /> Candles
              </button>
              <button
                type="button"
                onClick={() => setMode('line')}
                style={{
                  fontSize: 10,
                  padding: '2px 8px',
                  borderRadius: 4,
                  border: 'none',
                  background: mode === 'line' ? 'var(--green)' : 'transparent',
                  color: mode === 'line' ? '#fff' : 'var(--muted)',
                  cursor: 'pointer',
                  fontWeight: mode === 'line' ? 700 : 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  transition: 'all 0.15s',
                }}
                title="View Line Chart"
              >
                <LineChartIcon size={11} /> Line
              </button>
            </div>
          )}

          <button
            type="button"
            className="artifact-action"
            onClick={() => onCopy(JSON.stringify(candles || chartData, null, 2))}
            title="Copy chart data JSON"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'JSON'}</span>
          </button>
        </div>
      </div>

      {isCandleView ? (
        <div style={{ padding: '6px 4px 4px' }}>
          <FloatingCandleChart
            candles={candles}
            labels={labels}
            series={normalizedSeries as any}
            title={title}
          />
        </div>
      ) : (
        <div className="chart-wrap" style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'bar' ? (
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="var(--line-soft)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={formatYTick} tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)', borderRadius: 8, fontSize: 11 }}
                  formatter={(val: any) => [typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2)) : val, '']}
                />
                {normalizedSeries.length > 1 && <Legend wrapperStyle={{ fontSize: 10, paddingTop: 6 }} />}
                {normalizedSeries.map((s, i) => (
                  <Bar key={s.name} dataKey={s.name} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} />
                ))}
              </BarChart>
            ) : chartType === 'area' ? (
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  {normalizedSeries.map((s, i) => (
                    <linearGradient key={s.name} id={`grad-${i}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={PALETTE[i % PALETTE.length]} stopOpacity={0.0} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke="var(--line-soft)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <YAxis
                  domain={['auto', 'auto']}
                  tickFormatter={formatYTick}
                  tick={{ fontSize: 10, fill: 'var(--muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)', borderRadius: 8, fontSize: 11 }}
                  formatter={(val: any) => [typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2)) : val, '']}
                />
                {normalizedSeries.length > 1 && <Legend wrapperStyle={{ fontSize: 10, paddingTop: 6 }} />}
                {normalizedSeries.map((s, i) => (
                  <Area
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={PALETTE[i % PALETTE.length]}
                    fill={`url(#grad-${i})`}
                    strokeWidth={2}
                  />
                ))}
              </AreaChart>
            ) : chartType === 'pie' ? (
              <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                <Tooltip
                  contentStyle={{ background: '#fff', border: '1px solid #dbe4dc', borderRadius: 8, fontSize: 11 }}
                  formatter={(val: any) => [typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2)) : val, '']}
                />
                <Legend wrapperStyle={{ fontSize: 10, paddingTop: 6 }} />
                <Pie
                  data={labels.map((l, i) => ({
                    name: l,
                    value: normalizedSeries[0]?.data?.[i] ?? 0,
                  }))}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ name, percent }) => `${name} (${((percent || 0) * 100).toFixed(0)}%)`}
                >
                  {labels.map((_, i) => (
                    <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                  ))}
                </Pie>
              </PieChart>
            ) : (
              <LineChart data={chartData} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 4" stroke="var(--line-soft)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'var(--muted)' }} axisLine={false} tickLine={false} />
                <YAxis
                  domain={['auto', 'auto']}
                  tickFormatter={formatYTick}
                  tick={{ fontSize: 10, fill: 'var(--muted)' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)', borderRadius: 8, fontSize: 11 }}
                  formatter={(val: any) => [typeof val === 'number' ? (Number.isInteger(val) ? val.toLocaleString() : val.toFixed(2)) : val, '']}
                />
                {normalizedSeries.length > 1 && <Legend wrapperStyle={{ fontSize: 10, paddingTop: 6 }} />}
                {normalizedSeries.map((s, i) => (
                  <Line
                    key={s.name}
                    type="monotone"
                    dataKey={s.name}
                    stroke={PALETTE[i % PALETTE.length]}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  const [copied, setCopied] = useState(false)
  if (!artifact) return null

  let kind = artifact.kind
  const data = artifact.data

  // Intelligent fallback: if data has chart or table payload, resolve properly
  if (kind === 'data' || !kind) {
    if (data?.chart_type || (data?.labels && data?.series)) {
      kind = 'chart'
    } else if (data?.columns && data?.rows) {
      kind = 'table'
    }
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // ── Chart Artifact ────────────────────────────────────────────────────────
  if (kind === 'chart' && data) {
    return <ChartArtifact data={data} copied={copied} onCopy={handleCopy} />
  }

  // ── Table Artifact ────────────────────────────────────────────────────────
  if (kind === 'table' && data) {
    const columns: string[] = data.columns || []
    const rows: (string | number)[][] = data.rows || []

    const copyCsv = () => {
      const csvContent = [
        columns.join(','),
        ...rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')),
      ].join('\n')
      handleCopy(csvContent)
    }

    return (
      <div className="artifact table-artifact">
        <div className="artifact-head">
          <div>
            <span className="eyebrow">
              <TableIcon size={12} /> DATA TABLE
            </span>
            <h4>
              Query Results <small style={{ color: 'var(--muted)', fontWeight: 400 }}>({rows.length} rows)</small>
            </h4>
          </div>
          <button className="artifact-action" onClick={copyCsv} title="Copy as CSV">
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'CSV'}</span>
          </button>
        </div>

        <div style={{ overflowX: 'auto', marginTop: 10, maxHeight: 260 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ background: 'var(--panel-2)', borderBottom: '1px solid var(--line)' }}>
                {columns.map((col, i) => (
                  <th key={i} style={{ padding: '6px 10px', textAlign: 'left', fontWeight: 600, color: 'var(--text)' }}>
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr
                  key={rIdx}
                  style={{
                    borderBottom: '1px solid var(--line-soft)',
                    background: rIdx % 2 === 0 ? 'transparent' : 'rgba(0,0,0,0.015)',
                  }}
                >
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} style={{ padding: '6px 10px', color: 'var(--text)' }}>
                      {cell !== null && cell !== undefined ? String(cell) : '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  // ── Stock Artifact ────────────────────────────────────────────────────────
  if (kind === 'stock' && data) {
    const isUp = (data.change_pct ?? 0) >= 0
    return (
      <div className="artifact stock-artifact">
        <div className="artifact-head">
          <div>
            <span className="eyebrow">MARKET SNAPSHOT</span>
            <h4>{data.ticker}</h4>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 11,
              fontWeight: 700,
              color: isUp ? 'var(--green)' : 'var(--red)',
              background: isUp ? 'var(--green-soft)' : '#fde8e8',
              padding: '3px 8px',
              borderRadius: 6,
            }}
          >
            {isUp ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {data.change_pct !== null ? `${data.change_pct > 0 ? '+' : ''}${data.change_pct.toFixed(2)}%` : 'N/A'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
          <span style={{ fontSize: 24, fontWeight: 800, color: 'var(--text)' }}>
            {data.currency} {data.price !== null ? data.price.toLocaleString() : 'N/A'}
          </span>
        </div>

        {(data.day_low || data.day_high) && (
          <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 8, display: 'flex', gap: 14 }}>
            <span>Day Low: <b>{data.day_low ?? 'N/A'}</b></span>
            <span>Day High: <b>{data.day_high ?? 'N/A'}</b></span>
          </div>
        )}
      </div>
    )
  }

  // ── Weather Artifact ──────────────────────────────────────────────────────
  if (kind === 'weather' && data) {
    return (
      <div className="artifact weather-artifact">
        <div className="artifact-head">
          <div>
            <span className="eyebrow">WEATHER REPORT</span>
            <h4>{data.city}</h4>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700 }}>
            <Sun size={17} style={{ color: 'var(--orange)' }} />
            <span>{data.current_temp !== null ? `${data.current_temp}°C` : 'N/A'}</span>
          </div>
        </div>
        <p style={{ fontSize: 11, color: 'var(--muted)', margin: '4px 0 10px' }}>{data.condition}</p>

        {data.forecast && data.forecast.length > 0 && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${data.forecast.length}, 1fr)`,
              gap: 8,
              borderTop: '1px solid var(--line-soft)',
              paddingTop: 10,
            }}
          >
            {data.forecast.map((f: any, i: number) => (
              <div
                key={i}
                style={{
                  background: 'var(--panel-2)',
                  padding: '6px 8px',
                  borderRadius: 6,
                  textAlign: 'center',
                  fontSize: 10,
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--muted)', fontSize: 9 }}>{f.day}</div>
                <div style={{ margin: '4px 0', fontWeight: 700, color: 'var(--text)' }}>
                  {f.max}° / {f.min}°
                </div>
                <div style={{ color: 'var(--faint)', fontSize: 8 }}>{f.condition}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── News Artifact ─────────────────────────────────────────────────────────
  if (kind === 'news' && data && data.items) {
    return (
      <div className="artifact news-artifact">
        <div className="artifact-head">
          <div>
            <span className="eyebrow">
              <Newspaper size={12} /> SIGNAL RADAR
            </span>
            <h4>Breaking Coverage ({data.items.length})</h4>
          </div>
        </div>
        <div style={{ marginTop: 6 }}>
          {data.items.map((item: any, i: number) => (
            <a
              key={i}
              className="news-row"
              href={item.url || '#'}
              target="_blank"
              rel="noreferrer"
            >
              <div className="news-signal" />
              <div>
                <b>{item.title}</b>
                <small>
                  {item.source} {item.published ? `· ${item.published}` : ''}
                </small>
              </div>
              <ArrowUpRight size={14} style={{ flex: 'none', color: 'var(--muted)' }} />
            </a>
          ))}
        </div>
      </div>
    )
  }

  // ── Code Artifact ─────────────────────────────────────────────────────────
  if (kind === 'code' && data) {
    return (
      <div className="artifact code-artifact">
        <div className="artifact-head">
          <div>
            <span className="eyebrow">
              <Terminal size={12} /> PYTHON SANDBOX EXECUTION
            </span>
            <h4>Script & Standard Output</h4>
          </div>
          <button className="artifact-action" onClick={() => handleCopy(data.code || '')} title="Copy code">
            {copied ? <Check size={12} /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Code'}</span>
          </button>
        </div>

        {data.code && (
          <pre
            style={{
              background: '#1a241e',
              color: '#d4ecd8',
              padding: 10,
              borderRadius: 6,
              fontSize: 10,
              overflowX: 'auto',
              maxWidth: '100%',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              overflowWrap: 'anywhere',
              marginTop: 8,
              fontFamily: "'DM Mono', monospace",
            }}
          >
            <code>{data.code}</code>
          </pre>
        )}

        {data.stdout && (
          <div style={{ marginTop: 8, maxWidth: '100%' }}>
            <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--muted)', fontFamily: "'DM Mono', monospace" }}>
              STDOUT:
            </span>
            <pre
              style={{
                background: 'var(--panel-2)',
                color: 'var(--text)',
                padding: '8px 10px',
                borderRadius: 6,
                fontSize: 10,
                marginTop: 3,
                border: '1px solid var(--line)',
                fontFamily: "'DM Mono', monospace",
                maxWidth: '100%',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
                overflowX: 'auto',
              }}
            >
              {data.stdout}
            </pre>
          </div>
        )}

        {data.error && (
          <div
            style={{
              marginTop: 8,
              padding: 8,
              background: '#fde8e8',
              color: '#9b1c1c',
              borderRadius: 6,
              fontSize: 10,
              maxWidth: '100%',
              wordBreak: 'break-word',
              overflowWrap: 'anywhere',
            }}
          >
            <b>Execution Error:</b> {data.error}
          </div>
        )}
      </div>
    )
  }

  return null
}
