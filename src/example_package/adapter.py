import asyncio
from typing import Dict

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.clock import LiveClock
from nautilus_trader.common.logging import Logger
from nautilus_trader.core.data import Data
from nautilus_trader.live.data_client import LiveDataClient
from nautilus_trader.model.data.base import DataType
from response import LatestResponse
import msgspec
import requests
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.msgbus.bus import MessageBus


class CricinfoLiveDataClient(LiveDataClient):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        cache: Cache,
        msgbus: MessageBus,
        clock: LiveClock,
        logger: Logger,
        config: Dict = None,
    ):
        super().__init__(
            loop=loop,
            client_id=ClientId("cricinfo"),
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            logger=logger,
            config=config,
    )
        self.sport_name = 'cricket'
        self.series_id = 1307289
        self.match_id = 1307297
        self._is_running = False
        self._cric_connected = False
        self._loop = asyncio.get_event_loop()

    def connect(self):
        """
        Connect the client.
        """
        self._log.info("Connecting...")
        self._loop.create_task(self.loop())
        self._set_connected(True)
        assert self.is_connected

    def disconnect(self):
        """
        Disconnect the client.
        """
        self._log.info("Disconnecting...")
        self._is_running = False
        self._loop.create_task(self._disconnect())

    async def _disconnect(self):
        self._log.info("Disconnecting ...")
        while self._cric_connected:
            await asyncio.sleep(0.1)
        self._set_connected(False)


    def get_cricinfo_data(self):
        latest = requests.get(
            "https://hs-consumer-api.espncricinfo.com/v1/pages/match/details?lang=en&seriesId={}&matchId={}&latest=true".format(self.series_id, self.match_id))
        data = msgspec.json.decode(latest.content, type=LatestResponse)
        return data

    async def loop(self):
        self._cric_connected = True
        self._is_running = True
        while self._is_running:
            resp = self.get_cricinfo_data()
            self._handle_raw_data(data=resp)
            self._cric_connected = False

    # -- HANDLERS --------------------------------------------------------------------------------------
    def _handle_raw_data(self, data):
        parsed: CricInfoEnvelope = CricInfoEnvelope(data, ts_init=0)
        self._handle_data(data=parsed)

def make_generic_data(data: Data):
    from nautilus_trader.model.data.base import GenericData
    return GenericData(
        data_type=DataType(type=data.__class__),
        data=data
)

class CricInfoEnvelope(Data):
    def __init__(self, cric_info, ts_init: int):
        super().__init__(ts_init, ts_init)
        self.data = msgspec.json.encode(cric_info)



async def __main__():
    adapter = CricinfoLiveDataClient()
    adapter.connect()
    await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(__main__())
