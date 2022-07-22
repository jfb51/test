from typing import Optional

import pandas as pd
from nautilus_trader.common.actor import Actor, ActorConfig
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core.data import Data
from nautilus_trader.core.datetime import secs_to_nanos, unix_nanos_to_dt
# from nautilus_trader.model.data.bar import Bar, BarSpecification
from nautilus_trader.model.data.base import DataType
from nautilus_trader.model.identifiers import InstrumentId
from adapter import CricInfoEnvelope
import livematchsim
import cricinfodata
import copy
# from sklearn.linear_model import LinearRegression
# from sklearn.metrics import r2_score
# from util import bars_to_dataframe, make_bar_type


# class PredictedPriceConfig(ActorConfig):
#     source_symbol: str
#     target_symbol: str
#     bar_spec: str = "10-SECOND-LAST"
#     min_model_timedelta: str = "1D"


class WinProbabilityActor(Actor):
    def __init__(self, match_id, series_id, career_bowling_data,
                 career_batting_data, wicket_models, runs_models, threes, wide_models,
                 nb_models, bowling_models, bounds=None, debug=False):
        super().__init__()

        self.symbol = 'BETFAIR?'
        self.id = InstrumentId.from_str(self.symbol) # need help for how to actually get this source symbol
        self.jbl_prob = None
        self.match_id = match_id
        self.series_id = series_id
        self.career_bowling_data = career_bowling_data
        self.career_batting_data = career_batting_data
        self.wicket_models = wicket_models
        self.runs_models = runs_models
        self.threes = threes
        self.wide_models = wide_models
        self.nb_models = nb_models
        self.bowling_models = bowling_models
        self.bounds = bounds
        self.debug = debug
        self.pre_match_probabilities = {}

    def on_start(self):
        # I need to have received the pre-match piece of data, aka the "first" datapoint.
        self.subscribe_data(data_type=DataType(PreMatchEnvelope)) # not 100% sure how to create this in adapter.
        self.subscribe_data(data_type=DataType(CricInfoEnvelope))

    def on_data(self, data: Data):
        if isinstance(data, PreMatchEnvelope):
            self.do_prematch_shit(data)
        if isinstance(data, CricInfoEnvelope):
            self.do_in_game_shit(data)
            self.do_in_game_shit(data)

        # self._check_model_fit(bar)
        # self._predict(bar)

    def do_prematch_shit(self, data):
        # in this method we take in a prematchstate and run the game over 240 possible targets to chase.
        # The output is a dict mapping score : probability.
        self.pre_game = cricinfodata.PreMatchState(data)
        self.lms = cricinfodata.LiveMatchState(self.pre_game)

        lm_sim = livematchsim.LiveMatchSimulator(self.match_id, self.series_id, self.pre_game,
                                                 self.career_bowling_data, self.career_batting_data,
                                                 self.wickets_models, self.runs_models,
                                                 self.threes, self.wides_models, self.nb_models,
                                                 self.bowling_models, self.bounds, self.debug)

        n = 1000
        lm_sim.prep_obj()
        self.lms.change_innings(self.pre_game) #hmm, problematic, how do we get this object back to normal.
        winner = {}
        for i in range(n):
            winner[i] = lm_sim.parallel_function_tgt(self.lms)

        df = pd.DataFrame(winner)
        prob_per_score = (df.sum(axis=1) / len(df.columns)).to_dict()

        self.pre_match_probabilities = prob_per_score

    def do_in_game_shit(self, data):
        # In this method, I will need to:
        # 1. Update the live match state with the latest cricinfo data.
        self.lms.update(data) #maybe the innings update just works by itself once the data comes in?

        # 2. Run this through innings sim 1000x to get a score (1st inns) or result (2nd inns)
        lm_sim = livematchsim.LiveMatchSimulator(self.match_id, self.series_id, self.pre_game,
                                                 self.career_bowling_data, self.career_batting_data,
                                                 self.wickets_models, self.runs_models,
                                                 self.threes, self.wides_models, self.nb_models,
                                                 self.bowling_models, self.bounds, self.debug)

        if self.lms.innings == 1:
            n = 1000
            predicted_scores = {}
            for i in range(n):
                mc = copy.deepcopy(lm_sim) # is this necessary?
                predicted_scores[i] = mc.sim_live_match('innings', self.lms)
            # should have i:score
            # 3. Sumproduct with pre_match_probs if necessary
            for k, v in list(predicted_scores.items()):
                predicted_scores[k] = self.pre_match_probabilities[v]
            self.jbl_prob = sum(list(predicted_scores.values))/n
        else:
            n = 1000
            predicted_scores = {}
            for i in range(n):
                mc = copy.deepcopy(lm_sim) # is this necessary?
                predicted_scores[i] = mc.sim_live_match('innings', self.lms)
            # should have i:score
            for k, v in list(predicted_scores.items()):
                predicted_scores[k] = self.pre_match_probabilities[v]
            self.jbl_prob = sum(list(predicted_scores.values))/n




        n = 1000
        lm_sim.prep_obj()
        lms.change_innings(pre_game)
        winner = {}
        for i in range(n):
            winner[i] = lm_sim.parallel_function_tgt(lms)
        self.pre_match_probabilities = winner



    @property
    def data_length_valid(self) -> bool:
        return self._check_first_tick(self.source_id) and self._check_first_tick(self.target_id)

    @property
    def has_fit_model_today(self):
        return unix_nanos_to_dt(self.clock.timestamp_ns()).date() == self._last_model.date()

    def _check_first_tick(self, instrument_id) -> bool:
        """Check we have enough bar data for this `instrument_id`, according to `min_model_timedelta`"""
        bars = self.cache.bars(bar_type=make_bar_type(instrument_id, bar_spec=self.bar_spec))
        if not bars:
            return False
        delta = self.clock.timestamp_ns() - bars[-1].ts_init
        return delta > self._min_model_timedelta

    def _check_model_fit(self, bar: Bar):
        # Check we have the minimum required data
        if not self.data_length_valid:
            return

        # Check we haven't fit a model yet today
        if self.has_fit_model_today:
            return

        # Generate a dataframe from cached bar data
        df = bars_to_dataframe(
            source_id=self.source_id.value,
            source_bars=self.cache.bars(bar_type=make_bar_type(self.source_id, bar_spec=self.bar_spec)),
            target_id=self.target_id.value,
            target_bars=self.cache.bars(bar_type=make_bar_type(self.target_id, bar_spec=self.bar_spec)),
        )

        # Format the arrays for scikit-learn
        X = df.loc[:, self.source_id.value].astype(float).values.reshape(-1, 1)
        Y = df.loc[:, self.target_id.value].astype(float).values.reshape(-1, 1)

        # Fit a model
        self.model = LinearRegression(fit_intercept=False)
        self.model.fit(X, Y)
        self.log.info(
            f"Fit model @ {unix_nanos_to_dt(bar.ts_init)}, r2: {r2_score(Y, self.model.predict(X))}",
            color=LogColor.BLUE,
        )
        self._last_model = unix_nanos_to_dt(bar.ts_init)

        # Record std dev of predictions (used for scaling our order price)
        pred = self.model.predict(X)
        errors = pred - Y
        std_pred = errors.std()

        # The model slope is our hedge ratio (the ratio of source
        self.hedge_ratio = float(self.model.coef_[0][0])
        self.log.info(f"Computed hedge_ratio={self.hedge_ratio:0.4f}", color=LogColor.BLUE)

        # Publish model
        model_update = ModelUpdate(
            model=self.model, hedge_ratio=self.hedge_ratio, std_prediction=std_pred, ts_init=bar.ts_init
        )
        self.publish_data(
            data_type=DataType(ModelUpdate, metadata={"instrument_id": self.target_id.value}), data=model_update
        )

    def _predict(self, bar: Bar):
        if self.model is not None and bar.type.instrument_id == self.source_id:
            pred = self.model.predict([[bar.close]])[0][0]
            prediction = Prediction(instrument_id=self.target_id, prediction=pred, ts_init=bar.ts_init)
            self.publish_data(
                data_type=DataType(Prediction, metadata={"instrument_id": self.target_id.value}), data=prediction
            )


class ModelUpdate(Data):
    def __init__(
        self,
        model: LinearRegression,
        hedge_ratio: float,
        std_prediction: float,
        ts_init: int,
    ):
        super().__init__(ts_init=ts_init, ts_event=ts_init)
        self.model = model
        self.hedge_ratio = hedge_ratio
        self.std_prediction = std_prediction


class Prediction(Data):
    def __init__(
        self,
        instrument_id: str,
        prediction: float,
        ts_init: int,
    ):
        super().__init__(ts_init=ts_init, ts_event=ts_init)
        self.instrument_id = instrument_id
        self.prediction = prediction