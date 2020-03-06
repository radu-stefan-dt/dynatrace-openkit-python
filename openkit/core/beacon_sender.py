import logging
import time
from threading import Thread, Event, RLock
from typing import Optional, List

from core.communication.beacon_states import BeaconSendingInitState, AbstractBeaconSendingState
from core.configuration.server_configuration import ServerConfiguration
from core.session import SessionImpl

from requests import Response


from protocol.http_client import HttpClient


class BeaconSendingContext:
    def __init__(self, logger: logging.Logger, http_client: HttpClient):
        self.logger = logger
        self.http_client = http_client
        self.server_configuration = ServerConfiguration()  # Default Values
        self.last_response_attributes = None  # TODO: This is a class protocol.ResponseAttributes

        self.sessions: List[SessionImpl] = []

        self.last_open_session_beacon_send_time = None
        self.last_status_check_time = None
        self.shutdown_requested = False
        self.init_succeded = False

        self.current_state: AbstractBeaconSendingState = BeaconSendingInitState()
        self.next_state = None

        self._lock = RLock()

    @property
    def terminal(self):
        return self.current_state.terminal

    @property
    def server_id(self):
        return self.http_client.server_id

    @property
    def capture_on(self) -> bool:
        with self._lock:
            return self.server_configuration.capture_enabled

    @property
    def last_server_configuration(self) -> ServerConfiguration:
        with self._lock:
            return self.server_configuration

    def disable_capture(self):
        with self._lock:
            self.server_configuration.capture_enabled = False

    def clear_all_session_data(self):
        # TODO: Implement Session clear
        pass

    def execute_current_state(self):
        self.next_state = None
        self.current_state.execute(self)

        if self.next_state is not None and self.next_state != self.current_state:
            self.logger.debug(f"State change from {self.current_state} to {self.next_state}")

        self.current_state = self.next_state

    def sleep(self, millis):
        time.sleep(millis / 1000)

    def handle_response(self, response: Response):

        if response is None or response.status_code >= 400:
            return

        # TODO: Implement server response parsing

    def get_configuration_timestamp(self):
        return 0

    def add_session(self, session):
        self.sessions.append(session)


class BeaconSenderThread(Thread):
    def __init__(self, logger: logging.Logger, context: BeaconSendingContext):
        Thread.__init__(self, name="BeaconSenderThread")
        self.logger = logger
        self.shutdown_flag = Event()
        self.context = context

    def run(self):
        self.logger.debug("BeaconSenderThread - Running")
        while not self.context.terminal:
            self.context.execute_current_state()
            if self.shutdown_flag.is_set():
                break

        self.logger.debug("BeaconSenderThread - Exiting")


class BeaconSender:
    def __init__(self, logger: logging.Logger, http_client: HttpClient):
        self.logger = logger
        self.context = BeaconSendingContext(logger, http_client)
        self.thread: Optional[BeaconSenderThread] = None

    @property
    def server_id(self):
        return self.context.server_id

    def initalize(self):
        self.thread = BeaconSenderThread(self.logger, self.context)
        self.thread.start()

    def shutdown(self):
        if self.thread is not None:
            self.thread.shutdown_flag.set()

    def add_session(self, session):
        self.logger.debug(f"Adding session {session}")
        self.context.add_session(session)

    @property
    def last_server_configuration(self):
        return self.context.last_server_configuration
