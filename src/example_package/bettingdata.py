# zeljko-betting-data/dap/PRO/2020/Jan/12/29647451/1.167243110.bz2
from requests import Session
import copy
import numpy as np
import pathlib
import pickle
from typing import Optional
import pandas as pd


class BettingData():
    def __init__(self, from_pickle=False, market_path=None, nautilus_path=None, betfair_path=None):
        if from_pickle:
            self.nautilus_file = pd.read_pickle('{}'.format(nautilus_path))  # this gives the nautilus feed.
            self.betfair_file = pd.read_pickle('{}'.format(betfair_path))  # this is raw betfair
        else:
            self.market_path = market_path
            r = requests.get("http://100.125.47.118:8001/v1/nautilus/feed/?filename=/{}".format(market_path))
            self.raw_data = pickle.loads(r.content)  # this gives the nautilus feed.
            self.dap_file = BettingDataClient().betfair.read_dap_file('{}'.format(market_path))
        self.order_book_deltas = [element for element in self.nautilus_file if
                                  type(element).__name__ == 'OrderBookDeltas']
        self.trades = [element for element in self.nautilus_file if type(element).__name__ == 'TradeTick']
        self.runners = self.betfair_file[0]['mc'][0]['marketDefinition']['runners']
        self.team_map = {}
        for runner in self.runners:
            self.team_map[runner['id']] = runner['name']
        self.first_team_id = str(list(self.team_map.keys())[0])

    def combine_odds(self):
        home_buys = {}
        home_sells = {}
        away_buys = {}
        away_sells = {}
        overall = {}
        for i, d in enumerate(self.order_book_deltas):
            team = d.instrument_id.value.split(',')[-2]
            if team == self.first_team_id:
                for od in d.deltas:
                    a = od.action
                    o = od.order
                    if a == 2:  # if update
                        if o.side == 2:  # if sell
                            home_sells[o.price] = o.size
                        elif o.side == 1:
                            home_buys[o.price] = o.size
                    elif a == 3:  # if  delete
                        try:
                            if o.side == 2:
                                del home_sells[o.price]
                            else:
                                del home_buys[o.price]
                        except:
                            pass
                overall[(d.ts_event, team)] = [copy.deepcopy(home_buys), copy.deepcopy(home_sells)]
            else:
                for od in d.deltas:
                    a = od.action
                    o = od.order
                    if a == 2:  # if update
                        if o.side == 2:  # if sell
                            away_sells[o.price] = o.size
                        elif o.side == 1:
                            away_buys[o.price] = o.size
                    elif a == 3:  # if  delete
                        try:
                            if o.side == 2:
                                del away_sells[o.price]
                            else:
                                del away_buys[o.price]
                        except:
                            pass
                overall[(d.ts_event, team)] = [copy.deepcopy(away_buys), copy.deepcopy(away_sells)]
        return overall

    def bbo(self):
        overall = self.combine_odds()

        for m in overall.values():
            bids = m[0]
            if len(bids) == 0:
                m[0] = (0, 0)
            else:
                m[0] = sorted(bids.items())[-1]
            offers = m[1]
            if len(offers) == 0:
                m[1] = (1, 0)
            else:
                m[1] = sorted(offers.items())[0]
        return overall

    def populate_trade_df(self):
        trade_dict = {}
        for t in self.trades:
            team = t.instrument_id.value.split(',')[-2]
            trade_dict[(t.ts_event, team)] = (t.price.as_double(), t.size.as_double())
        trades = pd.DataFrame.from_dict(trade_dict, orient='index', columns=['trade_price', 'cumulative_trade_volume'])
        trades['team'] = [x[1] for x in trades.index]
        # todo: unhardcode based on competition
        trades['readable'] = [pd.to_datetime(x[0]) for x in trades.index]
        trades = trades.reset_index(drop=True)
        trades.loc[trades.team != self.first_team_id, 'trade_price'] = 1 - trades.loc[
            trades.team != self.first_team_id, 'trade_price']
        return trades

    def arb_market_df(self):
        betting = pd.DataFrame.from_dict(self.bbo(), orient='index', columns=['bb', 'bo'])
        betting['best_bid_volume'] = betting.bb.apply(lambda x: x[1])
        betting['best_bid_price'] = betting.bb.apply(lambda x: x[0])
        betting['best_ask_price'] = betting.bo.apply(lambda x: x[0])
        betting['best_ask_volume'] = betting.bo.apply(lambda x: x[1])
        betting['team'] = [x[1] for x in betting.index]
        # todo: unhardcode based on competition
        betting['readable'] = [pd.to_datetime(x[0]) for x in betting.index]
        betting = betting.drop(['bb', 'bo'], axis=1)
        betting = betting.reset_index(drop=True)
        betting['bb_copy'] = betting.best_bid_price
        betting['bo_copy'] = betting.best_ask_price
        betting['bbv_copy'] = betting.best_bid_volume
        betting['bov_copy'] = betting.best_ask_volume

        betting.loc[betting.team != self.first_team_id, 'best_bid_price'] = 1 - betting.loc[
            betting.team != self.first_team_id, 'bo_copy']
        betting.loc[betting.team != self.first_team_id, 'best_ask_price'] = 1 - betting.loc[
            betting.team != self.first_team_id, 'bb_copy']
        betting.loc[betting.team != self.first_team_id, 'best_bid_volume'] = betting.loc[
            betting.team != self.first_team_id, 'bov_copy']
        betting.loc[betting.team != self.first_team_id, 'best_ask_volume'] = betting.loc[
            betting.team != self.first_team_id, 'bbv_copy']
        betting = betting.drop(['bb_copy', 'bo_copy', 'bbv_copy', 'bov_copy'], axis=1)
        return betting

    def combine_trade_and_market_df(self):
        market_df = self.arb_market_df()
        home = market_df[lambda x: x.team == self.first_team_id]
        away = market_df[lambda x: x.team != self.first_team_id]
        hona = pd.merge_asof(home, away, on='readable', suffixes=('_h', '_a'))
        aonh = pd.merge_asof(away, home, on='readable', suffixes=('_a', '_h'))
        hona['best_combined_bid'] = np.maximum(hona.best_bid_price_h, hona.best_bid_price_a)
        hona['best_combined_offer'] = np.minimum(hona.best_ask_price_h, hona.best_ask_price_a)
        aonh['best_combined_bid'] = np.maximum(aonh.best_bid_price_h, aonh.best_bid_price_a)
        aonh['best_combined_offer'] = np.minimum(aonh.best_ask_price_h, aonh.best_ask_price_a)
        combined = pd.concat([aonh, hona]).sort_values(['readable'])
        combined = combined[['readable', 'best_combined_bid', 'best_combined_offer']].reset_index(drop=True)
        trades = self.populate_trade_df()
        mkts_and_trades = combined.merge(trades, how='left', on='readable', suffixes=('_mkt', '_trd'))
        return mkts_and_trades


class Endpoint:
    def __init__(self, host="0.0.0.0", port="8000", version="v1"):  # noqa: S104
        self.session = Session()
        self.host = host
        self.port = port
        self.version = version

    def request(self, path, method="GET", **kwargs):
        resp = self.session.request(method=method, url=self.make_url(path=path), **kwargs)
        resp.raise_for_status()
        return resp

    def make_url(self, path) -> str:
        return f"http://{self.host}:{self.port}/{self.version}/{path}"

    def ping(self):
        return self.request(path="")


class Capture(Endpoint):
    router = "capture"

    def files(self, source: str):
        return self.request(path=f"{self.router}/files/{source}").json()

    def metadata(self, source: str):
        return pd.DataFrame(self.request(path=f"{self.router}/metadata/{source}").json())

    def data(self, source: str, key: str):
        return self.request(path=f"{self.router}/data/{source}/{key}").json()


class Scoreboard(Endpoint):
    router = "scoreboard"

    def scores_historic(self, game_id: str):
        return self.request(path=f"{self.router}/scores/historic/{game_id}").json()

    def live_events(self, sport: str):
        return self.request(path=f"{self.router}/metadata/live/{sport}").json()

    def metadata(self, game_id: str):
        return self.request(path=f"{self.router}/metadata/{game_id}").json()

    def sports(self):
        return self.request(path=f"{self.router}/sports").json()

    def categories(self, sport: str):
        return self.request(path=f"{self.router}/sports/{sport}").json()

    def competitions(self, sport: str, category: str):
        return self.request(path=f"{self.router}/sports/{sport}/{category}").json()

    def seasons(self, sport: str, category: str, competition: str):
        return self.request(path=f"{self.router}/sports/{sport}/{category}/{competition}").json()

    def matches(self, sport: str, category: str, competition: str, season: str):
        return self.request(path=f"{self.router}/sports/{sport}/{category}/{competition}/{season}").json()


class Betfair(Endpoint):
    router = "betfair"

    def stream_historic_list(self):
        return [pathlib.Path(x).name for x in self.request(path=f"{self.router}/stream/historic/").json()]

    def stream_historic_get(self, market_id: str):
        return self.request(path=f"{self.router}/stream/historic/{market_id}").json()

    def market_definition_short(self, market_id: str):
        return self.request(path=f"{self.router}/market_definition_short/{market_id}").json()

    def market_definition_dap(self, filename: str):
        return self.request(path=f"{self.router}/dap/market_definition", params={'filename': filename}).json()

    def live_markets(self, **kwargs):
        return self.request(path=f"{self.router}/live/catalog", params=kwargs).json()

    def list_dap_files(self):
        return self.request(path=f"{self.router}/dap/list_files").json()

    def read_dap_file(self, filename: str):
        return self.request(path=f"{self.router}/dap/historic", params={'filename': filename}).json()


class Oddsportal(Endpoint):

    router = "odds"

    def sports(self):
        return self.request(path=f"{self.router}/sports").json()

    def competitions(self, sport: str):
        return self.request(path=f"{self.router}/competitions/{sport}").json()

    def seasons(self, sport: str, country: str, competition: str):
        return self.request(path=f"{self.router}/seasons/{sport}/{country}/{competition}").json()

    def events(self, sport: str, country: str, competition: str, season: str):
        return self.request(path=f"{self.router}/events/{sport}/{country}/{competition}/{season}").json()

    def metadata(self, game_id: Optional[str] = None, match_url: Optional[str] = None):
        params = {"match_url": match_url} if match_url is not None else {"game_id": game_id}
        return self.request(path=f"{self.router}/metadata/", params=params).json()

    def odds(
        self,
        game_id: Optional[str] = None,
        match_url: Optional[str] = None,
        bet_type: str = "home_away",
        scope_id: str = "full_time_inc_overtime",
        raw=False,
        opening_odds=True,
        history=False,
    ):
        if history:
            raise NotImplementedError
        params = {"match_url": match_url} if match_url is not None else {"game_id": game_id}
        return self.request(
            path=f"{self.router}/odds/{bet_type}/{scope_id}/",
            params={
                "raw": raw,
                "opening_odd": opening_odds,
                "history": history,
                **params,
            },
        ).json()

    def opening_odds(
        self,
        game_id: Optional[str] = None,
        match_url: Optional[str] = None,
        bet_type: str = "home_away",
        scope_id: str = "full_time_inc_overtime",
    ):
        params = {"match_url": match_url} if match_url is not None else {"game_id": game_id}
        return self.request(path=f"{self.router}/opening_odds_theo/{bet_type}/{scope_id}", params=params).json()


class Nautilus(Endpoint):
    router = "nautilus"

    def feed(self, market_id):
        resp = self.request(path=f"{self.router}/feed/{market_id}")
        return pickle.loads(resp.content)  # noqa: S#01


class NBA(Endpoint):
    router = "nba"

    def seasons(self):
        resp = self.request(path=f"{self.router}/seasons")
        return resp.json()

    def events(self, season: str):
        resp = self.request(path=f"{self.router}/events/{season}")
        return resp.json()

    def play_by_play(self, game_id: str):
        resp = self.request(path=f"{self.router}/play_by_play/{game_id}")
        return resp.json()


class BettingDataClient:
    def __init__(self, host="100.125.47.118", port="8001", version="v1"):  # noqa: S104
        self.base = Endpoint(host=host, port=port, version=version)
        self.capture = Capture(host=host, port=port, version=version)
        self.scores = Scoreboard(host=host, port=port, version=version)
        self.betfair = Betfair(host=host, port=port, version=version)
        self.nautilus = Nautilus(host=host, port=port, version=version)
        self.nba = NBA(host=host, port=port, version=version)
        self.odds = Oddsportal(host=host, port=port, version=version)

    def ping(self):
        return self.base.ping()

# if __name__ == "__main__":
#     c = BettingDataClient()
#     c.capture.files("betfair")
