"""This module contains the main process of the robot."""

from __future__ import annotations

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from OpenOrchestrator.database.queues import QueueElement

import time
from datetime import date, timedelta
import uuid

import win32com.client


# pylint: disable-next=unused-argument
def process(orchestrator_connection: OrchestratorConnection, queue_element: QueueElement | None = None) -> None:
    orchestrator_connection.log_trace("Running process.")

    session = get_sap_session(connection_index=0, session_index=0)

    # Date logic:
    # date_high = yesterday
    # date_low = 7 days before date_high
    high = date.today() - timedelta(days=1)
    low = high - timedelta(days=7)

    date_high = high.strftime("%d.%m.%Y")
    date_low = low.strftime("%d.%m.%Y")

    # Print params
    plist = "ROBOT"
    prtxt = build_prtxt(date.today())  # matches your example: uses "today" date for the label

    # Optional: if you REALLY want UUID too:
    prtxt = f"{build_prtxt(date.today())}_{uuid.uuid4().hex[:8]}"

    orchestrator_connection.log_trace(f"Using date range {date_low} - {date_high} and prtxt={prtxt}")
    wait_ready(session)

    
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/tbar[0]/okcd").text = "CJI3"
    session.findById("wnd[0]").sendVKey(0)

    session.findById("wnd[0]/tbar[1]/btn[17]").press()

    session.findById("wnd[1]/usr/txtENAME-LOW").setFocus()
    session.findById("wnd[1]/usr/txtENAME-LOW").caretPosition = 4
    session.findById("wnd[1]").sendVKey(2)

    session.findById("wnd[2]").close()

    session.findById("wnd[1]/usr/txtV-LOW").text = ""
    session.findById("wnd[1]/usr/txtENAME-LOW").text = ""
    session.findById("wnd[1]/usr/txtV-LOW").setFocus()
    session.findById("wnd[1]/usr/txtV-LOW").caretPosition = 0

    session.findById("wnd[1]/tbar[0]/btn[8]").press()

    alv = session.findById("wnd[1]/usr/cntlALV_CONTAINER_1/shellcont/shell")
    alv.currentCellRow = 72
    alv.firstVisibleRow = 60
    alv.selectedRows = "72"
    alv.doubleClickCurrentCell()

    session.findById("wnd[0]").sendVKey(21)
    session.findById("wnd[0]/usr/ctxt%%DYN002-HIGH").setFocus()
    session.findById("wnd[0]/usr/ctxt%%DYN002-HIGH").caretPosition = 3
    session.findById("wnd[0]").sendVKey(2)
    session.findById("wnd[1]").close()

    session.findById("wnd[0]/usr/ctxt%%DYN002-LOW").text = date_low
    session.findById("wnd[0]/usr/ctxt%%DYN002-HIGH").text = date_high
    session.findById("wnd[0]/usr/ctxt%%DYN002-HIGH").caretPosition = len(date_high)

    session.findById("wnd[0]/tbar[0]/btn[11]").press()

    session.findById("wnd[0]/mbar/menu[0]/menu[2]").select()

    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PLIST").text = plist
    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PRTXT").text = prtxt
    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PRTXT").setFocus()
    session.findById("wnd[1]/usr/subSUBSCREEN:SAPLSPRI:0600/txtPRI_PARAMS-PRTXT").caretPosition = len(prtxt)

    session.findById("wnd[1]/tbar[0]/btn[13]").press()
    session.findById("wnd[1]/usr/btnSOFORT_PUSH").press()

    session.findById("wnd[1]/tbar[0]/btn[11]").press()
    session.findById("wnd[0]/tbar[0]/btn[15]").press()

    orchestrator_connection.create_queue_element("SAPCJI3", prtxt, prtxt, "SAPCJI3Dispatcher")



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



