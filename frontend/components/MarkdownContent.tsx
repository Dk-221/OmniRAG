'use client'

import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy } from 'lucide-react'

interface CodeBlockProps {
  language?: string
  value: string
}

function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(value)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-[#2b4432] bg-[#142319] text-[#e2f0e5] shadow-md">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#1b2f22] border-b border-[#2b4432] text-[11px] font-mono text-[#9cc7a5]">
        <span className="uppercase tracking-wider">{language || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-[#254230] text-[#cfe6d4] transition-colors"
          title="Copy code"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3.5 text-xs font-mono overflow-x-auto leading-relaxed">
        <code>{value}</code>
      </pre>
    </div>
  )
}

export function MarkdownContent({
  content,
  className = '',
}: {
  content: string
  className?: string
}) {
  if (!content) return null

  // Strip raw <chart ... /> or <artifact ... /> tags emitted by the model
  const cleanedContent = content
    .replace(/<chart\s+[^>]*\/>/gi, '')
    .replace(/<chart\s+[^>]*>[\s\S]*?<\/chart>/gi, '')
    .replace(/<artifact\s+[^>]*\/>/gi, '')
    .trim()

  if (!cleanedContent) return null

  return (
    <div className={`markdown-body text-xs leading-relaxed text-[#26352d] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table({ children }) {
            return (
              <div className="markdown-table-wrap my-3.5 overflow-x-auto rounded-lg border border-[#d6e3d8] bg-white shadow-sm">
                <table className="w-full text-left text-xs border-collapse">
                  {children}
                </table>
              </div>
            )
          },
          thead({ children }) {
            return (
              <thead className="bg-[#edf5ef] text-[#1c4526] font-bold border-b border-[#d6e3d8]">
                {children}
              </thead>
            )
          },
          tbody({ children }) {
            return <tbody className="divide-y divide-[#e8f0e9]">{children}</tbody>
          },
          tr({ children }) {
            return (
              <tr className="hover:bg-[#f6faf7] transition-colors even:bg-[#fafcfa]">
                {children}
              </tr>
            )
          },
          th({ children }) {
            return (
              <th className="px-3.5 py-2.5 font-bold tracking-tight text-[11px] uppercase text-[#235832]">
                {children}
              </th>
            )
          },
          td({ children }) {
            return (
              <td className="px-3.5 py-2 text-[#2c3d32] text-[11px] leading-relaxed align-top">
                {children}
              </td>
            )
          },
          h1({ children }) {
            return (
              <h1 className="text-lg font-extrabold tracking-tight text-[#173320] mt-4 mb-2 pb-1 border-b border-[#e1ece2]">
                {children}
              </h1>
            )
          },
          h2({ children }) {
            return (
              <h2 className="text-base font-bold tracking-tight text-[#173320] mt-3.5 mb-2">
                {children}
              </h2>
            )
          },
          h3({ children }) {
            return (
              <h3 className="text-sm font-bold tracking-tight text-[#235832] mt-3 mb-1.5 flex items-center gap-1.5">
                {children}
              </h3>
            )
          },
          h4({ children }) {
            return (
              <h4 className="text-xs font-semibold text-[#2b4433] mt-2 mb-1">
                {children}
              </h4>
            )
          },
          p({ children }) {
            return (
              <p className="mb-2.5 leading-relaxed text-xs text-[#26352d] last:mb-0">
                {children}
              </p>
            )
          },
          ul({ children }) {
            return (
              <ul className="list-disc pl-5 mb-2.5 space-y-1 text-xs text-[#26352d]">
                {children}
              </ul>
            )
          },
          ol({ children }) {
            return (
              <ol className="list-decimal pl-5 mb-2.5 space-y-1 text-xs text-[#26352d]">
                {children}
              </ol>
            )
          },
          li({ children }) {
            return <li className="leading-relaxed pl-0.5">{children}</li>
          },
          strong({ children }) {
            return <strong className="font-bold text-[#142e1c]">{children}</strong>
          },
          em({ children }) {
            return <em className="italic text-[#294231]">{children}</em>
          },
          blockquote({ children }) {
            return (
              <blockquote className="border-l-3 border-[#33a852] pl-3 py-1.5 my-2.5 bg-[#f0f7f2] rounded-r text-[#2f4f38] italic text-xs">
                {children}
              </blockquote>
            )
          },
          code({ className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '')
            const textContent = String(children).replace(/\n$/, '')
            const isBlock = match || textContent.includes('\n')

            if (isBlock) {
              return (
                <CodeBlock
                  language={match ? match[1] : undefined}
                  value={textContent}
                />
              )
            }

            return (
              <code
                className="font-mono text-[11px] bg-[#eaf2ec] text-[#1d5c2e] px-1.5 py-0.5 rounded border border-[#d2e3d5] font-semibold"
                {...props}
              >
                {children}
              </code>
            )
          },
          a({ href, children }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#23743d] font-semibold underline underline-offset-2 hover:text-[#17522a] transition-colors"
              >
                {children}
              </a>
            )
          },
          img({ src, alt }) {
            const srcStr = typeof src === 'string' ? src : ''
            if (!srcStr || (!srcStr.startsWith('http://') && !srcStr.startsWith('https://') && !srcStr.startsWith('data:'))) {
              return null
            }
            const altLower = (alt || '').toLowerCase()
            if (
              altLower.includes('chart') ||
              altLower.includes('plot') ||
              altLower.includes('graph') ||
              altLower.includes('statistic') ||
              altLower.includes('visual')
            ) {
              return null
            }
            return (
              <span className="block my-3">
                <img
                  src={srcStr}
                  alt={alt || 'Image'}
                  className="max-w-full rounded-lg border border-[#dbe4dc] shadow-sm max-h-[400px] object-contain"
                  loading="lazy"
                  onError={(e) => {
                    const el = e.currentTarget as HTMLElement
                    el.style.display = 'none'
                    if (el.parentElement) el.parentElement.style.display = 'none'
                  }}
                />
              </span>
            )
          },
          hr() {
            return <hr className="my-4 border-t border-[#dce6dd]" />
          },
        }}
      >
        {cleanedContent}
      </ReactMarkdown>
    </div>
  )
}
