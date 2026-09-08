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


# Extraction windows
# ----------------------

# How many windows to dispatch per run. Each one becomes a CJI3 run, a spool job and a
# queue element, so this is what decides how fast the historic backfill catches up: at
# 10 a night the backfill from 2025 is done in about 9 nights. Once caught up there are
# only ever a couple of windows waiting per day.
#
# Deliberately 1 until one window has gone end to end. Ten windows on the first run
# means ten spool jobs in SAP before a single row is known to have landed, and it is the
# quickest way to hit the spool-overview paging limit. Raise it to 10 once the load log
# shows a clean window.
WINDOWS_PER_RUN = 1

# Days per window. Capped at 7 by CK_CJI3_Udtraek_MaksEnUge in the database.
DAGE_PR_VINDUE = 7

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

# How far back to re-extract every day. This is the "kor en uge bagud hver eneste
# dag" rule: it re-runs the last week so postings that were missing during an
# udfald a day or two ago still get picked up.
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
