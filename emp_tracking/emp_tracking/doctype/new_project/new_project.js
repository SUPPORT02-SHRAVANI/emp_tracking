// Copyright (c) 2026, milind and contributors
// For license information, please see license.txt

// ---------------------------------------------------------------------------------------------
// New Project: form script
//
// How this file works
//   The New Project form follows the project sheet. It has one tab per colour block of the
//   sheet, and each tab is filled by one owner (Project Head, Area Manager, Fiber Team or
//   Splicing Team). The server (new_project.py) works out the "Stage", i.e. whose turn it is.
//   This script does the parts that happen in the browser:
//     1. Paste WO Message -> "Extract & Fill" reads the pasted MWO text and fills the fields.
//     2. Months is worked out from the WO Date (billing month runs from the 21st to the 20th).
//     3. The tabs are coloured like the sheet and the form opens on the current stage's tab.
//     4. "Send Mail to Planning" opens an editable email draft for the Project Head.
//     5. The Save button says who gets the project next, e.g. "Send to Area Manager".
//     6. Each role sees only the tabs it fills, plus tabs someone has already filled.
//
// Change log
//   2026-10-07  Created: paste-message parser, Extract & Fill, billing month from WO Date.
//   2026-10-07  Added "Send Mail to Planning" (email draft the Project Head can edit and send).
//   2026-10-07  Mail button limited to Project Head / System Manager (not the Area Manager).
//   2026-10-07  Added stage tabs: first as Pending / Done, then one coloured tab per sheet block.
//   2026-10-07  Fiber Team merged into the Area Manager's "Survey & Fiber Team" tab.
//   2026-10-07  Added this header and a description on every function.
//   2026-10-08  Save button renamed after the next owner ("Send to Area Manager", "Send to
//               Project Head", "Send to Fiber Team", "Send to Splicing Team", "Mark RFS Done").
//   2026-10-08  Each role sees only its own tabs plus tabs already filled (System Manager: all).
//   2026-10-09  OH Project flow: new tabs "AT & HOTO" (Project Head) and "Billing" (Accounts);
//               stages after RFS are AT & HOTO -> Billing -> Closed, plus Cancelled.
//               Extract & Fill now reads every line of the WO (Unique ID, WO Type, BTS Type,
//               POP ID, Core, Ports, Feeder, B Point, Feeder Length, Nearest ODF, Remarks,
//               Marketing/Sales names), the City from the MWO No and sets the Customer to
//               Airtel; it warns when the Feeder Partner is not Evision.
//               Final Amount = Base + GST is shown while typing.
//   2026-10-09  Splicing Team is a table of Rider + Splicer pairs: entering "Splicing Team
//               Required No" gives that many rows. Assistant Splicer removed.
// ---------------------------------------------------------------------------------------------

// Month names, used to print the billing month ("October 2026") and to read "01-Oct-26".

const MONTH_NAMES = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
];
const SHORT_MONTHS = MONTH_NAMES.map((m) => m.slice(0, 3).toLowerCase());

// Which line of the pasted message fills which field: message label (normalised) -> fieldname.
const MESSAGE_FIELD_MAP = {
	mwono: "wo",
	wono: "wo",
	sitename: "end_location_name",
	sitelatlong: "end_location_lat_long",
	sitecontactperson: "cust_name",
	sitecontactno: "cust_contact_no",
	hp: "hp",
	giscode: "gis",
	// 2026-10-09: the rest of the Airtel MWO message.
	uniqueid: "unique_id",
	wotype: "wo_type",
	btstype: "bts_type",
	popid: "pop_id",
	core: "wo_core",
	portrequired: "port_required",
	portavailability: "port_availability",
	feederip1own: "feeder",
	feeder: "feeder",
	feederpartner: "feeder_partner",
	bpoint: "b_point",
	feederlength: "wo_distance",
	nearestodfno: "nearest_odf",
	nearestodf: "nearest_odf",
	remarks: "wo_remarks",
	connectfromprimary: "connect_from_primary",
	connectfromsecondary: "connect_from_secondary",
	marketingbde: "marketing_bde",
	marketingtm: "marketing_tm",
	salestsm: "sales_tsm",
};

// Message values that go into number fields: "160 mtrs" -> 160.
const NUMBER_FIELDS = ["wo_distance"];

// Date: 2026-10-07
// Returns true if the logged-in user may mail Planning.
// Only the Project Head mails Planning; the Area Manager gets no mail option.
function can_send_mail() {
	return frappe.user.has_role(["Project Head", "System Manager"]);
}

// One tab per colour block of the project sheet. `stage` is the Stage value during which the
// tab is being worked on; the first tab is the Project Head creating the project.
const STAGE_TABS = [
	{ tab: "project_details_tab", color: "#f2e600", stage: null },
	{ tab: "survey_tab", color: "#e59edd", stage: "Survey by Area Manager" },
	{ tab: "planning_approval_tab", color: "#00b0f0", stage: "B End Approval by Project Head" },
	// The Area Manager also assigns the Fiber Team, so it shares the Survey tab.
	{ tab: "survey_tab", color: "#e59edd", stage: "Fiber Team Assignment by Area Manager" },
	{ tab: "fiber_work_tab", color: "#92d050", stage: "Fiber Work by Fiber Team" },
	{ tab: "splicing_team_tab", color: "#bdd7ee", stage: "Splicer Assignment by Area Manager" },
	{ tab: "splicing_work_tab", color: "#f8cbad", stage: "Splicing by Splicing Team" },
	{ tab: "final_details_tab", color: "#41b0e4", stage: "Final Details by Project Head" },
	// 2026-10-09: after RFS.
	{ tab: "at_hoto_tab", color: "#f2e600", stage: "AT & HOTO by Project Head" },
	{ tab: "billing_tab", color: "#a9d08e", stage: "Billing by Accounts" },
];

// Which role fills each tab. System Manager sees every tab.
const TAB_OWNERS = {
	project_details_tab: "Project Head",
	survey_tab: "Area Manager",
	planning_approval_tab: "Project Head",
	fiber_work_tab: "Fiber Team",
	splicing_team_tab: "Area Manager",
	splicing_work_tab: "Splicing Team",
	final_details_tab: "Project Head",
	at_hoto_tab: "Project Head",
	billing_tab: ["Accounts User", "Accounts Manager"],
};

// Fields the server works out; they don't make a tab count as filled.
const CALCULATED_FIELDS = ["stage", "b_end_status", "site_status", "rfs_month", "distance_difference", "final_amount", "network_link"];

// Field types that hold no data of their own.
const NO_VALUE_TYPES = ["Section Break", "Column Break", "Tab Break", "Button", "HTML", "Heading"];

// Date: 2026-10-08
// True if any field in the tab already has a value (a Fiber Team row counts too).
// Fields worked out by the server (CALCULATED_FIELDS) don't count as filled.
function tab_is_filled(frm, tab_fieldname) {
	let in_tab = false;
	for (const df of frm.meta.fields) {
		if (df.fieldtype === "Tab Break") {
			in_tab = df.fieldname === tab_fieldname;
			continue;
		}
		if (!in_tab || NO_VALUE_TYPES.includes(df.fieldtype) || CALCULATED_FIELDS.includes(df.fieldname)) continue;
		const value = frm.doc[df.fieldname];
		if (Array.isArray(value) ? value.length : value) return true;
	}
	return false;
}

// Date: 2026-10-08
// Each role sees only its own tabs, plus tabs that are already filled (so the Area Manager can
// read the project details and the Project Head can see the survey). Empty tabs of other
// roles stay hidden until someone fills them.
function show_role_tabs(frm) {
	if (frappe.user.has_role("System Manager")) return;
	(frm.layout.tabs || []).forEach((tab) => {
		const owner = TAB_OWNERS[tab.df.fieldname];
		if (!owner) return;
		const show = frappe.user.has_role(owner) || tab_is_filled(frm, tab.df.fieldname);
		tab.df.hidden = show ? 0 : 1;
	});
	frm.layout.refresh_tabs();
}

// Date: 2026-10-07
// Runs on every form refresh. Colours each tab like the sheet, shows the "Current stage" banner,
// and opens the tab of the stage the project is at.
function arrange_stage_tabs(frm) {
	const tabs = {};
	(frm.layout.tabs || []).forEach((tab) => (tabs[tab.df.fieldname] = tab));
	STAGE_TABS.forEach(({ tab, color }) => {
		if (tabs[tab]) tabs[tab].tab_link.find(".nav-link").css("border-top", `3px solid ${color}`);
	});

	if (frm.is_new() || !frm.doc.stage) return;
	const colour = { Closed: "green", Cancelled: "red" }[frm.doc.stage] || "blue";
	frm.set_intro(__("Current stage: {0}", [__(frm.doc.stage).bold()]), colour);

	// Jump to the current stage's tab when the project opens or its stage changes, not on every refresh.
	const key = `${frm.doc.name}:${frm.doc.stage}`;
	if (frm.__stage_tab_key === key) return;
	frm.__stage_tab_key = key;
	const current = STAGE_TABS.find((entry) => entry.stage === frm.doc.stage) || STAGE_TABS[STAGE_TABS.length - 1];
	const tab = tabs[current.tab];
	if (tab && !tab.is_hidden()) tab.set_active();
}

// Who acts at each Stage; the Save button is named after them ("Send to Area Manager").
const STAGE_OWNERS = {
	"Survey by Area Manager": "Area Manager",
	"B End Approval by Project Head": "Project Head",
	"Fiber Team Assignment by Area Manager": "Area Manager",
	"Fiber Work by Fiber Team": "Fiber Team",
	"Splicer Assignment by Area Manager": "Area Manager",
	"Splicing by Splicing Team": "Splicing Team",
	"Final Details by Project Head": "Project Head",
	"AT & HOTO by Project Head": "Project Head",
	"Billing by Accounts": "Accounts",
	Closed: null,
	Cancelled: null,
};

// Payment statuses that end the Billing stage (same as PAYMENT_DONE in new_project.py).
const PAYMENT_DONE = ["Fully Received", "Cancelled/ Written Off"];

// Date: 2026-10-08
// The Stage the project will be at once saved. Same rules as get_stage() in new_project.py.
// 2026-10-09: Cancelled, then AT & HOTO, Billing and Closed after the RFS Date.
function get_next_stage(doc) {
	if (doc.is_cancelled) return "Cancelled";
	if ((doc.b_end_issue_or_distance_issue || "").trim() && !doc.planning_approval_date) {
		return "B End Approval by Project Head";
	}
	if (!(doc.survey_a_end_done_by_area_manager && doc.survey_b_end_done_by_area_manager && doc.survey_distance_done_by_area_manager)) {
		return "Survey by Area Manager";
	}
	if (!(doc.fiber_team || []).length) return "Fiber Team Assignment by Area Manager";
	if (!(doc.fiber_id_and_reading_a_end_snap && doc.fiber_id_and_reading_b_end_snap)) return "Fiber Work by Fiber Team";
	if (!(doc.splicing_team || []).length) return "Splicer Assignment by Area Manager";
	if (!(doc.splicing_snap_a_end && doc.splicing_snap_b_end)) return "Splicing by Splicing Team";
	if (!doc.rfs_date) return "Final Details by Project Head";
	if (!(doc.at_status === "Done" && doc.hoto_date)) return "AT & HOTO by Project Head";
	if (!PAYMENT_DONE.includes(doc.payment_status)) return "Billing by Accounts";
	return "Closed";
}

// Date: 2026-10-08
// Names the Save button after whoever gets the project next: "Send to Area Manager",
// "Send to Project Head", "Send to Fiber Team", "Send to Splicing Team", "Send to Accounts".
// It stays "Save" while the project would not change hands (the same owner keeps working).
// 2026-10-09: "Mark RFS Done" when the RFS Date is filled, "Close Project" / "Cancel Project".
function set_send_button(frm) {
	const btn = frm.page.btn_primary;
	if (!btn || frm.toolbar?.current_status !== "Save") return;
	// A new project is being filled by the Project Head.
	const current_owner = frm.is_new() ? "Project Head" : STAGE_OWNERS[frm.doc.stage];
	const next_stage = get_next_stage(frm.doc);
	const next_owner = STAGE_OWNERS[next_stage];
	const changes = next_stage !== frm.doc.stage;
	let label = __("Save");
	if (changes && next_stage === "Cancelled") label = __("Cancel Project");
	else if (changes && next_stage === "Closed") label = __("Close Project");
	else if (changes && frm.doc.stage === "Final Details by Project Head") label = __("Mark RFS Done");
	else if (next_owner && next_owner !== current_owner) label = __("Send to {0}", [__(next_owner)]);
	btn.html(label).attr("data-label", label);
}

// Form events: Frappe calls these when the form is drawn or when a field/button is used.
frappe.ui.form.on("New Project", {
	// Date: 2026-10-08
	// Runs once per form: rename the Save button again every time a field changes.
	setup(frm) {
		// Frappe redraws the Save button on each change; wait one tick so this runs after it.
		$(frm.wrapper).on("dirty", () => setTimeout(() => set_send_button(frm), 0));
	},

	// Date: 2026-10-07
	// Form opened or reloaded: hide the mail button from non Project Heads and set up the tabs.
	// 2026-10-08: also names the Save button after the next owner, and shows only the user's tabs.
	refresh(frm) {
		frm.toggle_display("send_mail_to_planning", can_send_mail());
		show_role_tabs(frm);
		arrange_stage_tabs(frm);
		set_send_button(frm);
	},

	// Date: 2026-10-08
	// After saving: say who the project went to when it changed hands.
	after_save(frm) {
		const owner = STAGE_OWNERS[frm.doc.stage];
		if (owner && owner !== frm.__sent_from_owner) {
			frappe.show_alert({ message: __("Sent to {0}: {1}", [__(owner), __(frm.doc.stage)]), indicator: "green" });
		}
	},

	// Date: 2026-10-08
	// Before saving: remember who held the project, so after_save can tell whether it changed hands.
	before_save(frm) {
		frm.__sent_from_owner = frm.is_new() ? "Project Head" : STAGE_OWNERS[frm.doc.stage];
	},

	// Date: 2026-10-08
	// Fiber Team rows added or removed don't mark the form dirty in every Frappe version.
	fiber_team_add: set_send_button,
	fiber_team_remove: set_send_button,

	// Date: 2026-10-07
	// "Extract & Fill" button: read the pasted WO message and fill the fields.
	extract_data(frm) {
		extract_and_fill(frm);
	},

	// Date: 2026-10-07
	// WO Date changed: recalculate the billing month.
	wo_date(frm) {
		frm.set_value("months", get_billing_month(frm.doc.wo_date));
	},

	// Date: 2026-10-07
	// "Send Mail to Planning" button: open the email draft.
	send_mail_to_planning(frm) {
		send_mail_to_planning(frm);
	},

	// Date: 2026-10-09
	// "Splicing Team Required No" changed: show exactly that many Rider + Splicer rows.
	splicing_team_required_no(frm) {
		set_splicing_rows(frm, cint(frm.doc.splicing_team_required_no));
	},

	// Date: 2026-10-09
	// Opening the Splicing Team tab with a number but no rows yet: draw the rows.
	onload_post_render(frm) {
		const wanted = cint(frm.doc.splicing_team_required_no);
		if (wanted && !(frm.doc.splicing_team || []).length && frm.perm[2]?.write) set_splicing_rows(frm, wanted);
	},

	// Date: 2026-10-09
	// Ownership changed: clear the team or vendor of the other kind.
	ownership(frm) {
		if (frm.doc.ownership !== "EVisions") frm.set_value("evision_team", null);
		if (frm.doc.ownership !== "Vendor") frm.set_value("project_vendor", null);
	},

	// Date: 2026-10-09
	// Base or GST amount changed: show Final Amount straight away (the server works it out too).
	base_amount: set_final_amount,
	gst_amount: set_final_amount,
});

// Date: 2026-10-09
// Final Amount = Base Amount + GST Amount.
function set_final_amount(frm) {
	frm.set_value("final_amount", flt(frm.doc.base_amount) + flt(frm.doc.gst_amount));
}

// Date: 2026-10-09
// Make the Splicing Team table have exactly `count` Rider + Splicer rows: add empty rows at the end,
// or remove rows from the end (empty ones first, so names already picked are kept where possible).
function set_splicing_rows(frm, count) {
	count = Math.max(0, Math.min(count, 20));
	let rows = [...(frm.doc.splicing_team || [])];
	// Too many: drop empty rows from the end first, then filled ones from the end.
	for (let i = rows.length - 1; i >= 0 && rows.length > count; i--) {
		if (!rows[i].rider && !rows[i].splicer) rows.splice(i, 1);
	}
	rows = rows.slice(0, count);
	frm.doc.splicing_team = rows;
	while (frm.doc.splicing_team.length < count) frm.add_child("splicing_team");
	frm.doc.splicing_team.forEach((row, i) => (row.idx = i + 1));
	frm.dirty();
	frm.refresh_field("splicing_team");
	set_send_button(frm);
}

// Child table events: adding or removing a pair by hand keeps the count in step.
frappe.ui.form.on("Project Splicing Team Member", {
	// Date: 2026-10-09
	// A row added with "Add Row": raise Splicing Team Required No to match.
	splicing_team_add(frm) {
		frm.doc.splicing_team_required_no = (frm.doc.splicing_team || []).length;
		frm.refresh_field("splicing_team_required_no");
		set_send_button(frm);
	},
	// Date: 2026-10-09
	// A row deleted by hand: lower Splicing Team Required No to match.
	splicing_team_remove(frm) {
		frm.doc.splicing_team_required_no = (frm.doc.splicing_team || []).length;
		frm.refresh_field("splicing_team_required_no");
		set_send_button(frm);
	},
});

// Date: 2026-10-07
// Opens the email composer with a ready draft; the Project Head edits it, adds recipients and sends.
// The draft is a table of the WO, the site, Planning's survey, the Area Manager's survey and the issue.
function send_mail_to_planning(frm) {
	if (!can_send_mail()) {
		frappe.msgprint(__("Only the Project Head can send this mail."));
		return;
	}
	if (frm.is_new() || frm.is_dirty()) {
		frappe.msgprint(__("Please save the project first."));
		return;
	}
	const doc = frm.doc;
	const esc = frappe.utils.escape_html;
	const row = (label, value) =>
		`<tr><td style="padding:4px 10px;border:1px solid #ccc;"><b>${label}</b></td>` +
		`<td style="padding:4px 10px;border:1px solid #ccc;">${esc(String(value ?? "") || "-")}</td></tr>`;
	const site = doc.end_location_name || doc.name;

	const message = `<p>Dear Planning Team,</p>
<p>During the site survey for the work order below, our Area Manager found an issue with the B End / distance. Please review and approve the new B End location.</p>
<table style="border-collapse:collapse;">
${row("WO", doc.wo)}
${row("WO Date", doc.wo_date ? frappe.datetime.str_to_user(doc.wo_date) : "")}
${row("Site", doc.end_location_name)}
${row("Site Lat Long", doc.end_location_lat_long)}
${row("GIS", doc.gis)}
${row("HP", doc.hp)}
${row("Survey Start Location (Planning)", doc.survey_start_location_received_by_planning)}
${row("Survey Start Lat Long (Planning)", doc.survey_start_location_received_by_planning_lat_long)}
${row("Survey Distance (Planning)", doc.survey_distance_received_by_planning)}
${row("Survey A End (Area Manager)", doc.survey_a_end_done_by_area_manager)}
${row("Survey B End (Area Manager)", doc.survey_b_end_done_by_area_manager)}
${row("Survey Distance (Area Manager)", doc.survey_distance_done_by_area_manager)}
${row("Issue", doc.b_end_issue_or_distance_issue)}
${row("New B End Location", doc.new_b_end_location)}
${row("Survey Distance from New B End", doc.survey_distance_from_new_b_end)}
</table>
<p>Kindly confirm the approval by reply.</p>
<p>Regards,<br>${esc(frappe.session.user_fullname)}</p>`;

	new frappe.views.CommunicationComposer({
		doc: doc,
		frm: frm,
		subject: __("B End issue: approval required for {0}", [site]) + (doc.wo ? ` (${doc.wo})` : ""),
		message: message,
	});
}

// Date: 2026-10-07
// Makes a message label comparable: lower case, letters and digits only ("Site Lat-Long" -> "sitelatlong").
function normalise_key(key) {
	return key.toLowerCase().replace(/[^a-z0-9]/g, "");
}

// Date: 2026-10-07
// Splits the pasted message into label/value pairs, one per line. Empty values and "-" are skipped.
// "→ Site Name:- Pokle Sankul" -> { sitename: "Pokle Sankul" }
function parse_message(text) {
	const data = {};
	text.split(/\r?\n/).forEach((line) => {
		const match = line.match(/^[^A-Za-z0-9]*([^:]+?)\s*:-?\s*(.*)$/);
		if (!match) return;
		const value = match[2].replace(/["\s]+$/, "").trim();
		if (value && value !== "-") data[normalise_key(match[1])] = value;
	});
	return data;
}

// Date: 2026-10-07
// Builds a "YYYY-MM-DD" date, or returns null if the day/month/year is not a real date.
function to_date_str(year, month, day) {
	const date = new Date(year, month - 1, day);
	if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
		return null;
	}
	return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// Date: 2026-10-07
// Finds the WO Date inside the MWO No and returns it as "YYYY-MM-DD" (null if there is none).
// WO date is the DDMMYYYY part of the MWO No: ".../IBW/01102026/153929"
function get_wo_date(wo) {
	const parts = (wo || "").split("/");
	for (let i = parts.length - 1; i >= 0; i--) {
		const match = parts[i].trim().match(/^(\d{2})(\d{2})(\d{4})$/);
		if (!match) continue;
		const date = to_date_str(cint(match[3]), cint(match[2]), cint(match[1]));
		if (date) return date;
	}
	return null;
}

// Reads the release date from the message heading; it is used as the WO Received Date.
// "New MWO Released - 01-Oct-26" -> "2026-10-01"
function get_released_date(text) {
	const match = text.match(/Released\s*[-:]*\s*(\d{1,2})[-\s/]([A-Za-z]{3})[A-Za-z]*[-\s/](\d{2,4})/i);
	if (!match) return null;
	const month = SHORT_MONTHS.indexOf(match[2].toLowerCase()) + 1;
	if (!month) return null;
	const year = cint(match[3]) < 100 ? 2000 + cint(match[3]) : cint(match[3]);
	return to_date_str(year, month, cint(match[1]));
}

// Date: 2026-10-07
// Works out the billing month ("October 2026") for a date.
// Month runs from 21st to 20th of next month, so 21st onwards belongs to the next month.
function get_billing_month(date_str) {
	if (!date_str) return "";
	const [year, month, day] = date_str.split("-").map((part) => cint(part));
	const date = new Date(year, month - 1, 1);
	if (day >= 21) date.setMonth(date.getMonth() + 1);
	return `${MONTH_NAMES[date.getMonth()]} ${date.getFullYear()}`;
}

// Date: 2026-10-07
// Looks up a master record (Company, Area) by name: exact match first, then "contains".
// Returns the record's name, or null when nothing matches.
async function find_link(doctype, fieldname, value) {
	const exact = await frappe.db.get_value(doctype, { [fieldname]: value }, "name");
	if (exact.message && exact.message.name) return exact.message.name;
	const like = await frappe.db.get_value(doctype, { [fieldname]: ["like", `%${value}%`] }, "name");
	return (like.message && like.message.name) || null;
}

// Date: 2026-10-07
// The whole "Extract & Fill" action: parse the pasted message, work out WO Date and Months,
// match Company and Area against their masters, fill the form, and report what was not found.
async function extract_and_fill(frm) {
	const text = frm.doc.wo_message || "";
	const data = parse_message(text);
	const values = {};
	const not_found = [];

	Object.keys(MESSAGE_FIELD_MAP).forEach((key) => {
		if (!data[key]) return;
		const fieldname = MESSAGE_FIELD_MAP[key];
		values[fieldname] = NUMBER_FIELDS.includes(fieldname) ? flt((data[key].match(/[\d.]+/) || [0])[0]) : data[key];
	});

	// 2026-10-09: City is the part after the state in the MWO No (".../Maharashtra/PUNE/Capex/...").
	const city = get_city(values.wo);
	if (city && !frm.doc.city) values.city = city;

	const released_date = get_released_date(text);
	const wo_date = get_wo_date(values.wo) || released_date;
	if (wo_date) {
		values.wo_date = wo_date;
		values.months = get_billing_month(wo_date);
	}
	if (released_date && !frm.doc.wo_received_date) values.wo_received_date = released_date;

	const company = text.match(/Hi\s+(.+?)\s+team/i);
	if (company) {
		const name = await find_link("Company", "company_name", company[1].trim());
		if (name) values.company = name;
		else not_found.push(__("Company {0}", [company[1].trim().bold()]));
	}
	if (data.area) {
		const name = await find_link("Area", "area_name", data.area);
		if (name) values.area = name;
		else not_found.push(__("Area {0}", [data.area.bold()]));
	}
	// 2026-10-09: MWO messages come from Airtel.
	if (/MWO/i.test(text) && !frm.doc.customer) {
		const name = await find_link("Customer", "customer_name", "Airtel");
		if (name) values.customer = name;
		else not_found.push(__("Customer {0}", ["Airtel".bold()]));
	}

	if (!Object.keys(values).length) {
		frappe.msgprint(__("Could not find any data in the message. Please check the pasted text."));
		return;
	}

	await frm.set_value(values);
	frappe.show_alert({
		message: __("{0} fields filled from the message", [Object.keys(values).length]),
		indicator: "green",
	});
	if (not_found.length) {
		frappe.msgprint({
			title: __("Not found in master"),
			indicator: "orange",
			message: __("These were not filled because no matching record exists: {0}", [
				not_found.join(", "),
			]),
		});
	}
	// 2026-10-09: the work is ours only when Evision is the feeder partner.
	if (values.feeder_partner && !/e\s*vision/i.test(values.feeder_partner)) {
		frappe.msgprint({
			title: __("Check Feeder Partner"),
			indicator: "red",
			message: __("Feeder Partner in this WO is {0}, not Evision. Please confirm before going ahead.", [
				frappe.utils.escape_html(values.feeder_partner).bold(),
			]),
		});
	}
}

// Date: 2026-10-09
// City from the MWO No: the part after the state, e.g. "BAL-ANG-UASL-ROM-Maharashtra/PUNE/Capex/..." -> "Pune".
function get_city(wo) {
	const part = ((wo || "").split("/")[1] || "").trim();
	if (!/^[A-Za-z ]{3,}$/.test(part)) return null;
	return part.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}
