# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# ---------------------------------------------------------------------------------------------
# Project Splicing Team Member: child table of New Project (Splicing Team tab)
#
# How this file works
#   One row per Rider + Splicer pair the Area Manager assigns. The number of rows follows
#   "Splicing Team Required No" on the project (see new_project.js). Names are fetched from
#   the Employee. No logic of its own.
#
# Change log
#   2026-10-09  Created; replaces the single Rider / Splicer / Assistant Splicer fields.
# ---------------------------------------------------------------------------------------------

from frappe.model.document import Document


class ProjectSplicingTeamMember(Document):
	pass
