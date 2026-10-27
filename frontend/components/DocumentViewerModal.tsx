'use client'

import React, { useEffect, useState } from 'react'
import {
  AlertCircle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  FileText,
  Loader2,
  X,
} from 'lucide-react'
import { fetchDocumentPage } from '@/lib/api'

interface DocumentViewerModalProps {
  filename: string | null
  initialPage?: number
  isOpen?: boolean
  open?: boolean
  onClose: () => void
}

export function DocumentViewerModal({
  filename,
  initialPage = 1,
  isOpen,
  open,
  onClose,
}: DocumentViewerModalProps) {
  const isModalOpen = (isOpen ?? open ?? true) && Boolean(filename)
  const [page, setPage] = useState<number>(initialPage)
  const [totalPages, setTotalPages] = useState<number>(1)
  const [text, setText] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setPage(initialPage || 1)
    setTotalPages(1)
  }, [initialPage, filename])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    if (!filename || !isModalOpen) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchDocumentPage(filename, page)
      .then((res) => {
        if (!cancelled) {
          setText(res.text || '(No text extracted from this page)')
          if (res.total_pages) {
            setTotalPages(res.total_pages)
          }
          if (res.page && res.page !== page) {
            setPage(res.page)
          }
          setLoading(false)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [filename, page, isModalOpen])

  if (!isModalOpen || !filename) return null

  const handleCopy = () => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isFirstPage = page <= 1
  const isLastPage = page >= totalPages

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        background: 'rgba(15, 33, 19, 0.55)',
        backdropFilter: 'blur(5px)',
        display: 'grid',
        placeItems: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 'min(92vw, 720px)',
          maxHeight: '88vh',
          background: '#ffffff',
          borderRadius: 14,
          border: '1px solid #c7d8cb',
          boxShadow: '0 24px 60px rgba(10, 28, 14, 0.25)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '14px 20px',
            borderBottom: '1px solid #e1ebe2',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#f8faf8',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                background: '#e4f2e6',
                border: '1px solid #c3e2c9',
                display: 'grid',
                placeItems: 'center',
                color: '#237a3d',
              }}
            >
              <FileText size={18} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <b style={{ fontSize: 13, color: '#183620', fontWeight: 700 }}>{filename}</b>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: '#e8f3e9',
                    color: '#246b38',
                    border: '1px solid #cce2ce',
                  }}
                >
                  {filename.split('.').pop() || 'doc'}
                </span>
              </div>
              <small style={{ display: 'block', fontSize: 11, color: '#5f7566', marginTop: 1 }}>
                Document Source Viewer · Page {page} of {totalPages}
              </small>
            </div>
          </div>
          <button
            onClick={onClose}
            className="icon-button hover:bg-stone-200/60 p-1.5 rounded-md transition text-stone-600 hover:text-stone-900"
            aria-label="Close document viewer"
            style={{ border: 'none', background: 'transparent' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div
          style={{
            flex: 1,
            padding: 20,
            overflowY: 'auto',
            fontSize: 12,
            lineHeight: 1.75,
            color: '#1a2e21',
            whiteSpace: 'pre-wrap',
            fontFamily: "'DM Mono', monospace",
            background: '#fcfdfc',
            minHeight: 240,
            maxHeight: 'calc(88vh - 140px)',
          }}
        >
          {loading ? (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: 200,
                gap: 10,
                color: '#4f6956',
              }}
            >
              <Loader2 size={22} className="animate-spin text-emerald-600" />
              <span style={{ fontSize: 12, fontWeight: 500 }}>
                Loading extracted text for page {page}…
              </span>
            </div>
          ) : error ? (
            <div
              style={{
                padding: '14px 16px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#991b1b',
                borderRadius: 8,
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <AlertCircle size={18} className="text-red-600 flex-shrink-0" />
              <span>{error}</span>
            </div>
          ) : (
            text
          )}
        </div>

        {/* Footer controls with high-contrast readable buttons */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid #e1ebe2',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: '#f8faf8',
          }}
        >
          {/* Pagination controls */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              disabled={isFirstPage || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              style={{
                padding: '6px 12px',
                background: isFirstPage ? '#f3f6f3' : '#ffffff',
                color: isFirstPage ? '#8b9e90' : '#183620',
                border: '1px solid #c7d8cb',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: isFirstPage ? 'not-allowed' : 'pointer',
                opacity: isFirstPage ? 0.6 : 1,
                transition: 'all 0.15s ease',
              }}
              title={isFirstPage ? 'First page reached' : 'Go to previous page'}
            >
              <ChevronLeft size={14} /> Previous Page
            </button>

            <div
              style={{
                padding: '5px 10px',
                borderRadius: 6,
                background: '#e9f3eb',
                border: '1px solid #cce2ce',
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              <span style={{ fontSize: 11, fontWeight: 700, color: '#1b4b27' }}>
                Page {page}
              </span>
              <span style={{ fontSize: 11, color: '#5e7d66', fontWeight: 500 }}>
                of {totalPages}
              </span>
            </div>

            <button
              disabled={isLastPage || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              style={{
                padding: '6px 12px',
                background: isLastPage ? '#f3f6f3' : '#ffffff',
                color: isLastPage ? '#8b9e90' : '#183620',
                border: '1px solid #c7d8cb',
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                cursor: isLastPage ? 'not-allowed' : 'pointer',
                opacity: isLastPage ? 0.6 : 1,
                transition: 'all 0.15s ease',
              }}
              title={isLastPage ? 'Last page reached' : 'Go to next page'}
            >
              Next Page <ChevronRight size={14} />
            </button>
          </div>

          {/* Copy button */}
          <button
            onClick={handleCopy}
            disabled={loading || !text}
            style={{
              padding: '6px 14px',
              background: copied ? '#e5f6e8' : '#ffffff',
              color: copied ? '#1e7535' : '#183620',
              border: copied ? '1px solid #a3d9af' : '1px solid #c7d8cb',
              borderRadius: 6,
              fontSize: 11,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              cursor: loading || !text ? 'not-allowed' : 'pointer',
              opacity: loading || !text ? 0.6 : 1,
              transition: 'all 0.15s ease',
            }}
            title="Copy extracted page text to clipboard"
          >
            {copied ? (
              <>
                <Check size={14} className="text-emerald-600" />
                <span>Copied Page Text!</span>
              </>
            ) : (
              <>
                <Copy size={13} />
                <span>Copy Page Text</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
