-- 004_meeting_notion_page_id.sql
ALTER TABLE telemost.meetings
    ADD COLUMN notion_page_id text,
    ADD COLUMN notion_page_url text;
