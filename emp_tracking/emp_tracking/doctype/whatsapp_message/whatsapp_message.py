# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# WhatsApp Message: server code
#
# How this file works
#   One record per WhatsApp message, sent or received. Outgoing records are made by
#   whatsapp_settings.deliver(); incoming ones and the Delivered / Read / Failed updates come
#   from Meta through whatsapp_settings.webhook(). Records are read-only in the desk.
#
# Change log
#   2026-10-08  Created to log sent messages, their delivery status and replies.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class WhatsAppMessage(Document):
	pass
