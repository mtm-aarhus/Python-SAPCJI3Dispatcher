"""Access to the CJI3 extraction work list in dbo.CJI3_Udtraek.

The work list decides which date range this run extracts. All logic lives in
stored procedures - this module only calls them, so the rules about ordering,
re-opening and giving up stay in one place (sql/create_CJI3.sql in the
Performer repo).
"""

import pyodbc

from robot_framework import config


def connect(orchestrator_connection) -> pyodbc.Connection:
    """
    Open a connection to the BI_Oekonomi database.

    autocommit is on deliberately: every procedure call is its own unit of work.
    A claim has to be durable before the robot starts driving SAP, so that a crash
    leaves the window IGang for the stale sweep to reclaim rather than rolling the
    claim back and re-extracting the same range immediately.
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


def opdater_vindueliste(conn: pyodbc.Connection) -> dict:
    """
    Extend the work list to yesterday and re-open the last week's windows.

    Returns the procedure's summary: UdvidetVindue, NyeVinduer, Genaabnede,
    AfventerIAlt.
    """
    cursor = conn.cursor()
    cursor.execute(
        "{CALL dbo.usp_CJI3_OpdaterVindueliste (?, ?)}",
        config.DAGE_PR_VINDUE,
        config.LOOKBACK_DAGE,
    )
    return _first_row_as_dict(cursor)


def reserver_udtraek(conn: pyodbc.Connection, antal_vinduer: int) -> list[dict]:
    """
    Claim up to antal_vinduer windows, oldest first.

    Returns one dict per claimed window with UdtraekId, DatoFra, DatoTil,
    Forsoeg, AntalKoersler and DatoFraSAP/DatoTilSAP (already dd.mm.yyyy, ready
    for the CJI3 selection screen). An empty list means there is nothing to do.
    """
    cursor = conn.cursor()
    cursor.execute("{CALL dbo.usp_CJI3_ReserverUdtraek (?)}", antal_vinduer)
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
    Hand a claimed window back: 'Afventer' to retry later, 'Fejlet' to give up.

    Fejlbesked is capped at the column width so a long stack trace cannot make the
    error handler itself fail.
    """
    conn.cursor().execute(
        "{CALL dbo.usp_CJI3_AfslutUdtraek (?, ?, ?)}",
        udtraek_id,
        status,
        (fejlbesked or "")[:1000] or None,
    )


def _first_row_as_dict(cursor: pyodbc.Cursor) -> dict:
    """Turn a single-row result set into a dict, or {} if the proc returned none."""
    row = cursor.fetchone()
    if row is None:
        return {}
    return dict(zip([column[0] for column in cursor.description], row))
