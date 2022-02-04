from example_package.matchsim import HistoricMatchSimulator
from example_package.bettingdata import BettingData
import numpy as np
import pandas as pd
import requests
from example_package.util import kelly_bet


class TradingStrategy:
    def __init__(self, match_id, series_id, match_row, historic_match_data, player_info,
                 wicket_model, runs, wms, nbs, num_sims,
                 from_pickle, nautilus_path, smooth_probs=True):
        self.match_id = match_id
        self.series_id = series_id
        self.num_sims = num_sims
        self.smooth_probs = smooth_probs
        self.nautilus_path = nautilus_path
        self.from_pickle = from_pickle
        self.match = HistoricMatchSimulator(match_id, match_row, historic_match_data, player_info,
                                            wicket_model, runs, wms, nbs)
        self.bd = BettingData(from_pickle=self.from_pickle, nautilus_path=self.nautilus_path)
        self.betting_data = self.bd.combine_trade_and_market_df()
        self.betting_reference_team = self.bd.team_map[self.bd.first_team_id]
        if self.betting_reference_team!=self.match.chasing_team:
            self.negate_sim_probabilities=True

    def simulate_historic_match(self):
        # these probabilities are in terms of the chasing team - need to make this consistent with the odds information
        print('simulating first innings scores...')
        fi_scores = self.match.first_innings_scores(self.num_sims)
        print('simulating first innings probabilities...')
        score_map = self.match.precalc_win_probs_for_score_array(self.num_sims, self.smooth_probs)
        print('simulating second innings probabilities...')
        second_innings_win_pct = self.match.historic_second_innings_sim(self.num_sims)
        second_innings_lower = [v[0] - v[1] for v in second_innings_win_pct.values()]
        second_innings_upper = [v[0] + v[1] for v in second_innings_win_pct.values()]
        first_innings_p_win_lower = {k: sum([(score_map[score][0] - score_map[score][1]) / self.num_sims
                                             for score in b]) for k, b in fi_scores.items()}
        first_innings_p_win_upper = {k: sum([(score_map[score][0] + score_map[score][1]) / self.num_sims
                                             for score in b]) for k, b in fi_scores.items()}
        raw_probs = list(first_innings_p_win_lower.values()) + second_innings_lower, list(
            first_innings_p_win_upper.values()) + second_innings_upper
        if self.negate_sim_probabilities:
            return 1 - np.array(raw_probs[1]), 1 - np.array(raw_probs[0])
        else:
            return raw_probs

    def scrape_comms(self):
        l = list()
        for innings in [1, 2]:
            for over in np.arange(2, 21, 2):  # will this be ok for a shorter innings.
                r = requests.get(
                    "https://hs-consumer-api.espncricinfo.com/v1/pages/match/comments?lang=en&seriesId={}&matchId={}"
                    "&inningNumber={}&commentType=ALL&fromInningOver={}&sortDirection=DESC".format(
                        self.series_id, self.match_id, innings, over))
                l.append(r.json())
        ball_to_timestamp_map = []
        for overs in l:
            for ball in overs['comments']:
                ball_to_timestamp_map.append((ball['inningNumber'], ball['oversUnique'], ball['timestamp']))
        ts_df = pd.DataFrame(ball_to_timestamp_map, columns=['innings', 'ball', 'comm_ts']).sort_values(
            ['innings', 'ball'])
        ts_df = ts_df.reset_index(drop=True)
        return ts_df

    def merge_comms_playing_and_betting_data(self):
        comms_df = self.scrape_comms()
        match_df = self.match.historic_match_data
        betting_df = self.betting_data
        match_df = pd.concat([match_df, comms_df[['ball', 'comm_ts']]], axis=1)
        # todo: unhardcode tz
        match_df['local_comm_ts'] = match_df['comm_ts'].apply(lambda x: pd.to_datetime(x).tz_localize(None))
        match_df = pd.merge_asof(match_df, betting_df, left_on='local_comm_ts', right_on='readable')
        return match_df

    def run_simulation_and_wagering(self, pass_sim_data=False, sim_data=None):
        if not pass_sim_data:
            simulated_probabilities = self.simulate_historic_match()
        else:
            simulated_probabilities = sim_data
        merged_data = self.merge_comms_playing_and_betting_data()
        merged_data['estimated_probability_lower'] = simulated_probabilities[0]
        merged_data['estimated_probability_upper'] = simulated_probabilities[1]
        merged_data['decimal_bid'] = merged_data.best_combined_bid.apply(lambda x: 1 / x)
        merged_data['decimal_offer'] = merged_data.best_combined_offer.apply(lambda x: 1 / x)
        merged_data['edge'] = np.maximum(merged_data.estimated_probability_lower - merged_data.best_combined_offer,
                                         merged_data.best_combined_bid - merged_data.estimated_probability_upper)
        merged_data['side'] = ["Back" if pl > o else "Lay" if pu < b else "None" for (b, o, pl, pu) in
                               zip(merged_data.best_combined_bid, merged_data.best_combined_offer,
                                   merged_data.estimated_probability_lower, merged_data.estimated_probability_upper)]
        merged_data['position_size'] = merged_data.apply(lambda x: kelly_bet(x), axis=1)
        merged_data['change_in_position'] = merged_data.position_size.diff()
        merged_data['shifted_position'] = merged_data.position_size.shift()
        merged_data['shifted_bb'] = merged_data.decimal_bid.shift()
        merged_data['shifted_bo'] = merged_data.decimal_offer.shift()
        merged_data['period_pnl'] = [(so / bb - 1) * sp if np.sign(sp) > 0 else (sb / bo - 1) * sp for
                                     (bb, bo, sb, so, sp) in
                                     zip(merged_data.decimal_bid, merged_data.decimal_offer,
                                         merged_data.shifted_bb, merged_data.shifted_bo, merged_data.shifted_position)]
        merged_data['cumulative_pnl'] = np.cumsum(merged_data.period_pnl)

        return merged_data

