"""Access to the CJI3 extraction planner and dispatch log in BI_Oekonomi.

Which date ranges this run extracts is decided by dbo.usp_CJI3_PlanlaegUdtraek.
All logic lives in stored procedures - this module only calls them, so the rules
about coverage, repair and giving up stay in one place (sql/create_CJI3.sql in the
Performer repo).
"""

import pyodbc

from robot_framework import config


def connect(orchestrator_connection) -> pyodbc.Connection:
    """
    Open a connection to the BI_Oekonomi database.

    autocommit is on deliberately: every procedure call is its own unit of work.
    The plan has to be durable before the robot starts driving SAP, so that a crash
    leaves the dispatch rows IGang to be written off by the next run's stale sweep
    rather than rolling them back and re-extracting the same ranges immediately.
    """
    sql_server = orchestrator_connection.get_constant(config.SQL_SERVER_CONSTANT).value
    conn_string = (
        f"DRIVER={{{config.SQL_DRIVER}}};"
        f"SERVER={sql_server};"
        f"DATABASE={config.SQL_DATABASE};"
        "Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_string)
    conn.autocommit = True
    return conn


def planlaeg_udtraek(conn: pyodbc.Connection) -> list[dict]:
    """
    Decide what this run extracts, and record it as IGang in the dispatch log.

    Returns one dict per range, each with UdtraekId, DatoFra, DatoTil, Slags and
    DatoFraSAP/DatoTilSAP (already dd.mm.yyyy, ready for the CJI3 selection
    screen), in the order they should be submitted:

      Slags 'Dagligt'    exactly one, always - the rolling LOOKBACK_DAGE range
                         ending today.
      Slags 'Reparation' zero to REPARATIONER_PR_KOERSEL chunks of days that have
                         never been loaded, oldest first.

    An empty list therefore means something is wrong, not that there is nothing to
    do - the rolling range is unconditional.
    """
    cursor = conn.cursor()
    cursor.execute(
        "{CALL dbo.usp_CJI3_PlanlaegUdtraek (?, ?, ?)}",
        config.LOOKBACK_DAGE,
        config.REPARATIONER_PR_KOERSEL,
        config.MAKS_DAGE_PR_KOERSEL,
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def tilknyt_spooljob(conn: pyodbc.Connection, udtraek_id: int, spool_job: str) -> None:
    """Record the spool job name (prtxt) on a claimed window."""
    conn.cursor().execute(
        "{CALL dbo.usp_CJI3_TilknytSpoolJob (?, ?)}",
        udtraek_id,
        spool_job,
    )


def afslut_udtraek(
    conn: pyodbc.Connection,
    udtraek_id: int,
    status: str,
    fejlbesked: str | None = None,
) -> None:
    """
    Close a dispatch that is not going to be loaded. Pass 'Fejlet': the range's days
    stay unmarked in dbo.CJI3_Dagdaekning, so the next run plans them again by
    itself. There is nothing to re-queue and no retry counter to respect.

    Fejlbesked is capped at the column width so a long stack trace cannot make the
    error handler itself fail.
    """
    conn.cursor().execute(
        "{CALL dbo.usp_CJI3_AfslutUdtraek (?, ?, ?)}",
        udtraek_id,
        status,
        (fejlbesked or "")[:1000] or None,
    )
