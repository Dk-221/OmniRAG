'use client'

import React, { useState } from 'react'
import { Check, ChevronDown, Loader2, Sparkles } from 'lucide-react'
import type { PlanStep } from '@/lib/types'

export function PlanCard({
  steps,
  plan,
}: {
  steps?: PlanStep[]
  plan?: { steps: PlanStep[] }
}) {
  const [collapsed, setCollapsed] = useState(false)
  const actualSteps = steps || plan?.steps || []
  if (!actualSteps || actualSteps.length === 0) return null

  const allDone = actualSteps.every((s) => s.status === 'done')

  return (
    <div className="plan-card">
      <div
        className="plan-head"
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Click to expand plan' : 'Click to collapse plan'}
      >
        <div>
          <span className="eyebrow">
            <Sparkles size={12} /> ROUTING & REASONING PLAN
          </span>
          <h3>Answering with {actualSteps.length} coordinated steps</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {allDone ? (
            <Check size={17} className="done-icon" />
          ) : (
            <Loader2 size={17} className="animate-spin" style={{ color: 'var(--green)' }} />
          )}
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 24,
              height: 24,
              color: 'var(--muted)',
              transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s ease',
            }}
          >
            <ChevronDown size={15} />
          </span>
        </div>
      </div>

      {!collapsed && (
        <div className="plan-steps">
        {actualSteps.map((s, idx) => {
          const isDone = s.status === 'done'
          const isRunning = s.status === 'running'

          return (
            <div key={s.id || idx} className={`plan-step ${isDone ? 'done' : isRunning ? 'running' : ''}`}>
              <span>0{s.id || idx + 1}</span>
              <i>
                {isDone ? (
                  <Check size={12} />
                ) : isRunning ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <span style={{ fontSize: 9 }}>·</span>
                )}
              </i>
              <div>
                <b>{typeof s.text === 'string' ? s.text : (s.text as any)?.text || String(s.text ?? '')}</b>
                <small>
                  {isDone ? 'Completed' : isRunning ? 'Executing…' : 'Queued'}
                </small>
              </div>
            </div>
          )
        })}
      </div>
      )}
    </div>
  )
}
