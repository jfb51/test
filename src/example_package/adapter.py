import asyncio
from typing import Dict

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.clock import LiveClock
from nautilus_trader.common.logging import Logger
from nautilus_trader.live.data_client import LiveDataClient
from nautilus_trader.model.data.base import DataType
from nautilus_trader.model.data.base import Data
from example_package.response import LatestResponse
import msgspec
import requests
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.msgbus.bus import MessageBus


class CricinfoLiveDataClient():
    def __init__(
        self,
    #     loop: asyncio.AbstractEventLoop,
    #     cache: Cache,
    #     msgbus: MessageBus,
    #     clock: LiveClock,
    #     logger: Logger,
    #     config: Dict = None,
    # ):
    #     super().__init__(
    #         loop=loop,
    #         client_id=ClientId("FLASHSCORE"),
    #         msgbus=msgbus,
    #         cache=cache,
    #         clock=clock,
    #         logger=logger,
    #         config=config,
    ):
        super().__init__()
        self.sport_name = 'cricket'
        self.series_id = 1307289
        self.match_id = 1307297
        self._is_running = False
        self._cric_connected = False

    def connect(self):
        """
        Connect the client.
        """
        # self._log.info("Connecting...")
        self._loop.create_task(self.loop())
        self._set_connected(True)
        assert self.is_connected

    def disconnect(self):
        """
        Disconnect the client.
        """
        # self._log.info("Disconnecting...")
        self._is_running = False
        self._loop.create_task(self._disconnect())

    async def _disconnect(self):
        # self._log.info("Disconnecting ...")
        while self._cric_connected:
            await asyncio.sleep(0.1)
        self._set_connected(False)

    def subscribe(self, data_type: DataType):
        self._log.debug(f"Received subscribe: {data_type}")

    def get_cricinfo_data(self):
        latest = requests.get(
            "https://hs-consumer-api.espncricinfo.com/v1/pages/match/details?lang=en&seriesId={}&matchId={}&latest=true".format(self.series_id, self.match_id))
        data = msgspec.json.decode(latest.content, type=LatestResponse)
        return data

    def loop(self):
        self._cric_connected = True
        while self._is_running:
            resp = self.get_cricinfo_data()
            self._handle_raw_data(data=resp)
            self._cric_connected = False

    # -- HANDLERS --------------------------------------------------------------------------------------
    def _handle_raw_data(self, resp):
        parsed: CricInfoEnvelope = CricInfoEnvelope(resp)
        self._handle_data(data=parsed)


class CricInfoEnvelope(Data):
    def init(self, cric_info, ts_init: int):
        self.data = msgspec.json.encode(cric_info)


def __main__():
    adapter = CricinfoLiveDataClient()
    adapter.connect()
