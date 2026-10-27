import type {
  DatasetItem,
  DocumentItem,
  HealthInfo,
  MemoryItem,
  Tool,
} from './types'

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * Fetch server health & active configuration.
 */
export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(`${API_BASE}/api/health`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`)
  return res.json()
}

/**
 * Fetch all registered agent tools with categories.
 */
export async function fetchTools(): Promise<Tool[]> {
  const res = await fetch(`${API_BASE}/api/tools`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch tools: ${res.statusText}`)
  return res.json()
}

/**
 * Fetch all indexed knowledge base documents.
 */
export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/api/documents`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.statusText}`)
  return res.json()
}

/**
 * Fetch extracted text for a specific document page.
 */
export async function fetchDocumentPage(
  filename: string,
  page: number
): Promise<{ filename: string; page: number; total_pages?: number; text: string }> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(filename)}/page/${page}`,
    { cache: 'no-store' }
  )
  if (!res.ok) throw new Error(`Failed to load page ${page} of ${filename}`)
  return res.json()
}

/**
 * Upload a document (PDF, TXT, MD) to the knowledge base and auto-ingest.
 */
export async function uploadDocument(
  file: File
): Promise<{ filename: string; chunks: number }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Upload failed: ${res.statusText}`)
  }
  return res.json()
}

/**
 * Re-index all files in the knowledge base directory.
 */
export async function reindexDocuments(): Promise<{
  documents: number
  chunks: number
}> {
  const res = await fetch(`${API_BASE}/api/ingest`, { method: 'POST' })
  if (!res.ok) throw new Error(`Re-indexing failed: ${res.statusText}`)
  return res.json()
}

/**
 * Fetch all available datasets for analysis.
 */
export async function fetchDatasets(): Promise<DatasetItem[]> {
  const res = await fetch(`${API_BASE}/api/data/files`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch datasets: ${res.statusText}`)
  return res.json()
}

/**
 * Upload a dataset file (CSV, XLSX, XLS).
 */
export async function uploadDataset(
  file: File
): Promise<{ filename: string; size_bytes: number; message: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/api/data/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Dataset upload failed: ${res.statusText}`)
  }
  return res.json()
}

/**
 * Fetch all stored persistent memories.
 */
export async function fetchMemories(): Promise<MemoryItem[]> {
  const res = await fetch(`${API_BASE}/api/memories`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`Failed to fetch memories: ${res.statusText}`)
  return res.json()
}

/**
 * Delete a memory fact by ID.
 */
export async function deleteMemory(
  id: string
): Promise<{ success: boolean; id: string }> {
  const res = await fetch(
    `${API_BASE}/api/memories/${encodeURIComponent(id)}`,
    {
      method: 'DELETE',
    }
  )
  if (!res.ok) throw new Error(`Failed to delete memory ${id}`)
  return res.json()
}

/**
 * Stream an agent chat conversation over SSE.
 */
export async function streamChat(
  message: string,
  history: { role: string; content: string }[],
  onEvent: (event: any) => void,
  onError: (error: Error) => void,
  signal?: AbortSignal
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message, history }),
      signal,
    })

    if (!response.ok) {
      throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`)
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported on this response')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim()
          if (!jsonStr) continue
          try {
            const eventData = JSON.parse(jsonStr)
            onEvent(eventData)
          } catch (e) {
            console.warn('Failed to parse SSE line:', jsonStr, e)
          }
        }
      }
    }

    // Flush any leftover buffer
    if (buffer.trim().startsWith('data:')) {
      const jsonStr = buffer.trim().slice(5).trim()
      if (jsonStr) {
        try {
          const eventData = JSON.parse(jsonStr)
          onEvent(eventData)
        } catch {}
      }
    }
  } catch (err: any) {
    if (err.name === 'AbortError') {
      console.log('Stream aborted by user')
      return
    }
    onError(err)
  }
}
