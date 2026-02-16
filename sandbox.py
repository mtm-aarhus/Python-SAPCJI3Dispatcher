"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection

from robot_framework.process import process
from robot_framework import reset

import os

# pylint: disable-next=unused-argum
orchestrator_connection = OrchestratorConnection(
    "SAPCJI3Dispatcher",
    os.getenv("OpenOrchestratorSQL"),
    os.getenv("OpenOrchestratorKey"),
    None,
    None
)

reset.reset(orchestrator_connection)

process(orchestrator_connection)