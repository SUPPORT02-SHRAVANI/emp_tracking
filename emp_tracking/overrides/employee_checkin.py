# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Employee Checkin extension: lets chosen employees punch in from anywhere.

Created: 2026-10-21

How it works: HRMS (EmployeeCheckin.validate_distance_from_shift_location) refuses a check-in that is
farther than the Shift Location's radius (home / office location set on the Shift Assignment), when
HR Settings > Allow Geolocation Tracking is on. This mixin is added to the Employee Checkin class
through `extend_doctype_class` in hooks.py, so it runs before the HRMS method in the MRO. When the
employee's "Punch-In Location" (Employee.custom_punch_in_location) is "Anywhere", the location check
is skipped; everyone else still goes through the normal HRMS check via super().

Checked against HRMS 16.19.0; field read re-checked on HRMS 16.53.0 (2026-11-23). After an HRMS
upgrade, re-check that the method name validate_distance_from_shift_location still exists in
hrms/hr/doctype/employee_checkin.

Change log:
	2026-10-21  Created: per-employee "Allow Punch From Anywhere" bypass of the shift location radius.
	2026-11-23  One setting instead of two: the bypass now follows Punch-In Location = "Anywhere" (the
	            field the mobile app already uses). The "Allow Punch From Anywhere" checkbox is retired by
	            setup.retire_allow_punch_from_anywhere() on migrate.
"""

import frappe

PUNCH_IN_LOCATION_FIELD = "custom_punch_in_location"
# Must match the option on the Punch-In Location custom field (fixtures/custom_field.json) and the
# mobile app's PUNCH_IN_LOCATION_RULES.ANYWHERE (src/api/config.ts).
ANYWHERE = "Anywhere"


class EmployeeCheckinMixin:
	# Date: 2026-10-21 (changed 2026-11-23: reads Punch-In Location instead of the old checkbox)
	# Skips the radius check for employees allowed to punch from anywhere. The latitude/longitude the
	# app sends are still saved on the check-in, so field tracking keeps the punch location.
	def validate_distance_from_shift_location(self):
		# The has_field guard keeps check-ins working on a site where the custom field is missing.
		if (
			self.employee
			and frappe.get_meta("Employee").has_field(PUNCH_IN_LOCATION_FIELD)
			and (frappe.db.get_value("Employee", self.employee, PUNCH_IN_LOCATION_FIELD) or "").strip().lower()
			== ANYWHERE.lower()
		):
			return
		return super().validate_distance_from_shift_location()
