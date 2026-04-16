-- Replace stress_lf_hf with stress_baevsky_si.
-- LF/HF requires ≥2 min of RR data (Task Force of ESC/NASPE 1996) and cannot
-- be computed reliably from a 60 s scan; we now expose the Baevsky Stress
-- Index directly alongside the 0–100 score.
--
-- The old stress_lf_hf column is kept (nullable) so historical rows remain
-- readable; it will simply stop receiving new writes.

ALTER TABLE scans ADD COLUMN IF NOT EXISTS stress_baevsky_si float;
