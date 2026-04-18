/**
 * Tracks which wiki pages the user has actually opened. Used to drive
 * the "继续阅读" section on the home page — so freshly-ingested pages
 * don't appear there until the user reads them.
 *
 * Stored in localStorage (shared-password auth = one history per browser),
 * which is fine until Phase B introduces per-user accounts.
 */

const STORAGE_KEY = 'wiki.reading-history'
const MAX_ENTRIES = 20

export interface ReadingHistoryEntry {
  slug: string
  title: string
  type?: string
  opened_at: string // ISO timestamp
}

function safeRead(): ReadingHistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function safeWrite(entries: ReadingHistoryEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Quota exceeded or disabled — silently drop.
  }
}

export function recordPageOpen(entry: Omit<ReadingHistoryEntry, 'opened_at'>) {
  if (!entry.slug) return
  const history = safeRead()
  const filtered = history.filter((e) => e.slug !== entry.slug)
  filtered.unshift({ ...entry, opened_at: new Date().toISOString() })
  safeWrite(filtered.slice(0, MAX_ENTRIES))
}

export function getReadingHistory(limit = 5): ReadingHistoryEntry[] {
  return safeRead().slice(0, limit)
}

export function clearReadingHistory() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}
