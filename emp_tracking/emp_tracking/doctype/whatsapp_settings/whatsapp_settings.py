# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# WhatsApp Settings: server code
#
# How this file works
#   One settings page (a Single doctype) that holds the Meta WhatsApp Cloud API details.
#     1. Other code calls send_template() to send an approved template message to a list of
#        mobile numbers. Sending runs in a background job, so a slow or failing WhatsApp API
#        never blocks a save. Every message sent is logged as a WhatsApp Message record.
#     2. Meta calls webhook() when someone replies, and when a sent message is delivered, read
#        or fails. Replies are logged too, linked to the project the person is answering, and
#        added to that project's timeline.
#
# Change log
#   2026-10-08  Created for New Project stage messages.
#   2026-10-08  Test Mode: all messages go to the Test Mobile Number; "Send Test Message" button.
#   2026-10-08  Webhook for replies and delivery status; every message logged in WhatsApp Message.
# ---------------------------------------------------------------------------------------------

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

import frappe
import requests
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.utils import convert_utc_to_system_timezone, get_url, now_datetime
from werkzeug.wrappers import Response

GRAPH_URL = "https://graph.facebook.com/{version}/{phone_number_id}/messages"
WEBHOOK_METHOD = "emp_tracking.emp_tracking.doctype.whatsapp_settings.whatsapp_settings.webhook"

# Meta's delivery statuses -> WhatsApp Message status. A late "delivered" never undoes "read".
STATUS_MAP = {"sent": "Sent", "delivered": "Delivered", "read": "Read", "failed": "Failed"}
STATUS_RANK = {"Sent": 1, "Delivered": 2, "Read": 3, "Failed": 4}


class WhatsAppSettings(Document):
	# Date: 2026-10-08
	@property
	def webhook_url(self):
		"""The Callback URL to paste into Meta (shown read-only on the settings page)."""
		return get_url(f"/api/method/{WEBHOOK_METHOD}")

	# Date: 2026-10-08
	def validate(self):
		"""Make a Verify Token the first time, so there is always one to paste into Meta."""
		if not self.verify_token:
			self.verify_token = frappe.generate_hash(length=24)


# Date: 2026-10-08
def normalise_number(number, country_code="91"):
	"""Digits only, with the country code in front: "098230 12345" -> "919823012345". None if unusable."""
	digits = re.sub(r"\D", "", number or "").lstrip("0")
	if len(digits) == 10:
		digits = (country_code or "91") + digits
	return digits if len(digits) >= 11 else None


# Date: 2026-10-08
def send_template(numbers, template, params, reference_doctype=None, reference_name=None):
	"""Queue one template message per number. Does nothing while WhatsApp Settings is disabled.

	`params` fills the template body variables {{1}}, {{2}}, ... in order.
	"""
	settings = frappe.get_cached_doc("WhatsApp Settings")
	if not settings.enabled or not template:
		return
	numbers = {normalise_number(n, settings.default_country_code) for n in numbers}
	numbers.discard(None)
	if not numbers:
		return
	# 2026-10-08: in Test Mode the real people get nothing; the test number gets one copy.
	if settings.test_mode:
		numbers = {normalise_number(settings.test_mobile_number, settings.default_country_code)} - {None}
		if not numbers:
			return
	frappe.enqueue(
		"emp_tracking.emp_tracking.doctype.whatsapp_settings.whatsapp_settings.deliver",
		queue="short",
		enqueue_after_commit=True,
		numbers=sorted(numbers),
		template=template,
		params=[str(p) if p not in (None, "") else "-" for p in params],
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)


# Date: 2026-10-08
def post_template(settings, number, template, params):
	"""Send one template message through the Cloud API. Returns the HTTP response (not checked)."""
	url = GRAPH_URL.format(version=settings.api_version or "v21.0", phone_number_id=settings.phone_number_id)
	headers = {"Authorization": f"Bearer {settings.get_password('access_token')}"}
	payload = {
		"messaging_product": "whatsapp",
		"to": number,
		"type": "template",
		"template": {
			"name": template,
			"language": {"code": settings.template_language or "en"},
			"components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}],
		},
	}
	return requests.post(url, json=payload, headers=headers, timeout=20)


# Date: 2026-10-08
def log_outgoing(number, template, params, response, reference_doctype=None, reference_name=None):
	"""Record a sent template as a WhatsApp Message (Sent, or Failed with Meta's error)."""
	ok = response is not None and response.ok
	wa_id = None
	if ok:
		wa_id = ((response.json().get("messages") or [{}])[0]).get("id")
	frappe.get_doc(
		{
			"doctype": "WhatsApp Message",
			"direction": "Outgoing",
			"status": "Sent" if ok else "Failed",
			"mobile_no": number,
			"timestamp": now_datetime(),
			"template": template,
			"message": " | ".join(params),
			"message_type": "template",
			"wa_message_id": wa_id,
			"error": None if ok else (response.text if response is not None else "No response"),
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
		}
	).insert(ignore_permissions=True)


# Date: 2026-10-08
def deliver(numbers, template, params, reference_doctype=None, reference_name=None):
	"""Background job: post the template to each number, log each one, and log failures."""
	settings = frappe.get_single("WhatsApp Settings")
	sent = []
	for number in numbers:
		response = None
		try:
			response = post_template(settings, number, template, params)
			response.raise_for_status()
			sent.append(number)
		except Exception:
			frappe.log_error(
				title=f"WhatsApp to {number} failed",
				message=f"{frappe.get_traceback()}\n\nResponse: {response.text if response is not None else ''}",
				reference_doctype=reference_doctype,
				reference_name=reference_name,
			)
		log_outgoing(number, template, params, response, reference_doctype, reference_name)
	if sent and reference_doctype and reference_name:
		frappe.get_doc(reference_doctype, reference_name).add_comment(
			"Info", "WhatsApp sent to " + ", ".join("+" + n for n in sent)
		)


# Date: 2026-10-08
@frappe.whitelist()
def send_test_message():
	"""The "Send Test Message" button: send the stage template with sample values to the test number.

	Runs straight away (not in the background) so Meta's answer is shown on screen.
	"""
	frappe.only_for("System Manager")
	settings = frappe.get_single("WhatsApp Settings")
	if not (settings.phone_number_id and settings.get_password("access_token", raise_exception=False)):
		frappe.throw("Fill in the Phone Number ID and Access Token, then save.")
	number = normalise_number(settings.test_mobile_number, settings.default_country_code)
	if not number:
		frappe.throw("Enter a valid Test Mobile Number, then save.")
	template = settings.project_stage_template or "project_stage_update"
	params = ["PRJ-TEST", "Test Site", "Survey by Area Manager", "Fiber Team Assignment by Area Manager"]
	response = post_template(settings, number, template, params)
	log_outgoing(number, template, params, response)
	if not response.ok:
		frappe.throw(f"WhatsApp refused the message ({response.status_code}): {response.text}")
	return f"Test message sent to +{number}. Reply to it from the phone to test receiving."


# Date: 2026-10-08
@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def webhook():
	"""Meta calls this URL. GET: the one-time check when the webhook is set up. POST: events."""
	if frappe.request.method == "GET":
		return verify_webhook()
	settings = frappe.get_single("WhatsApp Settings")
	raw = frappe.request.get_data(cache=True)
	if not signature_ok(settings, raw, frappe.request.headers.get("X-Hub-Signature-256")):
		return Response("Invalid signature", status=403)
	try:
		handle_events(json.loads(raw or b"{}"))
	except Exception:
		# Answer 200 anyway, or Meta keeps re-sending the same event; the error is in the Error Log.
		frappe.log_error(title="WhatsApp webhook failed", message=f"{frappe.get_traceback()}\n\n{raw!r}")
	return Response("OK", status=200)


# Date: 2026-10-08
def verify_webhook():
	"""Meta sends the Verify Token; answer with its challenge text if the token matches ours."""
	args = frappe.form_dict
	token = frappe.db.get_single_value("WhatsApp Settings", "verify_token")
	if args.get("hub.mode") == "subscribe" and token and args.get("hub.verify_token") == token:
		return Response(args.get("hub.challenge") or "", status=200, mimetype="text/plain")
	return Response("Verify token does not match", status=403)


# Date: 2026-10-08
def signature_ok(settings, raw, header):
	"""True if Meta signed this request body with our App Secret (so nobody can fake a reply)."""
	secret = settings.get_password("app_secret", raise_exception=False)
	if not secret or not header:
		return False
	expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, header)


# Date: 2026-10-08
def handle_events(payload):
	"""Walk Meta's payload: log each incoming message and apply each delivery status."""
	for entry in payload.get("entry") or []:
		for change in entry.get("changes") or []:
			value = change.get("value") or {}
			names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts") or []}
			for message in value.get("messages") or []:
				receive_message(message, names.get(message.get("from")))
			for status in value.get("statuses") or []:
				update_status(status)


# Date: 2026-10-08
def message_text(message):
	"""The readable text of an incoming message; media shows as e.g. "[image]" plus its caption."""
	kind = message.get("type")
	if kind == "text":
		return (message.get("text") or {}).get("body")
	if kind == "button":
		return (message.get("button") or {}).get("text")
	if kind == "interactive":
		reply = message.get("interactive") or {}
		return (reply.get("button_reply") or reply.get("list_reply") or {}).get("title")
	caption = (message.get(kind) or {}).get("caption") if isinstance(message.get(kind), dict) else None
	return f"[{kind}]" + (f" {caption}" if caption else "")


# Date: 2026-10-08
def to_system_time(timestamp):
	"""Meta's Unix timestamp -> a datetime in the site's time zone (now, if missing)."""
	if not timestamp:
		return now_datetime()
	utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)
	return convert_utc_to_system_timezone(utc).replace(tzinfo=None)


# Date: 2026-10-08
def find_reference(number, reply_to):
	"""The record a reply is about: the message it quotes, else the last one sent to this number."""
	filters = {"direction": "Outgoing", "reference_name": ["is", "set"]}
	if reply_to:
		ref = frappe.db.get_value("WhatsApp Message", {**filters, "wa_message_id": reply_to}, ["reference_doctype", "reference_name"])
		if ref:
			return ref
	return frappe.db.get_value(
		"WhatsApp Message", {**filters, "mobile_no": number}, ["reference_doctype", "reference_name"], order_by="creation desc"
	)


# Date: 2026-10-08
def receive_message(message, contact_name):
	"""Log one incoming message, then put it on the project's timeline and tell its creator."""
	wa_id = message.get("id")
	if wa_id and frappe.db.exists("WhatsApp Message", {"wa_message_id": wa_id}):
		return  # Meta sometimes sends the same event twice
	number = message.get("from")
	reply_to = (message.get("context") or {}).get("id")
	text = message_text(message) or ""
	ref = find_reference(number, reply_to) or (None, None)
	frappe.get_doc(
		{
			"doctype": "WhatsApp Message",
			"direction": "Incoming",
			"status": "Received",
			"mobile_no": number,
			"contact_name": contact_name,
			"timestamp": to_system_time(message.get("timestamp")),
			"message": text,
			"message_type": message.get("type"),
			"wa_message_id": wa_id,
			"reply_to_message_id": reply_to,
			"reference_doctype": ref[0],
			"reference_name": ref[1],
		}
	).insert(ignore_permissions=True)

	if not ref[1] or not frappe.db.exists(ref[0], ref[1]):
		return
	who = f"+{number}" + (f" ({contact_name})" if contact_name else "")
	doc = frappe.get_doc(ref[0], ref[1])
	doc.add_comment("Info", f"WhatsApp reply from {who}: {text}")
	if doc.owner and doc.owner not in ("Guest", "Administrator"):
		enqueue_create_notification(
			doc.owner,
			{
				"type": "Alert",
				"document_type": ref[0],
				"document_name": ref[1],
				"subject": f"WhatsApp reply on {ref[1]} from {who}",
				"email_content": text,
			},
		)


# Date: 2026-10-08
def update_status(status):
	"""Mark a sent message Delivered / Read / Failed as Meta reports it."""
	name = frappe.db.get_value("WhatsApp Message", {"wa_message_id": status.get("id"), "direction": "Outgoing"})
	new = STATUS_MAP.get(status.get("status"))
	if not name or not new:
		return
	current = frappe.db.get_value("WhatsApp Message", name, "status")
	if STATUS_RANK.get(new, 0) <= STATUS_RANK.get(current, 0):
		return
	values = {"status": new}
	if new == "Failed":
		values["error"] = json.dumps(status.get("errors") or [], indent=1)
	frappe.db.set_value("WhatsApp Message", name, values)
