-- Add 'ooo' channel for promo codes per v4 PROMO_CH list (was missing from initial seed)
INSERT INTO marketing.channels (slug, label) VALUES ('ooo', 'ООО') ON CONFLICT (slug) DO NOTHING;
