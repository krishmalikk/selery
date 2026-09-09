import type { z } from 'zod';

/** Storage adapters remain client-owned; data validation/freshness is identical on both surfaces. */
export type CacheEntry<T> = { data: T; retrievedAt: number; stale: boolean };
export function encodeCache<T>(data: T, retrievedAt = Date.now()): string {
  if (!Number.isFinite(retrievedAt) || retrievedAt < 0) throw new Error('Invalid cache timestamp');
  return JSON.stringify({ version: 1, data, retrievedAt });
}
export function parseCache<T>(
  raw: string | null,
  schema: z.ZodType<T>,
  { maxAgeMs = 30_000, now = Date.now() }: { maxAgeMs?: number; now?: number } = {},
): CacheEntry<T> | null {
  if (!raw || !Number.isFinite(now) || !Number.isFinite(maxAgeMs) || maxAgeMs < 0) return null;
  try {
    const entry = JSON.parse(raw);
    if (!entry || typeof entry !== 'object') return null;
    // Accept the original mobile envelope so existing installations retain their last-known data.
    if (entry.version !== undefined && entry.version !== 1) return null;
    const retrievedAt = entry.retrievedAt ?? entry.at;
    if (typeof retrievedAt !== 'number' || !Number.isFinite(retrievedAt) || retrievedAt < 0) return null;
    const data = schema.parse(entry.data);
    return { data, retrievedAt, stale: retrievedAt > now || now - retrievedAt >= maxAgeMs };
  } catch {
    return null;
  }
}
