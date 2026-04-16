-- Add blood pressure columns to scans table.
-- Run once against the Supabase project. Safe to re-run: uses IF NOT EXISTS.

ALTER TABLE scans ADD COLUMN IF NOT EXISTS sbp           float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS dbp           float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS bp_confidence float;
