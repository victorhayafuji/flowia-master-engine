-- Unique Meta phone_number_id per organization (partial — NULL/empty allowed for orgs without WhatsApp)

CREATE UNIQUE INDEX IF NOT EXISTS idx_organizations_whatsapp_phone_id_unique
  ON organizations (whatsapp_phone_id)
  WHERE whatsapp_phone_id IS NOT NULL AND whatsapp_phone_id <> '';
