-- project_root/bq_setup.sql
-- Run: bq --project_id=${GCP_PROJECT} query --use_legacy_sql=false < bq_setup.sql

CREATE SCHEMA IF NOT EXISTS `mckinseyvoicebot.voicebot_leads`;


CREATE TABLE IF NOT EXISTS `mckinseyvoicebot.voicebot_leads.leads`
 (
  lead_id STRING,
  first_name STRING,
  last_name STRING,
  phone_e164 STRING,
  email STRING,
  consent_email BOOL,
  consent_call BOOL,
  hot_lead BOOL,
  lead_source STRING,
  created_at TIMESTAMP,
  transcript STRING,
  last_contacted TIMESTAMP
);

-- Insert 10 sample Spanish leads (E.164 format +34)
INSERT INTO `mckinseyvoicebot.voicebot_leads.leads` (lead_id, first_name, last_name, phone_e164, email, consent_email, consent_call, hot_lead, lead_source, created_at)
VALUES
('L001','Alejandro','García','+34611223344','alejandro.garcia@example.es', TRUE, TRUE, FALSE,'campaign-abril', CURRENT_TIMESTAMP()),
('L002','María','Fernández','+34612223345','maria.fernandez@example.es', TRUE, FALSE, FALSE,'website', CURRENT_TIMESTAMP()),
('L003','Carlos','López','+34613323346','carlos.lopez@example.es', FALSE, TRUE, TRUE,'partner', CURRENT_TIMESTAMP()),
('L004','Lucía','Martínez','+34614423347','lucia.martinez@example.es', TRUE, TRUE, TRUE,'event', CURRENT_TIMESTAMP()),
('L005','Javier','Sánchez','+34615523348','javier.sanchez@example.es', TRUE, FALSE, FALSE,'campaign-mayo', CURRENT_TIMESTAMP()),
('L006','Sofía','Pérez','+34616623349','sofia.perez@example.es', FALSE, FALSE, FALSE,'list-purchase', CURRENT_TIMESTAMP()),
('L007','Pablo','Gómez','+34617723340','pablo.gomez@example.es', TRUE, TRUE, FALSE,'referral', CURRENT_TIMESTAMP()),
('L008','Ana','Díaz','+34618823341','ana.diaz@example.es', TRUE, TRUE, TRUE,'website', CURRENT_TIMESTAMP()),
('L009','Diego','Ruiz','+34619923342','diego.ruiz@example.es', FALSE, TRUE, FALSE,'telemarketing', CURRENT_TIMESTAMP()),
('L010','Elena','Vargas','+34610023343','elena.vargas@example.es', TRUE, FALSE, FALSE,'social', CURRENT_TIMESTAMP());
