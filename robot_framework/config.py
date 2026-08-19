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

# How many windows to dispatch per run. Each one becomes a CJI3 run, a spool job
# and a queue element, so this is what decides how fast the historic backfill
# catches up: at 10 a night the backfill from 2025 is done in about 9 nights.
# Once caught up there are only ever a couple of windows waiting per day.
WINDOWS_PER_RUN = 10

# Days per window. Capped at 7 by CK_CJI3_Udtraek_MaksEnUge in the database.
DAGE_PR_VINDUE = 7

# The dynamic selection field the date range is typed into. %%DYN002 is a position,
# not a field name: SAP numbers the fields in the dynamic selections area by the
# order they appear, so this says nothing about which CJI3 date it actually is.
DYN_DATE_FIELD = "%%DYN002"

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
