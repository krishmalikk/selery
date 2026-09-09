import { z } from 'zod';
import { AlertSchema, JournalEntrySchema } from './contracts';

// Compose generated schemas beside the pinned validator. Native clients must not
// combine them with a separately hoisted Zod version from framework tooling.
export const AlertListSchema = z.array(AlertSchema);
export const JournalEntryListSchema = z.array(JournalEntrySchema);
