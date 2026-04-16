-- Add HRV, respiration, and stress columns to scans table.
-- Run once against the Supabase project. Safe to re-run: uses IF NOT EXISTS.

ALTER TABLE scans ADD COLUMN IF NOT EXISTS rmssd_ms               float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS sdnn_ms                float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS pnn50                  float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS hrv_confidence         float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS respiration_bpm        float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS respiration_confidence float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS stress_score           int;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS stress_label           text;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS stress_lf_hf           float;
ALTER TABLE scans ADD COLUMN IF NOT EXISTS stress_confidence      float;
