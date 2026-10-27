'use client'

import React from 'react'
import {
  Activity,
  Check,
  Cpu,
  ExternalLink,
  RefreshCw,
  Server,
  ShieldCheck,
  X,
  Zap,
} from 'lucide-react'
import { API_BASE } from '@/lib/api'
import type { HealthInfo } from '@/lib/types'

interface SettingsModalProps {
  open?: boolean
  isOpen?: boolean
  onClose: () => void
  health: HealthInfo | null
  onRefresh?: () => void
  onRefreshHealth?: () => void
}

export function SettingsModal({
  open,
  isOpen,
  onClose,
  health,
  onRefresh,
  onRefreshHealth,
}: SettingsModalProps) {
  const isModalOpen = Boolean(open ?? isOpen)
  const handleRefresh = onRefresh || onRefreshHealth || (() => {})

  React.useEffect(() => {
    if (!isModalOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isModalOpen, onClose])

  if (!isModalOpen) return null

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
          width: 'min(90vw, 520px)',
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
            <Server size={18} style={{ color: 'var(--green)' }} />
            <b style={{ fontSize: 14 }}>System Status & Configuration</b>
          </div>
          <button onClick={onClose} className="icon-button" aria-label="Close modal">
            <X size={16} />
          </button>
        </div>

        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Status tile */}
          <div
            style={{
              padding: 12,
              borderRadius: 8,
              background: 'var(--panel-2)',
              border: '1px solid var(--line)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 600 }}>BACKEND HEALTH</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: health?.status === 'ok' ? 'var(--green)' : 'var(--orange)', display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                <span className="online-dot" /> {health?.status?.toUpperCase() || 'CONNECTING'}
              </div>
            </div>
            <button
              onClick={handleRefresh}
              className="quiet-button"
              style={{ padding: '6px 10px', background: 'var(--panel)', borderRadius: 6, border: '1px solid var(--line)' }}
            >
              <RefreshCw size={13} /> Check Health
            </button>
          </div>

          {/* Model info grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ padding: 10, borderRadius: 8, background: 'var(--panel-2)', border: '1px solid var(--line-soft)' }}>
              <small style={{ color: 'var(--muted)', fontSize: 9 }}>PRIMARY MODEL</small>
              <b style={{ display: 'block', fontSize: 11, marginTop: 3, fontFamily: "'DM Mono', monospace" }}>
                {health?.model || 'openai/gpt-oss-20b'}
              </b>
            </div>
            <div style={{ padding: 10, borderRadius: 8, background: 'var(--panel-2)', border: '1px solid var(--line-soft)' }}>
              <small style={{ color: 'var(--muted)', fontSize: 9 }}>FALLBACK MODEL</small>
              <b style={{ display: 'block', fontSize: 11, marginTop: 3, fontFamily: "'DM Mono', monospace" }}>
                {health?.fallback_model || 'openai/gpt-oss-120b'}
              </b>
            </div>
          </div>

          {/* Details list */}
          <div style={{ fontSize: 11, color: 'var(--text)', display: 'flex', flexDirection: 'column', gap: 8, padding: '6px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line-soft)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--muted)' }}>LLM Provider</span>
              <b>Groq Cloud (Free Tier)</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line-soft)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--muted)' }}>API Key Configured</span>
              <span style={{ color: health?.api_key_configured ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                {health?.api_key_configured ? 'Configured (GROQ_API_KEY)' : 'Missing'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line-soft)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--muted)' }}>Documents Chunks Indexed</span>
              <b>{health?.documents_indexed ?? 0}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line-soft)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--muted)' }}>Verification Gate (Self-Check)</span>
              <b style={{ color: 'var(--green)' }}>Enabled (VERIFY_ANSWERS)</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--line-soft)', paddingBottom: 6 }}>
              <span style={{ color: 'var(--muted)' }}>Router Max Tools</span>
              <b>{health?.router_max_tools || 6} tools per turn</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 2 }}>
              <span style={{ color: 'var(--muted)' }}>Backend URL</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 10 }}>{API_BASE}</span>
            </div>
          </div>

          {/* External links */}
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <a
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noreferrer"
              className="accent-button"
              style={{ textDecoration: 'none', textAlign: 'center', fontSize: 11 }}
            >
              Interactive Swagger Docs <ExternalLink size={13} style={{ marginLeft: 6 }} />
            </a>
            <a
              href={`${API_BASE}/api/tools`}
              target="_blank"
              rel="noreferrer"
              className="quiet-button"
              style={{
                textDecoration: 'none',
                padding: '0 14px',
                borderRadius: 6,
                border: '1px solid var(--line)',
                background: 'var(--panel-2)',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                fontSize: 11,
              }}
            >
              Raw Tools JSON <ExternalLink size={13} />
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
