'use client'

import React, { useState, useMemo } from 'react'
import type { CandleItem } from '@/lib/types'

interface FloatingCandleChartProps {
  candles?: Record<string, CandleItem[]>
  labels?: string[]
  series?: { name: string; data: number[] }[]
  title?: string
}

export function FloatingCandleChart({
  candles,
  labels = [],
  series = [],
  title,
}: FloatingCandleChartProps) {
  // If explicit candles dict is passed
  const tickerKeys = useMemo(() => {
    if (candles && Object.keys(candles).length > 0) {
      return Object.keys(candles)
    }
    if (series.length > 0) {
      return series.map((s) => s.name)
    }
    return []
  }, [candles, series])

  const [activeTab, setActiveTab] = useState<string>(() => {
    if (tickerKeys.length > 1) return 'dual'
    return tickerKeys[0] || 'default'
  })

  const [hoverIdx, setHoverIdx] = useState<number | null>(null)

  // Construct candle list for each ticker
  const resolvedCandlesByTicker = useMemo(() => {
    const result: Record<string, CandleItem[]> = {}

    tickerKeys.forEach((ticker, sIdx) => {
      if (candles && candles[ticker] && candles[ticker].length > 0) {
        result[ticker] = candles[ticker]
      } else {
        // Synthesize candles from series data points
        const sData = series[sIdx]?.data || []
        const synth: CandleItem[] = sData.map((val, idx) => {
          const prev = idx > 0 ? sData[idx - 1] : val
          const open = prev
          const close = val
          const delta = Math.abs(close - open)
          const high = Math.max(open, close) + delta * 0.35 + 0.5
          const low = Math.min(open, close) - delta * 0.35 - 0.5
          return {
            date: labels[idx] || `Point ${idx + 1}`,
            open,
            high,
            low,
            close,
          }
        })
        result[ticker] = synth
      }
    })

    return result
  }, [candles, series, labels, tickerKeys])

  // Get active candles based on tab
  const activeCandles = useMemo(() => {
    if (activeTab === 'dual') {
      // Comparison dual mode: use first ticker length
      const first = tickerKeys[0]
      return resolvedCandlesByTicker[first] || []
    }
    return resolvedCandlesByTicker[activeTab] || []
  }, [activeTab, resolvedCandlesByTicker, tickerKeys])

  // Chart dimensions in SVG viewBox
  const SVG_WIDTH = 680
  const SVG_HEIGHT = 220
  const PAD_LEFT = 45
  const PAD_RIGHT = 15
  const PAD_TOP = 20
  const PAD_BOTTOM = 30
  const plotWidth = SVG_WIDTH - PAD_LEFT - PAD_RIGHT
  const plotHeight = SVG_HEIGHT - PAD_TOP - PAD_BOTTOM

  // Price range calculation
  const { minP, maxP, rangeP } = useMemo(() => {
    let prices: number[] = []
    if (activeTab === 'dual') {
      tickerKeys.forEach((t) => {
        const cList = resolvedCandlesByTicker[t] || []
        cList.forEach((c) => {
          prices.push(c.low, c.high, c.open, c.close)
        })
      })
    } else {
      activeCandles.forEach((c) => {
        const isRaw = c.raw_low !== undefined && c.raw_high !== undefined
        if (isRaw) {
          prices.push(c.raw_low!, c.raw_high!, c.raw_open!, c.raw_close!)
        } else {
          prices.push(c.low, c.high, c.open, c.close)
        }
      })
    }

    if (prices.length === 0) prices = [90, 110]
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const span = Math.max(1, max - min)
    const margin = span * 0.08
    return {
      minP: min - margin,
      maxP: max + margin,
      rangeP: span + margin * 2,
    }
  }, [activeTab, activeCandles, resolvedCandlesByTicker, tickerKeys])

  const yScale = (p: number) => {
    if (rangeP <= 0) return PAD_TOP + plotHeight / 2
    return PAD_TOP + (1 - (p - minP) / rangeP) * plotHeight
  }

  const N = Math.max(1, activeCandles.length)
  const slotWidth = plotWidth / N

  // Hover item info
  const hoveredInfo = useMemo(() => {
    if (hoverIdx === null || hoverIdx < 0 || hoverIdx >= activeCandles.length) return null
    if (activeTab === 'dual') {
      return {
        date: activeCandles[hoverIdx].date,
        items: tickerKeys.map((t) => {
          const c = resolvedCandlesByTicker[t]?.[hoverIdx]
          if (!c) return null
          const chg = c.open > 0 ? ((c.close - c.open) / c.open) * 100 : 0
          return {
            ticker: t,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
            changePct: chg,
          }
        }).filter(Boolean),
      }
    }
    const c = activeCandles[hoverIdx]
    const hasRaw = c.raw_open !== undefined
    const o = hasRaw ? c.raw_open! : c.open
    const h = hasRaw ? c.raw_high! : c.high
    const l = hasRaw ? c.raw_low! : c.low
    const cl = hasRaw ? c.raw_close! : c.close
    const chg = o > 0 ? ((cl - o) / o) * 100 : 0
    return {
      date: c.date,
      items: [
        {
          ticker: activeTab,
          open: o,
          high: h,
          low: l,
          close: cl,
          changePct: chg,
        },
      ],
    }
  }, [hoverIdx, activeTab, activeCandles, resolvedCandlesByTicker, tickerKeys])

  // Y-axis grid lines (4 lines)
  const yTicks = useMemo(() => {
    const ticks = []
    const count = 4
    for (let i = 0; i <= count; i++) {
      const val = minP + (rangeP / count) * i
      ticks.push({
        val,
        y: yScale(val),
        label: val >= 1000 ? val.toFixed(0) : val >= 10 ? val.toFixed(1) : val.toFixed(2),
      })
    }
    return ticks
  }, [minP, rangeP])

  // X-axis sampled labels
  const xTicks = useMemo(() => {
    if (activeCandles.length <= 6) {
      return activeCandles.map((c, idx) => ({
        idx,
        label: c.date,
        x: PAD_LEFT + (idx + 0.5) * slotWidth,
      }))
    }
    const step = Math.ceil(activeCandles.length / 5)
    const ticks = []
    for (let i = 0; i < activeCandles.length; i += step) {
      ticks.push({
        idx: i,
        label: activeCandles[i].date,
        x: PAD_LEFT + (i + 0.5) * slotWidth,
      })
    }
    return ticks
  }, [activeCandles, slotWidth])

  return (
    <div className="floating-candle-chart-container" style={{ width: '100%', position: 'relative' }}>
      {/* Ticker / Mode Selection Bar */}
      {tickerKeys.length > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            marginBottom: 8,
            flexWrap: 'wrap',
          }}
        >
          <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 600 }}>TICKERS:</span>
          <button
            onClick={() => setActiveTab('dual')}
            style={{
              fontSize: 10,
              padding: '2px 8px',
              borderRadius: 4,
              border: '1px solid',
              borderColor: activeTab === 'dual' ? 'var(--green)' : 'var(--line)',
              background: activeTab === 'dual' ? 'var(--green-soft)' : 'transparent',
              color: activeTab === 'dual' ? 'var(--green-dark)' : 'var(--muted)',
              cursor: 'pointer',
              fontWeight: activeTab === 'dual' ? 700 : 500,
              transition: 'all 0.15s',
            }}
          >
            All Comparison (Dual)
          </button>
          {tickerKeys.map((t) => (
            <button
              key={t}
              onClick={() => setActiveTab(t)}
              style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 4,
                border: '1px solid',
                borderColor: activeTab === t ? 'var(--green)' : 'var(--line)',
                background: activeTab === t ? 'var(--green-soft)' : 'transparent',
                color: activeTab === t ? 'var(--green-dark)' : 'var(--muted)',
                cursor: 'pointer',
                fontWeight: activeTab === t ? 700 : 500,
                transition: 'all 0.15s',
              }}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Floating Info Header on Hover */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          minHeight: 22,
          fontSize: 10,
          color: 'var(--text)',
          marginBottom: 4,
          padding: '0 4px',
        }}
      >
        {hoveredInfo ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, color: 'var(--muted)' }}>📅 {hoveredInfo.date}</span>
            {hoveredInfo.items.map((item: any, idx: number) => {
              const isUp = item.changePct >= 0
              return (
                <span key={idx} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <b style={{ color: idx === 0 ? '#10b981' : '#f59e0b' }}>{item.ticker}:</b>
                  <span>O: {item.open.toFixed(2)}</span>
                  <span>H: {item.high.toFixed(2)}</span>
                  <span>L: {item.low.toFixed(2)}</span>
                  <span>C: {item.close.toFixed(2)}</span>
                  <span
                    style={{
                      fontWeight: 700,
                      color: isUp ? '#10b981' : '#ef4444',
                    }}
                  >
                    {isUp ? '+' : ''}
                    {item.changePct.toFixed(2)}%
                  </span>
                </span>
              )
            })}
          </div>
        ) : (
          <div style={{ fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>
            Hover over any floating candle to inspect OHLC metrics & price change
          </div>
        )}
      </div>

      {/* SVG Canvas */}
      <div style={{ width: '100%', height: 210 }}>
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          style={{ width: '100%', height: '100%', overflow: 'visible', userSelect: 'none' }}
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect()
            const relX = (e.clientX - rect.left) / rect.width * SVG_WIDTH
            const i = Math.floor((relX - PAD_LEFT) / slotWidth)
            if (i >= 0 && i < activeCandles.length) {
              setHoverIdx(i)
            } else {
              setHoverIdx(null)
            }
          }}
          onMouseLeave={() => setHoverIdx(null)}
        >
          <defs>
            <filter id="candle-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000000" floodOpacity="0.08" />
            </filter>
          </defs>

          {/* Background Grid Lines & Y-Labels */}
          {yTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={PAD_LEFT}
                y1={tick.y}
                x2={SVG_WIDTH - PAD_RIGHT}
                y2={tick.y}
                stroke="rgba(0,0,0,0.06)"
                strokeDasharray="3 3"
              />
              <text
                x={PAD_LEFT - 6}
                y={tick.y + 3}
                fontSize={9}
                fill="#718078"
                textAnchor="end"
                fontFamily="inherit"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* Hover Crosshair */}
          {hoverIdx !== null && (
            <g>
              <line
                x1={PAD_LEFT + (hoverIdx + 0.5) * slotWidth}
                y1={PAD_TOP}
                x2={PAD_LEFT + (hoverIdx + 0.5) * slotWidth}
                y2={PAD_TOP + plotHeight}
                stroke="rgba(40, 167, 69, 0.4)"
                strokeDasharray="2 2"
                strokeWidth={1}
              />
            </g>
          )}

          {/* Floating Candles Rendering */}
          {activeTab === 'dual' ? (
            // DUAL COMPARISON: Render side-by-side candles for both tickers
            activeCandles.map((_, idx) => {
              const xCenter = PAD_LEFT + (idx + 0.5) * slotWidth
              const numTickers = tickerKeys.length
              const singleW = Math.max(3, Math.min(8, (slotWidth * 0.75) / numTickers))

              return (
                <g key={idx}>
                  {tickerKeys.map((ticker, tIdx) => {
                    const c = resolvedCandlesByTicker[ticker]?.[idx]
                    if (!c) return null

                    const offset = (tIdx - (numTickers - 1) / 2) * (singleW + 2)
                    const candleX = xCenter + offset
                    const isUp = c.close >= c.open

                    // Palette: Ticker 0 = Green/Red, Ticker 1 = Orange/Rose
                    let fill = isUp ? '#10b981' : '#ef4444'
                    if (tIdx === 1) {
                      fill = isUp ? '#f59e0b' : '#dc2626'
                    } else if (tIdx > 1) {
                      fill = isUp ? '#3b82f6' : '#ec4899'
                    }

                    const topY = yScale(Math.max(c.open, c.close))
                    const botY = yScale(Math.min(c.open, c.close))
                    const hY = yScale(c.high)
                    const lY = yScale(c.low)
                    const bodyH = Math.max(2, botY - topY)

                    return (
                      <g key={ticker} opacity={hoverIdx !== null && hoverIdx !== idx ? 0.4 : 1}>
                        {/* Upper and lower wick */}
                        <line
                          x1={candleX}
                          y1={hY}
                          x2={candleX}
                          y2={lY}
                          stroke={fill}
                          strokeWidth={1.2}
                          strokeLinecap="round"
                        />
                        {/* Floating candle body */}
                        <rect
                          x={candleX - singleW / 2}
                          y={topY}
                          width={singleW}
                          height={bodyH}
                          rx={1.5}
                          fill={fill}
                          fillOpacity={0.9}
                          stroke={fill}
                          strokeWidth={0.8}
                          filter="url(#candle-shadow)"
                        />
                      </g>
                    )
                  })}
                </g>
              )
            })
          ) : (
            // SINGLE TICKER CANDLESTICK CHART
            activeCandles.map((c, idx) => {
              const xCenter = PAD_LEFT + (idx + 0.5) * slotWidth
              const candleW = Math.max(4, Math.min(14, slotWidth * 0.65))

              const hasRaw = c.raw_open !== undefined
              const o = hasRaw ? c.raw_open! : c.open
              const h = hasRaw ? c.raw_high! : c.high
              const l = hasRaw ? c.raw_low! : c.low
              const cl = hasRaw ? c.raw_close! : c.close

              const isUp = cl >= o
              const fill = isUp ? '#10b981' : '#ef4444'

              const topY = yScale(Math.max(o, cl))
              const botY = yScale(Math.min(o, cl))
              const hY = yScale(h)
              const lY = yScale(l)
              const bodyH = Math.max(2.5, botY - topY)

              return (
                <g key={idx} opacity={hoverIdx !== null && hoverIdx !== idx ? 0.35 : 1}>
                  {/* Upper & lower wick */}
                  <line
                    x1={xCenter}
                    y1={hY}
                    x2={xCenter}
                    y2={lY}
                    stroke={fill}
                    strokeWidth={1.5}
                    strokeLinecap="round"
                  />
                  {/* Floating candle body */}
                  <rect
                    x={xCenter - candleW / 2}
                    y={topY}
                    width={candleW}
                    height={bodyH}
                    rx={2}
                    fill={fill}
                    fillOpacity={0.92}
                    stroke={fill}
                    strokeWidth={1}
                    filter="url(#candle-shadow)"
                  />
                </g>
              )
            })
          )}

          {/* X-axis date labels */}
          {xTicks.map((tick, i) => (
            <text
              key={i}
              x={tick.x}
              y={PAD_TOP + plotHeight + 16}
              fontSize={9}
              fill="#718078"
              textAnchor="middle"
              fontFamily="inherit"
            >
              {tick.label}
            </text>
          ))}
        </svg>
      </div>

      {/* Floating Candles Legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: 16,
          marginTop: 6,
          fontSize: 10,
          color: 'var(--muted)',
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 10, borderRadius: 2, background: '#10b981', display: 'inline-block' }} />
          Bullish (Gain)
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 10, borderRadius: 2, background: '#ef4444', display: 'inline-block' }} />
          Bearish (Decline)
        </span>
        {tickerKeys.length > 1 && activeTab === 'dual' && (
          <>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
              {tickerKeys[0]}
            </span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
              {tickerKeys[1]}
            </span>
          </>
        )}
      </div>
    </div>
  )
}
