"""This module contains configuration constants used across the framework"""

# The number of times the robot retries on an error before terminating.
MAX_RETRY_COUNT = 1

# Whether the robot should be marked as failed if MAX_RETRY_COUNT is reached.
FAIL_ROBOT_ON_TOO_MANY_ERRORS = True

# Error screenshot config
SMTP_SERVER = "smtp.adm.aarhuskommune.dk"
SMTP_PORT = 25
SCREENSHOT_SENDER = "sapcji3@aarhus.dk"

# Constant/Credential names
ERROR_EMAIL = "Error Email"


# Queue specific configs
# ----------------------

# The queue this robot writes to. Not the performer's queue: elements go to the
# queuer first, which holds each one until SAP has had time to generate the spool
# job, so neither of the two blocking SAP robots has to sit and wait.
QUEUE_NAME = "SAPCJI3Wait"

# The limit on how many queue elements to process
MAX_TASK_COUNT = 100

# ----------------------


# Extraction ranges
# ----------------------

# How many REPAIR chunks to dispatch per run, on top of the rolling daily range, which
# always goes out. Total CJI3 runs per dispatcher run is therefore this plus one.
#
# 2 (so three extracts a run) because SAP may generate the spool jobs serially and
# nothing here controls that. Measured timings per range: ~24s to submit, 375-533s for
# SAP to generate the spool, ~90s for the performer. Worst case with three - fully
# serialised - the last spool is ready around minute 21, the performer reaches it around
# minute 16 and waits ~5, well inside SPOOL_TIMEOUT_S of 30 minutes, and the whole cycle
# is done by minute 23 with over half an hour of slack before the next run. At 10 the
# last spool would not be ready until roughly minute 70, past the performer's timeout.
#
# Paired with the trigger's cron ("0 22-23,0-4 * * *", 7 runs a night) this sets the
# catch-up pace: 14 chunks a night, so up to 98 days of hole repaired per night. Once
# there are no holes left the repair half returns nothing and a run is a single extract.
#
# Do not set this to 0. The rolling range would still run, so the figures would look
# current, but a day that was ever missed would never be repaired - which is precisely
# the failure the old model had.
REPARATIONER_PR_KOERSEL = 2

# Days per extract, and the cap on a repair chunk. Capped at 7 by
# CK_CJI3_Udtraek_MaksEnUge in the database, and by the 0-6 tally the merge uses to
# expand a range into days. Raising it means changing both.
MAKS_DAGE_PR_KOERSEL = 7

# The dynamic selection field the date range is typed into. %%DYN002 is a position,
# not a field name: SAP numbers the fields in the dynamic selections area by the
# order they appear, so this says nothing about which CJI3 date it actually is.
DYN_DATE_FIELD = "%%DYN002"

# Bogfoeringsdato (R_BUDAT) on the main selection screen, which the robot overwrites
# after loading the variant.
#
# This has to be set, not inherited. The saved variant carries a fixed range - it held
# 01.06.2025 to 31.08.2026 - and a fixed range breaks two ways: any window whose
# postings fall outside it returns nothing at all (which is why extracting January 2025
# produced no spool job whatsoever, not even an empty one), and the whole extract dies
# silently once today passes the end date.
#
# The rule is taken from the manual procedure recorded on 16 February 2026, which used
# 01.12.2024 to 28.02.2026: month-end of the reference month, back to the first day of
# the month N months earlier. Applied to the window being extracted rather than to
# today. Sanity check: at N=14 the rule reproduces exactly 01.06.2025 - 31.08.2026 for
# the week of 12-18 August 2026, the values the saved variant already had.
#
# 15, not the 14 the recording implies. Confirmed with Oekonomi: a fiscal year's posting
# period runs from e.g. 1 January 2025 until roughly 20 February 2026, so by 1 March
# 2026 nothing more is posted into 2025 - a posting date can therefore sit about 14
# months behind the day it is registered. 15 puts a month of margin on that.
#
# The span only needs to cover how far a posting date can sit behind the day the posting
# was registered; it is a scan limit, not a business rule.
BUDAT_MONTHS_BACK = 15

# Expected label beside that field, checked before it is overwritten. Same guard as
# DYN_DATE_LABEL: writing dates into the wrong field would quietly change what the
# extract covers.
BUDAT_LABEL = "Bogføringsdato"

# The label expected next to that field. It is read back before the dates are typed,
# and a mismatch fails the run.
#
# Confirmed by sandbox_layout.py: %%DYN002 is 'Registreringsdato' - the ENTRY date,
# not the posting date. That is the safer field to extract on, because a document is
# caught by the window covering the day it was entered whatever period it posts to, so
# a late posting into an old period still arrives. It also means date windows do not
# line up with Bogfoeringsdato: completeness must be judged on Registreringsdato.
#
# %%DYN001 is 'Kapitalmidler' and there is no %%DYN003, so the variant has exactly two
# dynamic selections. If someone adds one, the numbering shifts and this guard fires.
DYN_DATE_LABEL = "Registreringsdato"

# Length of the rolling range that goes out on EVERY run: today-6 .. today.
#
# This is the "kor en uge bagud hver eneste dag" rule, and it means a rolling range
# recomputed from the current date - not a re-run of some stored week. An earlier
# version read it the second way, tiled the timeline into fixed 7-day windows and
# re-opened the window rows overlapping the last week. Those re-opened rows always
# sorted ahead of the current one, so the current week went six days without ever
# being extracted. Coverage is tracked per day now (dbo.CJI3_Dagdaekning) and the
# planner returns the rolling range and the repair chunks from the same call, so
# neither can starve the other.
#
# It ends at TODAY, not yesterday. Oekonomi holds these figures up against the OPUS
# reports the organisation uses day to day, so the top-line totals have to match what
# OPUS shows now. Including a day that is not over is safe because the range is not a
# commitment: today is re-extracted on every run for the next seven days, so the
# figures are complete as of the most recent run rather than as of the last whole day.
#
# It is also why nothing needs to periodically re-read closed periods, which is not
# obvious. Correcting a posting gives it a NEW Registreringsdato - the date of the
# correction - so a posting originally booked in March reappears in the CURRENT week's
# window when it is corrected in August. Confirmed with Oekonomi. Since windows are cut
# on Registreringsdato, every correction therefore arrives here by itself: either as an
# update to the existing Bilagsnummer + OpV, or as a new row.
#
# The corollary is that Registreringsdato is NOT immutable, so windows do not strictly
# partition the data - a row first loaded from a March window can appear again in an
# August one. Harmless: the merge is keyed on Bilagsnummer + OpV, and DataTidspunkt
# stops an older extract from overwriting a newer one.
LOOKBACK_DAGE = 7

# ----------------------


# MSSQL (BI_Oekonomi.dbo.CJI3)
# ----------------------

# Name of the OpenOrchestrator constant holding the SQL server host.
SQL_SERVER_CONSTANT = "SqlServer"

SQL_DATABASE = "BI_Oekonomi"

# Not the legacy "SQL Server" driver - it cannot bind the DATE/TIME types.
SQL_DRIVER = "ODBC Driver 17 for SQL Server"

# ----------------------
