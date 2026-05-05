-- 015_relax_integration_constraints.sql
-- Allow NULL marketer_id on integrations so the ETL can load historical rows
-- that have no marketer assigned in the Google Sheet.
-- channel and marketplace keep NOT NULL but get defaults (wb / instagram)
-- so the transformer can always supply a value.

ALTER TABLE crm.integrations
    ALTER COLUMN marketer_id DROP NOT NULL;

ALTER TABLE crm.integrations
    ALTER COLUMN marketplace SET DEFAULT 'wb';

ALTER TABLE crm.integrations
    ALTER COLUMN channel SET DEFAULT 'instagram';
