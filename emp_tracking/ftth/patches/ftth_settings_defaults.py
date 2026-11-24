# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

"""Fill the FTTH Settings defaults on sites that had emp_tracking before the FTTH module moved in.

Created: 2026-11-24

after_install only runs when emp_tracking is first installed, so a site that already had it
(e.g. Frappe Cloud) gets the FTTH doctypes on migrate but no defaults. Only empty fields are filled.
"""

from emp_tracking.ftth.install import apply_settings_defaults


def execute():
	apply_settings_defaults()
