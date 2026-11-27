# Changelog

Created 2026-10-21. Earlier changes are recorded in git history and in the change logs inside each file.

## 2026-11-27: Desk tiles hidden even when the menu rebuild fails

- **Summary:** `after_migrate()` now runs `keep_only_desk_icons()` in its own try block. Until now it ran only as the last step of `make_navigation()`, so any earlier failure in the menu rebuild (logged as "rebuilding the desk menu after migrate failed") skipped the hiding.
- **Reason:** After deploying on Frappe Cloud, the main site still showed Milestone. The cause there is not known yet (the site's Error Log has not been checked); this makes the hiding independent of the rest of the menu rebuild.
- **Files or modules affected:** `page/workforce_dashboard/setup.py`
- **Testing (newsite.local, on the server):**
  - `py_compile` passed.
  - `after_migrate()` with `frappe.flags.in_migrate` set, as during a real migrate: the menu rebuild succeeded and only OverHead Project, NOC Helpdesk and Frappe HR stay visible.
  - Without the flag (a plain `bench execute`), Frappe 16.54 refuses to save the archived Workspace Sidebars and the menu rebuild fails. The new block still hid the tiles.
- **Not tested:** The Frappe Cloud site.
- **Pending items:** On the main site: check that the site was updated after the deploy, check its Error Log for "emp_tracking" entries, and redeploy to pick up this commit.

## 2026-11-27: Desk home shows only OverHead Project, NOC Helpdesk and Frappe HR

- **Summary:**
  - `DESK_ICONS` is now OverHead Project, NOC Helpdesk and Frappe HR (it was OverHead Project, Emp Tracking, NOC Helpdesk and EVision). After every migrate, `keep_only_desk_icons()` hides all other desk tiles.
  - The Emp Tracking and EVision tiles are still built, so their sidebars and pages (e.g. the Workforce Dashboard home page) keep working, but they are hidden from the desk home.
  - **Why tiles such as Milestone still showed:** in Frappe 16.54 the desk home follows the hidden flags of a user's saved Desktop Layout, not the Desktop Icon's. The new `hide_others_in_saved_layouts()` therefore sets, in every saved layout:
    - the three tiles and the modules inside them (e.g. Frappe HR's Leaves, Payroll) to shown;
    - everything else to hidden, including the modules of hidden apps, which Frappe otherwise draws loose on the home screen (Accounting, Users, Build, ...).
  - Frappe HR and its modules, hidden by this app before, are shown again in Desktop Icon too.
- **Reason:** User's request: "just keep overhead, noc and hr on the screen on main site" (screenshot of the main site showed Flow, Frappe Framework, Underground, WorkForce, Emp Tracking, ERPNext, Milestone, EVision and Studio as well).
- **Files or modules affected:** `page/workforce_dashboard/setup.py`
- **Testing (newsite.local, on the server):**
  - `py_compile` passed.
  - Ran `keep_only_desk_icons()`. Administrator's saved layout and the Desktop Icons now show only OverHead Project, NOC Helpdesk and Frappe HR at the top level.
  - Headless-browser screenshot of `/desk`: exactly those three tiles. Clicking Frappe HR shows its 9 modules (Expenses, HR Setup, Leaves, Payroll, Performance, Recruitment, Shift & Attendance, Tax & Benefits, Tenure).
  - A first version left the hidden apps' modules loose on the home screen and HR's modules hidden; both were fixed and retested.
- **Not tested:** The main site (it has apps newsite.local doesn't, e.g. Underground; the rule hides any tile not in the list). Users other than Administrator.
- **Pending items:** On the main site: pull and run `bench --site <main-site> migrate`. Staff who used the Emp Tracking tile no longer see it; their login home page (Workforce Dashboard) is unchanged. Not committed.

## 2026-11-27: Office attendance: Present when 9 hours (15 min grace) are completed, whatever the punch times

- **Summary:**
  - The Shift Type "Office 09:30-18:30 (Mobile App)" now judges hours worked (first punch-in to last punch-out), not the clock times:
    - 8 h 45 min or more = Present (a 9-hour day with 15 min grace; e.g. 10:00–19:00, 10:00–18:45, 07:00–16:00);
    - 4.5 h to under 8 h 45 min = Half Day;
    - under 4.5 h = Absent.
  - Punches at any time of the day count (window 00:00–23:59; it used to be 08:30–21:30).
  - The field shift (riders / splicers) is unchanged: any punch-in = Present.
  - It is HRMS's own Auto Attendance with the Shift Type's working-hours thresholds; no HRMS code is changed.
  - New sites get the values from `app_attendance.SHIFT_TYPES`. Existing sites get them from a one-time patch, because `ensure_shift_types()` never overwrites an existing Shift Type.
- **Reason:** User's request: "if an employee punches in at 10 and out at 7 and office hours are completed, mark Present irrespective of shift". User's choices: 9 h full day, Half Day then Absent below it, office staff only; then "add 15 min grace, present from 8h45".
- **Files or modules affected:** `app_attendance.py`, new patch `patches/office_shift_hours_rule.py`, `patches.txt`
- **Testing (newsite.local, on the server):**
  - `py_compile` passed.
  - `bench run-patch emp_tracking.patches.office_shift_hours_rule` succeeded, then was re-run with `--force` after the grace was added. The Shift Type now has 570 / 329 min, Half Day threshold 8.75 h, Absent 4.5 h, and the patch is in Patch Log.
  - HRMS `ShiftType.get_attendance` on sample punches (9 h rule, before the grace): 09:30–18:30 and 07:00–16:00 → Present 9.0 h; 12:00–21:30 → Present 9.5 h.
  - With the grace:
    - 10:00–19:00 → Present 9.0 h; 10:00–18:59 → Present 8.98 h; 10:00–18:45 → Present 8.75 h.
    - 10:00–18:44 → Half Day 8.73 h; 10:00–17:00 → Half Day 7.0 h; 10:00–14:30 → Half Day 4.5 h.
    - 10:00–13:00 → Absent 3.0 h.
  - Punches at 00:05, 07:00 and 23:50 all match the office shift (window 00:00–23:59). Checked with an employee's Default Shift set temporarily and rolled back.
- **Not tested:** A full run of the hourly Auto Attendance job on real punches. No active employee has Mode of Attendance = Mobile App yet, and there are no November attendance records.
- **Pending items:**
  - Days are counted from midnight to midnight, so a day that crosses midnight is split across two dates.
  - Not committed or deployed.

## 2026-11-27: Map: building points, and hovering a building or violet route highlights its routes

- **Summary:**
  - **Hover highlight:** on the NOC Dashboard Map tab, hovering a violet (other building) route makes every route to that same building bold and full colour, drawn on top. Moving away restores them. The tooltip follows the mouse and names the building (Site's `site_name`). A route with no building lights up alone.
  - **Building points:**
    - Each building of the node is a cyan square at its KMZ pin (Site has no coordinates), so it differs from the round complaint dots in both shape and colour.
    - The complaint's own building is larger, with a blue border.
    - Hovering a building lights up its routes and shows its name and route count.
    - The side panel says how many buildings are shown and how many have no pin.
  - **Layer order fixed with map panes:** routes < buildings < closed complaint dots < open complaint pins, so buildings never cover complaints.
  - The map key has three new lines (building, the complaint's building, hover).
  - `get_complaint_route` now returns `site` / `site_name` per route, plus `buildings` and `no_pin`.
- **Reason:** User's requests: "when I hover over building purple line highlight it" and "add building point with different color".
- **Files or modules affected:** `page/noc_dashboard/noc_dashboard.js`, `page/noc_dashboard/noc_dashboard.py`
- **Testing (newsite.local, on the server):**
  - `py_compile` and `node --check` passed.
  - `get_complaint_route("CMP-2610-02729")`: node V0N, 222 routes, 118 buildings with a pin, 0 without. The own building is SITE-01774 "Vastu Anand Apartment".
  - Headless-browser screenshot, with the hover fired from script on "Shree Ram Residency": cyan squares drawn, its 6 routes bold, tooltip "Shree Ram Residency · SITE-01756, 6 fibre routes", and the map key updated.
- **Not tested:** A real mouse hover in a real browser.
- **Pending items:** Reload the page (and restart bench if the Python change isn't picked up). Not committed or deployed.

## 2026-11-26: NOC Performance redesigned; map shows open complaints and the complaint's node routes

- **Summary:**
  - **NOC Performance redesigned:**
    - What the user didn't like in the first version: 18 cut-off columns, and a chart that was one big block.
    - Now each period (and team / splicer) is a bold total row, with a "Day calls" and a "Night calls" row under it.
    - 7 columns: Calls, Closed, Still open, In SLA, Out of SLA, In SLA %, Avg MTTR (h).
    - Cards: Day / Night calls, In SLA % and average MTTR.
    - Chart: with one period, day vs night split into In SLA / Out of SLA / still open; with several, day and night calls per period. Whole numbers on the y axis.
  - **Fluid report tables removed again:** `evision.noc_fluid_table`, added earlier the same day, squeezed grouped (tree) tables into unreadable columns and left them empty. The Pending / Performance reports get wider fixed columns instead.
  - **Map: open complaints stand out:**
    - a dot with a pulsing ring (red after 4 hours) and an age badge ("30d");
    - counts above the map (open, over 4 h, oldest);
    - the side panel lists open complaints oldest first, and a click zooms to one.
  - **Map: the complaint's node route:**
    - Opening a complaint draws its GIS Node's KMZ routes. Routes to its own building are thick blue, the node's other routes thin violet.
    - The node comes from the Node ID, GIS Node ID, Site's node or LINKID's Network Link.
    - The view fits the building's routes, else the node's routes within 3 km.
    - Buttons: "Open node on KMZ Map", "Hide routes". New API `get_complaint_route`.
- **Reason:** User's feedback and requests on 2026-11-26.
- **Files or modules affected:**
  - `report/noc_performance` (.py/.js), `report/noc_pending_summary/noc_pending_summary.py` (widths)
  - the report .js files (fluid option removed)
  - `public/js/evision.js`, `hooks.py` (`EV_ASSET_VERSION` 20261126k)
  - `page/noc_dashboard` (.py/.js)
- **Testing (newsite.local):**
  - `py_compile` and `node --check` passed.
  - Headless-browser screenshots:
    - NOC Performance for Team 1, Sep–Nov: one bold row (93 calls) with Day 78 / Night 15 rows, 7 readable headers and a filled chart.
    - Month-wise Jun–Sep chart.
    - Pending Summary table and chart.
    - Map: 4 open complaints with pulsing rings and age badges, and the open list.
    - Complaint CMP-2610-02729: "Node V0N: 222 fibre routes drawn, 2 to this building", zoomed to the building with the thick blue route.
- **Not tested:** In a real browser. Complaints whose node has no KMZ routes (the panel says so).
- **Pending items:** Not committed or deployed.

## 2026-11-26: NOC points: vendor rule, cut team summary, performance, team availability, field hours, complaints map

- **Summary (user's NOC points):**
  - **Vendor rule:** when a complaint is assigned to a vendor, Rider / Splicer / 2nd Rider / 2nd Splicer are hidden (form) and emptied.
    - The form empties them when a vendor is picked.
    - The server empties them only when the vendor is newly set, so the 39 old closed complaints that name both keep their history.
  - **NOC Cut Team Summary (new report):** per day and team, every SR counted, with "Closed by" (splicer with count). NOC Unique Cut Summary also gets "Closed by".
  - **NOC Performance (new report):** month-wise or day-wise, optionally per team or splicer, with day calls and night calls side by side. A day call is one received 08:00–19:59 (the user's choice). For each: received, closed, In/Out of SLA, In-SLA % and average MTTR.
  - **Team members and NOC Team Availability (new report):** new child table Maintenance Team Member (employee, role, active) on Maintenance Team. Per day and team the report shows:
    - members and splicers;
    - who was Present in Attendance;
    - SRs received;
    - who was sent (with counts);
    - present members with no call.
  - **Field Staff Location Hours (new report):** hours at home / office / complaint sites / other per field employee per day, using the same rules as the dashboard's Employee sheet.
  - **NOC Dashboard Map tab:** complaints only, coloured by status. Clicking one shows its details with an "Open complaint" button.
    - Position: the complaint's own coordinates, else the operator's, else its LINKID's Network Link, else a KMZ pin of its site.
    - Complaints without any of these are counted under the map, not drawn.
  - **Reports look:**
    - An empty period shows a message (no complaints between the dates, and the latest complaint date) instead of an empty chart and rows of dashes.
    - "Closed within 4 h" shows "–" when nothing was closed.
    - Tables with few columns stretch to the full width.
    - Any `…_pct` column is coloured by SLA.
  - **Menu:** NOC Helpdesk gets "Cut Team Summary" and a new section "Performance & Teams".
- **Reason:** User's requests on 2026-11-26.
- **Files or modules affected:**
  - `noc_reports.py`
  - new reports `noc_cut_team_summary`, `noc_performance`, `noc_team_availability`, `field_staff_location_hours`
  - `noc_pending_summary` / `noc_unique_cut_summary` / `noc_unique_cut_master` / `noc_major_outage_closure` / `noc_sla_tat_summary`
  - new doctype `maintenance_team_member`; `maintenance_team` (.json/.py)
  - `complaint_information` (.json/.py/.js)
  - `page/noc_dashboard` (.py/.js)
  - `page/workforce_dashboard/setup.py`
  - `public/js/evision.js`, `hooks.py` (`EV_ASSET_VERSION` 20261126i)
- **Testing (newsite.local, on the server):**
  - `py_compile`, `node --check` and JSON checks passed. `bench migrate` passed: the 4 reports, the Members table, the vendor `depends_on` and the menu are all there.
  - Report results (April 2026):
    - Cut Team Summary: 210 rows; "Closed by" filled (e.g. Team 1, 1 Apr: Rohan Tupe (4), Aakash Nawadi (1)).
    - Performance: April 675 day + 142 night calls = 817 SRs, the same as Pending Summary. Day In-SLA 44.1%, night 16.9%.
    - Team Availability: 202 rows; shows who was sent; "Members not set" because no team has members yet.
    - Field Staff Location Hours: 63 rows (Sep–Nov 2026 pings).
    - November (no data) shows the message.
  - Vendor rule, checked as a real save would see it (`load_doc_before_save`), with nothing saved and the transaction rolled back: a newly set vendor empties the people, and an unrelated edit to an old vendor complaint keeps its splicer.
  - Map tab, in a headless-browser screenshot: 4 of 6 open complaints drawn, details panel filled on click, and "2 not on the map" shown.
  - **New complaints show up live.**
    - Test: one complaint was inserted for today (Team 3, no RFO, like a real new complaint) and then rolled back; it no longer exists.
    - It appeared at once in the Performance tab (received 0 → 1), NOC Performance (1 day call), Team Availability (Team 3, who was sent), the Map (4 → 5) and Live complaints (6 → 7).
  - **Fix found by that test:** "Own fibre faults only" used to keep only RFO = Own Fiber Issue. RFO is filled only at closing, so new open complaints were left out of the reports.
    - A blank RFO now counts.
    - Only complaints marked with another RFO are left out.
- **Not tested:** These screens in a real browser. The vendor rule through the form by a user. Team Availability with real member lists and attendance.
- **Pending items:**
  - Fill each Maintenance Team's Members list, or Team Availability cannot show who was present.
  - Only 2 of 28,661 complaints have coordinates, and Areas / GIS Nodes have none, so old complaints cannot be placed on the map. New complaints appear when NOC fills LINKID / Site / coordinates. Giving Areas coordinates would let old complaints show at their area (not done; needs a decision).
  - Not committed or deployed.

## 2026-11-26: Month bands on charts, NOC reports full screen, one OverHead sidebar for FTTH

- **Summary:**
  - **Month bands:** day-by-day charts covering more than one month get a light band behind every other month, with the month's name. This applies to the NOC Pending / Unique Cut Summary reports and the NOC Dashboard's "Day by day" chart.
    - New helper `evision.month_bands()` draws the bands into the chart's SVG and redraws them after a resize.
    - Labels are day numbers, and the chart shows every n-th one.
    - Frappe's report page overwrites a chart's `axisOptions`. The reports therefore send theirs as `ev_axis`, and `evision.noc_report_after_render` merges it in and draws the chart once more.
  - **NOC reports full screen:**
    - A "Full screen" button shows the report page alone on the whole screen (browser Fullscreen API).
    - The table now fills the screen height (`100vh - 150px`; Frappe's default box left empty space below).
    - Major Outage Closure columns were narrowed to about 1,455 px, so it fits a desktop screen. A missing 2nd splicer shows blank, not "Na".
  - **OverHead Project / FTTH:**
    - The cause: the FTTH module, moved into emp_tracking on 2026-11-24, had no Sidebar document, so Frappe 16.54 computed an "FTTH" sidebar (hammer icon) listing the same work-order screens as OverHead Project.
    - The OverHead Project Sidebar now belongs to module FTTH (`SHELL_MODULES` in setup.py). Frappe no longer builds the copy, and FTTH screens open inside OverHead Project.
- **Reason:** User's requests: a light background per month on charts, "make it full screen", and "why overhead and ftth is same?".
- **Files or modules affected:**
  - `public/js/evision.js`, `public/css/evision.css`, `hooks.py` (`EV_ASSET_VERSION` 20261126g)
  - `report/noc_*/*.js`, `report/noc_pending_summary/noc_pending_summary.py`, `report/noc_major_outage_closure/noc_major_outage_closure.py`
  - `page/noc_dashboard/noc_dashboard.js`
  - `page/workforce_dashboard/setup.py`
- **Testing (newsite.local, on the server):**
  - `py_compile` and `node --check` passed.
  - `make_navigation()` ran with the migrate flag. The app's shells are now Emp Tracking, NOC Helpdesk and OverHead Project (module FTTH), and the computed "FTTH" shell is gone.
  - In headless Chromium screenshots:
    - Pending Summary over August–October shows three month bands and readable day labels.
    - Major Outage Closure has the Full screen button, and its table is 850 px tall at a 940 px window. At 1,740 px with the desk sidebar open it is 33 px wider than the screen; it fits with the sidebar collapsed or in full screen.
    - An FTTH Work Order opens with the OverHead Project sidebar.
- **Not tested:** The Full screen button in a real browser (the headless one cannot enter full screen).
- **Pending items:** Unrelated error seen in the Error Log: "Report execution failed for: FTTH GIS Summary" (2026-11-26 10:34, filter GIS = 03W). Not investigated.

## 2026-11-26: NOC dashboard and reports redesigned; tabs on the dashboard and the Complaint form

- **Summary:**
  - **EVision colours fixed in both themes.** In Frappe 16.54 the Espresso "ink" colours are pale tints in light mode and deep shades in dark mode. Every EVision accent built on them (icons, coloured figures, bars) washed out on white and disappeared on dark cards.
    - `evision.css` now uses explicit accent colours for light and dark.
    - This affects every EVision page, not only NOC.
  - **NOC Dashboard in tabs:** Live complaints (with the open-cut count), Performance and Employee sheet.
    - The last tab is remembered.
    - Performance and Employee sheet load when they are first opened.
  - **Performance redesigned:**
    - It opens with a carry-forward strip (opening + received − closed = pending, the NOC sheet's own rule) and the In/Out SLA split.
    - Quick ranges (This month / Last month / Last 3 months).
    - The team table shows SLA bars.
    - Time to close is one split bar with a legend.
    - Busiest days are grouped by month.
    - Labels are in sentence case and chart colours follow the theme.
  - **Reports restyled:**
    - Shared cell colours (`evision.noc_formatter`): In SLA green, Out of SLA red, pending amber, zeros shown as "–".
    - Shared scope filters (`evision.noc_scope_filters`).
    - Short column names.
    - Pending / Unique Cut Summary team-wise and Major Outage Closure are trees (day or month rows with their teams under them).
    - Readable chart labels. The SLA/TAT chart is split by the first row key that has more than one value.
  - **Complaint Information form in tabs:** Complaint / Location / Assignment / Closure & SLA. Time & SLA is no longer collapsed.
  - **Bug fix:** `frappe.datetime.month_start()` ignores its argument, so "last 3 months" defaults (dashboard quick range and Major Outage report) used this month. They now use moment.
- **Reason:** User's requests: the dashboard and reports "don't look good", and asked for tabs on the dashboard and the complaint form.
- **Files or modules affected:**
  - `public/css/evision.css`, `public/js/evision.js`, `hooks.py` (`EV_ASSET_VERSION` 20261126c)
  - `emp_tracking/page/noc_dashboard/noc_dashboard.js`, `noc_reports.py` (`kpis.opening`)
  - `emp_tracking/report/noc_*` (.py / .js)
  - `doctype/complaint_information/complaint_information.json` (4 Tab Breaks; the diff only adds them) and `.py` (file history)
- **Testing (newsite.local, on the server):**
  - `py_compile` and `node --check` passed. `bench migrate` passed, and the four Tab Break fields are in the DocType.
  - Reviewed in headless Chromium screenshots (logged in as Administrator):
    - the dashboard's Live and Performance tabs, in light and dark mode;
    - Pending Summary (team-wise tree), SLA TAT Summary, Major Outage Closure and Unique Cut Master;
    - a closed complaint's form with its tabs.
  - The quick range and tab buttons worked when clicked in that browser.
- **Not tested:** A real user's browser and phone-width layouts. The Employee sheet tab with an employee picked.
- **Pending items:** As in the entry below (missing workbook complaints, Unique Cut grouping).

## 2026-11-26: NOC reports and dashboard laid out like the NOC report workbook

- **Summary:**
  - Five new Script Reports. Each one is a tab of the client's NOC workbook:
    - **NOC Pending Summary** (PENDING SUMMARY; with "Team Wise", TEAM WISE PENDING SUMMARY)
    - **NOC Unique Cut Summary** (UNIQUE CUT TEAM SUMMARY)
    - **NOC Unique Cut Master** (UNIQUE CUT MASTER)
    - **NOC Major Outage Closure** (MAJOR OUTAGE CLOSURE)
    - **NOC SLA TAT Summary** (the ALL TEAM SUMMARY pivots; "Rows" picks the pivot layout)
  - All five are in a new "NOC Reports" section of the NOC Helpdesk menu.
  - The NOC Dashboard has a new **Performance** section, with From / To / Team filters. It shows KPI tiles, a daily received / closed / pending chart, a team-wise table, TAT buckets and the major outage days. It also has a "NOC Reports" button menu that opens each report with the same dates.
  - Every number comes from one module, `emp_tracking/noc_reports.py`, so the dashboard and the reports always agree. The rules are copied from the workbook's LOGIC / CUT LOGIC notes.
  - New field **Unique Cut** on Complaint Information. If left blank, it is set to the Complaint Code. The NOC import fills it from UNIQUE CUT.
  - Patch `backfill_unique_cut` filled it for the existing complaints from their "Unique cut:" detail line, then the code, then the name.
- **Reason:** User's request ("this is how you have to show dashboard and … reports"), with the NOC workbook as the layout.
- **Default scope = the workbook's scope:** own teams only, RFO "Own Fiber Issue" only, no terminations. Checked against the workbook: 3,555 of the 3,576 complaints in both are Own Fiber Issue. Both scope checks can be switched off in every report.
- **Differences from the workbook (on purpose):**
  - The first day's opening carry-forward is the real backlog. The workbook started from 0.
  - Days ≥ 3 are labelled "3+ Days". The workbook says ">3 Days" for 3 days too.
  - A Closed complaint with no Team SR closed time counts at its Company close time. With neither time it is left out (46 imported 2025 complaints).
  - The workbook's PRESENT TEAM COUNT / AVAILABLE SPLICER were typed by hand. The report shows "Splicers Working", counted from the complaints.
- **Files or modules affected:**
  - `emp_tracking/noc_reports.py` (new)
  - `emp_tracking/emp_tracking/report/noc_*` (5 new reports)
  - `emp_tracking/emp_tracking/page/noc_dashboard/noc_dashboard.js`
  - `emp_tracking/emp_tracking/doctype/complaint_information/complaint_information.{json,py}`
  - `emp_tracking/noc_complaint_import.py`
  - `emp_tracking/patches/backfill_unique_cut.py`
  - `emp_tracking/patches.txt`
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (menu)
- **Testing (newsite.local, on the server):**
  - `py_compile` passed for every changed Python file. `node --check` passed for every JS file. All JSON files parse.
  - `bench migrate` passed. The patch ran: no empty Unique Cut is left, and 506 differ from the Complaint Code. All 5 reports exist, and the NOC Helpdesk menu shows the NOC Reports section.
  - All 5 reports ran for April 2026, in 0.1–0.4 s each.
  - Against the workbook's PENDING SUMMARY:
    - 2 Apr (77 / 31) and 5 Apr (24 / 57) received / closed match exactly. 1, 3 and 4 Apr are within 1–4.
    - Closing pending on 30 Apr is 8, as in the workbook.
  - `get_performance` returns in 0.2 s.
- **Not tested:** The reports and the dashboard section in a browser (layout, chart, buttons).
- **Pending items:**
  - 462 complaints in the workbook (April–September 2026) are not in the app, so app totals are lower than the workbook's.
  - The app's Unique Cut mostly equals the Complaint Code, while the workbook groups about 15% of SRs into shared cuts. Until those are imported, cut counts ≈ SR counts.
  - The dashboard opens on the current month. newsite.local has no complaints after 2026-10-27, so it shows zeros until the dates are changed.

## 2026-11-26: Separate workspace icons for OverHead Project and NOC (NOC tile renamed "NOC Helpdesk")

- **Summary:**
  - Each module tile now writes its own Frappe 16.54 `Sidebar` ("shell") through the new `make_shell()` in `make_navigation()`. Each one has its own header icon and menu:
    - OverHead Project: `radio-tower`
    - Emp Tracking: `dashboard`
    - NOC Helpdesk: `monitor-cog`
  - The NOC tile is renamed **NOC Helpdesk** (`NOC_TILE`). The old "NOC" Desktop Icon, archived Workspace Sidebar and Sidebar are deleted through `OLD_SIDEBARS`.
  - The NOC desk tile picture is renamed to `noc_helpdesk.svg` (solid and subtle) and recoloured orange (`#EA580C`). It was the same purple as EVision.
- **Reason:**
  - User's request: OverHead Project and NOC showed the same workspace icon.
  - Cause: Frappe 16.54's migration merged the "OverHead Project", "Emp Tracking" and "NOC" sidebars into one `Sidebar` called "Emp Tracking" (see its `merged_from`). All three tiles therefore showed its single "dashboard" icon.
  - Why the rename: a shell's name is its URL segment, and `/desk/noc` already belongs to the NOC DocType. With a shell named "NOC", routes would be read as NOC records.
- **Files or modules affected:**
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py`
  - `emp_tracking/emp_tracking/page/workforce_dashboard/workforce_dashboard.js` (`OH_SIDEBARS`)
  - `emp_tracking/public/icons/desktop_icons/{solid,subtle}/noc.svg` → `noc_helpdesk.svg`
- **Testing (newsite.local, on the server):**
  - `py_compile` passed for `setup.py`. `node --check` passed for `workforce_dashboard.js`.
  - Before the change, the merged "Emp Tracking" sidebar items were backed up to `~/backups/sidebar_emp_tracking_items_2026-11-26.tsv`.
  - Ran `make_navigation()` with `frappe.flags.in_migrate` set, as `after_migrate` would. The boot `module_sidebars` then had three shells:
    - Emp Tracking (`dashboard`, Dashboards)
    - OverHead Project (`radio-tower`, FTTH / Fiber Store / Network / Teams & Vendors)
    - NOC Helpdesk (`monitor-cog`, Complaints)
  - The "NOC" Desktop Icon, Workspace Sidebar and Sidebar are gone. "NOC Helpdesk" exists. No new Error Log entries.
- **Follow-up (same day): tiles added to saved desk layouts**
  - The new tiles were still missing from the desk home. Frappe 16.54 draws only what a user's saved Desktop Layout lists, and never appends icons created later. Administrator's layout (saved 2026-11-24) had "Emp Tracking" only.
  - New `add_desk_icons_to_saved_layouts()` runs from `keep_only_desk_icons()` after every migrate. It adds each missing `DESK_ICONS` tile as a visible entry after "Emp Tracking" and drops a stale "NOC" entry. The user's other entries, their order and their hidden flags are left alone.
  - Before the change, Administrator's layout was backed up to `~/backups/desktop_layout_administrator_2026-11-26.json` on the server.
  - Ran it on newsite.local: the layout went from 42 to 45 entries, and the visible top level now has Emp Tracking, OverHead Project, NOC Helpdesk and EVision. A second run changed nothing. `py_compile` passed.
- **Not tested:** The desk home, sidebar header and tile clicks in a browser.
- **Pending items:**
  - Outside `bench migrate`, Frappe 16.54 refuses writes to the archived Workspace Sidebar. A plain `bench execute ...make_navigation` therefore fails in `make_tile()`. `after_migrate` works.
  - The `Sidebar` writes also need developer mode or migrate.
  - EVision has no Sidebar of its own, because the Module Def "Evision" blocks that title. Its tile behaves as before.

## 2026-11-25: Milestone tile removed from the desk home

- **Summary:** "Milestone" was taken out of `DESK_ICONS`. `keep_only_desk_icons()` now hides its desk tile, like every other non-EVision icon. Only the tile is hidden: milestone_app (BNI Milestone) and its data stay installed.
- **Reason:** User's request. Milestone belongs to milestone_app (BNI) and is not an EVision module. It was on the desk home only because it was in the keep list since 2026-10-29.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py`.
- **Testing (newsite.local):**
  - `py_compile` passed.
  - `keep_only_desk_icons()` ran, and the cache was cleared.
  - The visible top-level tiles are now EVision, NOC, Emp Tracking and OverHead Project. Milestone has `hidden = 1`.
- **Follow-up (same day):**
  - The tile was still shown for Administrator. Administrator had a saved **Desktop Layout** (2026-11-24) in which Milestone was `hidden: 0`, and Frappe 16 draws the desk home from that saved layout.
  - Only the Milestone entry in that layout was set to `hidden: 1`. This was a data change on newsite.local, with no code change.
  - Checked afterwards: it reads `hidden = 1`. It is the only Desktop Layout on the site.
- **Not tested:** The desk home in the browser.
- **Pending items:**
  - `keep_only_desk_icons()` does not update saved Desktop Layouts. A user who saved an arrangement before an icon was hidden keeps seeing that icon until they reset their layout.
  - To show Milestone again, put "Milestone" back in `DESK_ICONS`, set the icon's `hidden` to 0, and unhide it in the user's layout.

## 2026-11-25: Weekly Shift Roster tool

- **Summary:**
  - New **Weekly Roster** button on the Shift Assignment list. The dialog takes:
    - employees;
    - a shift rotation (1 or more Shift Types, in order);
    - a start date (defaults to next Monday);
    - a number of weeks (1–26).
  - **Preview** shows the plan. **Create** makes one submitted Shift Assignment per employee per week.
  - Week *i* gets rotation row *i mod n*. With one row, the employee gets the same shift every week.
  - A week is **skipped** if the employee already has an active submitted Shift Assignment that overlaps it. It is also skipped if the employee is not Active. Existing assignments are never changed, so running it again is safe.
  - Each week is created in its own savepoint. A failed week is shown as "Failed" with the error, and the weeks before it are kept.
  - HRMS's own list `onload` ("Shift Tools" button) is kept.
- **Reason:** HRMS 16.53.0 has no Shift Assignment Schedule. Before this, a different shift each week had to be entered by hand, one assignment per week. User asked for a weekly roster tool.
- **Files or modules affected:** `emp_tracking/shift_roster.py` (new), `emp_tracking/public/js/shift_assignment_list.js` (new), `emp_tracking/hooks.py` (`doctype_list_js`).
- **Testing (newsite.local, on the server):**
  - `py_compile` passed for `shift_roster.py` and `hooks.py`. `node --check` passed for the JS.
  - Ran `create_weekly_roster` on demo employee HR-EMP-00066 in one transaction, rolled back afterwards. The Shift Assignment count was 5 before and 5 after.
    - Dry run, 6 weeks: the 4 existing demo weeks were Skipped, and weeks 5–6 were To Create.
    - Real run with JSON arguments (as the browser sends them): 2 created (Office, then Field), 4 skipped.
    - Re-run with the same input: 0 created, 6 skipped.
    - Empty employees, an unknown Shift Type and 99 weeks were all rejected with clear messages.
  - `bench --site newsite.local clear-cache` was run.
- **Not tested:**
  - The dialog in the browser.
  - The "Failed" path: no HRMS validation error was produced in the test.
  - A non-Administrator user's permissions.
- **Pending items:** Try the button in the browser. The demo records (employee HR-EMP-00066 and HR-SHA-26-11-00002 … 00005) are still on newsite.local and can be removed when no longer needed.

## 2026-11-24: FTTH Work Order tests fixed; New Project removal keeps a backup

- **Summary:**
  - `test_ftth_work_order.py`: `setUp` now creates the Field Staff "Test Manager" before the GIS Node. GIS Node.area_manager is a Link to Field Staff, and the tests still passed plain text, so all 4 failed with `LinkValidationError`. They were already broken in the ftth_tracker app before the move.
  - `patches/remove_new_project.py`: new `backup_rows()`. Before anything is deleted, it writes every New Project row, its Fiber / Splicing team rows, comments and attachment list to `<site>/private/backups/new_project_backup_<time>.json`. If the file cannot be written, the patch stops and nothing is deleted. If there are no rows, it does nothing.
- **Reason:**
  - CI "Run Tests" still failed (in 2 seconds) after the stub clean-up.
  - The first deploy to the Frappe Cloud site (evision.mymagicerp.com, still on the old code) runs this patch. That site may hold real New Projects, unlike the 4 test rows on newsite.local.
- **Files or modules affected:** `emp_tracking/ftth/doctype/ftth_work_order/test_ftth_work_order.py`, `emp_tracking/patches/remove_new_project.py`.
- **Testing:**
  - The 4 FTTH Work Order tests passed on newsite.local, run in one transaction with commit disabled and rolled back. Before the fix they failed with the same error. Afterwards there were 0 test work orders and no ZZT node left.
  - `backup_rows()`:
    - It wrote nothing when the table is missing (newsite.local).
    - In a simulated run against the Area table it saved 175 of 175 rows. That test file was deleted.
- **Not tested:** CI (runs after the push); the patch on the cloud site.
- **Pending items:** Deploy on Frappe Cloud is done by the user (no access from here). Take a site backup there first.

## 2026-11-24: CI test run fixed (empty test stubs removed)

- **Summary:**
  - Removed the 24 auto-generated doctype test files that had no test methods (15 in Emp Tracking, 9 in FTTH).
  - `test_ftth_work_order.py` (4 real tests) now declares `IGNORE_TEST_RECORD_DEPENDENCIES` for its 10 linked doctypes.
- **Reason:** CI failed in "Run Tests" with `DocType Payment Gateway not found` before any test ran. For every doctype that has a test file, Frappe builds sample records by following Link fields. The chain went into ERPNext and ended at Payment Gateway (payments app, not installed in CI or on the bench). The stubs tested nothing, and the work order test makes its own GIS Node and IBD Team in `setUp`.
- **Files or modules affected:** 24 deleted `test_*.py` files under `emp_tracking/emp_tracking/doctype/` and `emp_tracking/ftth/doctype/`, and `emp_tracking/ftth/doctype/ftth_work_order/test_ftth_work_order.py`.
- **Testing:**
  - On the server, `py_compile` passed.
  - The 19 pure-Python tests (`test_performance`, `test_logic`, `test_linking`) passed.
- **Not tested:** The integration tests (including `test_ftth_work_order`) were not run locally. They insert records, so they were not run on newsite.local, and there is no throwaway test site. CI runs them.
- **Pending items:** None known. If CI still fails, the next step depends on its log.

## 2026-11-24: FTTH Tracker code moved into emp_tracking (module "FTTH")

- **Summary:**
  - The whole ftth_tracker app is now part of emp_tracking as module **FTTH** (`emp_tracking/ftth/`): 13 doctypes, the FTTH GIS Summary report, the FTTH Tracker workspace, number cards, dashboard charts, the importer, `logic.py`, `linking.py`, `install.py`, patches and tests.
    - DocType names did not change (FTTH Work Order, GIS Node, KMZ Route …), so all data and links stay as they are.
    - All `ftth_tracker.*` import and method paths were rewritten to `emp_tracking.ftth.*`. That includes the uses in `kmz_upload.py`, `kmz_map.py`, `ftth_stages.py` and the FTTH Work Order JS.
    - The `modified` time of every moved JSON was bumped, so migrate re-syncs it under the new module.
  - `hooks.py`:
    - `required_apps = ["ftth_tracker"]` removed.
    - New `before_install` / `after_install` (FTTH roles and FTTH Settings defaults).
    - FTTH roles added to `after_migrate`.
  - New patch `emp_tracking.ftth.patches.ftth_settings_defaults` fills FTTH Settings on sites that already had emp_tracking, such as Frappe Cloud.
  - CI now builds a version-16 bench and installs ERPNext and HRMS before emp_tracking.
  - **newsite.local:**
    - Backup taken first: `20261124_143510-newsite_local-database.sql.gz`.
    - The old patch names were marked done in Patch Log under their new names.
    - ftth_tracker was removed from the site's installed apps (`remove-from-installed-apps`, no data deleted), then migrate was run.
    - The leftover Module Defs "FTTH Tracker" / "FTTH Tracker (Custom)" were deleted. The FTTH Tracker Workspace Sidebar and Desktop Icon were pointed at the new module and app.
- **Reason:** ftth_tracker was never on GitHub (it existed only on the bench server), so CI and Frappe Cloud could not install emp_tracking, which required it. User asked to bring its code into emp_tracking.
- **Files or modules affected:**
  - `emp_tracking/ftth/` (new).
  - `emp_tracking/modules.txt`, `emp_tracking/hooks.py`, `emp_tracking/patches.txt`.
  - `emp_tracking/emp_tracking/doctype/kmz_upload/kmz_upload.py`, `emp_tracking/emp_tracking/page/kmz_map/kmz_map.py`.
  - `emp_tracking/ftth_stages.py`, `emp_tracking/public/js/ftth_work_order.js`, `emp_tracking/public/js/ftth_work_order_list.js`.
  - `emp_tracking/emp_tracking/report/performance_leaderboard/performance_leaderboard.py` (comment).
  - `.github/workflows/ci.yml`.
- **Testing:**
  - On the server:
    - `compileall` passed, and the importer, work order controller and new patch import.
    - The 12 FTTH unit tests (`test_logic`, `test_linking`) passed.
  - On newsite.local:
    - Migrate ran twice without errors.
    - Row counts of all 12 FTTH tables are the same before and after the move (e.g. 3012 work orders, 486 GIS Nodes, 27898 KMZ Points).
    - Every FTTH DocType, Report, Workspace, Number Card and Dashboard Chart is now module FTTH.
    - FTTH Work Order loads its controller from `emp_tracking.ftth`, and FTTH-33926 validates.
- **Not tested:**
  - CI (runs on GitHub after the push).
  - A fresh install, and Frappe Cloud.
  - Not opened in a browser.
- **Pending items:**
  - **OH.local** still has the separate ftth_tracker app (it has no emp_tracking), so `apps/ftth_tracker` stays on the bench for it. That copy no longer gets changes made in emp_tracking.
  - ftth_tracker's 11 uncommitted local changes were moved in as they were; its own repo was left untouched.

## 2026-11-24: HR / Payroll setup shipped with the app (no employee or payroll data)

- **Summary:**
  - New `emp_tracking/hr_setup.py`, run from `after_migrate`. It creates the HR setup saved in `emp_tracking/hr_setup/*.json` on any site where it is missing:
    - 25 Salary Components. Account rows are kept only when their company and account exist on that site.
    - 7 Leave Types.
    - 3 Salary Structures (RKBG Staff Monthly RA / RI / RIF). Each is submitted, and only created when its Company and all of its components exist.
    - HR Settings and Payroll Settings. Applied once per site (default `emp_tracking_hr_settings_applied`), so later edits there are kept.
    - The "RKBG IPTECH" Letter Head (not set as default). Its logo now points to `/assets/emp_tracking/images/rkbg_group_logo.png`, shipped in `public/images`.
  - Existing records are never changed, and a failed record is written to the Error Log without stopping the migrate.
  - Refresh the JSON from a site with `bench --site <site> execute emp_tracking.hr_setup.export_hr_setup`.
  - The 27 HR form and list settings made in Customize Form now ship as Property Setter fixtures (module set to "Emp Tracking", `HR_FORM_DOCTYPES` in hooks.py). They cover Attendance, Expense Claim, Leave Allocation and Leave Application naming series, Salary Slip and Payroll Entry list columns, track changes, and hidden accounting dimensions.
  - Both RKBG print formats were already app files and are unchanged.
- **Reason:** User asked to push all HR structure (print formats, salary structures, settings) to the repo without data. Plain fixtures were not used for masters and settings: they overwrite the record on every migrate, and a submitted Salary Structure whose Company is missing would stop the migrate.
- **Files or modules affected:**
  - `emp_tracking/hr_setup.py` (new).
  - `emp_tracking/hr_setup/` (new: `salary_component.json`, `leave_type.json`, `salary_structure.json`, `settings.json`, `letter_head.json`).
  - `emp_tracking/public/images/rkbg_group_logo.png` (new).
  - `emp_tracking/hooks.py` (`after_migrate`, `HR_FORM_DOCTYPES`, Property Setter fixture filter).
  - `emp_tracking/fixtures/property_setter.json`.
- **Testing:**
  - On the server, `py_compile` passed.
  - Import test on newsite.local, inside a transaction that was rolled back:
    - A renamed Leave Type, Salary Component and RA Salary Structure were created, and the structure was submitted.
    - An account row for a missing company was dropped.
    - A structure for a missing company was skipped.
  - `bench --site newsite.local migrate` ran without errors:
    - 27 HR Property Setters are in place.
    - The settings flag is set.
    - No "emp_tracking HR setup" entries are in the Error Log.
- **Not tested:** Not run on a second site (for example Frappe Cloud) where the records are actually missing.
- **Pending items:**
  - **RKBG Staff Monthly - RI will not import on another site.** Current HRMS (16.53) rejects its House Rent Allowance row, formula `round((BDA)*0.35)` with "Depends On Payment Days" on. BDA is already prorated by payment days, so HRA is prorated twice in months with absent days. The error lands in that site's Error Log. Fixing it (turning "Depends On Payment Days" off on that row) changes payroll, so it waits for HR's decision. RA and RIF pass.
  - Accounts of Salary Components and Structures must be set on a site whose companies or accounts differ.
  - Employee Type (`custom_employee_type`) on newsite.local: after this migrate its options are "Field Employee / Office Employee" (from the merged `setup.py`), but 77 employees hold "Office" and 2 hold "Field". Saving those employees will fail until the data or options are aligned.

## 2026-11-24: "RKBG Payslip Classic" print format, laid out like the Excel payslip

- **Summary:**
  - New standard Print Format **RKBG Payslip Classic** for Salary Slip. It copies the Excel payslip layout:
    - One bordered box with the logo, company name and address at the top.
    - Name / Emp Code, Date of Joining / Bank Name, Designation / Account No., Location / PF No., ESIC No., Present Days / PAN.
    - "Payslip for the month of October - 2026".
    - Earning & Reimbursements | Deduction & Recoveries, followed by two empty rows.
    - Total Earnings / Total Deduction, Net Pay, and "Amount In Words:- ... Only."
    - The company stamp under the box.
  - Components print with the sheet's short labels: Earned Basic + D.A., H.R.A, Local Conv., Prov. Fund, P. Tax, MLWF.
  - Amounts are rounded to rupees and printed as 52151.00.
  - Employer-only rows (PF Employer, ESIC Employer, Bonus, Net CTC Cost) are not printed.
  - The existing "RKBG Salary Slip" (modern layout) is unchanged.
  - New Company Custom Fields **Name on Payslip** (`custom_payslip_name`) and **Company Stamp** (`custom_company_stamp`). They are created in `after_migrate`.
  - **Data, same day:**
    - The RKBG Group logo the user sent is uploaded as the public file `/files/rkbg_group_logo.png`. It is set as Company Logo on RKBG IPTECH, AUTOTECH and INFRATECH (not SWSPL).
    - The RKBG IPTECH stamp is set as that company's Company Stamp, as the **private** file `/private/files/rkbg_iptech_stamp.png`, because it carries a signature. Frappe embeds private images into the PDF.
    - The stamp image the user sent did not reach the session's disk, so it was cropped from the user's Excel payslip screenshot. It is low resolution (149×132 px).
    - New Letter Head **RKBG IPTECH**, laid out like the sheet's header: logo on the left, then "RKBG IPTECH PVT. LTD." and the two address lines. It is HTML, not the default, and is not set on the Company.
    - RKBG IPTECH "Name on Payslip" is set to "RKBG IPTECH PVT. LTD.".
    - New Address "RKBG IPTECH-Billing" (Swasti Apartment, 2nd Floor, Opp SNDT / Karve Road, Erandwane, Pune 411004, Maharashtra), linked to the Company.
  - The payslip template prints the address in the sheet's two lines: line 1, then "line 2, city;pincode".
- **Reason:** User asked for the salary print format in the structure of their Excel payslip. The Company records hold only the short name ("RKBG IPTECH") and have no stamp, so the full legal name and the stamp needed a place to be stored.
- **Files or modules affected:**
  - `emp_tracking/emp_tracking/print_format/rkbg_payslip_classic/` (new).
  - `emp_tracking/payslip_print.py` (new).
  - `emp_tracking/hooks.py` (`after_migrate`).
- **Testing:**
  - On the server, `py_compile` and the JSON parse passed, and `bench --site newsite.local migrate` ran without errors.
  - The Print Format is in the DB as standard (module Emp Tracking), and both Company Custom Fields exist.
  - Rendered `Sal Slip/RKBG-MID-00002/00001` to HTML and PDF without errors.
    - Values checked: deductions 1800 + 200 + 4 = 2004, Net Pay 50147, and "Fifty Thousand One Hundred Forty Seven Only."
- **Not tested:**
  - The PDF was not looked at as an image, because no PDF-to-image tool was available.
  - Not opened in a logged-in browser.
  - Logo, address and stamp are empty on every company, so those parts were not seen printed.
- **Pending items:**
  - Logo and the IPTECH stamp are set (the PDF of an IPTECH slip has both images).
  - HR still to fill in:
    - Name on Payslip on all three companies.
    - The Company Stamp for AUTOTECH and INFRATECH.
    - A Company Address for each company.
  - A sharper scan of the stamp can replace the cropped one later.
  - Choose "No Letterhead" when printing, or the default letter head prints above the box.
  - Gross is the slip's exact total rounded, so it can differ by ₹1 from the sum of the rounded rows (Oct slip: rows 52150, total 52151). This is the same as "RKBG Salary Slip".
  - Not committed.

## 2026-11-23: PT by the Maharashtra rule, PF back on 15,000, October payroll redone; coloured attendance Excel

- **Summary:**
  - **Data, all three RKBG structures (RI / RA / RIF):**
    - Professional Tax now applies to women too. Men: 0 up to 7,500, 175 up to 10,000, 200 above. Women: 0 up to 25,000, 200 above. February is 300 instead of 200. The `gender == 'Male'` condition was removed and the rule moved into the formula.
    - PF on RI set back to `round(min(BDA, 15000) * 0.12)`. It had been edited on screen to 25,000.
  - **October payroll redone:**
    - HR-PRUN-2026-00001 / 00002 / 00003 were cancelled. HRMS cancelled and deleted their 17 slips and cancelled Journal Entry ACC-JV-2026-00001.
    - The cancelled runs are kept, because the cancelled JV links to them and cannot be deleted.
    - New runs HR-PRUN-2026-00005 (IPTECH), 00006 (AUTOTECH) and 00007 (INFRATECH) made 17 draft slips.
  - **Salary Formula Viewer** explains the new men / women PT rule in simple words.
  - **Employee Attendance Detail** has a new **Download Excel (Coloured)** button.
    - It calls whitelisted `download_xlsx` (HR / System Manager only) and builds the .xlsx with openpyxl.
    - Styling: navy header; status fills P green / A red / ½P orange / L blue / WO and H yellow; the weekly-off column shaded; Late / Early in red.
    - Layout: a thick border per employee block, frozen headers, landscape fit-to-width printing, and a legend.
  - **Simplified the same day** (user: too much, especially on a phone):
    - 3 rows per employee (Status, In, Out), with the name merged across them.
    - A late In or early Out is shown in red instead of separate Late By / Early By rows.
    - Totals: Present, Absent, Weekly Off, Work Hrs, Late Days.
    - One title line, no filter line or legend, softer colours, grid lines hidden.
  - **Then laid out like the biometric sheet**, same day, from the user's screenshot:
    - Title, date range, company and printed-on line, then one "Days" header row.
    - Per employee: an "Employee: code : Name" line with the month summary (Total Work Duration, Present, Absent, WeeklyOff, Leaves Taken, Late By Days, Early going By Days).
    - A 6-row block (Status, InTime, OutTime, Duration, Late By, Early By) with dotted inner lines and a thick outer border, in Arial 8.
    - Status A in red and WO in blue; the employee's weekly-off / holiday columns yellow in the rows below, even when the status is A.
    - The report rows now carry `_off_days` and `_early_days` for this; they are not shown on screen.
    - Checked on Minal's block: the same values and colours as the sheet.
- **Reason:** User's requests: PT ₹200, PF on 15,000 for now, and a proper coloured table when exporting the report (Frappe's Export writes plain cells).
- **Files or modules affected:**
  - `doctype/salary_formula_viewer/salary_formula_viewer.py`.
  - `report/employee_attendance_detail/employee_attendance_detail.py` and `.js`.
  - Data: Salary Structures RKBG Staff Monthly - RI / RA / RIF, the October Payroll Entries, Salary Slips and JV.
- **Testing:**
  - Site backup taken first (`20261123_153700-newsite_local-database.sql.gz`).
  - New slips: Minal PT 200, PF 1,800, net 40,075.06. Trushali (22,177) and Vijaya (25,000) have no PT. Men keep 200. Every PF is capped at 1,800.
  - The first redo attempt stopped on deleting a cancelled Payroll Entry. It rolled back fully (state re-checked) and was rerun without the delete.
  - Viewer text checked in the console. `py_compile` OK.
  - Coloured Excel built in the console for October / RKBG IPTECH; fills, borders, freeze panes and print setup were read back with openpyxl.
  - **Not tested in the browser:** the button, the download and the viewer screen.
- **Pending items:** the October slips are drafts again and need submitting (and the JV again) in the demo. The cancelled Payroll Entries and JV stay as cancelled records.

## 2026-11-23: Employee Attendance Detail report (biometric-style month grid)

- **Summary:** New Script Report **Employee Attendance Detail**.
  - **Layout:** for each employee, six rows (Status, In Time, Out Time, Duration, Late By, Early By) and one column per day of the month, plus totals: Present, Absent, Leave, Weekly Off, Work Hrs and Late Days.
  - **Filters:** Month, Year, Company, Employee, Department, Branch, Shift Start / End, Late / Early grace.
  - **Colours:** P green, A red, ½P orange, WO / H yellow, L blue.
  - **Data:** submitted Attendance (status, In / Out Time). Employee Checkins are used when an Attendance has no times. WO / H come from the Holiday List.
  - **Late / Early:** measured against the Attendance shift, then the employee's Default Shift, then the filter defaults 09:30–18:29 with 15 min late / 10 min early grace. These copy the biometric machine's "FS" shift.
  - Read-only.
- **Reason:** User's request: view the biometric "Monthly Status Report" data employee-wise in Frappe. HRMS's Monthly Attendance Sheet shows only the status.
- **Files or modules affected:** `emp_tracking/emp_tracking/report/employee_attendance_detail/` (`__init__.py`, `.json`, `.py`, `.js`).
- **Testing:**
  - Loaded with `frappe.reload_doc`, `py_compile` OK, `bench clear-cache`.
  - `execute()` run in the bench console for October 2026.
  - **Minal Mhatre:** every In / Out / Late By / Early By value for 1–16 Oct equals the biometric sheet. Totals also equal it: present 23, absent 4, weekly off 3, work 189:07, late days 10, early-going days 15.
  - **Trushali Jori:** present 22.5, absent 3.5, weekly off 4 and work 184:37 equal the sheet. Late days are 24 against 23, and early days 3 against 2.
  - All employees: 73 shown.
  - **Not tested in the browser** (filters, colours).
- **Pending items:**
  - "RKBG Holiday List 2026" has Weekly Off = Sunday but no holiday dates. The report shows Sundays as WO from the list's weekly-off day only when a month has no holidays; the list itself was not changed.
  - The machine's Duration and OT split is not copied: Duration here is out minus in.
  - No workspace shortcut yet.

## 2026-11-23: "RKBG Salary Slip" print format

- **Summary:** New standard Jinja print format **RKBG Salary Slip** for Salary Slip, in the Emp Tracking module. The template is a separate `.html` file, which Frappe reads for standard formats. It shows:
  - the company and the month;
  - employee details: code, designation, department, joining date, PAN, UAN/PF, ESIC, bank, IFSC, and the account number masked to its last 4 digits;
  - days in month, paid days and absent/LOP days;
  - Earnings (full month and earned) next to Deductions, with totals;
  - Net Pay in figures and words;
  - an "information only" line for employer contributions and CTC rows. These are rows marked "do not include in total" or statistical, so they are not mixed into pay.
  - Advance rows also show the Additional Salary Remarks.
- **Redesign, same day (user: "make professional salary slip"):** the layout is now a formal bordered payslip.
  - **Header:** company name and "PAYSLIP for the month of …". The Company Logo and the company's linked Address / GSTIN / phone / email are shown automatically once they are filled in; none are set today.
  - **Employee details:** a bordered grid that now also shows the Pay Period.
  - **Attendance row:** days in month, paid days, absent/LOP days, pay date and slip number.
  - **One combined table:** Earnings | Rate | Amount | Deductions | Amount, with a Gross / Total row.
  - **Net Pay band** with the amount in words.
  - **Employer Contributions & Benefits grid**, for information only.
  - **Signature lines:** employee and authorised signatory.
- **Rounding, same day:**
  - All amounts now print in whole rupees, using `frappe.utils.rounded`. This affects the print only; the slip keeps its exact values.
  - Checked on Minal's October slip: the rows add up to the printed gross 42,079, deductions are 3,004 and net is 39,075. In some months the rounded rows may differ from the printed total by ₹1–2.
- **Reason:** User's request: a good salary slip print format. HRMS's own "Salary Slip" format fails on this site with "Unknown column 'uan_number'".
- **Files or modules affected:** `emp_tracking/emp_tracking/print_format/__init__.py`, `print_format/rkbg_salary_slip/` (`__init__.py`, `rkbg_salary_slip.json`, `rkbg_salary_slip.html`).
- **Testing:**
  - Loaded on newsite.local with `frappe.reload_doc` (no full migrate).
  - Rendered Minal's October slip to HTML and to PDF (wkhtmltopdf 0.12.6) and checked the PDF by eye: layout, amounts and totals match the slip (gross 42,079.06, deductions 3,004, net 39,075).
  - PDF from the bench console needs the site URL to resolve. `newsite.local` does not resolve on the server, so the test used `host_name = http://127.0.0.1:8005` for that run only, not saved.
  - **Not tested:** printing from the browser.
- **Pending items:**
  - Not set as the default print format for Salary Slip (Customize Form → Default Print Format).
  - The letter head is not drawn by this format.
  - Bank / IFSC / ESIC show "-" where the Employee record is empty.

## 2026-11-23: Salary Advance deduction on the salary slip (like the Excel "Advance" column)

- **Summary:**
  - The existing deduction component **Advance** (ADV) is now linked to each company's **Employee Advances - RI / RA / RIF** account (data change on newsite.local, so the payroll Journal Entry can post it). A description was also added to it.
  - New `emp_tracking/payroll_advance.py`: `after_migrate` adds a **Remarks** custom field (`custom_remarks`) to Additional Salary, for notes like "3000 fooding" from the Excel. It is registered in `hooks.py`.
  - How to use it: add an Additional Salary (Employee, component Advance, amount, Payroll Date in the month, Remarks) and submit it. Then re-save the draft salary slip, or recreate the slips from the Payroll Entry.
- **Reason:** User's request: an advance option on the salary slip, like the "Advance" column in the attendance Excel (Nagpur - MDPE sheet).
- **Files or modules affected:** `emp_tracking/payroll_advance.py` (new), `emp_tracking/hooks.py`. Data: Salary Component "Advance" (accounts, description), Custom Field "Additional Salary-custom_remarks".
- **Testing:**
  - On newsite.local, Advance ₹3,000 for Minal (October): after submitting the Additional Salary, the draft slip was unchanged until it was saved again. After the re-save it showed Advance 3,000 and net pay was ₹3,000 lower. The test was rolled back and the slip is back to net 40,275.06.
  - The same re-save also changed PF from 1,800 to 3,000. This is because of the PF formula edit `min(BDA, 25000)` made from the screen today on "RKBG Staff Monthly - RI"; it is not part of this change.
  - `after_migrate` was run in the bench console: the field was created and the column exists. Then `bench clear-cache`.
  - **Not tested:** the browser form, and payroll Journal Entry submit with an Advance row.
- **Pending items:**
  - "Advance / Petrol Amount" (APA) has no accounts yet.
  - Remarks show on Additional Salary only, not on the printed slip.
  - The full Employee Advance flow (pay first, recover through salary) is available in HRMS but not set up.

## 2026-11-23: Salary Formula Viewer (salary structure formulas in simple words)

- **Summary:** New single DocType **Salary Formula Viewer** with child table **Salary Formula Row**. Choose a Salary Structure plus an example gross, variable pay and gender. Every component is then listed with:
  - the formula in simple words (e.g. "60% of Gross", "12% of Basic + DA (counted up to 15,000)");
  - its condition ("Only if Gross ≤ 21,000");
  - whether it is cut for absent days, and whether it is part of pay or information only (CTC break-up);
  - an example amount for a full month;
  - example totals: gross, deductions, net pay and CTC.
  
  It reads the live structure and saves nothing (save disabled), so it never goes out of date or changes payroll. Example amounts use HRMS's own formula evaluator (`hrms.payroll.utils._safe_eval` / `COMPONENT_EVAL_GLOBALS`, checked on HRMS 16.53.0), guarded by a fallback to `frappe.safe_eval` if those internal names change.
- **Reason:** User's request: a screen that shows the salary structure formulas, for the payroll demo and for HR.
- **Files or modules affected:** `emp_tracking/emp_tracking/doctype/salary_formula_viewer/` (json, py, js, `__init__`), `emp_tracking/emp_tracking/doctype/salary_formula_row/` (json, py, `__init__`).
- **Testing:**
  - `py_compile` and JSON parse on the server: OK.
  - Loaded on newsite.local with `frappe.reload_doc` for these two doctypes only, then `bench clear-cache`. A full `bench migrate` was **not** run, because the app-attendance change below is still waiting for its own migrate.
  - `load_formulas` run in the bench console on "RKBG Staff Monthly - RI" with gross 48,313, variable 2,843, Female (Minal's assignment). The example amounts equal the full-month amounts on her October slip: Basic + DA 28,988, HRA 10,146, Education 3,836, PF 1,800, LWF 4, Net CTC 55,844. A second check with gross 18,000, Male gave ESIC 135 and PT 200, so the conditions apply.
  - **Not tested in the browser** (form, buttons, read-only table).
- **Pending items:** Simple-words text covers the patterns in the RKBG structures; other formulas show with component names in place of abbreviations. No workspace link yet: open it from the search bar.

## 2026-11-23: Attendance from mobile-app punches; one "punch from anywhere" setting

- **Summary:**
  - **Attendance from app punches (new `emp_tracking/app_attendance.py`):** uses HRMS's own Auto Attendance, no HRMS code changed.
    - New Mode of Attendance option **"Mobile App"** (fixture). Only employees with this mode get automatic attendance (user's decision).
    - `after_migrate` creates two Shift Types once (never overwritten afterwards):
      - **Office 09:30-18:30 (Mobile App)**: punches 08:30–21:30 count.
      - **Field 12 Hours (Mobile App)**: riders, splicers and maintenance staff. They work 12 hours from their own punch-in, so any punch between 00:00 and 23:59 counts.
    - Both shifts: Auto Attendance on, HRMS updates "Last Sync of Checkin" itself, IN/OUT taken from the app's log type, **Present if punched in** (no half-day / absent hour thresholds, user's decision), and Absent on working days without a punch from the day the shift is created ("Process Attendance After" = creation date, so no past dates are marked).
    - `after_migrate` gives active "Mobile App" employees without a Default Shift the right one. Employee `before_save` (doc_events) does the same when HR sets the mode, and clears our shift when the mode is changed to something else. Field shift = designation contains Rider / Splicer / Maintenance, or leader of an active Maintenance Team. HR can still change Default Shift by hand.
  - **One setting instead of two:** "Allow Punch From Anywhere" (checkbox, 2026-10-21) is retired. `overrides/employee_checkin.py` now skips the Shift Location radius when **Punch-In Location = "Anywhere"**, the field the mobile app already uses. On migrate, `setup.retire_allow_punch_from_anywhere()` gives ticked employees "Anywhere" (only RKBG-MID-00011, already "Anywhere"), then deletes the checkbox custom field. Punch-In Location label fixed ("Punch- In" → "Punch-In") and given a description.
- **Reason:** User's requests: app punch in/out should count as attendance for payroll (Payroll Settings already use Attendance); the Employee form had two settings for the same thing.
- **Files or modules affected:** `emp_tracking/app_attendance.py` (new), `emp_tracking/hooks.py` (after_migrate, Employee before_save), `emp_tracking/overrides/employee_checkin.py`, `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py`, `emp_tracking/fixtures/custom_field.json` (Mode of Attendance, Punch-In Location).
- **Testing:**
  - `py_compile` on the changed Python files: OK. `custom_field.json` parses as valid JSON.
  - Field-shift rule checked on the site's designations (Rider, Splicer, Rider / Splicer, O&M managers → 12-hour; Office Assistant, Noc Executive, Field Engineer, Team Lead → office).
  - HRMS 16.53.0 source read to confirm the Shift Type field names, `auto_update_last_sync`, and that default-shift employees are processed.
  - **Not run:** `bench --site newsite.local migrate` (no shell access to the server from this session), so the shifts, the "Mobile App" option and the checkbox removal are not on the site yet. Nothing tested in the browser or by the hourly job.
- **Pending items:**
  - Run `bench --site newsite.local migrate`, then set Mode of Attendance = "Mobile App" on the employees who use the app.
  - Company SWSPL has no default Holiday List: "Mobile App" employees there would be marked Absent on Sundays and holidays.
  - Field shift: a punch-out after midnight is counted on the next day.
  - Not implemented: automatic punch-out after 12 hours.

## 2026-11-21: Leave setup, 15 leaves a year (office carried forward, field encashed)

- **Summary:**
  - **HR's rule (2026-11-21):** 15 leaves a year and no other leave types. For field employees the balance is encashed; for the others it is carried forward.
  - **User's choices:** leave year Jan–Dec; all 15 credited at the start of the year; unlimited carry-forward; encashment per day = Gross / 30.
  - **App code:** new hook `overrides/salary_structure_assignment.py` (`before_validate`). It fills the standard field "Leave Encashment Amount Per Day" with `base / 30` when that field is blank. HR can still type another value.
  - **Site data on newsite.local** (one-time script, not part of the app):
    - Salary Component **Leave Encashment** (LENC).
    - Leave Types:
      - **Annual Leave - Office**: max 15, carry forward, no limit;
      - **Annual Leave - Field**: max 15, encashable, earning component Leave Encashment.
    - Leave Policies HR-LPOL-2026-00001 (office) and HR-LPOL-2026-00002 (field), 15 days each.
    - Leave Periods 2026 for RKBG IPTECH / AUTOTECH / INFRATECH (HR-LPR-2026-00001..3).
    - 17 submitted Leave Policy Assignments (HR-LPOL-ASSGN-00001..17). Each creates a 15-day allocation:
      - 2 field: RKBG-MID-00001, RKBG-MID-00008;
      - 15 office.
    - "Leave Encashment Amount Per Day" set on the 3 submitted Salary Structure Assignments, where it was blank: 1,796.27 / 1,610.43 / 1,609.03.
- **Reason:** HR confirmed the company leave rule. HRMS takes the per-day encashment from each employee's Salary Structure Assignment. The salary structures are shared by employees with different Gross, so the amount has to come from each assignment's own Gross.
- **Files or modules affected:** `emp_tracking/overrides/salary_structure_assignment.py` (new), `emp_tracking/hooks.py` (doc_events). Site data as listed above.
- **Testing:**
  - The setup script was first run with rollback, then committed. All 17 allocations show 15 new leaves.
  - Hook checked in `bench console` without saving: base 30,000 with a blank rate gives 1,000; a typed 999 is kept.
  - `bench clear-cache` was run.
  - Not tested in the browser: a Leave Application, the year-end carry-forward, or a Leave Encashment to Additional Salary.
- **Pending items:**
  - **Leave already taken in 2026:** the 15 days are the full 2026 allowance, so leave already taken in Jan–Nov 2026 must be entered or the balances adjusted.
  - **Leave approvers:** HR Settings requires a leave approver on each Leave Application, and none of the 17 employees has one yet. Approvers need user logins.
  - **2027 periods:** make 2027 Leave Periods, then assign policies with "carry forward" ticked for office staff. For field staff, create Leave Encashment at year end; it posts as Additional Salary.
  - **Accounts:** the Leave Encashment component has no expense account yet. This is the same open item as the other payroll accounts.
  - **Field staff list:** only employees with Employee Type / Work Type = Field (2 today) get the encashable leave type. Mark other field staff before assigning their policy.

## 2026-11-20: DEMO attendance for the two field employees, June 2026 (site data, no app code)

- **Summary:** For a demo, the user asked for attendance that matches the field staff's full pay. Two submitted HRMS **Attendance Requests** (reason "On Duty", 01–30 June 2026, holidays included) were created:
  - HR-ARQ-26-11-00001 for RKBG-MID-00001 Dasharath Yewale;
  - HR-ARQ-26-11-00002 for RKBG-MID-00008 Amol Jagdale.

  Each request created 30 "Present" Attendance records linked to it. The explanation on both says **"DEMO DATA … Not real attendance."**
- **Reason:** The draft June slips pay these two in full, and the demo should show attendance that agrees with that pay.
- **Files or modules affected:** None in the app. Site newsite.local: Attendance Request (2), Attendance (60), Salary Slip (2 drafts re-saved).
- **Testing:** 30 Present records per employee. After re-saving, both draft slips still show 30 / 30 days, with net 51,884 and 46,267.
- **Pending items:** This is not real attendance. Cancel both Attendance Requests before real payroll, which also cancels the 60 attendance records they made, and enter real field attendance (mobile check-in or On Duty requests).

## 2026-11-20: Field staff no longer paid by eSSL machine attendance (site data, no app code)

- **Summary:** The user confirmed that Dasharath Yewale (RKBG-MID-00001) and Amol Jagdale (RKBG-MID-00008) are field employees.
  - Their 60 imported June 2026 eSSL Attendance records (30 each) were **cancelled**, not deleted. Payroll counts unmarked days as present, so they are paid in full.
  - Both were set to Work Type = Field and Employee Type = Field.
  - Their draft June slips were recalculated: 30 / 30 days, net 51,884 and 46,267, the same as the payment sheet.
  - Minal Mhatre (RKBG-MID-00005, office) keeps her attendance cut: 24.5 / 30 days, net 37,651.61.
- **Reason:** The user asked why the slips differed from the payment sheet. The sheet pays a full month, while the slips cut pay for days not punched on the office eSSL machine, which field staff don't use daily.
- **Files or modules affected:** None in the app. Site newsite.local: Attendance (60 cancelled), Employee (2), Salary Slip (2 drafts recalculated).
- **Testing:** Gross, deductions, net pay and every CTC row of both recalculated slips equal the payment sheet: 53,888 / 2,004 / 51,884 / 61,929 and 48,271 / 2,004 / 46,267 / 55,798.
- **Pending items:**
  - When the eSSL machine is connected live, field staff must not get automatic attendance from the office shift. Their attendance should come from the mobile check-in or leave applications.
  - Other field employees among the 16 matched machine users have not been identified.

## 2026-11-20: June 2026 draft salary slips (site data, no app code)

- **Summary:**
  - The 3 Salary Structure Assignments (RKBG-MID-00001 / 00005 / 00008) were cancelled and amended to start **2026-06-01** instead of 2026-11-01 (a date chosen at setup, not by the user), with the same structure, Gross and Incentive.
  - Draft Salary Slips were created for 01–30 June 2026. Payment days come from the imported eSSL attendance (payroll based on Attendance; half day = 0.5; weekly offs paid).

  | Employee | Payment days / 30 | Gross | Deductions | Net |
  |---|---|---|---|---|
  | RKBG-MID-00001 | 5.5 | 9,879.46 | 915 | 8,964.46 |
  | RKBG-MID-00005 | 24.5 | 39,455.61 | 1,804 | 37,651.61 |
  | RKBG-MID-00008 | 2.5 | 4,022.57 | 494 | 3,528.57 |

- **Reason:** The user asked for salary slips. June is the only month with attendance on the site, and November is not over.
- **Files or modules affected:** None in the app. Site newsite.local: Salary Structure Assignment (3 cancelled, 3 amended), Salary Slip (3 drafts).
- **Testing:**
  - Amounts were checked by hand. Gross = rate × payment days ÷ 30 (e.g. 48,313 × 24.5 ÷ 30 = 39,455.6). PF = 12% of earned Basic + DA capped at 15,000 (711 / 1,800 / 290). PT 200 for men, LWF 4.
  - **Not done:** submitting the slips, a Payroll Entry, and printing.
- **Pending items:**
  - PT and the ESIC threshold use the monthly rate, not the salary earned in the month. In short months Maharashtra PT would be 175 below 10,000 earned.
  - Leave With Wages (CTC side only) is not reduced in short months, unlike Bonus.
  - The deduction accounts must be set before submitting.
  - The other 14 employees have no salary assigned.

## 2026-11-20: eSSL attendance for June 2026 imported; employees linked to machine IDs (site data, no app code)

- **Summary:**
  - **Source:** the eSSL "Monthly Status Report (Detailed Work Duration)" for 1–30 June 2026, the file `ThumbPrint_report.xls` from the auto-milestone site's private files, with 42 machine users.
  - **Matching:** each machine user was matched by name (same first name, near-identical last name) to an **active** employee on newsite.local. 16 matched: 13 RKBG employees, plus SWSPL HR-EMP-00024 Amar Belapurkar, HR-EMP-00055 Pramod Kalvankar and HR-EMP-00059 Shyam Morale. Their eSSL user ID was written to **Attendance Device ID** (it was blank for all of them), so punches from the machine can be matched to the employee.
  - **Attendance:** 469 submitted Attendance records (84 Present, 22 Half Day, 363 Absent), with in/out time, working hours, late entry and early exit. P / WOP → Present, ½P / WO½P → Half Day (other half Absent), A → Absent. Weekly offs (WO) get no record.
  - **Payroll Settings:** "Payroll Based On" changed from Leave to **Attendance**, so absent days reduce pay. Unmarked days, including weekly offs, still count as present, as before.
- **Reason:** The user sent the eSSL attendance report and chose both: import the month, and link employees to the machine.
- **Files or modules affected:** None in the app. Site newsite.local: Employee (attendance_device_id), Attendance, Payroll Settings.
- **Testing:**
  - The parsed report was checked against eSSL's own summary line: the Present count (P + ½ × half days) is equal for all 42 users.
  - A dry run (rolled back) created 469 records without errors. After the real run, each of the 16 employees' present days on the site equal the eSSL summary (e.g. RKBG-MID-00005 21.5, RKBG-MID-00006 23, RKBG-MID-00013 18.5), and no record was skipped as an existing one.
  - HRMS's check-in API `add_log_based_on_employee_field` (matches on attendance_device_id) exists in this HRMS version.
  - **Not done:** connecting a machine, and a salary slip for June. Salary structures start 2026-11-01, so June attendance cannot go through payroll.
- **Pending items:**
  - 26 machine users are not on the site, so they got no attendance: Rohan Mhatre, Omkar Kangude, Abhishek Gaikwad, Aniket Baikar, Nitesh Pathak, Rushikesh Angre, Rahul Gangote, Rajesh Bhapkar, Shrikant Shewale, Sheetal Shimpi, Ashish Biradar, Sambhaji Kende, Atul Ghate, Vaishnavi Mahajan, Amrut / Prakash / Harilal Rathod, Sanjay Pawar, six "Solar" users, and the two Admin cards.
  - Live sync from the machine needs a program on a PC in the office network (e.g. Frappe's biometric attendance sync tool), an API user, and a Shift Type for the "FS" shift (about 09:30–18:30 from the report) with auto attendance. None of these is set up yet.
  - The one-time import script stays in the session scratchpad (`essl/essl_import.py`), and the server copies were deleted.

## 2026-11-20: Payroll structure from the "Payment calculation format" sheet (site data, no app code)

- **Summary:** HRMS payroll was set up on newsite.local to reproduce "Payment_calculation_format.xlsx".
  - **Salary Structures:** "RKBG Staff Monthly - RI / RA / RIF" (one per RKBG company), monthly, submitted.
  - **Earnings** (prorated by payment days):
    - Basic + DA = 60% of Gross; House Rent Allowance = 21% of Gross; Conveyance = 2,500.
    - Incentive = the assignment's *Variable*.
    - Education Allowance = Gross − the others (the balancing figure). Gross rate = the assignment's *Base*.
  - **Deductions:**
    - Provident Fund = 12% of Basic + DA, capped at 15,000.
    - ESIC = 0.75%, only when Gross ≤ 21,000.
    - Professional Tax: men only, Maharashtra slabs (nil up to 7,500, 175 up to 10,000, 200 above, 300 in February).
    - Labour Welfare Fund = 4.
  - **Employer / CTC rows:** shown on the slip with "Do not include in total", so they never change gross or net. PF Employer = 13% of capped Basic + DA; ESIC Employer = 3.25% (Gross ≤ 21,000); Bonus = 8.33% of Basic + DA; Insurance Policy = 1,140; LWF Employer = 13; Leave With Wages = Gross ÷ 24; ESIC Wages; Net CTC Cost = the sum.
  - **Amounts that change month to month, via Additional Salary:** Washing Allowance, Petrol & Other, Arrear, Advance, Income Tax, Advance / Petrol Amount.
  - **Components:** 18 new Salary Components. House Rent Allowance, Provident Fund, Professional Tax, Income Tax and Arrear already existed and were reused. Salary Component expense account "Salary - <abbr>" was set on the paid earnings.
  - **Assignments** for the 3 employees in the sheet, matched by UAN and date of joining, from 2026-11-01: RKBG-MID-00001 (Gross 53,888 / Incentive 3,670), RKBG-MID-00005 (48,313 / 2,843), RKBG-MID-00008 (48,271 / 3,670).
  - **Payroll Settings:** "Include holidays in total working days" turned on, so a month is its calendar days like the sheet (31 / 31). Holiday List "RKBG Holiday List 2026" (no holidays yet) was assigned to the 3 companies through Holiday List Assignment, which HRMS 16 requires for salary slips.
- **Reason:** The user asked for the payroll structure of this sheet.
- **Files or modules affected:** None in the app. Site newsite.local records: Salary Component, Salary Structure, Salary Structure Assignment, Holiday List, Holiday List Assignment, Payroll Settings. The one-time setup script stayed in the session scratchpad (`empimp/payroll_setup.py`), not in the app.
- **Testing:**
  - A dry run (rolled back) calculated December 2026 salary slips for the 3 employees.
  - Gross, total deductions, net, PF, PT, LWF, PF Employer, Bonus, Insurance, LWF Employer, Leave With Wages and Net CTC Cost match the sheet exactly for all 3 (net 51,884 / 46,509 / 46,267; Net CTC Cost 61,929 / 55,844 / 55,798).
  - The only difference: for RKBG-MID-00005 the sheet has Conveyance 2,499 / Education 3,837, and the structure gives 2,500 / 3,836 (same gross).
  - After the real run: 3 submitted structures, 3 assignments, 3 holiday list assignments, and no salary slips saved.
  - **Not done:** a Payroll Entry, a month with leave without pay or a mid-month joiner (proration), and printing a slip.
- **Pending items:**
  - Deduction components (PF, ESIC, PT, LWF, Advance, Income Tax) have no liability accounts yet. The accountant must set them before a Payroll Entry can post its journal entry.
  - Professional Tax follows the sheet and skips women. Maharashtra law charges women earning over 25,000 (200 / 300 in February), so this should be confirmed.
  - LWF 4 / 13 every month follows the sheet. Maharashtra LWF is normally deducted in June and December only.
  - Income Tax is entered manually (Additional Salary). HRMS can calculate TDS from an Income Tax Slab if wanted.
  - The other 14 employees need a Salary Structure Assignment with their Gross and Incentive rates.
  - "RKBG Holiday List 2026" has no holidays and ends 2026-12-31. Add the holidays, and a 2027 list before January payroll.
  - This was set up on newsite.local only. The production site needs the same setup.

## 2026-11-20: 17 employees imported from the employee sheet; Employee Master ID series fixed

- **Summary:** The 17 employees in "Copy of Employee Sheet Sample Data_Software.xlsx" were added on newsite.local: 15 RKBG IPTECH, 1 RKBG AUTOTECH, 1 RKBG INFRATECH.
  - **IDs and codes:** each keeps the sheet's Employee Master ID (RKBG-MID-00001 … 00016, 00119, 00124) and Employee Code (IPT-0001 …, AUT-0001, INF-0001). All filled sheet columns went into the new tabs.
  - **Reporting Person:** set for 9 employees. Shyam Arjun Morale is the existing employee HR-EMP-00059.
  - **Masters created:** Branch "Pune"; Departments "Operations & Maintenance", "Administration" and "Inventory & Stores" (RKBG IPTECH); 8 Designations. "Accounts / Finance" went into the existing "Accounts" department, and "Full Time" into the existing Employment Type "Full-time".
  - **Duplicates:** 9 SWSPL employees who are the same people (HR-EMP-00020, 21, 22, 23, 27, 30, 32, 60, 64) were set to **Inactive**, with a remark naming their new ID. They were not deleted. They were not set to "Left", because that needs a relieving date and none is known. Only Status and Remark were written, directly, because these old records lack DOB / gender / joining date and a full save is refused.
  - **Employee Master ID series:** the option was changed from `RKBG-MID-#####` (which named employees `RKBG-MID-#####00001`) to `RKBG-MID-`, and its counter was set to 124, so the next employee is RKBG-MID-00125. Re-exported to `fixtures/property_setter.json`.
- **Reason:** The user asked to fill in the employee details from the sheet, chose "create new and retire the old duplicates", and asked to fix the series.
- **Files or modules affected:**
  - `emp_tracking/fixtures/property_setter.json` (naming_series options)
  - Site newsite.local: Employee records, Branch, Department, Designation, Series
- **Testing:**
  - A dry run, rolled back at the end, inserted all 17 without errors.
  - After the real run, all 17 were compared with the sheet (code, company, full name, DOB, joining date, mobile, Aadhar, PAN, status) with 0 mismatches.
  - The 9 duplicates show Inactive with the remark.
  - Series: IPT- 16, AUT- 1, INF- 1, RKBG-MID- 124.
  - No employee is missing its tree position (lft), and no user accounts were created.
  - The one-time import scripts and the copy of the sheet rows were deleted from the server's `/tmp` afterwards.
  - **Not done:** opening the employees in a browser.
- **Pending items:**
  - "Rahul Bhaskar Gangote" (Reporting Person and leave approver for 5 employees) is not an employee or user on the site, so their Reporting Person is blank.
  - "Leaves will be approved by" is a link to a User. None of the named approvers has a login, so it was left blank for everyone.
  - Sheet columns that were empty stay empty (blood group, bank details, ESIC, insurance numbers, etc.). "NA" and "?" were treated as empty.
  - The misspelt department "Operationa & Maintenance - RI" already existed and was left as it is.
  - The Employee Master ID field still defaults to HR-EMP-; pick RKBG-MID- when adding an RKBG employee.

## 2026-11-20: Employee form in the 13 sections of the employee master sheet

- **Summary:** The Employee form now has one tab per section of "Employee Sheet Sample Data_Software", in the sheet's order:
  1. System Identification & Company Info
  2. Personal Information
  3. Contact & Communication Details
  4. Emergency Contacts
  5. Identity & Statutory Documents
  6. Organisational & Job Details
  7. Probation, Tenure & Lifecycle
  8. Previous Employment & Experience
  9. Banking & Statutory Compliance
  10. Insurance & Dependents
  11. Assets & Equipment
  12. Offboarding & Separation
  13. Remarks

  These are followed by **Login & Attendance** (User ID, attendance device, holiday list, shift, punch settings, approvers; kept because login, attendance and field tracking use them) and Connections.
  - Standard ERPNext/HRMS fields are reused and relabelled to the sheet's names wherever one exists. Examples: Probation End Date = `final_confirmation_date`, Work Location = `branch`, Last Working Day = `relieving_date`, Leaves will be approved by = `leave_approver`, Notice Period (Days) = `notice_number_of_days`. Previous employer, designation, salary and experience use the standard Previous Work Experience table.
  - 60 new Custom Fields were added for sheet columns with no standard field (Aadhar, licence, PF/ESIC, insurance and family members, assets, offboarding Yes/No fields, remark, and the tab, section and column breaks).
  - Fields not in the sheet are moved to a hidden tab and hidden, not deleted, so existing values and HRMS logic are unchanged.
  - "Show only when Salary Mode = Bank" was removed from the bank fields, and "show only when a provider is set" from Medical Insurance No.
  - Not added: Sr. No., Age, Days / Years Since Joining (calculated in the sheet), and Updated By / Last Updated On (Frappe records these itself).
- **How:** Everything was done through Frappe's **Customize Form** (`save_customization`, run once from `bench console`), so the result is only Custom Fields and Property Setters; no Employee code was added. The 64 custom fields made in Customize Form (60 new, plus Employee Code, Photo Needed?, Employee Type and Punch-In Location made earlier in the UI) and the 84 Employee Property Setters were given Module = Emp Tracking. They were exported as fixtures (`fixtures/custom_field.json`, `fixtures/property_setter.json`), so they are in git and reach Frappe Cloud on deploy. HRMS's own Employee fields, and Work Type / Allow Punch From Anywhere (created by `workforce_dashboard/setup.py`), are not in the fixtures.
- **Reason:** The user asked for the Employee form to show the sheet's fields section by section, using Customize Form and Property Setters with as little code as possible, and to hide fields that are not needed.
- **Files or modules affected:**
  - `emp_tracking/hooks.py` (two `fixtures` entries)
  - New: `emp_tracking/fixtures/custom_field.json`, `emp_tracking/fixtures/property_setter.json`
  - Site newsite.local: Employee Custom Fields and Property Setters
- **Testing:**
  - Before the change, all 27 Employee Custom Fields and 10 Property Setters were backed up to JSON (in the session scratchpad and at `/tmp/employee_customization_backup_2026-11-20.json` on the server).
  - Customize Form saved 196 fields (60 new).
  - The Employee meta, read back after a cache clear, shows the 13 sheet tabs + Login & Attendance + Connections with the fields above. All required fields (Employee Master ID, Company, First Name, Date of Birth, Gender, Date of Joining, Status) are visible.
  - `bench --site newsite.local migrate` ran without errors, and the layout was unchanged afterwards. The only new Error Log was a Data Import save (the known "section title row" sheet problem), not from this change.
  - **Not done:** opening the form in a browser, and saving an employee through the new tabs.
- **Pending items:**
  - Customize Form named the new fields from their labels, so a few have double underscores (e.g. `custom_laptop__pc_serial_no`). Users don't see this.
  - Future Customize Form changes to Employee get no module. Set Module = Emp Tracking on them and re-export these two fixtures, or the next deploy won't carry them.
  - Employment Type values in the sheet ("Full Time") don't match the existing records ("Full-time"), and Work Location ("Pune") needs a Branch record, before importing.
  - "Employee Type" (Office/Field, made in the UI) and the app's "Work Type" (Field/Office) look like the same thing. Both are kept; the user should pick one.

## 2026-11-20: Employee Code series per company (IPT / AUT / INF)

- **Summary:** A new Employee's **Employee Code** (`custom_employee_code`) comes from its company's **Employee Code Prefix**: RKBG IPTECH → `IPT-0001`, RKBG AUTOTECH → `AUT-0001`, RKBG INFRATECH → `INF-0001`. Each prefix has its own 4-digit counter.
  - The Employee ID ("Employee Master ID" naming series) is not changed. Companies with no prefix (SWSPL) get no automatic code.
  - The form fills the next code as soon as a company is picked. This is only a preview and does not use up a number. The final number is given on save (`before_insert`).
  - On save:
    - A blank code, a code with another prefix, or a code another employee already has gets the next number.
    - A free code with the right prefix (typed in, or from Data Import) is kept, and the counter moves up to it, so imported codes are never given out again.
  - The prefix is a new Custom Field on Company (`custom_employee_code_prefix`, after Abbreviation). `after_migrate` creates it and fills IPT / AUT / INF only where it is blank, so a prefix changed later is never overwritten.
  - The first version, earlier the same day, named the Employee ID itself IPT-####. It was replaced before any employee was saved with it, because the form's Employee ID is the separate "Employee Master ID" series.
- **Reason:** The user asked for employee codes to start with IPT-, AUT- or INF- depending on the company, and to see the code on the form when the company is picked.
- **Files or modules affected:**
  - New: `emp_tracking/overrides/employee.py`, `emp_tracking/public/js/employee.js`
  - `emp_tracking/hooks.py` (`doctype_js`, `doc_events`, `after_migrate`)
- **Testing:**
  - `py_compile` passed on the server, and `node --check` passed on `employee.js`.
  - `setup()` ran on newsite.local, then `clear-cache`. The three RKBG companies have AUT / INF / IPT, and SWSPL is blank. `get_hooks` lists the `before_insert` hook and `public/js/employee.js`.
  - In `bench console`, real `Employee.insert()` calls were made and then rolled back. Results:
    - Blank codes gave IPT-0001, IPT-0002, AUT-0001, INF-0001.
    - INF-0010 was kept, and the next INF employee got INF-0011. A lowercase "inf-0005" was saved as INF-0005.
    - A used IPT-0001 was replaced by the next number, AUT-0009 on an IPTECH employee was replaced by an IPT code, and SWSPL got no code.
    - The preview showed IPT-0001 / AUT-0001 / none for SWSPL.
    - After the rollback there were no IPT/AUT/INF Series rows.
  - **Not done:** the form in a browser, an import through Data Import, and a full `bench migrate`.
- **Pending items:** The "Employee Master ID" naming series option is `RKBG-MID-#####` (Property Setter on Employee `naming_series`). Frappe adds its own `.#####`, so IDs come out as `RKBG-MID-#####00001`. The option should be `RKBG-MID-` (or `RKBG-MID-.#####`). Not changed; waiting for the user's decision.

## 2026-11-17: KMZ Map: map blank on Frappe 16.54

- **Summary:** The KMZ Map page now loads Frappe's Leaflet map library itself (`frappe.require("leaflet.bundle.js")` and `.css`) before it draws the map. The filter options load at the same time.
- **Reason:** The user reported that the KMZ map was not visible. Frappe 16.54 (released 2026-10-27) no longer loads Leaflet with the desk; its own Geolocation field loads it on demand. The page called `L.map()` with `L` undefined, so no map was drawn.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/kmz_map/kmz_map.js`
- **Testing:** `node --check` passed. On the server, `assets.json` lists `leaflet.bundle.js` / `leaflet.bundle.css`, and `bench --site newsite.local clear-cache` ran. **Not done:** opening /app/kmz-map in a browser.
- **Pending items:** Manager Dashboard loads Leaflet from unpkg.com, so its maps don't need Frappe's copy. The Workforce Dashboard maps check `window.L` and show a plain list of locations when it is missing. They could use the same `frappe.require` if their maps should show.

## 2026-11-17: EVision tile back on the desk, next to the module tiles

- **Summary:** The desk home shows an **EVision** tile again, after OverHead Project, Emp Tracking and NOC (those three stay). Its sidebar has every module menu in one list: Dashboards, FTTH, Fiber Store, Network, Teams & Vendors, Complaints (19 links). It is seen by the same roles as the old EVision tile (`TILE_ROLES`). Frappe still hides links a user cannot open. It has its own purple "grid" picture icon.
- **Reason:** The user asked to show EVision on the workspace, alongside the three module tiles.
- **Files or modules affected:**
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`EVISION_TILE`, `EVISION_MODULES`, `OLD_SIDEBARS`, `DESK_ICONS`, `module_tiles`, `make_navigation`)
  - `emp_tracking/emp_tracking/page/workforce_dashboard/workforce_dashboard.js` (`OH_SIDEBARS`)
  - New: `emp_tracking/public/icons/desktop_icons/{solid,subtle}/evision.svg`
- **Testing:**
  - `py_compile` and `node --check` passed.
  - `bench --site newsite.local migrate` ran on the server. It left no "rebuilding the desk menu" Error Log. A second migrate started by mistake hit the migrate lock and logged one Filelock error. The Helpdesk search-index Error Log comes from Helpdesk, not from this change.
  - The `EVision` Desktop Icon exists: not hidden, idx 3, 17 roles, and its sidebar has the 6 sections and 19 links above. `/assets/emp_tracking/icons/desktop_icons/solid/evision.svg` returns HTTP 200.
  - **Not done:** a look at the desk in the browser, and a login as a non-admin role.
- **Pending items:** Staff (Employee-only users) also see the EVision tile, as they did before 2026-10-29. Their sidebar only lists the links they can open. Users whose browser kept an old desk layout may need "Reset Desktop Layout" once.

## 2026-11-02: FTTH Work Order form: the layout the user chose

- **Summary:**
  - The top of the FTTH Work Order form now follows the layout the user picked from a screenshot:
    - **Header:** place name, then ID · WO · area · WO date. On the right, badges for the Stage (short name, coloured by who acts), the Status (only when it differs from the stage) and the Issue Type.
    - **Step card:** neutral circles (done = dark tick, current = ringed with its owner under it, upcoming = grey number). Under them a status bar: "Waiting on you: <stage>" (amber) when the viewer's role acts, else "Now with <owner>: <stage>". Completed is green, Cancelled red.
    - **"Check this work order"** box with FTTH Tracker's warnings.
    - **Network Link row:** shows the link, or "Create Network Link" for the Project Head once HOTO is done.
  - The form below is **flat again**: the per-section cards and grey page from earlier today are removed. It keeps calmer labels and read-only values as plain text.
  - The figure tiles in the header are dropped.
  - Complaint Information uses the same step card and status bar.
  - **Browser cache:** `evision.css` / `evision.js` are loaded with `?v=` (`EV_ASSET_VERSION` in `hooks.py`). Browsers kept the old files for up to 12 hours; the user's screenshots showed the desk without the new styles.
- **Reason:** The user sent a screenshot of the layout they want ("yeh wala layout") and said the stage list was missing on their form.
- **Files or modules affected:**
  - `emp_tracking/hooks.py`
  - `emp_tracking/public/js/evision.js` (`stepper` rewritten, `notice_html`, `hero_html`)
  - `emp_tracking/public/js/ftth_work_order.js` (`wo_hero`, `wo_notices`, `wo_stage_color`)
  - `emp_tracking/public/css/evision.css` (sections 3, 3b, 5)
- **Testing:**
  - **Local:** `node --check` on both JS files and `py_compile` on `hooks.py` passed.
  - **Visual (local):** headless Chrome screenshots of a mock FTTH Work Order form looked right in light and dark mode. The mock used Frappe 16's markup and compiled desk CSS, the real `evision.js` / `ftth_work_order.js` / `evision.css`, and work order FTTH-01836's real values.
  - **Server:** `bench --site newsite.local clear-cache` run; `get_hooks` lists the `?v=` paths, and both files return HTTP 200 with them.
  - **Not done:** not seen in a logged-in browser on the real form; the Complaint Information form wasn't checked.
- **Pending items:** check FTTH-33969 and a complaint in the browser after one reload.

## 2026-11-02: FTTH Work Order list: stage strip removed

- **Summary:** The stage pipeline strip above the FTTH Work Order list ("All 1,408 | Survey 0 | …") is removed, with its styles. The coloured Stage and Issue Type pills in the list columns stay.
- **Reason:** The user asked to remove the strip and keep the coloured stage pills.
- **Files or modules affected:** `emp_tracking/public/js/ftth_work_order_list.js`, `emp_tracking/public/css/evision.css`.
- **Testing:** `node --check` passed; `bench --site newsite.local clear-cache` run so the list script is reloaded. Not checked in a logged-in browser.
- **Pending items:** none.

## 2026-11-02: OverHead desk forms: summary header and card layout

- **Summary:**
  - **FTTH Work Order form, summary header** at the top of the stage tracker. It shows:
    - the place name, large;
    - a meta line with the ID, WO ID, area, GIS and WO date;
    - badges for the Issue Type (coloured as on the list) and "Has warnings";
    - key figure tiles: planning, survey and final distance, fiber used, and days from WO to RFS. Empty figures are left out.
  - **Card layout** on the FTTH Work Order and Complaint Information forms:
    - the form page is quiet grey, and each section is a white rounded card;
    - section titles are clearer, tabs calmer, field labels smaller and grey;
    - **read-only values are plain text** (empty ones show "—"), so the grey input boxes left on a card are exactly what that role can fill in.
  - **FTTH dashboard workspace (FTTH Tracker):** rounder number cards and charts, muted titles, larger figures. Scoped to that workspace only.
  - Desk only and upgrade-safe: CSS in `evision.css` (sections 3b, 5, 6) and form scripts in emp_tracking. No Frappe or FTTH Tracker files are changed. The card layout only applies to forms that call `evision.form_style()`. It depends on Frappe 16.33 form classes; if they change, the styling stops applying but the form keeps working.
- **Reason:** The user asked for the OH project to look simple and beautiful inside the desk, not as a separate portal.
- **Files or modules affected:**
  - `emp_tracking/public/css/evision.css`
  - `emp_tracking/public/js/evision.js` (`hero_html`, `form_style`, `stepper` `opts.hero`)
  - `emp_tracking/public/js/ftth_work_order.js` (`wo_hero`, `wo_issue_color`)
  - `emp_tracking/emp_tracking/doctype/complaint_information/complaint_information.js`
- **Testing:**
  - **Local:**
    - `node --check` passed on the three JS files and `py_compile` passed on `hooks.py` / `setup.py`; files are LF.
    - Headless Chrome screenshots of a mock FTTH Work Order form looked right in light and dark mode. The mock used Frappe 16's markup, the site's compiled desk CSS and the real `evision.js` / `ftth_work_order.js`, with work order FTTH-01836's real values from newsite.local.
  - **Server:**
    - `bench --site newsite.local migrate` passed.
    - `evision.css` and `evision.js` return HTTP 200, and `/oh` returns 404.
  - **Not done:**
    - Not checked in a logged-in browser on the real forms.
    - The FTTH Tracker workspace styling wasn't screenshotted at all.
- **Pending items:**
  - Hard-refresh the desk once (Ctrl+Shift+R). The CSS / JS are plain files without a build hash, so a browser may keep the old copy.
  - Check both forms and the FTTH dashboard in light and dark mode, and send a screenshot if anything looks off.

## 2026-11-02: OH Portal tried and removed (desk only)

- **Summary:** A separate frappe-ui app at `/oh` was built and migrated today, then removed on the user's word ("make in desk only"). Removed: `frontend/`, `emp_tracking/oh_portal.py`, `emp_tracking/www/oh.py` / `oh.html`, `emp_tracking/public/oh/`, the `/oh` route rule in `hooks.py` and the "OH Portal" desk menu link in `workforce_dashboard/setup.py`.
- **Reason:** The user wants the OverHead work to stay in the Frappe desk and only look better there.
- **Files or modules affected:** the files above; `hooks.py` and `setup.py` are back to their state before the portal.
- **Testing:** see the desk design entry below for the migrate run after the removal.
- **Pending items:** none for the portal.

## 2026-11-02: FTTH Work Order list: stage pipeline and clearer columns

- **Summary:**
  - **Fixed the title column:** names like "Ashiana Malhar Tower 8 And 9" showed raw `<span class="indicator-pill…` text. FTTH Tracker's list formatter adds a warning badge as HTML to the title, and Frappe 16 shows the title as plain text. The title is now plain text, and the warning shows as a red "!" in the Stage pill.
  - **Stage column:**
    - Short names ("AT & HOTO" instead of "AT & HOTO by Pro…"), with the full name on hover.
    - Coloured by who acts: Area Manager orange, Project Head blue, Fiber Team yellow, Splicing purple, Accounts cyan, Closed green, Cancelled red.
    - Still click-to-filter.
  - **Issue Type column:** coloured by meaning. Completed is green and WIP blue. Waiting on someone is yellow (mail approval, OLT, site location, details). Permission / access / local issues are orange. B End Not Evisions, Wrong WO and Cancelled are red.
  - **Final Distance column:** "110 m"; empty or 0 shows a muted dash.
  - **Stage pipeline strip** above the rows: All plus one chip per stage in process order, with counts under the current filters (Frappe's group-by count, so permissions apply). A click filters to that stage; a second click clears it.
  - Done from emp_tracking (`doctype_list_js`), which extends FTTH Tracker's list settings and keeps its status indicator and "Only with warnings" button. FTTH Tracker's files are not edited.
- **Reason:** The user asked to make the FTTH Work Order list better (screenshot of the dark-mode list with the raw HTML in the first row and truncated stage names).
- **Files or modules affected:**
  - New: `emp_tracking/public/js/ftth_work_order_list.js`.
  - Changed: `emp_tracking/hooks.py` (`doctype_list_js`), `emp_tracking/public/css/evision.css` (section 4).
- **Testing:**
  - **Local:** `node --check` and `py_compile` passed; files are LF.
  - **Visual (local):** headless Chrome screenshots of a mock list. It ran the real formatters and pipeline code with Frappe's desk CSS and the live stage counts (Survey 1,576, AT & HOTO 1,406, Cancelled 28, Billing 2). Light and dark mode looked correct. Frappe's own dark yellow / cyan pills were too bright, so ours get a soft tint.
  - **Server:** `bench migrate` on newsite.local passed. `doctype_list_js` is registered and the file returns HTTP 200. Live stage / issue counts came from `get_group_by_count` on newsite.local.
  - **Not done:** no look at the real list in a logged-in browser.
- **Pending items:**
  - The filter bar still shows 18 standard filters (3 rows). Trimming it would change the list for every role, so that waits for the user's choice.

## 2026-11-02: EVision design layer: one Sketch-style look, dark mode, stage trackers

- **Summary:**
  - **Shared design layer** `public/css/evision.css`, loaded on the desk through `app_include_css`. It follows Frappe's own Espresso design system, the one frappe-ui and the Sketch app (sketch.netchamp.dev/feed, the user's reference) use: neutral grays, quiet borders, medium-weight type, colour only where it means something. It defines `--ev-*` tokens mapped onto Frappe's `--surface-*` / `--ink-*` / `--outline-*` variables.
  - **All 7 Evision desk pages re-themed** (Workforce / EVision Dashboards, Manager, NOC, Employee Performance, KMZ Map, KMZ Site Check, Network Topology):
    - Hard-coded hex colours in the pages' `<style>` blocks and inline styles became `--ev-*` tokens, so **dark mode now works**. Before, the cards stayed white in dark mode.
    - Type weights 800 → 600 and 700 → 500.
    - The thick coloured top strip on KPI tiles is gone; the tinted icon tile keeps the colour cue.
    - Line icons replace the emoji on the Workforce and Manager tabs.
  - **Skeleton loading** (shimmer) replaces the "Loading…" text, and **empty states** show an icon above the message, as in Sketch's empty feed.
  - **Stage tracker** at the top of two forms (`evision.stepper` in the new `public/js/evision.js`, loaded through `app_include_js`):
    - **FTTH Work Order:** steps from Survey to Closed (B End Approval only when B End / Distance Issue is ticked). It shows the done steps, the current step, "Step N of M" and who acts now. The chip says "With you" when the step is the viewer's role. Cancelled orders show the tracker greyed out.
    - **Complaint Information:** the OHP Maintenance Workflow path from New to Closed. Who acts is read from the workflow's own transitions. Rejected shows in red at the Maintenance Team step, with the Area Manager to reassign.
  - Chart series, avatar palettes and map pin / route colours are unchanged: they are data colours, not CSS.
- **Reason:** The user asked to make the whole Evision process look and work like the Sketch reference. Each page had its own hard-coded light palette (up to 44 hex colours per page), so the pages broke in dark mode and drifted apart. The forms also gave no picture of where a job stands or whose turn it is.
- **Files or modules affected:**
  - New: `emp_tracking/public/css/evision.css`, `emp_tracking/public/js/evision.js`.
  - Changed:
    - `emp_tracking/hooks.py` (`app_include_css`, `app_include_js`)
    - `public/js/ftth_work_order.js` (`WO_STEPS`, `wo_stage_tracker`)
    - `complaint_information.js` (`COMPLAINT_STEPS`, `complaint_stage_tracker`)
    - `page/workforce_dashboard`, `manager_dashboard`, `noc_dashboard`, `employee_performance`, `kmz_map`, `kmz_site_check`, `network_topology` (the `.js` of each)
  - ftth_tracker's files are not edited.
- **Testing:**
  - **Local:** `node --check` passed on all 10 changed JS files and `py_compile` passed on `hooks.py`. The changed files kept their line endings: LF, except `kmz_map.js` and `kmz_site_check.js`, which were already CRLF and were left that way.
  - **Visual (local):** a preview page loaded Frappe's real compiled desk CSS, `evision.css` and the Workforce / NOC style blocks taken from the edited files, then ran the real `evision.stepper()` against a mocked form. Headless Chrome screenshots looked correct in light and dark mode: KPI tiles, table, chips, bars, empty state, skeleton, and work order / rejected complaint / closed trackers.
  - **Server:** `bench --site newsite.local migrate` passed. `frappe.get_hooks` lists both new includes, and `/assets/emp_tracking/css/evision.css` and `/js/evision.js` return HTTP 200.
  - **Not done:** no look at the live pages or forms in a logged-in browser on newsite.local. Logging in a headless browser as Administrator was not allowed, so nothing was checked against real data, real roles or the real form layout.
- **Pending items:**
  - Check each page and both forms in the browser, in light and dark mode. Hard-refresh once (Ctrl+Shift+R): the two new files are plain assets without a build hash, so a browser may keep an old copy.
  - Standard list and form views keep Frappe's own styling. Only the Evision pages and the two trackers changed.
  - The trackers sit at the top of the forms' first tab (Frappe's form dashboard), so they don't show on other tabs.

## 2026-10-31: FTTH Work Order: each role edits only its own part

- **Summary:**
  - FTTH Work Order fields now have permission levels by owner, the same way New Project's tabs did. **1 = Project Head** (WO details, GIS, locations, planning distance, distances, KMZ, mail approval, RFS, AT & HOTO), **2 = Area Manager** (site status / issues, survey distance, B End issue, Fiber Team, splicers / riders), **3 = Fiber Team** (fiber type / ID / readings, reading and route snaps), **4 = Splicing Team** (splicing snaps), **5 = Accounts** (PO, invoice, amount, payment).
  - Calculated / read-only fields and Remarks stay at level 0, so the server still sets stage, status, area and other derived values on any save.
  - Every role that can open work orders can read all levels. Area Manager, Fiber Team, Splicing Team and Accounts User / Manager can write only their own level (plus level 0). Project Head, System Manager, FTTH Manager and FTTH User can write all levels, so imports and office corrections keep working.
  - Applied from emp_tracking with Property Setters (`permlevel`) and Custom DocPerm rows, rebuilt on every migrate by `ftth_stages.apply_field_levels()`. ftth_tracker's files are not edited.
- **Reason:** The user asked whether the system follows the role diagram. It followed the stage order, but any role could edit any field. That role restriction existed only on New Project and was lost when New Project was merged into FTTH Work Order today. The user approved adding it back.
- **Files or modules affected:** `emp_tracking/ftth_stages.py` (`FIELD_LEVELS`, `LEVEL_WRITERS`, `apply_field_levels`, `after_migrate`).
- **Testing:**
  - `py_compile` passed, the file is LF, and `bench migrate` on newsite.local passed.
  - Field levels on the server: 81 at level 0, 46 at 1, 14 at 2, 9 at 3, 3 at 4, 13 at 5. The Custom DocPerm rows match the table above.
  - In rolled-back saves:
    - The Area Manager user (pune.areamanager@example.com) saved Survey Distance and the stage moved to Fiber Team Assignment. Their PO No change was discarded.
    - The Accounts User (finance@demo.local) saved PO No. Their Fiber ID change was discarded.
  - **Not done:** a test as a Fiber Team or Splicing Team user (no user on the site has only that role), and a look at the form as each role in the browser.
- **Pending items:**
  - Users who also have Project Head, System Manager or an FTTH role can still edit everything.
  - The form shows other roles' fields as read-only. It doesn't hide empty tabs per role the way New Project's form did.

## 2026-10-31: New Project merged into FTTH Work Order

- **Summary:**
  - **FTTH Work Order is now the only doctype for a job**, from WO to billing. The **New Project** doctype and its two child tables (Project Fiber Team Member, Project Splicing Team Member) are removed.
  - Patch `remove_new_project` deleted the 4 New Project rows. They were test entries made by Administrator on 7-9 Oct 2026, and the user chose to drop them. It also deleted the rows that pointed at them (2 comments, 1 communication, 3 notification logs, 2 sidebar links, 1 child row) and dropped the three tables.
  - FTTH Work Order already had the same 11 stages, roles, Extract & Fill, AT & HOTO and Billing. It now also has these, ported from New Project:
    - **Network Link on HOTO:** when the HOTO Date is entered or changed, a Network Link (LINKID = Evisions Link ID, type FTTH, operator Airtel, Area matched to an Area record) is created. It is stored in the new custom field **Network Link (Maintenance)** (`custom_network_link`). If data is missing, the user gets an orange message listing what to fill.
    - **"Project" button menu**, for Project Head and System Manager only:
      - **Send Mail to Planning**, shown when B End / Distance Issue is ticked. It opens the same email draft as before, built from the work order's fields.
      - **Create Network Link**, for work orders that already had a HOTO Date (49 do) or whose first attempt was missing data.
  - **Network Link** "New Project" field is now **Work Order**, linking to FTTH Work Order. The fieldname `project` is unchanged and had no data.
  - **Performance Leaderboard** report and **Employee Performance** FTTH view: the "New Project" source and the "EVisions Team" rank (New Project only) are removed. The report's ref doctype is now FTTH Work Order.
  - **OverHead Project menu:** the "Projects" section is removed and "FTTH Work Orders" is now labelled **Work Orders**.
  - **WhatsApp Settings:** the field label is now "Work Order Stage Template".
  - Old patches `oh_project_masters`, `splicing_team_rows` and `transport_is_backbone` skip New Project when it no longer exists.
  - Not ported: the mobile splicing endpoints `splicing_jobs` / `upload_splicing_snap`. The EmployeeTracker app (`E:\New folder\EmployeeTrackerApp`) does not call them, and FTTH Work Order's splicers are Field Staff with no Employee or login.
- **Reason:** The user said New Project and work order are the same thing and chose to merge them into one doctype, keeping FTTH Work Order (3,012 rows) and porting only the Network Link and mail behaviour.
- **Files or modules affected:**
  - Removed: `emp_tracking/emp_tracking/doctype/new_project/`, `project_fiber_team_member/`, `project_splicing_team_member/`.
  - New: `emp_tracking/patches/remove_new_project.py` (in `patches.txt`), `emp_tracking/public/js/ftth_work_order.js`.
  - Changed:
    - `emp_tracking/hooks.py` (`doctype_js`)
    - `emp_tracking/ftth_stages.py` (helpers moved in, `make_network_link`, `find_area`, `create_network_link`, `make_custom_fields`)
    - `network_link.json`
    - `whatsapp_settings.json` / `.py`
    - `performance_leaderboard.py` / `.js` / `.json`
    - `employee_performance.py` / `.js`
    - `performance.py`
    - `workforce_dashboard/setup.py` / `workforce_dashboard.js`
    - `fiber_pulling_team.py`, `maintenance_team.py` (header comments)
    - `patches/oh_project_masters.py`, `splicing_team_rows.py`, `transport_is_backbone.py`
- **Testing:**
  - **Local:** `py_compile` and `node --check` passed, the JSON parses, all changed files are LF, and `python -m unittest emp_tracking.tests.test_performance` passed (7 tests).
  - **Server:**
    - A database backup of newsite.local was taken before migrating (`20261031_103649-newsite_local-database.sql.gz`), and `bench migrate` passed.
    - The 3 DocTypes and their tables are gone, with 0 leftover comments and notification logs. The custom field exists, Network Link.project links to FTTH Work Order, the report ref doctype and WhatsApp label are updated, both sidebars show "Work Orders", and 3,012 work orders are unchanged.
    - In a rolled-back transaction:
      - The FTTH Work Order form script includes both buttons.
      - `create_network_link("FTTH-33800")` created Network Link 202609109 (area Narhe, FTTH, Airtel, EVisions), and a second call did not create a duplicate.
      - Changing a HOTO Date on save created a link for FTTH-32652.
      - The leaderboard (42 rows) and `get_jobs_dashboard` returned data.
  - **Not done:** clicking the buttons and sending the mail in the browser, and a login as Project Head.
- **Pending items:**
  - The 49 work orders that already have a HOTO Date get no Network Link until a Project Head presses "Create Network Link" or changes the HOTO Date.
  - Only 2,576 of 3,012 work orders have an Evisions Link ID, and the Area text must match an Area record.
  - FTTH Work Order has no Customer, Link Type or Project Type, so these Network Links are always FTTH / Airtel.
  - Comments in the ftth_tracker app still say "like New Project". They were left alone because that app has other sessions' uncommitted changes.
  - The removal can't be undone with git alone: restore the database backup above if the old rows are needed.

## 2026-10-31: "Who Attended Where" split by role for each splicer

- **Summary:** On the Employee Performance page, the "Who Attended Where" card now shows each person's area chips split into one row per role they had on the complaints: **As Splicer**, **As 2nd Splicer**, **As Rider**, **As 2nd Rider**. Each row also shows that role's call count. The name, totals and click-through to the profile are unchanged.
  - Each person's own profile (click a name, or pick them in the Employee filter) now opens with a **"Where <name> Attended"** card showing the same per-role area rows, above their complaint charts. It follows the Area filter.
- **Reason:** The user asked to see the area breakdown for each splicer role separately.
- **Files or modules affected:**
  - `emp_tracking/emp_tracking/page/employee_performance/employee_performance.py`: `area_calls()` returns `roles: [{role, calls, areas}]` for each person.
  - `emp_tracking/emp_tracking/page/employee_performance/employee_performance.js`: new `role_areas_html()` and `.ep-role-line` / `.ep-role` styles.
- **Testing:**
  - `node --check` passed and both files are LF.
  - `get_calls_dashboard` ran on newsite.local for Splicer (22 people) and Supervisor (49 people) and returned the role split. For example, Sanket Kotkar: 1,117 calls as Splicer and 126 as 2nd Splicer.
  - In the person view (`employee=HR-EMP-00057`), `area_calls.people` holds only that person, with the same role split, which the profile card reads.
  - `bench clear-cache` was run on newsite.local.
  - **Not done:** a look at the card in the browser.
- **Pending items:** A complaint that names the same person in two roles counts once in each role row. That's why Sanket Kotkar's role rows add up to 1,243 while his total is 1,242.

## 2026-10-29: Desk home shows only the four module tiles, with picture icons

- **Summary:**
  - The desk home now shows only **OverHead Project, Emp Tracking, NOC and Milestone**.
    - Every other Desktop Icon is hidden after each migrate by `keep_only_desk_icons()`: Frappe HR and its children, and the ERPNext ones (Selling, Buying, Stock, Assets, Projects, Quality, Manufacturing).
    - The hidden names are stored in the default `emp_tracking_desk_hidden_icons`; `show_hidden_desk_icons()` brings them back.
  - The four tiles have picture icons in Frappe's rounded-square style, in solid and subtle variants: network nodes (OverHead Project, blue), location pin (Emp Tracking, green), headset (NOC, purple), flag (Milestone, orange).
  - The extra tiles the user saw (Framework, Accounting, Helpdesk, Organization ...) are not icon records on the server. They come from an old desk layout saved in the browser and go away with the desk menu's "Reset Desktop Layout".
- **Reason:** The user asked to keep only these modules on the home screen, with icons.
- **Files or modules affected:**
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`DESK_ICONS`, `keep_only_desk_icons`, `show_hidden_desk_icons`).
  - New `emp_tracking/public/icons/desktop_icons/{solid,subtle}/{overhead_project,emp_tracking,noc}.svg`.
  - New `milestone_app/public/icons/desktop_icons/{solid,subtle}/milestone.svg`.
- **Testing:**
  - The SVGs parse. `bench migrate` on newsite.local passed.
  - Visible Desktop Icon rows are exactly the four tiles. The Administrator's boot list shows the same four. Frappe's icon lookup lists the four SVGs, and they are served with HTTP 200 as image/svg+xml.
  - **Not done:** seeing the icons in the browser, and a login as a non-admin user.
- **Pending items:**
  - HR and accounts users lose the Frappe HR / ERPNext tiles too. They can still open those screens from the search bar.
  - Each user whose browser kept an old layout must use "Reset Desktop Layout" once.

## 2026-10-29: Three desk tiles instead of EVision: OverHead Project, Emp Tracking, NOC

- **Summary:** The single "EVision" tile on the desk home is replaced by one tile per module, each with its own sidebar:
  - **OverHead Project** (icon "project"): Projects (New Project) · FTTH (FTTH Dashboard, Work Orders, Imports) · Fiber Store (Fiber Dashboard, Cable Inward / Outward) · Network (GIS Nodes, Link Register, Sites, KMZ Map, Upload KMZ) · Teams & Vendors (Areas, EVisions Teams, Vendors, Field Staff). Seen by Project Head, Area Manager, Fiber / Splicing Team, Accounts User / Manager, FTTH Manager / User, Management, System Manager.
  - **Emp Tracking**: Workforce Dashboards, Employee Performance. Seen by everyone who saw EVision, staff included (staff keep this tile plus Leaves and Expenses).
  - **NOC**: NOC Dashboard, Complaints. Seen by NOC Head, Maintenance Agent, Management, System Manager.
  - The "Helpdesk NOC" tile is hidden, since NOC replaces it. Its sidebar stays and shows the NOC menu. The FTTH Tracker sidebar shows the OverHead Project menu. The EVision tile and sidebar are deleted.
- **Reason:** The user asked for the three modules as separate tiles on the desk home.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`oh_menu` per tile, `module_tiles`, `make_navigation`, `make_tile` roles / order, `OLD_SIDEBARS`, `HIDDEN_ICONS`, `MIRROR_SIDEBARS`, `restrict_desktop_icons`) and `workforce_dashboard.js` (`EV_SIDEBAR` = Emp Tracking, `OH_SIDEBARS`).
- **Testing:** `py_compile` and `node --check` passed. `bench migrate` on newsite.local passed. On the server: the 3 tiles exist and are visible with 10 / 17 / 4 roles; EVision is gone; Helpdesk NOC is hidden; the sidebars have the sections and link counts listed above. **Not done:** a look at the desk and sidebars in the browser, and a login as a non-admin role.
- **Pending items:** The tiles' place on the desk (they were given idx 0, 1, 2) is not checked on screen. Accounts users now see the OverHead Project tile; take them off if billing is not done from there.

## 2026-10-29: EVision sidebar trimmed and grouped under section headings

- **Summary:** The EVision sidebar (also copied to the Helpdesk NOC and FTTH Tracker sidebars) now has 19 links instead of 37, in collapsible sections:
  - Dashboards: Workforce Dashboards, FTTH Dashboard, NOC Dashboard, Employee Performance.
  - FTTH Work Orders: FTTH Work Orders, FTTH Imports.
  - OH Projects: New Project.
  - Complaints: Complaints.
  - Fiber Store: Fiber Dashboard, Cable Inward / Outward.
  - Network: GIS Nodes, Link Register, Sites, KMZ Map, Upload KMZ.
  - Teams & Vendors: Areas, EVisions Teams, Vendors, Field Staff.
  - Taken off the menu but still opening from the search bar: Staff Monthly Performance, Work Order Map, FTTH GIS Summary, Drum Balance, Fiber Stock Balance, Drums, Network Links (LINKID), Node Sites, KMZ Routes, KMZ Points, Network Topology, KMZ Site Check, KMZ Map Settings, IBD Teams, Fiber Pulling Teams, Fiber Teams, FTTH Settings, Leaderboard Settings.
  - Fix: the section headings never showed, because every link was saved as a top-level row (`child = 0`). Links are now children of their section.
- **Reason:** The user asked to keep only the necessary items. Their screenshot showed one long flat list.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`oh_menu`, `set_sidebar_items`).
- **Testing:** The file compiles. `bench migrate` on newsite.local passed, and the rebuilt "EVision" sidebar has the 7 sections and 19 child links listed above. **Not done:** a look in the browser.
- **Pending items:** The removed links can be put back one by one if someone misses them.
- **Later the same day:** the sections were regrouped by module, on the user's request:
  - **OverHead Project:** New Project, FTTH Dashboard, FTTH Work Orders, FTTH Imports, Fiber Dashboard, Cable Inward / Outward, GIS Nodes, Link Register, Sites, KMZ Map, Upload KMZ, Areas, EVisions Teams, Vendors, Field Staff.
  - **Emp Tracking:** Workforce Dashboards, Employee Performance.
  - **NOC:** NOC Dashboard, Complaints.
  - Migrate passed. The EVision, Helpdesk NOC and FTTH Tracker sidebars all show these 3 sections with 19 links. The 2 new Error Log rows come from Helpdesk's search index, not from this change.

## 2026-10-29: "Paste WO Message" + "Extract & Fill" on FTTH Work Order (ftth_tracker)

- **Summary:** The first tab of FTTH Work Order now starts with New Project's "Paste WO Message" section: a WO Message box and an "Extract & Fill" button.
  - It reads the Airtel MWO text and fills: WO Number (which also fills WO ID, WO Date, Segment, Building Type), Airtel Unique ID (upper case), End Location (Site Name), End Lat, Long, HP, GIS, B End or B End Lat, Long (B Point), Planning Distance (Feeder Length, "160 mtrs" → 160), Nearest ODF, Pincode, RSU, Remarks, City (from the MWO No) and WO Received Date (the "Released" date).
  - A GIS code that is not an existing GIS Node is reported, not filled. It warns when the Feeder Partner is not Evision.
- **Reason:** The user asked for New Project's paste feature on FTTH work orders.
- **Files or modules affected:** `ftth_work_order.json` (`sb_paste`, `wo_message`, `extract_data`), `ftth_work_order.js` (`MESSAGE_FIELD_MAP`, `parse_message`, `get_released_date`, `get_city`, `extract_and_fill`).
- **Also fixed:** earlier edits today had saved several files with Windows (CRLF) line endings. They were converted back to LF, so git shows only the real changes. Files: `logic.py`, `readers.py`, `run.py`, `ftth_work_order.js/.py`, `ftth_import.py`, `set_work_order_stage.py`, emp_tracking `hooks.py`, `ftth_stages.py`, and this changelog.
- **Testing:** `node --check` passed. The parser on a sample MWO message gave the right field values, released date 2026-10-01 and city Pune. `bench migrate` on newsite.local passed and the button is in the doctype. **Not done:** pasting a real message in the browser.
- **Pending items:** Message lines without an FTTH field (WO Type, BTS Type, POP ID, Core, Ports, Marketing / Sales names) are not stored.

## 2026-10-29: Link ID register imported, and "Send to Area Manager" button on FTTH Work Order (ftth_tracker)

- **Summary:**
  - **Link ID register:** "Merge - Link ID From - 2019 To Till Date.pdf" (1,240 pages, Sr No 1 to 17,005, Link IDs from 2011 to Oct 2026) was rebuilt as an .xlsx and imported as IMP-31863, mode Fill empty.
    - The PDF prints four column bands of 310 pages each; rows were lined up by their y position.
    - Result: 16,902 Link Registers created, 89 existing ones filled, 238 vendor / supervisor masters created, 0 issues.
    - Afterwards 2,573 more work orders were connected to their Link Register (36 by Link ID, 2,537 by building name + GIS). 2,576 of 3,012 are now linked. 37 picked up HOTO details for the Billing tab. This was written directly to the database: no notifications, "modified" unchanged.
  - **Save button flow** copied from New Project onto the FTTH Work Order form. The button is named after the next owner: "Send to Area Manager", "Send to Project Head", "Send to Fiber Team", "Send to Splicing Team", "Send to Accounts", "Mark RFS Done", "Close Work Order", "Cancel Work Order". It stays "Save" while the same owner keeps working.
- **Reason:** The user sent the Link ID register to import, and asked for New Project's "Send to Area Manager" flow on FTTH work orders.
- **Files or modules affected:** `ftth_tracker/ftth_tracker/doctype/ftth_work_order/ftth_work_order.js` (`STAGE_OWNERS`, `get_next_stage`, `set_send_button`). The register itself is data only.
- **Testing:**
  - The importer's reader on the rebuilt .xlsx: 17,002 rows, 16,991 unique Link IDs, 0 issues. The import on newsite.local completed with the counts above.
  - The form's `get_next_stage()` gives the same result as the server's `compute_stage()` on 11 cases. `node --check` passed. `bench migrate` passed.
  - **Not done:** clicking the button in a browser.
- **Pending items:**
  - 1 distance cell ("4800", PDF page 274) could not be placed on a row.
  - Rows where vendor and supervisor are printed close together may have both names in Vendor.
  - 436 work orders are still without a Link Register (no Link ID and no unique building-name match).

## 2026-10-29: FTTH stages and stage owners now exactly as New Project (ftth_tracker + emp_tracking)

- **Summary:** FTTH Work Order Stage now has New Project's full list. After RFS, a work order moves to **AT & HOTO by Project Head** (until AT Status = Done and a HOTO Date is set), then **Billing by Accounts** (until Payment Status is Fully Received or Cancelled/ Written Off), then **Closed**. The FTTH-only "RFS Done" stage is removed; the separate Status field still says RFS Done.
  - Notifications use New Project's owner for each stage:
    - Area Manager: Survey, Fiber Team Assignment, Splicer Assignment.
    - Project Head: B End Approval, Final Details, AT & HOTO.
    - Fiber Team: Fiber Work.
    - Splicing Team: Splicing.
    - Accounts User / Accounts Manager: Billing.
    - Closed / Cancelled: WhatsApp to the Project Heads only, no bell.
- **Reason:** The user showed New Project's stage list and asked FTTH to take the same stages, and the same "which stage goes to the Area Manager", from New Project.
- **Files or modules affected:**
  - ftth_tracker: `logic.py` (`compute_stage`, `PAYMENT_DONE`), `ftth_work_order.json` (stage options), `patches/set_work_order_stage.py` and `patches.txt` (re-run).
  - emp_tracking: `ftth_stages.py`.
- **Testing:**
  - Locally: `compute_stage()` on RFS without AT, AT without HOTO date, AT + HOTO, fully paid, cancelled, and a survey-only case. All were as expected.
  - On newsite.local: `bench migrate` passed and the stage patch re-ran. Result: 1,576 Survey by Area Manager, 1,406 AT & HOTO by Project Head, 2 Billing by Accounts, 28 Cancelled. The patch writes to the database directly, so no notifications were sent.
  - **Not done:** a real stage change sending the bell / WhatsApp, and a browser check.
- **Pending items:** The 1,406 finished sites sit at "AT & HOTO by Project Head" until AT / HOTO is entered. Most are old sites whose AT/HOTO was never recorded in the app; filling them in, or marking old ones Closed in bulk, is open.

## 2026-10-29: Billing tab on FTTH Work Order, and "FTTH - Billing Details" imported (ftth_tracker + emp_tracking)

- **Summary:**
  - **New "Billing" tab** on FTTH Work Order, with the same fields and options as New Project's AT & HOTO and Billing tabs.
    - AT & HOTO: AT Status, AT Paper Status, Billed (from Link Register), HOTO No, HOTO Date, HOTO Signature Status, Billing Year, Section Name.
    - Customer PO & Invoice: Billing Status, PO No and date, Invoice No and date, Invoice Sent, ARN, Airtel Approver.
    - Amount & Payment: Base, GST, Final (Base + GST, worked out on save), Payment Due Date, Payment Status, Billing Remark.
  - **Auto-fill:** HOTO details come from the linked Link Register's HOTO rows, filling empty fields only. The sheet's "HOTO NO" column is read as follows:
    - "HOTO 296" → HOTO No 296, AT Done, signature Done.
    - "Sign Pending" → AT Done, signature Pending.
    - "AT Pending" → AT Pending.
  - **First tab:** Evisions Link ID and Link Register moved from the RFS tab to the Work Order section.
  - **Accounts User / Accounts Manager** can open and edit FTTH Work Orders, to fill the Billing tab.
  - **Importer:** billing rows without a Link ID (the recent ones) are no longer dropped. They are placed on the work order with the same building name and GIS; when several work orders share the name, the one whose RFS month matches is used. Rows that can't be placed are listed as Issues.
  - **Import ID fix:** a file without a month/year in its name now continues the plain numbering (IMP-31861). Before, it restarted at IMP-00001 and failed as a duplicate.
- **Data loaded on newsite.local:** "FTTH - Billing Details.pdf" (170 rows, all GIS V0N, 2022-23 to 2026-27) was rebuilt as an .xlsx and imported as IMP-31861 and IMP-31862, mode Fill empty.
  - 89 rows with a Link ID → 89 Link Registers with HOTO rows. 3 existing work orders connected to them.
  - 81 rows without a Link ID → 47 placed on work orders. 34 not placed: no work order with that building name on V0N; they are listed in IMP-31862's Issues.
  - In total 49 work orders now carry billing data: 4 AT Done with HOTO No, 45 AT Pending.
  - The connection and backfill ran directly in the database: no notifications, "modified" unchanged.
- **Reason:** The user asked to add billing in a new tab of the work order and sent the billing sheet. They also asked for Evisions Link ID and Link Register on the first tab.
- **Files or modules affected:**
  - ftth_tracker:
    - `ftth_work_order.json` (Billing tab, field order)
    - `ftth_work_order.py` (`set_billing_values`)
    - `logic.py` (`hoto_values`, `final_amount`)
    - `importer/readers.py` (`wo_billing`), `importer/run.py` (`billing_to_work_orders`)
    - `doctype/ftth_import/ftth_import.py` (`sync_plain_series`)
    - new patch `patches/fill_billing_from_link_register.py`
  - emp_tracking: `ftth_stages.py` (Accounts roles).
- **Testing:**
  - Locally: `hoto_values()` on HOTO, Sign Pending, AT Pending, name-only, multiple rows and empty input; `final_amount()`; the reader on the rebuilt .xlsx (170 rows: 89 with a Link ID, 81 without, no issues).
  - On newsite.local: `bench migrate` passed and the patch ran. Both imports completed, with the counts above. The Shrirang Apartment tie was resolved to FTTH-31781 (RFS Feb-26).
  - **Not done:** a browser check of the new tab.
- **Pending items:**
  - 34 billing rows have no matching work order (e.g. Arya Heights, Khilate Niwas, Balaji Vishwa Phase 2). They may be named differently on the work order, or not loaded yet.
  - Most Link-ID rows (2022 to mid-2024) are older buildings that are not FTTH work orders on the site.
  - FTTH stages still end at RFS Done; there are no AT & HOTO / Billing stages yet.

## 2026-10-29: FTTH Work Order gets New Project's stages and roles (ftth_tracker + emp_tracking)

- **Summary:**
  - **Stage field** (read-only, in the list and its filters) on FTTH Work Order, using the same stage names as New Project. It is worked out on every save:
    `Survey by Area Manager` (no survey distance) → `B End Approval by Project Head` (B end issue without approval date) → `Fiber Team Assignment by Area Manager` → `Fiber Work by Fiber Team` (no Fiber ID / reading snaps) → `Splicer Assignment by Area Manager` → `Splicing by Splicing Team` (splicing snaps missing) → `Final Details by Project Head` → `RFS Done`, or `Cancelled`.
    An RFS or completed work order goes straight to RFS Done, so old imported rows don't show as pending survey.
  - **Area Manager (Login)** user field. It is filled automatically when exactly one user's full name matches the Area Manager name.
  - **Notifications on stage change** (emp_tracking): a bell notification and a WhatsApp message with New Project's template go to the next person.
    - Area Manager stages → the Area Manager (Login), else the Area Manager role.
    - Project Head stages and RFS Done / Cancelled → the Project Head role.
    - Fiber Work → the Fiber Team's contact number and the Fiber Team role.
    - Splicing → the splicer / rider contact numbers and the Splicing Team role.
    - Saves made by an FTTH Import send nothing.
  - **Roles:** Project Head, Area Manager, Fiber Team and Splicing Team can open and edit FTTH Work Orders (Project Head can also create). They can also select and read Fiber Team, Field Staff, IBD Team, GIS Node, KMZ Route, KMZ Point and FTTH Link. This is applied on every migrate.
  - **Patch** `ftth_tracker.patches.set_work_order_stage` fills Stage on existing work orders directly in the database. No notifications are sent and "modified" is unchanged.
- **Reason:** The user asked for FTTH work orders to follow the same roles and stages as New Project ("area manager ko gaya" and so on).
- **Files or modules affected:**
  - ftth_tracker:
    - `logic.py` (`compute_stage`, `STAGE_*`; `derive()` sets `stage`)
    - `doctype/ftth_work_order/ftth_work_order.json` (`stage`, `area_manager_user`)
    - `ftth_work_order.py` (`set_area_manager_user`)
    - `patches/set_work_order_stage.py`, `patches.txt`
  - emp_tracking:
    - new `emp_tracking/ftth_stages.py`
    - `hooks.py` (doc_events "FTTH Work Order" on_update, after_migrate)
- **Testing:**
  - `compute_stage()` checked locally with 9 cases, one per stage plus RFS and Cancelled. All were as expected.
  - All changed Python files compile. The doctype JSON diff contains only the two new fields.
  - **On newsite.local (2026-10-29):** `bench migrate` ran without errors. Afterwards the patch had filled Stage on every work order (1,576 Survey by Area Manager, 1,408 RFS Done, 28 Cancelled), and the 4 roles have Custom DocPerm rows on FTTH Work Order (Project Head with create). The web server reloaded the new code by itself.
  - **Not exercised:** a real stage change that sends the bell notification and WhatsApp.
- **Pending items:**
  - Only document-level rights were added. Field-level blocks, where each role edits only its own section as in New Project, are not set yet.
  - Fiber Team and Splicing Team roles see all work orders, not only their own (FTTH staff are Field Staff records without logins).
  - FTTH has no AT / HOTO / Billing stages; it ends at RFS Done.

## 2026-10-29: Warning when an RFS work order has no route mapped (ftth_tracker)

- **Summary:** An FTTH Work Order that is RFS Done (status RFS Done, or an RFS date set) but has no matched KMZ Route now gets the warning "RFS done but no KMZ route is mapped." It shows in the red "Please check" box and sets Has Warnings. It is a warning, not a block: the work order still saves and imports still load.
- **Reason:** The user pointed out that a site that is Ready For Service must have its mapping. Until now the only check was "RFS done but KMZ not marked done", and that needed both an RFS date and a Fiber ID and only looked at the tick box, not an actual route.
- **Files or modules affected:** `ftth_tracker/ftth_tracker/logic.py`. `compute_warnings()` has the new rule, and `derive()` now passes the computed status into it.
- **Testing:** Checked locally by calling `derive()` with: no RFS (no warning), an RFS date (warning), a work completed date only (warning), and an RFS date with a KMZ route (no warning). All four gave the expected result.
  - `bench migrate` ran on newsite.local on 2026-10-29. **Not done:** a browser check.
- **Pending items:**
  - Existing work orders get the new warning only when they are next saved or re-imported. Older RFS sites without a KMZ will start showing it then.
  - Not decided: whether to block RFS without a route, or to recalculate warnings for every existing work order in one go.

## 2026-10-29: Route Map on FTTH Work Order shows distance in metres (ftth_tracker)

- **Summary:** The Route Map on an FTTH Work Order now shows how far the route goes.
  - Each route line has a permanent "<n> m" label on it.
  - Under the map: "Route covered: <n> m" (the sum of the drawn line) and, when both ends have coordinates, "A end to B end straight line: <n> m".
- **Reason:** The user asked for the map to show how many metres the mapped route covers.
- **Files or modules affected:** `ftth_tracker/ftth_tracker/doctype/ftth_work_order/ftth_work_order.js` (new `ftth.line_length_m()` and `ftth.show_route_distance()`, called from `refresh`). Client-side only; no field or data change.
- **Testing:**
  - `node --check` on the file passed.
  - `bench migrate` ran on newsite.local on 2026-10-29. `bench build --app ftth_tracker` fails on the server (Node 18; this Frappe needs Node 24 or later), but doctype form scripts are served without a build. **Not done:** a browser check.
- **Pending items:** The length is measured from the drawn KMZ line, so it can differ slightly from the stored "KMZ Route Length (m)" if the KMZ file's own figure was calculated differently.

## 2026-10-29: FTTH Import IDs carry the file's month and year (ftth_tracker)

- **Summary:** A new FTTH Import now takes its ID from the attached file's name.
  - When the name has a month word and a year, the ID is `IMP-<MON>-<YEAR>-#####`, with its own counter per month. For example, "April 2026 FTTH Sheet.xlsx" becomes `IMP-APR-2026-00001`.
  - Short and full month names both count ("Aug", "July", "Sept"). Only whole words match, so "Marquee" is not read as March.
  - Otherwise the ID stays `IMP-#####` and continues the existing counter (e.g. "Master Data for Software.xlsx", "export.zip").
- **Reason:** The user asked for the import ID to show which month's sheet it holds, instead of a bare number like IMP-31860.
- **Files or modules affected:** `ftth_tracker/ftth_tracker/doctype/ftth_import/ftth_import.py`, which gained `month_year()` and `FTTHImport.autoname()`. The JSON autoname `format:IMP-{#####}` is unchanged; it is used only if the controller method is removed.
- **Testing:**
  - Checked locally (Windows): `month_year()` on 9 sample file names (April/Aug/Feb/July sheets, Master Data, export.zip, a Sept/Marquee name, fiber_register_2026_27, "April 2026-2027"), and the file compiles.
  - Live on newsite.local: imports IMP-APR-2026-00001/00002, IMP-MAR-2026-00001 and IMP-MAY-2026-00001 were created with the new IDs.
- **Pending items:**
  - Existing imports keep their old IDs. IMP-31860 (April 2026 sheet, queued) is not renamed.
  - The rule reads the file name only, not the sheet contents.
  - The ID is set when the import is first saved. Swapping the file later does not change it.

## 2026-10-28: "Feb 2026 FTTH Sheet" (193 Airtel FTTH work orders) imported

- **Summary:** The 193 rows of "Feb 2026 FTTH Sheet_.pdf" are now FTTH Work Orders. They were loaded through ftth_tracker's FTTH Import (monthly-sheet reader), as import IMP-31666, mode "Fill empty fields only".
  - 193 created, 0 updated, 0 failed, and 179 connections made. All 193 are RFS Done.
  - Work completed dates run from 23-01-2026 to 10-03-2026.
  - Site status: 28 Clear Site and 4 Issue Site (with manager Shyam Morale), as in the sheet. The rest are blank.
  - No new IBD Teams or GIS Nodes were needed. The site now has 1,627 work orders.
- **Reason:** The user sent the PDF to import. None of its WO numbers were on the site.
- **How it was done:** The PDF was transcribed into an .xlsx with the sheet's headers, previewed (read only), imported, and then the temporary files were deleted. Corrections made while transcribing:
  - Row 120's WO prefix "AL-ANG" was changed to "BAL-ANG".
  - Row 129's communication date 02-01-2025 was changed to 02-01-2026.
  - Row 28's distance "480+700" was entered as 1180.
  - Vendor "Skyline tecnoligy" was mapped to the existing IBD Team "Skyline".
  - HO Date was left blank, because the sheet has day counts there, not dates. The "Warje" text in the Re-work column was ignored.
- **Files or modules affected:** No code changed. Only data on newsite.local changed (FTTH Work Order, plus the File and FTTH Import IMP-31666).
- **Testing (newsite.local):**
  - The preview showed 193 work orders, no missing WO ids and none already existing.
  - The import log showed 193 created and 0 failed. The counts by status and site status were checked by SQL.
  - `bench migrate` ran.
  - **Not checked:** the records in a browser.
- **Pending items:** 8 rows have no Unique ID in the sheet. 5 have short Unique IDs that look truncated (PUN1140, PUN1057, PUN1734, PUN1164, PUN2350); they were kept as written.

## 2026-10-28: 03Y node sites imported (76 Sites with their B location)

- **Summary:** The "03Y Node details" sheet is now 76 Site records under GIS Node 03Y, which had none before. Each has its B location (what it is fed from), so the Network Topology and KMZ Map pages draw the 03Y feeder tree.
  - 19 sites hang directly off the node: 17 have B location "03Y" and 2 have "03Y Middle Enclosure", which is not a site.
  - The other 57 are linked to the 03Y site that feeds them.
- **Reason:** The user asked to import "03Y Node details.pdf".
- **Files or modules affected:** `emp_tracking/patches/import_03y_sites.py` (new), `patches/sites_03y.json` (new, the sheet's rows), `patches.txt`. Same pattern as the Team 2 site import: re-running skips rows already present (same name, node and B location).
- **Testing (newsite.local):**
  - JSON checked: 76 rows, and every B location except "03Y" and "03Y Middle Enclosure" is a site in the list.
  - `bench migrate` ran: 76 Sites under 03Y.
  - `site_parents` from the Network Topology page gives 19 sites under the node and 57 linked, e.g. Siddhi Gold ← Siddhi Vijay.
  - **Not checked:** the pages in a browser.
- **Pending items:**
  - "Arihant Society" is in the sheet twice, once fed from 03Y and once from Jyoti Palace. Both are kept; please confirm whether they are two buildings.
  - No ETIPL code or vendor was in the sheet.
  - The ftth_tracker Node Site list still has its own 3 rows for 03Y (Mantri Estate B Block Shop, Poornima Park A Wing, Siddhi Gold), not linked to these Sites.

## 2026-10-28: "Master Data for Software" (36 Airtel FTTH work orders) imported; GIS Node save fixed in ftth_tracker

- **Summary:** The 36 rows of "Master Data for Software.pdf" are now FTTH Work Orders (WOs from Oct 2023 to Jul 2026, all with an RFS month). They were loaded through ftth_tracker's own FTTH Import (master-sheet reader), as import IMP-31555, mode "Fill empty fields only".
  - 34 work orders created, all RFS Done, with IBD Team, GIS, splicer / assistant splicer, fiber team, fiber ID and A/B readings, distances and Evisions Link ID.
  - 2 existing work orders were filled, not overwritten: FTTH-01657 Gloriana Villa Society (WO 135567) and FTTH-01734 Devyani Society (WO 135630). Their RFS dates (2026-04-02, 2026-04-17) and IBD Team (Team 6 / Team 3) were kept.
  - New masters (20): 6 IBD Teams (R.K. Technosmart, Nilam, Evisions Tele Infra, OM, L K Services, Giga), 2 Fiber Teams (Prakesh Rathod, Amrut Rathod), 12 Field Staff (5 splicers, 5 assistant splicers, area managers Sanket Khandare and Vilas Gaikwad).
- **Fix in ftth_tracker:** `ftth_tracker/ftth_tracker/doctype/gis_node/gis_node.py` `on_update` used `wo.field(field)`, which returns a pseudo-column, so any GIS Node save that changed its area or people failed with a TypeError. The first import attempt failed on it and was rolled back. Changed to `getattr(wo, field)`. The generated SQL was checked before re-running.
- **Reason:** The user asked to import the PDF. Nothing from this sheet was on the site: the 1,400 earlier work orders came from the April 2026 monthly sheet.
- **How it was done:** The PDF was transcribed into an .xlsx with the sheet's own headers, previewed (read only), then imported. Cell choices:
  - Red "0" placeholder cells (no fiber snap) were left empty in 11 rows: fiber ID, A reading and the red B reading.
  - RFS is a month only, so the RFS Date is the 1st of that month.
  - Two names were aligned with the existing records: "Akash Pardesi" → "Akash Pardeshi" (existing Field Staff) and "Aditsay Manjre" → "Aditya Manjare" (spelling in the NOC sheet).
  - The temp folder, the failed import IMP-31554 and its file were deleted afterwards.
- **Files or modules affected:** `ftth_tracker/.../gis_node/gis_node.py` (one line). Data only otherwise; no emp_tracking code changed.
- **Testing / results (newsite.local):** 0 failed rows. All 34 new work orders are RFS Done with a splicer and fiber team. Spot-checked WO 104922, 135567, 138996 and 89468 against the PDF. `bench migrate` ran. **Not checked:** the records and a GIS Node save in a browser.
- **Pending items (from the sheet itself):**
  - WO 138996 Vasundhara Building has no IBD Team: the sheet had the WO number in that cell.
  - 4 rows had the survey B end differ from the planning B end while "B end issue" says No. The survey value was put in New B End (WO 138791, 139768, 67803, 129708).
  - 12 work orders carry warnings, e.g. Distance Shared more than Final Distance (WO 138996, 139768, 89468, 97958, 73046, 87313, 84187), or the RFS month before the WO received date (sheet date errors, e.g. WO 89468, 111776, 129708).
  - "Prakesh Rathod" is kept as spelled in the sheet; rename the Fiber Team if it should be "Prakash".
  - No work order is linked to the Link Register (FTTH Link): those Link IDs are not in it yet.

## 2026-10-27: Team Monthly Cable doctype; Fiber Maintenance & Project data added (Apr–Aug 2026)

- **Summary:** New doctype **Team Monthly Cable**: one record = one Maintenance Team's total cable (m) for one month and one work type (Maintenance / Project).
  - Named "TEAM 2 - Maintenance - Apr 2026"; the month is saved as its 1st day, so a team, work type and month can be entered only once.
  - The 50 figures of "Fiber Maintenance & Project Data - April 2026-2027.pdf" were added: TEAM 1–5, Apr–Aug 2026, Maintenance and Project.
  - "Team 1/6" in the sheet (Team 1 and Team 6 reported together) is saved under TEAM 1. "Team in Sheet" keeps "Team 1/6" and the remarks say so.
- **Reason:** The user asked to add this sheet's data; there was no place for cable per team per month.
- **Files or modules affected:** `doctype/team_monthly_cable/` (new: `team_monthly_cable.json`, `team_monthly_cable.py`, `__init__.py`).
- **Testing / results (newsite.local):** `bench migrate` ran. 50 records inserted. Per-team sums match the sheet's Grand Total row: Maintenance 117,759 / 35,589 / 34,003 / 26,079 / 44,948 = 258,378 m; Project 17,903 / 17,000 / 8,991 / 5,640 / 23,623 = 73,157 m. **Not checked:** the form and list in a browser.
- **Pending items:**
  - The year is assumed 2026 from the title "April 2026-2027"; the sheet has no year per row.
  - Team 1 and Team 6 cannot be split from the sheet.
  - Not yet shown on any dashboard or chart.
- **Follow-up (2026-10-27): entries added one by one, and a summary report.** The user said the sheet is only past data and teams will add entries one by one, so entry must be easy.
  - **Changed:** one record = one entry with a **Date** (default today), so a team can have many entries in a month. Month is set from the date on save. Names are `CBL-YYMM-#####`. The unique team / month / work type rule is gone; the same team, date, work type and metres only shows a warning against double entry.
  - **Added:** quick entry (`+ Add` popup) and Site / Link / Location. The list has **Add for All Teams** (one date, a grid of every active Maintenance Team; rows left at 0 are skipped; `add_entries`) and **Summary by Month**.
  - **New Script Report "Team Cable Summary":** months × teams with a Total column, a total row and a stacked chart, like the PDF pivot. Filters: Project / Maintenance (blank = both), Team, From, To.
  - **Past data:** the 50 records were deleted and re-added as dated the 1st of the month, ticked **Monthly Total from Sheet**; "Team in Sheet" is kept.
  - **Files:** `doctype/team_monthly_cable/team_monthly_cable.json`, `.py` (`add_entries`, `warn_if_repeated`), `team_monthly_cable_list.js` (new); `report/team_cable_summary/` (new: `.json`, `.py`, `.js`, `__init__.py`).
  - **Testing (newsite.local):** `bench migrate`, `clear-cache`, `node --check` on both JS files. The report gives the sheet's numbers exactly for Maintenance (258,378 m), Project (73,157 m) and both (331,535 m). `add_entries` with TEAM 2 = 120, TEAM 3 = 0, TEAM 4 = 80 made 2 entries (Month 2026-10-01). Repeating TEAM 2 = 120 saved with the orange warning; all teams 0 → "Enter the metres for at least one team". The test entries were rolled back; 50 records remain. **Not checked:** the popup, the grid dialog and the report in a browser.
  - **Pending:** no workspace shortcut was added (the WorkForce workspace is managed on the site); it can be pinned from the UI.
- **Follow-up (2026-10-27): Apr 2025 – Mar 2026 data imported.** From "Fiber Maintenance & Project Data - From Apr - 25 To Mar - 26.pdf", Maintenance and Project, TEAM 1 ("Team 1/6") to TEAM 5. Apr–Dec are saved as 2025 and Jan–Mar as 2026.
  - 119 records, ticked Monthly Total from Sheet. Project Nov 2025 for Team 4 is blank in the sheet, so no record was made. Same one-off script on the server as before; no code changed.
  - **Testing (newsite.local):** before saving, every sheet row and column was checked against its Grand Total. Team Cable Summary for 2025-04-01 to 2026-03-31 gives Maintenance 504,695 m (176,409 / 63,868 / 95,176 / 79,001 / 90,241) and Project 205,263 m (69,246 / 48,187 / 17,505 / 33,010 / 37,315), as in the sheet. 169 records in total.
  - This file's title runs Apr-25 to Mar-26, which supports reading the earlier "April 2026-2027" file as 2026 (no overlap).

## 2026-10-27: NOC Master Data sheet imported into Complaint Information (28,655 complaints)

- **Summary:** Every row of "NOC MASTER DATA APRIL 2025 TO SEPT 2026 SHEET.xlsx" (sheet MAIN DATA, received 2025-04-01 to 2026-10-01) is now a Complaint Information. All rows are in the Closed state.
  - Linked to Employee, Maintenance Team / Vendor and Area. Received / assigned / restored / company-closed times, link status, RFO, RFO type and NOC executives are copied from the sheet.
  - MTTR, SLA and aging are worked out by the doctype's own `set_times_and_sla()`.
  - New read-only fields **NOC Sheet No.** (the sheet's unique NO; the import key, so a re-run adds nothing twice) and **Complaint Code**.
  - Area is read from the link name (place words). 56 Areas were created for places not in the Area list (Baner, Chakan, Narhe, Undri, Ravet…). Their `area_code` is `NOC-<NAME>`, not a PIN code.
  - Spelling variants are mapped: people (e.g. Deepak Lad → HR-EMP-00054 "Deepak") and vendors. Values that could not be matched are written into Assignment Remarks ("Not matched from NOC sheet: …").
  - Also: the Employee Performance page now sends the Designation the dropdown shows if the control has no value. The user saw 17 people (Supervisors included) while "Splicer" was shown.
- **Reason:** The user asked to add the complaints (PDF of the June 2026 rows of NOC executive Rushikesh) so the Employee Performance page shows each splicer's calls per area with their times. The user then chose to import the whole sheet and to create the missing Areas.
- **Files or modules affected:** `emp_tracking/noc_complaint_import.py` (new: `preview`, `run`), `doctype/complaint_information/complaint_information.json` (fields `noc_sheet_no`, `complaint_code`), `page/employee_performance/employee_performance.js` (designation fallback).
- **How it was run (newsite.local):** `bench migrate`; `preview` (nothing saved); a trial `run` with `limit` 20, checked row by row; the full `run`; then a re-run.
  - First full run: 87 rows failed (RFO check inside `set_times_and_sla()` for rows without RFO Type; 6 rows with no SR RECEIVED date).
  - Fixed: times are worked out as "Resolved", and the Assigned Call time is used when SR RECEIVED is empty (noted in the remarks).
  - Re-run: 87 inserted, 28,568 skipped, 0 failed.
- **Testing / results:**
  - 28,655 imported, all Closed; 17,839 have an Area and 11,611 a Splicer.
  - Sheet NO 18580 matches the PDF: Sanket Kotkar / Hemant Chaudhari, TEAM 2, Ambegaon, 08-06-2026 16:18 → 18:00, MTTR 6,120 s, SLA In.
  - `get_calls_dashboard(Splicer)`: 12 people, 0.4 s. Deepak Lad's profile lists 645 complaints. The Area filter (Baner) works.
  - `node --check` and a Python parse passed. `clear-cache` ran. The server's /tmp copy of the sheet was deleted afterwards.
  - **Not checked:** the page in a browser, and why the Designation control was empty in the user's browser (only worked around).
- **Pending items:**
  - 10,816 complaints have no Area: the link name has no known place (e.g. "Section: … tapping HH"). More places can be added to `PLACES` and the import re-run only for the area, or Areas set by hand.
  - The 56 new Areas need their real PIN codes and Area Managers.
  - People not in Employee stay as names in the remarks (e.g. Ganesh Pangaonkar, Vithal Bhagat, Rohan Yadav, Ganesh Gonte, Digamber Waghmode, Sanjay Kolap, Ashish Birajdar); creating them as Employees and re-linking would add their calls.
  - Rows marked "OTHER" in the sheet have no splicer.
  - Complaint names use the import month (CMP-2610-…), not the month received.
  - Received Via is empty (not in the sheet).
- **Follow-up (2026-10-27): complaint charts in the person profile.** Above the Complaint Calls table, four charts are drawn from the same rows:
  - Calls by Month (In SLA / Out of SLA / not restored, stacked)
  - Average Time by Month (hours to assign, hours to restore)
  - How Long Restores Took (< 1h … > 24h)
  - Top Causes (RFO Type, top 8)
  - **Files:** `employee_performance.py` (sends `rfo_type`) and `employee_performance.js` (`complaint_visuals_html`, `complaint_charts`).
  - **Testing:** `node --check` passed. For Sanket Kotkar the server returns 1,242 calls: 709 In / 528 Out / 5 without SLA; top cause PMC TREE CUTTING ACTIVITY (173). `clear-cache` ran. **Not checked:** the charts in a browser.

## 2026-10-27: KMZ Map: Assign Nodes (nearest node by distance)

- **Summary:** "Assign Nodes" button on the KMZ Map (users who may edit KMZ Routes). A KMZ Route / Point with no GIS Node gets the node of the closest route vertex or pin that was matched by Node Name or Building Name, within a chosen distance (default 200 m, max 1000 m). A row whose next-closest other node is about as close (≤ 1.5 × distance + 30 m) is "Unsure" and only assigned when "Also assign unsure rows" is ticked. The dialog previews first (totals, top nodes, first 300 rows, unsure first, with links), then "Assign N" (worked out again on the server). Assigned rows get Matched By "Nearest Node" (new option on both doctypes, also in the map's Matched By filter); "Undo All" takes the node off every such row. Rows that are already matched are never changed.
- **Reason:** 6,155 of 10,650 routes and 16,992 of 27,898 pins had no GIS Node (KMZ folder not a GIS code, building not a Site), so most of the map showed as no-node routes.
- **Files or modules affected:** `page/kmz_map/kmz_map.py` (`nearest_node_plan`, `preview_nearest`, `apply_nearest`, `undo_nearest`), `page/kmz_map/kmz_map.js` (button, `assign_nodes` dialog), `page/workforce_dashboard/setup.py` ("Nearest Node" option).
- **Testing:** `node --check kmz_map.js` ok. On newsite.local: `bench migrate`, clear-cache; options show "Nearest Node". Preview timings on all rows: 100 m 6 s, 300 m 9 s, 500 m 12 s, 1000 m 31 s (first version took over 2 min, so reference points are now merged per 25 m and searched in a grid). Preview at 100 m: 17,550 found, 11,759 sure, 5,791 unsure. Rolled-back test: apply at 100 m assigned exactly the 11,759 sure rows (no-node routes 6,155 → 3,248, pins 16,992 → 8,140); Undo All restored 6,155 / 16,992; Guest refused; nothing left after rollback. **Not run:** the dialog in a browser; **no assignment has been saved** on the site (left for the user to run after reviewing the preview).
- **Pending items:** the user should review the preview and run Assign; "nearest" is a guess by distance, so unsure rows and routes between two nodes need a person's check.

## 2026-10-27: KMZ Map: Add Route (draw one route on the map)

- **Summary:** "Add Route" button on the KMZ Map (shown to users who may create KMZ Routes: System Manager, FTTH Manager). Click points on the map to draw the line; a click on a pin puts the point exactly on it. A toolbar shows points / length with Undo, Finish, Cancel; popups stay shut while drawing. Finish opens a dialog: Route Name (pre-filled "First pin to Last pin" when both ends were pins), GIS Node (current filter, else the pins' node), Site. Saved as a KMZ Route with Source File / KMZ Path "Drawn on KMZ Map", Matched By "Drawn on Map" (new option, also in the map's Matched By filter), A / B end split from the name, length computed, and the same dedupe key as KMZ Upload (so uploading the same line later does not duplicate it). The map refreshes without moving.
- **Reason:** user asked how to add just one route without making a KMZ file.
- **Files or modules affected:** `page/kmz_map/kmz_map.py` (`add_route`), `page/kmz_map/kmz_map.js` (button, drawing mode, dialog; `refresh(fit)`), `page/workforce_dashboard/setup.py` (KMZ Route `custom_kmz_matched_by` option "Drawn on Map").
- **Testing:** `node --check kmz_map.js` ok. On newsite.local: `bench migrate` (Matched By options now include "Drawn on Map") and clear-cache. Rolled-back test through `bench execute`: a 3-point route saved (230.6 m, node, A / B ends, Matched By, GeoJSON correct); the same route again, one point only and an empty name were refused; Guest was refused (PermissionError); nothing left after rollback. **Not run:** not tried in a browser (drawing, snapping to pins, dialog).
- **Pending items:** a drawn route can only be changed by deleting it (KMZ Route form) and drawing again; no editing of the line's shape.
- **Follow-up (2026-10-27): no-node routes dashed.** In central Pune 430 of 593 routes have no GIS Node, and node colours purple #9333ea / #7c3aed and pink #db2777 looked like the no-node fuchsia, so it was unclear which routes had a node. Routes with no GIS Node are now dashed (Index shows a dashed line), and the node palette no longer has purple, pink or red (red is for open complaints): replaced with brown, navy, slate, olive. Node colours therefore change. `kmz_map.js` only; `node --check` ok; not checked in a browser.

## 2026-10-27: KMZ Map Settings: pin types and map colours editable

- **Summary:** New single doctype **KMZ Map Settings** (Network menu → KMZ Map Settings; "Map Settings" button on the KMZ Map).
  - **Pin Types** table (child doctype **KMZ Pin Type**): Pin Type name, Match ("Name has word" / "Short code (e.g. 1PZ21)" / "Everything else"), Words in Pin Name (comma separated; `encl*` matches any ending), Colour (colour picker), Show (untick to hide that type when the map opens; it can still be switched on from the map's Index). Rows can be added, removed and reordered; the first matching row wins.
  - **Other Colours:** Down (open complaint), Affected, No GIS Node.
  - Validation: colours must be `#rrggbb`; "Name has word" rows need words; only one "Everything else", always moved to the end on save.
  - The KMZ Map reads the settings with its filter options; built-in defaults apply when nothing is saved.
- **Reason:** user asked for settings to choose the colours (after asking whether trees need to be shown).
- **Files or modules affected:** `emp_tracking/emp_tracking/doctype/kmz_map_settings/` (new), `doctype/kmz_pin_type/` (new), `patches/kmz_map_settings_defaults.py` (new; fills the current types / colours only into an empty table or empty colours) and `patches.txt`, `page/kmz_map/kmz_map.py` (`settings` in `get_filter_options`), `page/kmz_map/kmz_map.js` (`km_apply_settings`; complaint red via a CSS variable), `page/workforce_dashboard/setup.py` (menu entry).
- **Testing:** On newsite.local, `bench migrate` ran and the patch seeded the 7 current types with all colours. Through `bench execute`: settings returned correctly; in a rolled-back save, "Everything else" placed first was moved to the end, and colour "red" was refused. Locally in Node: the seeded rows classify real pin names the same as before ("Kiran Shubham Enclouser" → Encloser / JC, "Treeline Apts" → Building), Show unticked → that type starts hidden, a changed Down colour is used. **Not run:** not opened in a browser.
- **Pending items:** none known (the all-shown default was changed in the follow-up below).
- **Follow-up (2026-10-27): no-node routes no longer grey.** Routes / pins with no GIS Node were grey (#6b7280) and hard to see; the default "No GIS Node" colour is now fuchsia #c026d3 (settings JSON, `OTHER_COLOURS`, page fallback). The saved setting on newsite.local was changed from #6b7280 to #c026d3 (only because it was still the old grey); migrate re-run and cache cleared. Not checked in a browser.
- **Follow-up (2026-10-27): fewer pin types shown by default.** ODF, Encloser / JC, Pole / Light, Tree and Chamber / HH are now hidden when the map opens; only Code point and Building show. Hidden types are shown by clicking them in the map's Index, or permanently by ticking Show in KMZ Map Settings. Files: `kmz_map_settings.py` (`DEFAULT_PIN_TYPES` gets `show`), `patches/kmz_map_settings_defaults.py` (seeds Show from it). On newsite.local the saved rows were updated (verified: 5 hidden, Code point / Building shown); Python parse ok on the server. Not checked in a browser.

## 2026-10-27: KMZ Map: pins coloured by type

- **Summary:** KMZ pins are now coloured by what they are instead of their node's colour, with a white outline so they stand out from the lines: ODF (teal), Encloser / JC / Tapping (yellow), Pole / Light (grey), Tree (green), Chamber / HH (blue), code points such as "1PZ21" (pink), buildings (violet). The type is read from the pin name, because the KMZ has no type field. The legend lists each type with its count; clicking a type hides or shows those pins. Node pins keep their node colour; red / orange for open complaints still take priority.
- **Reason:** user asked for points in different colours (they blended into the lines of the same node).
- **Files or modules affected:** `emp_tracking/emp_tracking/page/kmz_map/kmz_map.js`.
- **Testing:** `node --check` passed; the type rule was run locally in Node on real pin names (e.g. "Anand Residency ODF" → ODF, "Tapping jc (Pavni PG)" → Encloser / JC, "G7M03" → code point, "Mauli Building" → building). Server cache cleared. **Not run:** not opened in a browser.
- **Pending items:** names that don't say what they are fall under Building.
- **Follow-up (2026-10-27): Index on the map.** The legend below the map is replaced by a collapsible **Index** box in the map's bottom-right corner. It explains pins by type (with counts; click to hide / show), route lines (coloured by GIS Node; grey = no node), the node pin, and, while "Show open complaints" is ticked, the complaint marker, the red-ringed node, and the red (down) and orange (affected) lines. Clicks and scrolling inside the box don't move the map. Tested with `node --check` only; not opened in a browser.

## 2026-10-27: KMZ Site Check page: check Site names against KMZ names on screen

- **Summary:** New Desk page **KMZ Site Check** (`/app/kmz-site-check`; EVision menu → Network → KMZ Site Check; it has a button to open the KMZ Map).
  - Each Site that needs checking, with its status (Exact / Close match / No match), how many KMZ lines and pins are linked to it, and the 3 closest KMZ pin names on the same node (similarity %, pins, and the Site a name is already linked to).
  - **Link:** links the chosen KMZ name's free pins (and routes whose name / A end / B end is that name) to the Site, with Matched By = Building Name.
  - **Rename & Link:** also corrects the Site name. The suggested name is the KMZ spelling without ODF / Encloser / JC and can be edited; the old name is kept in a comment on the Site.
  - Nothing changes until a button is pressed. KMZ names are never changed (KMZ Upload finds rows again by name, so renamed pins would come back as duplicates).
  - A KMZ name whose pins are all linked to another Site shows "already used" with no buttons, and the server refuses it. This prevents renaming a Site after another wing's pins.
- **Reason:** the user asked to correct building-name spelling mistakes between Sites and the KMZ, and to see them on screen for checking first.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/kmz_site_check/` (new: `__init__.py`, `kmz_site_check.json`, `.py`, `.js`); `page/workforce_dashboard/setup.py` (menu entry).
- **Testing:** On newsite.local: `bench migrate` ran (page registered). Through `bench execute` as Administrator: 115 Sites listed under "Needs Check" (592 exact, 40 close, 64 no match, 79 not linked), 102 of them with a free KMZ name to link. Apply was tested inside a rolled-back transaction: Vithal Angan linked 1 pin and was renamed, then restored by rollback. Abhirochi Parisar → "Abhiruchi Parisar D Wing Encloser" was refused because those pins belong to Site "Abhiruchi Parisar D Wing". **No data was changed.** `node --check` and a Python parse passed. **Not run:** page not opened in a browser; not tested as a non-admin user.
- **Pending items:** the team still has to go through the list and press Link / Rename & Link for each real same-building pair.

## 2026-10-27: KMZ Map: open complaints on the map; GIS Node and Area filters linked

- **Summary:**
  - **Open complaints on the map** ("Show open complaints" tick box, on by default), using the same rules as the Network Topology live view:
    - KMZ lines and pins of a site with an open complaint are drawn thick red; those of the sites fed through it (ETIPL code tree) orange. Hovering says Down / Affected.
    - The node's own pin gets a red ring and a "⚠ V0N · 2 open" label; the node list shows a red count.
    - A pulsing red "!" marker sits at each complaint (its latitude / longitude, else a KMZ pin of its site, else the node pin), with a popup linking to the complaint and site.
    - New "Open Complaints" KPI tile (only the chosen node's when a GIS Node is selected), a legend, and an "Open Complaints" layer in the layer switcher.
  - **Linked filters:** picking a GIS Node limits Area to that node's area; picking an Area limits GIS Node to the nodes in it. A value the other filter no longer allows is cleared.
- **Reason:** user asked to show nodes that stopped working through complaints in red on the map, as on the topology page, and for Area to show only the selected node's area.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/kmz_map/kmz_map.py` (`fault_overlay`, Site on route / pin rows, `node_area` in `get_filter_options`); `kmz_map.js`.
- **Testing:** On newsite.local through `bench execute` as Administrator:
  - `get_map_data(gis="V0N")`: 2 down sites (SITE-01708, SITE-01774), 16 affected sites; 21 of 222 V0N routes and 30 of 622 pins drawn red / orange; 6 open complaints, 4 with coordinates; V0N shows 2 open.
  - `get_filter_options`: every node has an area (V0N → Narhe).
  - `node --check` on the JS and a Python parse passed locally.
  - **Not run:** the page was not opened in a browser, and not tested as a non-admin user.
- **Pending items:**
  - Only about 9% of KMZ routes / pins are linked to a Site, so for other sites only the complaint marker and node ring show.
  - 2 open complaints have no site, node or coordinates, so they cannot be placed on the map.
  - The GIS Node Area values have many spelling variants (e.g. Bibewadi / Bibwewadi, Viman Nagar / Viman nagar); cleaning them would shorten the Area list.

## 2026-10-27: Leaderboard Settings: Maintenance Calls weights stored (form showed 0.000)

- **Summary:** The six Maintenance Calls weights in Leaderboard Settings are now saved values. Splicer / Rider: Per Call 1, Per Call as Assistant 0.5, In SLA +0.25, Out of SLA −0.25. Supervisor: In SLA +0.5, Out of SLA −0.5.
- **Reason:**
  - **What the user asked:** set the splicer formula from the FY 2025-26 sheet (Splicer calls × 1, Assistant calls × 0.5, In SLA × 0.25, Out of SLA × −0.25).
  - **What I found:** the scoring already used this formula through the `CALL_POINTS` defaults, but the fields had never been saved, so the form showed 0.000. Saving that form would have stored zeros and wiped every call score.
- **Files or modules affected:** `emp_tracking/patches/leaderboard_call_defaults.py` (new; writes only fields that are still empty, safe to re-run); `emp_tracking/patches.txt`.
- **Testing:** On newsite.local, I ran the patch through `bench execute`.
  - The stored values and the loaded form both show 1 / 0.5 / 0.25 / 0.25 / 0.5 / 0.5.
  - **FY 2025-26 splicer totals** from the stored Staff Monthly Performance months: Arun Charhate 618.75 and Shamburaj Khilare 435, the same as the formula on the user's table.
  - **Where totals differ, the cause is the source data**, not the formula:
    - Some stored In / Out SLA counts differ from the pasted table. For example, Sanket Kotkar's Out SLA is 277 stored against 290, and Rohan Tupe's is 387 against 427.
    - The pasted Total Score column does not follow its own formula on several rows. For example, Akshay Chavan's sheet total is 588.5, but the formula on the same row gives 538.5.
  - **Not run:** `bench migrate` has not been run yet; it will mark the patch as done without changing the stored values. The form was not opened in a browser.
- **Pending items:**
  - The differing SLA counts and sheet totals need checking against the original monthly sheets.
  - Dilip Pawar and Mahesh Khedekar (marked * on the sheet) have no FY 2025-26 months stored.

## 2026-10-27: Network Topology dashboard: feeder tree per node and failure impact

- **Summary:** A new Desk page, **Network Topology** (`/app/network-topology`; EVision menu → Network → Network Topology; also the "Topology" button on each GIS Node form).
  - **All Nodes view:** one card per node with sites, levels, open faults, upstream / fed nodes, and the "most critical" site (the one whose failure cuts off the most others).
  - **One node view:** the feeder tree drawn left to right. The node comes first, then each site under the site that feeds it, built from the Site ETIPL codes the same way as the Site Diagram.
    - A site whose feeder code has no Site hangs under the nearest code above it.
    - A site without a code hangs under its B Location.
  - **What-if simulation** (nothing is saved):
    - Click a site box to mark it as stopped; every site fed through it turns orange, and the Impact panel counts and lists them.
    - **Node Down** stops the whole node, plus the nodes fed from it.
    - **Open faults as down** marks sites with an open complaint (workflow state not Closed / Resolved / Fiber Restored / Rejected) as stopped.
  - **Side panels:** Most Critical Points (top 10, click to simulate), Open Faults and Upstream.
  - **Tree tools:** Find site, zoom, collapse / expand.
  - **Hand tool (follow-up, same day):** press and drag the tree to move it in any direction; the scrollbars are hidden.
    - A drag is not counted as a click on a box.
    - The tree now keeps its position when a click redraws it; before, it jumped back to the top-left.
    - Tested only with `node --check` and the stubbed Node run; not tried in a browser.
  - **Live faults on by default (follow-up, same day):** "Show open complaints as down" is now ticked when a node opens and after Reset. A site with an open complaint is a red box and its branch is orange without any click; untick it for a clean what-if view.
    - Tested on the live V0N data with the stubbed Node run. Open complaint CMP-2610-02728 on V0N.1.1.2.1 (Audumbar Complex A Wing) drew 1 red box and 2 orange boxes (V0N.1.1.2.1.1 Aryan Complex and V0N.1.1.2.1.2 DK Heights Audumber Complex).
    - Not tried in a browser.
  - **New field: "Fed From Node"** (`custom_fed_from`, Link GIS Node) on GIS Node records which node feeds this one, so a node failure also reaches the nodes downstream of it.
- **Reason:** The user asked for a new sidebar item showing each node's topology and what is affected when one part stops working.
- **Files or modules affected:**
  - New: `emp_tracking/emp_tracking/page/network_topology/` (`.json`, `.py`, `.js`).
  - Changed: `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (field, menu link); `emp_tracking/public/js/gis_node.js` (Topology button).
- **Testing:**
  - **Server (newsite.local):** I ran `bench migrate`, which created the page and the field. The menu link is in the EVision, Helpdesk NOC and FTTH Tracker sidebars.
    - The overview returned 22 nodes.
    - V0N: 122 sites, 6 levels, 13 first-level sites. Its most critical point is V0N.9, which feeds 57 sites. Every parent is a site of the same node, and all 122 sites are placed in the tree.
    - D1J: 95 sites, 7 levels. Its most critical point is D1J.1, which feeds 39 sites.
    - Fed-from chain test (D1J ← V0N, 1VD ← D1J, rolled back): V0N fed 2 nodes (188 more sites).
  - **This PC:** I ran the page's JS in Node with Frappe stubbed, on the real V0N data.
    - Stopping V0N.9 marked exactly 57 sites as affected, matching the server, and drew 123 boxes and 58 cut lines.
    - Node Down affected all 122 sites.
    - Collapse left 14 boxes, and the search highlighted 2 sites.
    - `node --check` passed and the Python files parse.
  - **Not checked:** the page in a real browser (look, clicks, zoom), the GIS Node button, and a login as a non-admin user.
- **Pending items:**
  - **No node-to-node data yet:** "Fed From Node" is empty on every node, so Node Down only covers the node's own sites until it is filled in.
  - **Open faults:** the 4 open complaints on the site have no site or node, so no fault shows on any tree yet.
  - **What the topology covers:** it shows feeder relations between sites. It does not trace KMZ routes or individual fiber cores.

## 2026-10-27: KMZ Map dashboard, with the full KMZ path and filters

- **Summary:** A new Desk page, **KMZ Map** (`/app/kmz-map`; EVision menu → Network → KMZ Map; also the "KMZ Map" button on each GIS Node form). Work started 2026-10-26 and finished 2026-10-27.
  - **On the map:** every KMZ Route as a line and every KMZ Point as a pin, coloured by GIS Node. A node's own pin ("C1U Node") is larger and labelled, and rows with no node are grey.
  - **Map controls:** Street / Satellite tiles (Frappe's own Leaflet and tiles), and Routes / Pins layers that can be switched off.
  - **Filters:** GIS Node, Area, KMZ File, KMZ Path contains (e.g. "C1U" or "Icon Residency"), Matched By (including Not Matched), Site, and Routes / Pins / both.
  - **KPI tiles:** routes, route km, pins, GIS Nodes, and rows with no node.
  - **Node list:** shows each node's counts; clicking a node filters the map to it, and clicking "No Node" shows the unmatched rows.
  - **Popup:** clicking a line or pin loads its node, site, length / coordinates, KMZ file, full KMZ path and how it was matched, with a link to the record.
  - **Drawing limits:** up to 4,000 routes and 8,000 pins are drawn at once, and the page says when a filter is needed to see the rest.
  - **New field: KMZ Path** (`custom_kmz_path`) on KMZ Route / KMZ Point holds the full folder chain inside the KMZ (e.g. "My Places / C1U / Kaypee Granduer to VIVANTA PRIMERA SOCIETY Encloser"). KMZ Upload now fills it.
  - **Backfill:** patch `backfill_kmz_path` filled it for the rows of the 8 uploads already made, without changing anything else.
- **Reason:** The user asked for one dashboard to view the KMZ, with its whole path, on a map with filters.
- **Files or modules affected:**
  - New: `emp_tracking/emp_tracking/page/kmz_map/` (`.json`, `.py`, `.js`) and `emp_tracking/patches/backfill_kmz_path.py`.
  - Changed: `emp_tracking/patches.txt`; `emp_tracking/emp_tracking/doctype/kmz_upload/kmz_upload.py` (fills KMZ Path, shared `row_key()`); `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (field, menu link); `emp_tracking/public/js/gis_node.js` (KMZ Map button).
  - Nothing in FTTH Tracker was changed.
- **Testing:** On newsite.local:
  - **Data on the site:** 8 KMZ Uploads already existed (Part 01 to Part 08, run from the form on 2026-10-26), with 10,650 routes and 27,898 pins.
  - **Backup and migrate:** I took a backup (`20261027_092704`), then ran `bench migrate`. The backfill filled 38,548 rows, leaving 0 without a path, and the uploads' counts stayed the same.
  - **Rolled-back rerun:** a rerun of Part 08 inside a rolled-back transaction created 0 rows.
  - **API checks:**
    - No filter: 10,650 routes, 6,654 km, 27,898 pins and 351 nodes; 4,000 lines and 7,999 pins drawn (limit reached), a 2.7 MB response in 1.3 s.
    - C1U: 21 routes and 94 pins (27 KB). "Icon Residency" path: 1 route and 2 pins. Part 03: 1,394 routes and 3,920 pins. Area and Not Matched filters also returned data.
    - The popup method returned the full path, and it refuses non-KMZ doctypes.
  - **Page:** the page loads with its script and 4 roles, and the menu link is in 3 sidebars. The JS passed `node --check` and the Python files parse.
  - **Not checked:** the page in a browser (map drawing, tiles, popups, filters), the GIS Node button, and a login as a non-admin user.
- **Pending items:**
  - **Unfiltered view:** it is capped and about 2.7 MB; a filter is needed to see every row.
  - **Unmatched rows:** 23,147 rows (60%) have no node, so the unfiltered map is mostly grey.
  - **Map tiles** come from the internet (OpenStreetMap / Esri), as in Frappe's own map view.

## 2026-10-26: KMZ Upload: one KMZ, matched to GIS Nodes by node name and building name

- **Summary:** A new doctype, **KMZ Upload** (EVision menu → Network → Upload KMZ). You attach a whole KMZ / KML and click **Match & Import**. A background job turns every route and pin into FTTH Tracker's KMZ Route / KMZ Point and files each one under a GIS Node. First match wins:
  - **Node name:** the pin is named with a GIS code (B1V, B1V05), the nearest folder above it is, or a route ends at the node ("Delight Pride to R0C Node").
  - **Building name:** the pin name, or either end of a route "A to B", equals a Site / Node Site name or a Site's B Location. Words like ODF, Encloser, JC, Node and B end are ignored, and a name that starts with the other (8+ letters) also counts. A name found under two nodes is not used.
  - **Same folder:** the rest of a building folder takes the node its matched pins got.
  - **Row details:** custom fields on KMZ Route / KMZ Point record how each row was matched (Matched By), the Site it was matched to, and the KMZ Upload it came from.
  - **Unmatched rows** are still imported without a node, and the form lists them. The log lists folders named like a GIS code that have no GIS Node.
  - **No duplicates:** the dedupe keys are FTTH Import's, so a file loaded through both never makes duplicates. Re-running only fills a missing node. Polygons are skipped.
  - **On the GIS Node form**, the rows appear in that node's "Imported KMZ Files" table.
- **Reason:** The user asked for one option to add a whole KMZ, matched to nodes by building name and node name.
- **Files or modules affected:** `emp_tracking/emp_tracking/doctype/kmz_upload/` (new: `.json`, `.py`, `.js`); `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (KMZ Route / KMZ Point Custom Fields, menu link). Nothing in FTTH Tracker was changed.
- **Testing:** On newsite.local:
  - **Backup and migrate:** I took a backup (`20261026_150447`), then ran `bench migrate`, which created the doctype and the fields. The "Upload KMZ" link is in the EVision, Helpdesk NOC and FTTH Tracker sidebars.
  - **Full import test:** I ran a full import of `KMZ_Till_16.09.2026_Part_08.kmz` inside one transaction, then rolled it back. Afterwards there were 0 KMZ rows and 0 KMZ Uploads.
    - The file has 4,113 placemarks; 325 polygons were skipped, leaving 3,541 unique rows: 837 routes and 2,704 points.
    - Matched rows: 876 by node name, 257 by building name, and 130 by same folder. These cover 96 GIS Nodes and 65 Sites.
    - 2,278 rows were not matched. Most are folders with no node: the Pathare Vasti Lohgaon survey, the PUNE_MAH_PUN2121 FAT plan, and cameras / switches. The log reports 04F as a code-like folder with no GIS Node.
    - B1V's "Imported KMZ Files" table showed its rows.
  - **Re-run:** it created 0 rows and reported 3,541 as already imported.
  - **Validation:** a non-KMZ attachment was blocked.
  - **Not checked:** the form and button in a browser, the job through the real queue (the test called it directly), and a login as a non-admin user.
- **Pending items:**
  - **The real import has not been run;** the user starts it from the form.
  - **Folders with no node** (survey and planning data) stay unmatched. Matching by distance to the nearest node pin is not done.
  - **Short names:** building names shorter than 4 letters are not matched.

## 2026-10-26: GIS Node: "KMZ Files" section

- **Summary:** Each GIS Node form has a new collapsible "KMZ Files" section, placed above the Site Diagram. It has three parts:
  - **KMZ File:** an Attach field for uploading the node's .kmz / .kml file.
  - **KMZ Folder Path:** a text field for where the node's KMZ is kept on the shared drive.
  - **Imported KMZ Files:** a table of the KMZ source files that FTTH Tracker imported for this node. It shows the folder inside the KMZ and the route and point counts, and each count links to the filtered KMZ Route / KMZ Point list.
- **Reason:** The user asked to see the KMZ file path under each node.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (GIS Node Custom Fields; the Site Diagram section now comes after the KMZ section); `emp_tracking/overrides/gis_node.py` (new `get_kmz_files`); `emp_tracking/public/js/gis_node.js` (`render_kmz_files`). Nothing in FTTH Tracker was changed.
- **Testing:** On newsite.local:
  - **Fields:** I ran `setup.after_migrate()`, which created the fields. The columns `custom_kmz_file` and `custom_kmz_path` exist, and the field order is KMZ section, then Site Diagram.
  - **API:** `get_kmz_files("03W")` returns `[]`, because the site has no KMZ Route / KMZ Point rows yet.
  - **Grouping:** with two temporary KMZ Points inserted and then rolled back, it returned one row with 2 points.
  - **Static checks:** the JS passed `node --check` and the Python files parse.
  - **Not checked:** the form in a browser, uploading a file, and a login as a non-admin user.
- **Pending items:**
  - The imported list stays empty until KMZ files are imported through FTTH Import on this site.
  - KMZ Folder Path is free text; it is not checked against the drive.

## 2026-10-26: Fiber Store: cable drum inward / outward register with a dashboard

- **Summary:** The store's fiber register ("Fiber Maintenance Project Data April 2026-2027": Outward Details, Inward Details and the Team Wise Fiber summary) now lives in ERPNext's own stock features, with no new doctypes.
  - **Items and drums:** each fiber type (6F / 12F / 24F / 48F / 96F) is an Item in metres, and each drum is a Batch named "<type>-<Cable ID>". Accessories are plain Items: closure, sleeve, rope, power meter, cleaver and IPA.
  - **Inward** is a Material Receipt into a new "Fiber Store" warehouse, with the party as a standard Supplier.
  - **Outward** is a Material Issue. Custom Fields on Stock Entry hold the job: Link ID, Project / Maintenance, A / B end, area, team, client, issued to, own / vendor and vendor bill. Stock Entry Detail holds the start / end meter readings.
  - **Validation:** a `validate` hook blocks an End Reading above the Start Reading and fills the entry's total fiber metres.
  - **Dashboard:** a standard Frappe Dashboard, "Fiber Store", with 4 Number Cards and 9 Dashboard Charts: metres issued per month (total, maintenance, project), received per month, by team, project vs maintenance, by client, by person / vendor and top areas. Drum balances use the standard "Batch-Wise Balance History" and "Stock Balance" reports.
  - **Menu:** a new "Fiber Store" section in the EVision menu.
  - **Stock Settings:** "Activate Serial / Batch No for Item" and "Use Serial / Batch fields" were switched on.
  - **Import:** the PDF's rows were read with pdfplumber into `patches/fiber_register_2026_27.json` and loaded by a patch.
- **Reason:** The user asked for a visual of the inward / outward fiber data, built with Frappe's existing features.
- **Files or modules affected:** `emp_tracking/fiber_store.py` (new); `emp_tracking/patches/import_fiber_register.py`, `patches/fiber_register_2026_27.json` (new); `emp_tracking/patches.txt`; `emp_tracking/hooks.py` (`after_migrate`, `doc_events`); `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (menu).
- **Testing:** On newsite.local:
  - **Backup:** I took a database backup first (`20261026_142932-newsite_local-database.sql.gz`).
  - **Trial run:** before the import, two sample entries posted and were rolled back, and an End Reading above the Start Reading was blocked.
  - **Migrate and import:** `bench migrate` ran the patch. It created 1 opening entry (139 drums / accessories in hand on 2026-04-01, 132,346 m), 404 inward entries and 1,162 outward entries, with 0 failures and no batch below zero.
  - **Fix on the first run:** 11 inward rows without a Sr No were first skipped as duplicates. I fixed the reference and re-ran, which posted 12 rows. The extra one was a second copy of the first such row, which the first run had already posted, so I cancelled that first copy (MAT-STE-2026-00360).
  - **Maintenance totals** match the sheet's Team Wise summary exactly for every team and month: 258,378 m (Team 1/6 117,759; Team 2 35,589; Team 3 34,003; Team 4 26,079; Team 5 44,948).
  - **Project totals** match for every team and month except Team 5 in July. The sheet has 6,717 m there and the register 4,708 m. The 2,009 m gap is the three "Rope" rows, which the sheet's summary counts as cable and the register keeps as rope.
  - **Dashboard check:** the charts and cards return data, and the menu link is in 3 sidebars.
  - **Not checked:** the dashboard in a browser, and a login as a non-admin user.
- **Pending items:**
  - **Opening stock is derived.** It comes from each drum's first reading, not from a physical count.
  - **Sheet errors kept as they were:**
    - Some rows have an End Reading above the Start Reading (e.g. S.No 108 and 622). They were posted with the sheet's Total cable and without readings, and the remarks say so.
    - Some rows have text in Total cable ("1430 H", "5 Ltr"); the number was used.
    - Vendor names are spelled differently in places (e.g. "Swarad" / "Swarad Connect").
  - **Dashboard totals differ from the sheet's summary.** The cards include vendor rows (e.g. Sheetal Enterprises, Spine Teleinfra), which the summary leaves out. Maintenance shows 260,878 m and Project 190,570 m.
  - **No prices.** Stock is posted at zero value.

## 2026-10-26: Visual "Employee Performance" dashboard page

- **Summary:** New Desk page `/app/employee-performance`, in the card style of the NOC Dashboard. The "Maintenance Calls" tab (Designation, From, To filters) shows KPI tiles (people, calls, SLA %, average MTTR, field time per day, leaves), a top-3 podium, score bars with levels and badges, a monthly calls / points chart, SLA % by month against a 70% target, In vs Out of SLA per person, a field / home / office donut and average MTTR per person. Clicking a person opens their profile: rank, level progress, badges, KPI tiles and month-by-month charts. The "FTTH / Projects" tab draws the job-based ranking (RFS, fiber, home pass) from the Performance Leaderboard report as a podium and bars. In the EVision menu, the page replaces the Performance Leaderboard report link. The report still works by URL.
- **Reason:** The user asked to see employee performance in visual form only, like the other dashboards, not as a table.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/employee_performance/` (new: `employee_performance.json`, `.py`, `.js`, `__init__.py`); `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (Dashboards menu).
- **Testing:** On newsite.local: `bench migrate` created the Page with no errors, and the menu has the link in 3 sidebars. `get_calls_dashboard` returned 5 supervisors and 12 splicers for April 2025 to today, with 12 trend months and the time split. The person view for Sanket Kotkar returned 12 months. `get_jobs_dashboard` (Vendor, from 2026-01-01) returned 16 rows (80 RFS, 14,216 m fiber). `bench clear-cache` ran. Locally: `node --check` passed. Not checked: the page in a browser (layout and charts), or as an Area Manager.
- **Pending items:** "Rider" shows an empty state, because the sheet data lists riders under Splicer. The figures are still the typed FY 2025-26 data.
- **Follow-up (same day):** An Employee dropdown was added to the Maintenance Calls tab. It lists, A to Z, the people with data for the chosen designation and period. Picking one opens their profile, and "All Employees" goes back to the full view. Clicking a name on the page also updates the dropdown. Checks: `node --check` passed and `bench clear-cache` ran on newsite.local. The dropdown has not been tried in a browser.
- **Follow-up (2026-10-27): complaint calls by area, with times.** The Maintenance Calls tab now also reads the real complaints in Complaint Information (received in the chosen period):
  - New **Area** filter. It narrows only the complaint parts, because the monthly figures have no area.
  - Main view: a **Calls by Area** chart (each complaint counted once) and **Who Attended Where**: each person's calls, restored and in-SLA counts, and calls per area. The Splicer view counts Splicer / 2nd Splicer, the Rider view Rider / 2nd Rider, and Supervisor all four. People with complaints but no monthly row are included; their names come from Employee, and they are added to the Employee dropdown.
  - Person profile: their calls by area, plus a **Complaint Calls** table. One row per complaint: Area, Site / Link, Operator, the person's role, Received, Assigned to Team, Restored, Time to Assign, Time to Restore (EVisions MTTR), SLA, Status. The complaint number links to the form.
  - Hidden for users who may not read Complaint Information. Their own complaint permissions apply.
  - **Reason:** The user asked to see how many calls a splicer attended in an area, and when each complaint was assigned and done.
  - **Files:** `page/employee_performance/employee_performance.py` (`complaint_calls`, `designation_roles`, `area_calls`, `area` argument), `employee_performance.js` (Area filter, `area_cards_html`, `area_chart`, `person_complaints_html`).
  - **Testing:** `node --check` and a Python parse passed. On newsite.local through `bench console`: Splicer view gives Amit Jadhav 1 call in Pune; Rider view gives Rahul Patil 1; the profile gives CMP-2609-00005 with role Splicer; Area Pune gives 1 person and Akurdi 0; a one-day period includes the complaint at 13:51; Guest gets None. `bench migrate` and `clear-cache` ran. **Not checked:** the page in a browser.
  - **Pending:** Only 6 complaints exist (1 with a splicer), and "Assigned to Team" / "Restored" are filled only when the workflow reaches those steps, so most of these cards stay empty until complaints are worked in the system. The FY 2025-26 monthly sheet data has no per-complaint detail.
- **Follow-up (2026-10-27): Monthly Trend legend in the top-right corner.** The chart's own Calls / Points legend overlapped the bars, so it is now hidden (`showLegend: 0`). The same legend is shown in the card header's top-right corner instead. File: `employee_performance.js`. `node --check` passed. Not checked in a browser, and `bench clear-cache` not run.

## 2026-10-24: Maintenance calls, SLA and location data in the Performance Leaderboard

- **Summary:** New doctype "Staff Monthly Performance" (one record per person per month: total days, leaves, working days, average daily time on field / home / office location, calls as supervisor or splicer, calls as assistant splicer, In / Out of SLA, average MTTR, score). The FY 2025-26 Summary sheets of the two "Location and Calls Data" files (Supervisor; Splicer and Rider) were transcribed into `patches/staff_performance_fy2025_26.json` and loaded by a patch: 17 people, 204 person-months, April 2025 to March 2026, linked to their Employee records except Dhammadip Jondhale (no Employee). The Performance Leaderboard has a new Source "Maintenance Calls" with a Designation filter. It scores each month with the sheets' formulas: Supervisor = calls + 0.5 × In SLA − 0.5 × Out SLA; Splicer / Rider = splicer calls + 0.5 × assistant calls + 0.25 × In SLA − 0.25 × Out SLA. The weights are editable in Leaderboard Settings (new "Maintenance Calls" section). It shows SLA %, call-weighted average MTTR, average field time and working hours, leaves, levels, medals and badges (Call Champ, SLA Star, Fast Fixer, Field Warrior, Always There). The doctype is in the EVision menu under Dashboards.
- **Reason:** Requested: add the supervisor and splicer/rider location and calls data to the performance report.
- **Files or modules affected:** `emp_tracking/performance.py` (`CALL_POINTS`, `score_calls`, `build_call_leaderboard`); `emp_tracking/tests/test_performance.py` (2 new tests); `emp_tracking/emp_tracking/doctype/staff_monthly_performance/` (new); `emp_tracking/emp_tracking/doctype/leaderboard_settings/leaderboard_settings.json`; `emp_tracking/emp_tracking/report/performance_leaderboard/performance_leaderboard.py`, `.js`; `emp_tracking/patches/import_staff_performance.py`, `patches/staff_performance_fy2025_26.json` (new); `emp_tracking/patches.txt`; `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (menu link).
- **Testing:** Locally: 7 unit tests passed (including one sheet value per formula), `py_compile`, `node --check`. On newsite.local: `bench migrate` ran the patch (204 records created); the report returned 5 supervisors and 12 splicers for April 2025 to March 2026. Supervisor scores match the supervisor Sheet1 (Sachin 1865, Sanket Kandhare 1826.5, Akash 1389); Rahul Dilliwala is 2060 against the sheet's 2062. An empty period returns a message, and the FTTH Vendor ranking still returns 16 rows. No new Error Log entry from this code. Not checked: the report and the form in a browser (filter show/hide when choosing Maintenance Calls), or a login as an Area Manager.
- **Pending items:** The sheets' own yearly totals differ from the sum of their monthly rows for some people (for example Rohan Tupe Out SLA 427 against 387, Akshay Chavan In SLA 366 against 316, Amol Waghmare In SLA 307 against 281), so a few splicer scores differ from the MARKS SUMMARY sheet. The monthly rows were used. Not loaded: Raj Kashinath Rathod (rows are #REF! errors), Dilip Pawar and Mahesh Khedekar (no monthly summary rows). The figures are typed data. Working them out from Complaint Information (splicer / rider, MTTR, SLA) and Employee Checkin would keep them current; not done yet.

## 2026-10-24: Node merged into GIS Node

- **Summary:** The Node master (this app) is merged into GIS Node (FTTH Tracker), which is now the only node master. Site.node and Complaint Information.node_id link to GIS Node. A patch moved the data: 21 of the 22 Nodes already existed in GIS Node; "OWC" was a typo for GIS "0WC" (Warje), and its 1 Site was moved there. The Node doctype was removed (Frappe deleted it as an orphan; the old `tabNode` table is still in the database). The Node form's Site Diagram moved to the GIS Node form (Custom Field `custom_site_diagram`, script through `doctype_js`). GIS Node's Connections panel now also lists Sites and Complaints (`override_doctype_dashboards`). OverHead roles get select / read on GIS Node instead of Node. "Nodes" left the EVision and Helpdesk NOC menus. `required_apps = ["ftth_tracker"]` was added to hooks.py, because two links now point at an FTTH Tracker doctype. The Team 2 site import patch now creates GIS Nodes instead of Nodes, which only matters on a new site.
- **Reason:** GIS Node and Node held the same GIS codes. The user asked to check the data and merge them.
- **Files or modules affected:** `emp_tracking/patches/merge_node_into_gis_node.py` (new), `patches/import_team2_sites.py`, `patches.txt`; `emp_tracking/overrides/gis_node.py` (new); `emp_tracking/public/js/gis_node.js` (new, moved from `doctype/node/node.js`); `emp_tracking/emp_tracking/doctype/node/` (removed); `doctype/site/site.json`; `doctype/complaint_information/complaint_information.json`, `.js`; `workspace_sidebar/helpdesk_noc.json`; `hooks.py`; `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`OH_LINK_PERMS`, menu, `CUSTOM_FIELDS`, `grant_oh_link_permissions`).
- **Testing:** Before the change I backed up newsite.local (`20261024_163849-newsite_local-database.sql.gz`) and exported the 22 Node rows to `sites/newsite.local/private/backups/20261024-node-before-merge.tsv`. After `bench migrate` on newsite.local: all 696 Sites link to an existing GIS Node; a Site saves; GIS Node shows the Sites & Complaints connections and has the Site Diagram field; OverHead roles have select / read on GIS Node; neither menu links Node. The first migrate logged "rebuilding the desk menu after migrate failed": `frappe.permissions.add_permission` re-validates GIS Node's standard permission rows, and FTTH Tracker ships "import" ticked on a non-importable doctype. `grant_oh_link_permissions` now inserts the Custom DocPerm row directly. I re-ran the menu rebuild and the grant without errors, and the later migrate was clean. Locally: `py_compile`, `node --check`, JSON loads. Not checked: the GIS Node form in a browser (Site Diagram and Connections).
- **Pending items:** The empty `tabNode` table can be dropped once nobody needs the old rows. FTTH Link ↔ Network Link and Field Staff ↔ Employee are not linked yet. The "import" flag on GIS Node's System Manager / FTTH Manager rows in FTTH Tracker's doctype JSON should be fixed in that app.

## 2026-10-24: One "EVision" tile for dashboards, FTTH and OH Project

- **Summary:** The desk now has one EVision tile in place of the separate Dashboard, OverHead Project and FTTH Tracker tiles. Its menu follows the work: Dashboards (Workforce, FTTH Dashboard, NOC, Performance Leaderboard) → FTTH Work Orders (list, map, imports, GIS summary) → OH Projects → Complaints → Network (GIS Nodes, Nodes, Network Links, Link Register, Sites, Node Sites, KMZ Routes and Points) → Teams & Vendors (Areas, EVisions Teams, Vendors, IBD Teams, Fiber Pulling Teams, Fiber Teams, Field Staff) → Settings (FTTH, Leaderboard). The Dashboard and OverHead Project tiles and sidebars are deleted; the FTTH Tracker and empty WorkForce tiles are hidden. The Helpdesk NOC and FTTH Tracker sidebars carry the same menu, so it stays the same while moving between screens. The FTTH Manager and FTTH User roles also see the tile. FTTH links are left out on sites without ftth_tracker.
- **Reason:** There were too many separate tiles and menus for one business. The user asked to bring them together into one EVision workspace with a proper flow.
- **Files or modules affected:** `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py` (`SIDEBAR`, `OLD_SIDEBARS`, `HIDDEN_ICONS`, `MIRROR_SIDEBARS`, `TILE_ROLES`, `oh_menu()`, `link_exists()`, `make_navigation()`, new `hide_replaced_icons()`); `workforce_dashboard.js` (`EV_SIDEBAR`, `OH_SIDEBARS`).
- **Testing:** On newsite.local I ran `make_navigation()`, then a full `bench migrate`. After both, EVision is visible with 34 menu rows, FTTH Tracker is hidden, the Dashboard and OverHead Project tiles and sidebars are gone, and no Error Log entry came from this code (the only new entry is Helpdesk's search-index rebuild). Locally: `py_compile` and `node --check`. I did not check the desk in a browser, or as an OverHead-only or Employee-only user.
- **Pending items:** Helpdesk NOC keeps its own tile (for NOC users). The menu links the FTTH and OH screens, but the records are not yet linked to each other (GIS Node ↔ Node, FTTH Link ↔ Network Link, Field Staff ↔ Employee).

## 2026-10-24: Performance Leaderboard also scores FTTH Work Orders

- **Summary:** The leaderboard now also reads FTTH Work Orders (status RFS Done) when the ftth_tracker app is installed, next to New Projects. A new "Source" filter picks FTTH Work Order, New Project or both (blank). Each Rank choice uses the matching FTTH field: Employee → Splicer / Assistant Splicer / Splicer 2 / Rider 1 / Rider 2 (Field Staff), Fiber Pulling Team → Fiber Team, Vendor → IBD Team, plus Area, Area Manager and GIS. The period now defaults to 1 January of this year, and Rank defaults to Vendor. The Vendor / Fiber Team / Link Type / Project Type filters were replaced by one Area text filter, because the two sources link to different doctypes.
- **Reason:** The report was empty on newsite.local. The FTTH data copied from OH.local is in FTTH Work Order (1,400 rows; 87 with an RFS Date, the latest on 2026-04-20), while the report read only New Project (4 rows, none with an RFS Date) and only for the current month.
- **Files or modules affected:** `emp_tracking/emp_tracking/report/performance_leaderboard/performance_leaderboard.py`, `performance_leaderboard.js`
- **Testing:** On the server (newsite.local), I ran `execute()` for every Source × Rank combination with no errors. 2026 to date: 16 IBD teams, 46 areas, 8 area managers and 58 GIS nodes ranked; the Area filter works. Locally: `py_compile`, `node --check`, and the 5 unit tests passed. I did not open the page in a browser.
- **Pending items:** The Employee rank is empty for FTTH because only 1 of the 147 RFS Done work orders has a Splicer or Rider filled in. 60 RFS Done work orders have no RFS Date (completed through Issue Type only), so they can't be placed in a period and are not scored. No FTTH work order has "Splicing Snaps A & B" ticked, so each one gets the Missing Snap penalty and none gets the Clean bonus; set the penalty to 0 in Leaderboard Settings if snaps were not tracked for the old data.

## 2026-10-24: Performance Leaderboard (gamified performance report)

- **Summary:** New Script Report "Performance Leaderboard" on New Project. Each project with an RFS Date in the period (cancelled ones excluded) earns points: per RFS, per 100 m fiber, per home pass, an on-time bonus (WO Received → RFS within the target days) and a clean-job bonus (all four fiber/splicing snaps, no re-work). Missing snaps and re-work cost points. Totals give a Level (Rookie → Bronze → Silver → Gold → Platinum → Diamond) with a progress bar to the next level, 🥇🥈🥉 medals for the top 3, badges (Fiber King, Home Hero, Speedster, Clean Sheet, On Fire 4-week streak, Century) and a best weekly streak. A "Rank" filter switches between Employee (everyone in the Fiber Team and Splicing Team tables), Fiber Pulling Team, Vendor, EVisions Team, Area, Area Manager and GIS. Point values are editable in the new single doctype "Leaderboard Settings". Both are added to the desk menu.
- **Reason:** Requested performance report with gamification, built on the existing New Project data in emp_tracking instead of the separate ftth_tracker app.
- **Files or modules affected:**
  - `emp_tracking/performance.py` (new): scoring, levels, badges, streaks (no frappe import)
  - `emp_tracking/tests/test_performance.py`, `emp_tracking/tests/__init__.py` (new)
  - `emp_tracking/emp_tracking/report/performance_leaderboard/` (new): report JSON, Python, JS
  - `emp_tracking/emp_tracking/doctype/leaderboard_settings/` (new): single doctype
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py`: menu links in `oh_menu()`, `link_exists()` checks Report links
- **Testing:** Run locally: `python -m unittest emp_tracking.tests.test_performance` (5 tests, passed); the report's `execute()` against a stubbed `frappe` with sample New Project rows for every Rank option (points match hand calculation); `py_compile` on all changed Python; `node --check` on the report JS; JSON files load. Not run on the server: `bench --site newsite.local migrate`, `bench build`, opening the report in the browser, and checking it as Fiber Team / Splicing Team / Area Manager users.
- **Pending items:** Run migrate on newsite.local, then open Leaderboard Settings once and Save so the default points are stored (until then the report uses the same defaults from `performance.py`). An employee in a team gets the full points of a shared project. The FTTH Tracker app's other features (importer, KMZ, link register) were not moved into emp_tracking.

## 2026-10-21: Allow Punch From Anywhere

- **Summary:** New Employee checkbox "Allow Punch From Anywhere" (`custom_allow_punch_from_anywhere`). When ticked, that employee's check-ins skip the HRMS Shift Location radius check (home / office location), so they can punch in or out from anywhere. Everyone else is checked as before. The punch latitude and longitude are still saved.
- **Reason:** Some employees need to punch from any location instead of only near their home or office location.
- **Files or modules affected:**
  - `emp_tracking/overrides/employee_checkin.py` (new): `EmployeeCheckinMixin`
  - `emp_tracking/overrides/__init__.py` (new)
  - `emp_tracking/hooks.py`: `extend_doctype_class` for Employee Checkin
  - `emp_tracking/emp_tracking/page/workforce_dashboard/setup.py`: Employee custom field, created by `after_migrate`
- **Testing:** Local Python syntax check (`py_compile`) only. Not run on the server: `bench --site newsite.local migrate`, and a test check-in outside the radius with the box ticked and unticked.
- **Pending items:** Run migrate on the server, then test both cases. After an HRMS upgrade, confirm that `EmployeeCheckin.validate_distance_from_shift_location` still exists (verified on HRMS 16.19.0).
