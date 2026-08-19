"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

import json
import time
from datetime import date
import uuid

import win32com.client

from robot_framework import config
from robot_framework import udtraek


# The CJI3 selection variant the robot loads. Its layout is what decides which field
# config.DYN_DATE_FIELD points at, so it is named here rather than inline.
VARIANT_NAME = "FULDT UDTRÆK"


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    """
    Dispatch the oldest pending extraction windows.

    The date range is no longer computed here - it comes from the work list in
    dbo.CJI3_Udtraek, which is what makes the historic backfill resumable
    across runs and keeps track of what has and has not been loaded.
    """
    orchestrator_connection.log_trace("Running process.")

    conn = udtraek.connect(orchestrator_connection)
    try:
        summary = udtraek.opdater_vindueliste(conn)
        orchestrator_connection.log_trace(
            "Work list updated: " + ", ".join(f"{key}={value}" for key, value in summary.items())
        )

        windows = udtraek.reserver_udtraek(conn, config.WINDOWS_PER_RUN)
        if not windows:
            orchestrator_connection.log_info("No windows waiting to be extracted. Nothing to do.")
            return

        orchestrator_connection.log_trace(
            f"Reserved {len(windows)} window(s): "
            + ", ".join(f"{w['DatoFraSAP']}-{w['DatoTilSAP']}" for w in windows)
        )

        session = get_sap_session(connection_index=0, session_index=0)
        wait_ready(session)
        session.findById("wnd[0]").maximize()

        dispatched = 0
        try:
            for window in windows:
                prtxt = f"{build_prtxt(window['DatoTil'])}_{uuid.uuid4().hex[:8]}"

                label = submit_cji3_extract(
                    session, window["DatoFraSAP"], window["DatoTilSAP"], prtxt
                )
                if dispatched == 0:
                    # Logged once per run. With config.DYN_DATE_LABEL still empty this
                    # is how you find out which CJI3 date the extract is filtered on.
                    orchestrator_connection.log_info(
                        f"Dynamic selection field {config.DYN_DATE_FIELD} is labelled "
                        f"'{label}'. The date range is filtered on that field."
                    )

                udtraek.tilknyt_spooljob(conn, window["UdtraekId"], prtxt)

                # Goes to the queuer, not the performer. The element's created_date
                # is stamped here, and the queuer uses it to give SAP a head start
                # before the performer starts looking for the spool job.
                orchestrator_connection.create_queue_element(
                    config.QUEUE_NAME,
                    prtxt,
                    json.dumps({"UdtraekId": window["UdtraekId"], "SpoolJob": prtxt}),
                    orchestrator_connection.process_name,
                )

                dispatched += 1
                orchestrator_connection.log_trace(
                    f"Dispatched window {window['UdtraekId']} "
                    f"({window['DatoFraSAP']} - {window['DatoTilSAP']}) as {prtxt}."
                )
        except Exception:
            # Hand back everything that never reached the queue, so the next run
            # retries it instead of it sitting IGang until the stale sweep.
            for window in windows[dispatched:]:
                udtraek.afslut_udtraek(
                    conn,
                    window["UdtraekId"],
                    "Afventer",
                    f"Dispatcher afbrudt efter {dispatched} af {len(windows)} vinduer.",
                )
            raise
    finally:
        conn.close()


def submit_cji3_extract(session, date_low: str, date_high: str, prtxt: str, plist: str = "ROBOT") -> str:
    """
    Run CJI3 for one date range and send the result to a spool job named prtxt.

    Returns the label found next to the date field, so the caller can log which CJI3
    date the extract is actually filtered on.

    This is the recorded click sequence; only the dates and the print parameters
    change per window. It starts from and returns to the SAP main screen, so it can
    be called once per window in a loop.

    Dates must already be dd.mm.yyyy - usp_CJI3_ReserverUdtraek returns them
    in that format as DatoFraSAP/DatoTilSAP.
    """
    session.findById("wnd[0]/tbar[0]/okcd").text = "CJI3"
    session.findById("wnd[0]").sendVKey(0)
    wait_ready(session)

    session.findById("wnd[0]/tbar[1]/btn[17]").press()          # Hent variant
    session.findById("wnd[1]/usr/txtENAME-LOW").text = ""
    session.findById("wnd[1]/usr/txtV-LOW").text = VARIANT_NAME
    session.findById("wnd[1]/tbar[0]/btn[8]").press()
    wait_ready(session)

    session.findById("wnd[0]").sendVKey(21)                     # Dynamiske selektioner
    wait_ready(session)

    label = read_dyn_field_label(session, config.DYN_DATE_FIELD)
    if config.DYN_DATE_LABEL and label.casefold() != config.DYN_DATE_LABEL.casefold():
        raise RuntimeError(
            f"Dynamic selection field {config.DYN_DATE_FIELD} is labelled {label!r}, "
            f"but {config.DYN_DATE_LABEL!r} was expected. The {VARIANT_NAME} variant "
            "has most likely been changed, which shifts the %%DYNnnn numbering - the "
            "dates would be filtered on the wrong field and nothing else would notice."
        )

    session.findById(f"wnd[0]/usr/ctxt{config.DYN_DATE_FIELD}-LOW").text = date_low
    session.findById(f"wnd[0]/usr/ctxt{config.DYN_DATE_FIELD}-HIGH").text = date_high

    session.findById("wnd[0]/tbar[0]/btn[11]").press()          # Udfoer
    wait_ready(session)

    session.findById("wnd[0]/mbar/menu[0]/menu[2]").select()    # Udskriv
    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PLIST").text = plist
    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PRTXT").text = prtxt
    session.findById("wnd[1]/tbar[0]/btn[13]").press()

    session.findById("wnd[1]/usr/btnSOFORT_PUSH").press()

    session.findById("wnd[1]/tbar[0]/btn[11]").press()
    session.findById("wnd[0]/tbar[0]/btn[15]").press()          # Afslut, back to main screen
    wait_ready(session)



def read_dyn_field_label(session, field_id: str) -> str:
    """
    Read the on-screen label belonging to a dynamic selection field.

    SAP gives the label its own control with an id derived from the field's, so
    %%DYN002 is described by txt%_%%DYN002_%_APP_%-TEXT. Reading that directly is far
    more reliable than hunting by screen geometry.

    Position matching is kept only as a fallback, and it accepts GuiTextField as well
    as GuiLabel: on this screen the labels are GuiTextField controls, which is why an
    earlier version that only looked at GuiLabel found nothing at all.

    Returns an empty string if no label can be found; the caller decides whether that
    is fatal.
    """
    try:
        text = session.findById(f"wnd[0]/usr/txt%_{field_id}_%_APP_%-TEXT").Text
        if text and text.strip():
            return text.strip()
    except Exception:  # pylint: disable=broad-exception-caught
        pass  # Fall through to the positional search below.

    field = session.findById(f"wnd[0]/usr/ctxt{field_id}-LOW")
    usr = session.findById("wnd[0]/usr")

    best_text = ""
    best_left = -1

    for index in range(usr.Children.Count):
        control = usr.Children(index)
        try:
            if control.Type not in ("GuiLabel", "GuiTextField"):
                continue
            if control.Top != field.Top or control.Left >= field.Left:
                continue
            if control.Left > best_left:
                best_left = control.Left
                best_text = control.Text.strip()
        except Exception:  # pylint: disable=broad-exception-caught
            # SAP GUI scripting raises COM errors for properties a control lacks.
            continue

    return best_text


def get_sap_session(connection_index: int = 0, session_index: int = 0):
    """
    Get an active SAP GUI Scripting session.
    Assumes SAP GUI is open and you're logged in.
    """
    sap_gui_auto = win32com.client.GetObject("SAPGUI")
    application = sap_gui_auto.GetScriptingEngine

    # Depending on SAP GUI version, either Children or Connections works.
    try:
        connection = application.Children(connection_index)
    except Exception:
        connection = application.Connections(connection_index)

    session = connection.Children(session_index)
    return session


def wait_ready(session, timeout_s: int = 30):
    """Wait until SAP session is not busy."""
    start = time.time()
    while getattr(session, "Busy", False):
        if time.time() - start > timeout_s:
            raise TimeoutError("SAP session stayed busy too long.")
        time.sleep(0.1)


def danish_week_number(d: date) -> int:
    """Danish week numbering is ISO week number."""
    return d.isocalendar().week


def build_prtxt(d: date) -> str:
    """
    prtxt format: YYYYMMDD + 'UGE' + weekno (Danish/ISO)
    Example: 20260216UGE7
    """
    weekno = danish_week_number(d)
    return f"{d:%Y%m%d}UGE{weekno}"



