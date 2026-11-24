# Copyright (c) 2026, milind and contributors
# For license information, please see license.txt

# Salary Formula Viewer (single doctype): shows every component of a chosen Salary Structure with its
# formula in simple words, its condition, whether it is cut for absent days, whether it is part of pay,
# and an example amount for a chosen monthly gross. Read-only: it only reads the structure and never
# changes payroll data. Created: 2026-11-23.
#
# Example amounts use HRMS's own formula evaluator and globals (hrms.payroll.utils, checked on HRMS
# 16.53.0), so they match what a salary slip calculates for a full month. If an HRMS upgrade renames
# them, the fallback below uses frappe.safe_eval with the same basic functions (re-check after upgrade).

import math
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money, get_last_day, getdate, nowdate

try:
	from hrms.payroll.utils import COMPONENT_EVAL_GLOBALS, _safe_eval
except ImportError:  # guarded: internal HRMS names, see header
	COMPONENT_EVAL_GLOBALS = {"round": round, "min": min, "max": max, "ceil": math.ceil,
		"floor": math.floor, "getdate": getdate, "int": int, "float": float}

	def _safe_eval(code, eval_globals=None, eval_locals=None):
		return frappe.safe_eval(code, eval_globals, eval_locals)


class SalaryFormulaViewer(Document):
	@frappe.whitelist()
	def load_formulas(self):
		"""Fill the Formulas table from the chosen Salary Structure (called from the form)."""
		self.set("formulas", [])
		for f in ("company", "example_total_earnings", "example_total_deductions", "example_net_pay", "example_ctc"):
			self.set(f, None)
		if not self.salary_structure:
			return
		ss = frappe.get_doc("Salary Structure", self.salary_structure)
		self.company = ss.company
		names = {r.abbr: r.salary_component for r in ss.earnings + ss.deductions if r.abbr}

		# same variables a salary slip offers to formulas; abbreviations are added as rows are worked out
		end_date = get_last_day(nowdate())
		data = frappe._dict(base=flt(self.example_gross), variable=flt(self.example_variable),
			gender=self.example_gender, end_date=end_date, start_date=end_date.replace(day=1),
			payment_days=end_date.day, total_working_days=end_date.day)
		for abbr in names:
			data[abbr] = 0
		totals = {"earnings": 0.0, "deductions": 0.0}

		for table, label in (("earnings", "Earning"), ("deductions", "Deduction")):
			for r in ss.get(table):
				amount, error = self._example_amount(r, data)
				if r.abbr:
					data[r.abbr] = amount
				in_pay = not r.do_not_include_in_total and not r.statistical_component
				if in_pay:
					totals[table] += amount
				if r.abbr == "CTC":
					self.example_ctc = amount
				self.append("formulas", {
					"component_type": label,
					"salary_component": r.salary_component,
					"abbr": r.abbr,
					"rule": error or explain_formula(r, names),
					"condition_text": explain_condition(r.condition, names),
					"example_amount": amount,
					"cut_for_absent_days": 1 if r.depends_on_payment_days else 0,
					"part_of_pay": 1 if in_pay else 0,
					"formula": r.formula if r.amount_based_on_formula else fmt_money(r.amount, currency="INR"),
					"condition": r.condition,
				})
		self.example_total_earnings = totals["earnings"]
		self.example_total_deductions = totals["deductions"]
		self.example_net_pay = totals["earnings"] - totals["deductions"]

	def _example_amount(self, row, data):
		"""Amount of one structure row for the example (full month); 0 when its condition is false."""
		try:
			if row.condition and not _safe_eval(row.condition.strip(), COMPONENT_EVAL_GLOBALS.copy(), data):
				return 0.0, None
			if row.amount_based_on_formula and row.formula:
				return flt(_safe_eval(row.formula.strip(), COMPONENT_EVAL_GLOBALS.copy(), data), 2), None
			return flt(row.amount, 2), None
		except Exception as e:
			# a formula error is shown in the row instead of stopping the whole view
			return 0.0, _("Could not work out the example: {0}").format(str(e)[:140])


# ---- formula -> simple words ---------------------------------------------------------------
# Covers the patterns used in the RKBG structures (percent of gross, caps, rounding, fixed amounts,
# sums of components). Anything else is shown with component names in place of abbreviations.

def _names(text, names):
	text = re.sub(r"\(\s*base\s*\)|\bbase\b", "Gross", text)
	text = re.sub(r"\bvariable\b", "Variable pay", text)
	if names:
		# one pass, so "PF" is not replaced again inside the already written "PF Employer"
		pattern = r"\b(" + "|".join(re.escape(a) for a in sorted(names, key=len, reverse=True)) + r")\b"
		text = re.sub(pattern, lambda m: names[m.group(1)], text)
	# "(Gross * 0.60)" inside a longer formula -> "60% of Gross"
	text = re.sub(r"\(\s*Gross\s*\*\s*(0?\.\d+)\s*\)", lambda m: f"{flt(m.group(1)) * 100:g}% of Gross", text)
	return text


def _percent(m):
	return f"{flt(m.group(1)) * 100:g}% of"


def explain_formula(row, names):
	if not row.amount_based_on_formula or not row.formula:
		return _("Fixed {0} every month").format(fmt_money(row.amount, currency="INR"))
	f = " ".join(row.formula.split())
	special = []
	if "getdate(end_date).month == 2" in f:  # Professional Tax slab with the February amount
		# 2026-11-23: Maharashtra rule with separate slabs for men and women (structure change of that day)
		g = re.match(r"\(0 if \(?base\)? <= (\d+) else (\d+) if \(?base\)? <= (\d+) else \((\d+) if .*?== 2 else (\d+)\)\)"
			r" if gender == 'Male' else \(0 if \(?base\)? <= (\d+) else \((\d+) if .*?== 2 else (\d+)\)\)$", f)
		if g:
			v = [f"{int(x):,}" for x in g.groups()]
			return _("Men: gross up to {0}: 0; up to {2}: {1}; above: {4} a month ({3} in February). "
				"Women: gross up to {5}: 0; above: {7} a month ({6} in February)").format(*v)
		m = re.match(r"0 if \(base\) <= (\d+) else (\d+) if \(base\) <= (\d+) else \((\d+) if .*== 2 else (\d+)\)", f)
		if m:
			return _("Gross up to {0}: 0; up to {2}: {1}; above: {4} a month ({3} in February)").format(
				*[f"{int(x):,}" for x in m.groups()])
	if f.startswith("round(") and f.endswith(")"):
		f = f[6:-1]
	elif f.startswith("ceil(") and f.endswith(")"):
		f, special = f[5:-1], [_("rounded up")]
	if f.startswith("max(") and f.endswith(", 0)"):
		f = f[4:-4]
		special.append(_("never below 0"))
	f = re.sub(r"min\(\s*(\w+)\s*,\s*(\d+)\s*\)", lambda m: f"{m.group(1)} (counted up to {int(m.group(2)):,})", f)
	f = re.sub(r"round\(", "(", f)
	f = _names(f, names)
	# "(X) * 0.60" / "X * 0.0325" -> "60% of X"; outer brackets dropped only when they wrap the whole X
	m = re.match(r"^\((.+)\)\s*([*/])\s*(\d*\.?\d+)$", f) or re.match(r"^(.+?)\s*([*/])\s*(\d*\.?\d+)$", f)
	if m:
		x, op, n = m.groups()
		f = f"{flt(n) * 100:g}% of {x}" if op == "*" and flt(n) < 1 else f"{x} {'×' if op == '*' else '÷'} {n}"
	if f.startswith("(") and f.endswith(")") and f.count("(") == 1:
		f = f[1:-1]
	f = re.sub(r"\b(\d{4,})\b", lambda m: f"{int(m.group(1)):,}", f)
	if row.formula.strip() == "variable":
		f = _("Variable pay from the employee's Salary Structure Assignment")
	if f.startswith("Gross - "):
		f = _("What is left of Gross after: {0}").format(f[len("Gross - "):].replace(" - ", ", "))
	return f + (f" ({', '.join(special)})" if special else "")


def explain_condition(cond, names):
	if not cond:
		return ""
	c = " ".join(cond.split())
	c = c.replace("<=", "≤").replace(">=", "≥").replace("==", "=").replace("!=", "≠")
	c = re.sub(r"'([^']*)'|\"([^\"]*)\"", lambda m: m.group(1) or m.group(2), c)
	c = re.sub(r"\b(\d{4,})\b", lambda m: f"{int(m.group(1)):,}", c)
	c = c.replace("gender", "Gender")
	return _("Only if {0}").format(_names(c, names))
