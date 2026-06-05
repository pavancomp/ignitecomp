-- ============================================================
-- Ignite DB Patch: Tracking Center support
-- Run against existing ignite_engine database
-- Safe to run multiple times (uses IF NOT EXISTS / DO $$)
-- ============================================================

-- 1. tracking_centers table
CREATE TABLE IF NOT EXISTS tracking_centers (
    id              SERIAL PRIMARY KEY,
    distributor_id  INTEGER NOT NULL REFERENCES distributors(id),
    center_number   INTEGER NOT NULL CHECK (center_number BETWEEN 1 AND 3),
    position_id     INTEGER UNIQUE REFERENCES tree_positions(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    activated_at    TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_center_dist_num UNIQUE (distributor_id, center_number)
);
CREATE INDEX IF NOT EXISTS ix_center_distributor ON tracking_centers(distributor_id);

-- 2. tree_positions: drop distributor_id (now linked via tracking_centers)
--    Only run this after migrating existing data (see step 7 below)
--    ALTER TABLE tree_positions DROP COLUMN IF EXISTS distributor_id;

-- 3. commission_ledger: swap key from (distributor_id,cycle_id) to (center_id,cycle_id)
ALTER TABLE commission_ledger ADD COLUMN IF NOT EXISTS center_id INTEGER REFERENCES tracking_centers(id);
DO $$ BEGIN
  ALTER TABLE commission_ledger DROP CONSTRAINT IF EXISTS uq_ledger_dist_cycle;
EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE commission_ledger ADD CONSTRAINT uq_ledger_center_cycle UNIQUE (center_id, cycle_id);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;
CREATE INDEX IF NOT EXISTS ix_ledger_distributor_cycle ON commission_ledger(distributor_id, cycle_id);

-- 4. distributor_carry_forward: swap key to (center_id, cycle_id)
ALTER TABLE distributor_carry_forward ADD COLUMN IF NOT EXISTS center_id INTEGER REFERENCES tracking_centers(id);
DO $$ BEGIN
  ALTER TABLE distributor_carry_forward DROP CONSTRAINT IF EXISTS uq_carry_dist_cycle;
EXCEPTION WHEN others THEN NULL; END $$;
DO $$ BEGIN
  ALTER TABLE distributor_carry_forward ADD CONSTRAINT uq_carry_center_cycle UNIQUE (center_id, cycle_id);
EXCEPTION WHEN duplicate_table THEN NULL; END $$;

-- 5. orders: add center_id (nullable — links order to a specific center)
ALTER TABLE orders ADD COLUMN IF NOT EXISTS center_id INTEGER REFERENCES tracking_centers(id);

-- 6. coin_transactions: add center_id
ALTER TABLE coin_transactions ADD COLUMN IF NOT EXISTS center_id INTEGER REFERENCES tracking_centers(id);

-- 7. plan_config: add max_centers_per_ba
ALTER TABLE plan_config ADD COLUMN IF NOT EXISTS max_centers_per_ba INTEGER NOT NULL DEFAULT 3;

-- 8. cycles: add center_count
ALTER TABLE cycles ADD COLUMN IF NOT EXISTS center_count INTEGER NOT NULL DEFAULT 0;

-- 9. Migrate existing single-center BAs:
--    For every BA who has a tree_position, create a TrackingCenter (center_number=1)
INSERT INTO tracking_centers (distributor_id, center_number, position_id, is_active)
SELECT tp.distributor_id, 1, tp.id, TRUE
FROM tree_positions tp
WHERE tp.distributor_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM tracking_centers tc
    WHERE tc.distributor_id = tp.distributor_id AND tc.center_number = 1
  );

-- 10. Backfill center_id on commission_ledger for existing rows
UPDATE commission_ledger cl
SET center_id = tc.id
FROM tracking_centers tc
WHERE tc.distributor_id = cl.distributor_id
  AND tc.center_number = 1
  AND cl.center_id IS NULL;

-- 11. Backfill center_id on distributor_carry_forward
UPDATE distributor_carry_forward cf
SET center_id = tc.id
FROM tracking_centers tc
WHERE tc.distributor_id = cf.distributor_id
  AND tc.center_number = 1
  AND cf.center_id IS NULL;

-- Done
SELECT 'Patch applied successfully' AS status;
