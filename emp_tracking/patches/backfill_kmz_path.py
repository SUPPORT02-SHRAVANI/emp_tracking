# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Fills KMZ Route / KMZ Point "KMZ Path" (custom_kmz_path, the folder chain inside the KMZ) for
# rows imported by KMZ Upload before the field existed (the 8 uploads of 2026-10-26).
# Each completed KMZ Upload's file is read again and matched to its rows by dedupe key. Only
# empty paths are written: nodes, sites, the uploads' result counts and everything else stay
# as they are. Safe to run again.
#
# Change log
#   2026-10-27  Created.
# ---------------------------------------------------------------------------------------------

import frappe

from emp_tracking.emp_tracking.doctype.kmz_upload.kmz_upload import read_placemarks, row_key


def execute():
	if not frappe.db.has_column("KMZ Point", "custom_kmz_path") or not frappe.db.exists("DocType", "KMZ Upload"):
		return
	filled = 0
	for upload in frappe.get_all("KMZ Upload", filters={"status": "Completed"}, fields=["name", "kmz_file"], order_by="creation"):
		file_name = frappe.db.get_value("File", {"file_url": upload.kmz_file})
		if not file_name:
			continue
		try:
			placemarks, _ = read_placemarks(frappe.get_doc("File", file_name).get_full_path())
		except Exception:
			frappe.log_error(title=f"KMZ path backfill: could not read {upload.kmz_file}")
			continue
		for doctype in ("KMZ Route", "KMZ Point"):
			# dedupe key -> row name, only rows still without a path
			empty = dict(frappe.get_all(doctype, filters={"custom_kmz_path": ["is", "not set"]},
				fields=["dedupe_key", "name"], as_list=True))
			for pm in placemarks:
				dt, key = row_key(pm)
				if dt == doctype and key in empty and pm["folders"]:
					frappe.db.set_value(doctype, empty.pop(key), "custom_kmz_path", " / ".join(pm["folders"]),
						update_modified=False)
					filled += 1
		frappe.db.commit()
	print("KMZ path backfill: filled", filled)
