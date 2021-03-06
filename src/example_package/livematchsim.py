from liveteam import LiveTeam
import copy
import pandas as pd
import cloudpickle
from scipy.signal import savgol_filter
from collections import OrderedDict
import numpy as np
import math
from collections import Counter
from util import calculate_probit_model_probability, calculate_mnlogit_model_probabilities, \
    calculate_logit_model_probability, find_le, SlimRegModel, update_career_bowling, update_career_batting
from random import choices
from cricinfodata import *
from response import *


class LiveMatchSimulator:
    def __init__(self, match_id, series_id, pre_match_state, career_bowling_data,
                 career_batting_data, wicket_models, runs_models, threes, wide_models,
                 nb_models, bowling_models, bounds=None, debug=False):
        self.match_id = str(match_id)
        self.series_id = str(series_id)
        self.wicket_models = wicket_models
        self.runs_models = runs_models
        self.threes_model = threes
        self.bowling_models = bowling_models
        self.wide_models = wide_models
        self.nb_models = nb_models
        self.pre_match_state = pre_match_state
        # self.op_odds = self.pre_match_oddsportal_call()
        # in sim, we get the data for the actual match so it's easy to slice out the players...
        # but here we have to take the latest data for each player individually, which could be anywhere in the df...
        # also, this means that shifting the stuff we know is now bad because we should use the newest datapoints!
        self.career_bowling_data = career_bowling_data
        self.career_batting_data = career_batting_data

        self.bowling_plan = []
        self.bounds = bounds
        self.live_match_state = {}
        self.live_match_state['event_name'] = self.pre_match_state.event_name
        self.live_match_state['venue'] = self.pre_match_state.venue
        #         self.pre_match_state['opening_probabilities'] = some_function(self.op_odds)
        # self.live_match_state['avg_ground_rpo'] = self.pre_match_state.avg_ground_rpo
        self.live_match_state['runs_required'] = 0
        self.live_match_state['innings_runs_b4b'] = 0
        self.live_match_state['required_run_rate'] = 0
        self.live_match_state['over_runs_b4b'] = 0
        # self.career_bowling_data_dict = self.career_bowling_data.droplevel(1).to_dict(orient='index')
        self.outcomes = ['0', '1', '2', '4', '6', 'w', 'nb', 'W', '3']
        self.wide_outcomes = [1, 2, 5]
        self.nb_outcomes = [1, 2]
        self.run_out_outcomes = [0, 1]
        self.run_splits = [k[1] for k in self.runs_models.keys() if k[1] != 'N/A']
        self.wicket_splits_1 = [k[1] for k in self.wicket_models.keys() if k[0] == 1]
        self.wicket_splits_2 = [k[1] for k in self.wicket_models.keys() if k[0] == 2]
        self.debug = debug

        # initialise match state
        self.innings = 1
        self.over = 1
        self.ball = 0
        self.setting_team = self.pre_match_state.setting_team
        self.chasing_team = self.pre_match_state.chasing_team
        self.setting_career_batting_data = {}
        self.setting_career_bowling_data = {}
        debut_career_batting_dict = career_batting_data.iloc[
            0].to_dict()  # need to maintain bowling style and playing role somehow
        debut_career_batting_dict = {k: 0 for k, v in debut_career_batting_dict.items()}
        debut_career_bowling_dict = career_bowling_data.iloc[0].to_dict()
        debut_career_bowling_dict = {k: 0 for k, v in debut_career_bowling_dict.items()}
        debut_career_bowling_dict['playing_role_bowl'] = 'N/A'
        debut_career_bowling_dict['bowling_style_bowl'] = 'right_arm_offspin'
        for p in self.pre_match_state.setting_players:
            try:
                old = career_batting_data.loc[p.player.name].iloc[-1].to_dict()
                new = update_career_batting(old)
                self.setting_career_batting_data[p.player.name] = new
            except KeyError:
                self.setting_career_batting_data[p.player.name] = debut_career_batting_dict
            try:
                old = career_bowling_data.loc[p.player.name].iloc[-1].to_dict()
                new = update_career_bowling(old)
                self.setting_career_bowling_data[p.player.name] = new
            except KeyError:
                self.setting_career_bowling_data[p.player.name] = debut_career_bowling_dict
        self.chasing_career_batting_data = {}
        self.chasing_career_bowling_data = {}
        for p in self.pre_match_state.chasing_players:
            try:
                old = career_batting_data.loc[p.player.name].iloc[-1].to_dict()
                new = update_career_batting(old)
                self.chasing_career_batting_data[p.player.name] = new
            except KeyError:
                self.chasing_career_batting_data[p.player.name] = debut_career_batting_dict
            try:
                old = career_bowling_data.loc[p.player.name].iloc[-1].to_dict()
                new = update_career_bowling(old)
                self.chasing_career_bowling_data[p.player.name] = new
            except KeyError:
                self.chasing_career_bowling_data[p.player.name] = debut_career_bowling_dict

        self.batting_team = LiveTeam(self.setting_team, self.pre_match_state, self.setting_career_bowling_data,
                                     self.setting_career_batting_data,
                                     )
        self.bowling_team = LiveTeam(self.chasing_team, self.pre_match_state, self.chasing_career_bowling_data,
                                     self.chasing_career_batting_data
                                     )
        self.comm = []
        self.winner = ''

    def sim_live_match(self, match_or_innings, live_match_state=None, simulated_target=None, verbose=False):
        # to be clear, we pass in the state for ball n then simulate from here to get the outcome from n+1 onwards
        # currently, "ball 0" = end of last over, "ball 1" = 1 ball has been bowled this over...
        # so now when ball 1 is given, "b4b" refers to before ball 2, and ball 6 given implied b4b is before ball 1 for over n+1.
        if live_match_state:
            if simulated_target is None:
                self.live_match_state['runs_required'] = live_match_state.runs_required
            else:
                self.live_match_state['runs_required'] = simulated_target
            self.innings = live_match_state.innings
            self.live_match_state['innings_runs_b4b'] = live_match_state.innings_runs
            self.live_match_state['wickets_in_innings_b4b'] = live_match_state.wickets_in_innings
            self.live_match_state['legal_balls_in_innings_b4b'] = live_match_state.legal_balls_in_innings
            self.live_match_state['legal_balls_remaining'] = live_match_state.legal_balls_remaining_in_innings
            self.initial_over = live_match_state.over
            self.over = live_match_state.over
            self.ball = live_match_state.balls_actual  # 1->6
            if self.ball != 0:
                self.batting_team.zero_all_stats()
                self.bowling_team.zero_all_stats()
                self.batting_team.populate_with_initial_state(live_match_state, simulated_target)
                self.bowling_team.populate_with_initial_state(live_match_state, simulated_target)
            else:
                self.batting_team.zero_all_stats()
                self.bowling_team.zero_all_stats()
                self.batting_team.populate_with_start_of_game_state(live_match_state, simulated_target)
                self.bowling_team.populate_with_start_of_game_state(live_match_state, simulated_target)
            self.live_match_state['senior_partner'] = self.batting_team.onstrike.current_match_stats[
                                                          'striker_runs_b4b'] > \
                                                      self.batting_team.offstrike.current_match_stats[
                                                          'striker_runs_b4b']
            self.live_match_state['batter_first_ball'] = self.batting_team.onstrike.current_match_stats[
                                                             'striker_balls_faced_b4b'] == 0
            self.live_match_state['batter_on_0'] = self.batting_team.onstrike.current_match_stats[
                                                       'striker_runs_b4b'] == 0
            self.live_match_state['batter_no_11'] = self.batting_team.onstrike.current_match_stats[
                                                        'batting_position_bat'] == 11
            if self.innings == 1:
                self.wicket_model = self.wicket_models[(
                    self.innings, find_le(self.wicket_splits_1, self.live_match_state['legal_balls_in_innings_b4b']),
                    self.live_match_state['batter_first_ball'])]
            else:
                self.wicket_model = self.wicket_models[(
                    self.innings, find_le(self.wicket_splits_2, self.live_match_state['legal_balls_in_innings_b4b']),
                    self.live_match_state['batter_first_ball'])]

            if self.live_match_state['batter_no_11']:
                self.runs_model = self.runs_models[(self.innings,
                                                    'N/A',
                                                    self.live_match_state['batter_on_0'],
                                                    self.live_match_state['batter_no_11'],
                                                    'N/A')]
            elif self.live_match_state['legal_balls_in_innings_b4b'] < 12:
                self.runs_model = self.runs_models[(self.innings,
                                                    find_le(self.run_splits,
                                                            self.live_match_state['legal_balls_in_innings_b4b']),
                                                    'N/A',
                                                    self.live_match_state['batter_no_11'],
                                                    'N/A')]
            elif (self.live_match_state['legal_balls_in_innings_b4b'] >= 12) & (
                    self.live_match_state['legal_balls_in_innings_b4b'] < 108):
                self.runs_model = self.runs_models[(self.innings,
                                                    find_le(self.run_splits,
                                                            self.live_match_state['legal_balls_in_innings_b4b']),
                                                    self.live_match_state['batter_on_0'],
                                                    self.live_match_state['batter_no_11'],
                                                    self.live_match_state['senior_partner'])]
            elif self.live_match_state['legal_balls_in_innings_b4b'] >= 118:
                self.runs_model = self.runs_models[(self.innings,
                                                    find_le(self.run_splits,
                                                            self.live_match_state['legal_balls_in_innings_b4b']),
                                                    self.live_match_state['batter_on_0'],
                                                    self.live_match_state['batter_no_11'],
                                                    'N/A')]
            else:
                self.runs_model = self.runs_models[(self.innings,
                                                    find_le(self.run_splits,
                                                            self.live_match_state['legal_balls_in_innings_b4b']),
                                                    self.live_match_state['batter_on_0'],
                                                    self.live_match_state['batter_no_11'],
                                                    'N/A')]

            if self.innings == 1:
                self.setting_team = self.batting_team.name
                self.chasing_team = self.bowling_team.name
            else:
                self.chasing_team = self.batting_team.name
                self.setting_team = self.bowling_team.name

        self.bowling_plan = self.sim_bowlers_for_innings()

        self.live_match_state['partnership_runs_b4b'] = self.batting_team.partnership_runs
        # self.live_match_state['implied_batting_team_prob'] = \
        #     self.historic_match_data['implied_batting_team_prob'].iloc[0]

        while self.innings == 1:
            while (self.over <= 20) and (self.batting_team.bat_wkts < 10):
                self.sim_over()

            if match_or_innings == 'innings':
                if verbose:
                    return self.batting_team.name, self.batting_team.bat_total, self.batting_team.bat_wkts
                else:
                    return self.batting_team.bat_total
            else:
                self.change_inns()

        while (self.over <= 20) and (self.batting_team.bat_wkts < 10) and (self.batting_team.bat_total
                                                                           <= self.bowling_team.bat_total):
            self.sim_over()

        if self.batting_team.bat_total > self.bowling_team.bat_total:
            self.winner = self.batting_team.name
        elif self.batting_team.bat_total < self.bowling_team.bat_total:
            self.winner = self.bowling_team.name
        else:
            self.winner = 'Tie'

        if verbose:
            return [self.winner,
                    [self.bowling_team.name, self.bowling_team.bat_total, self.bowling_team.bat_wkts],
                    [self.batting_team.name, self.batting_team.bat_total, self.batting_team.bat_wkts],
                    [self.over, self.ball]]
        else:
            return self.winner

    def sim_over(self):
        # module to simulate an over

        self.wide_model = self.wide_models[(self.innings, self.over)]
        self.nb_model = self.nb_models[self.over]

        self.live_match_state['over'] = self.over
        # need to tweak for BBL in 2020, 21 (19?)
        self.bowling_team.bowler = self.bowling_plan[self.over - self.initial_over]

        while (self.ball < 6) and (self.batting_team.bat_wkts < 10) and \
                ((self.innings == 1) or (self.batting_team.bat_total <= self.bowling_team.bat_total)):
            self.sim_ball()

        self.ball = 0
        self.live_match_state['over_runs_b4b'] = 0
        self.batting_team.new_over()
        self.bowling_team.new_over()

        self.over += 1

    def sim_ball(self):
        # module to simulate a ball
        # get model inputs from match state
        # anything above the "outcomes" has to be state as of before the ball is bowled.
        # anything below the "outcomes" is updating state for the next ball, given we now know outcome of this ball.

        self.live_match_state['legal_balls_in_innings_b4b'] = (self.over - 1) * 6 + self.ball
        self.live_match_state['senior_partner'] = self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] > \
                                                  self.batting_team.offstrike.current_match_stats['striker_runs_b4b']
        self.live_match_state['batter_first_ball'] = self.batting_team.onstrike.current_match_stats[
                                                         'striker_balls_faced_b4b'] == 0
        self.live_match_state['batter_on_0'] = self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] == 0
        self.live_match_state['batter_no_11'] = self.batting_team.onstrike.current_match_stats[
                                                    'batting_position_bat'] == 11

        if self.innings == 1:
            self.wicket_model = self.wicket_models[(
                self.innings, find_le(self.wicket_splits_1, self.live_match_state['legal_balls_in_innings_b4b']),
                self.live_match_state['batter_first_ball'])]
        else:
            self.wicket_model = self.wicket_models[(
                self.innings, find_le(self.wicket_splits_2, self.live_match_state['legal_balls_in_innings_b4b']),
                self.live_match_state['batter_first_ball'])]

        if self.live_match_state['batter_no_11']:
            self.runs_model = self.runs_models[(self.innings,
                                                'N/A',
                                                self.live_match_state['batter_on_0'],
                                                self.live_match_state['batter_no_11'],
                                                'N/A')]
        elif self.live_match_state['legal_balls_in_innings_b4b'] < 12:
            self.runs_model = self.runs_models[(self.innings,
                                                find_le(self.run_splits,
                                                        self.live_match_state['legal_balls_in_innings_b4b']),
                                                'N/A',
                                                self.live_match_state['batter_no_11'],
                                                'N/A')]
        elif (self.live_match_state['legal_balls_in_innings_b4b'] >= 12) & (
                self.live_match_state['legal_balls_in_innings_b4b'] < 108):
            self.runs_model = self.runs_models[(self.innings,
                                                find_le(self.run_splits,
                                                        self.live_match_state['legal_balls_in_innings_b4b']),
                                                self.live_match_state['batter_on_0'],
                                                self.live_match_state['batter_no_11'],
                                                self.live_match_state['senior_partner'])]
        elif self.live_match_state['legal_balls_in_innings_b4b'] >= 118:
            self.runs_model = self.runs_models[(self.innings,
                                                find_le(self.run_splits,
                                                        self.live_match_state['legal_balls_in_innings_b4b']),
                                                self.live_match_state['batter_on_0'],
                                                self.live_match_state['batter_no_11'],
                                                'N/A')]
        else:
            self.runs_model = self.runs_models[(self.innings,
                                                find_le(self.run_splits,
                                                        self.live_match_state['legal_balls_in_innings_b4b']),
                                                self.live_match_state['batter_on_0'],
                                                self.live_match_state['batter_no_11'],
                                                'N/A')]

        self.live_match_state['wickets_in_innings_b4b'] = int(self.batting_team.bat_wkts)
        self.live_match_state['wl_squared'] = (self.live_match_state['wickets_in_innings_b4b'] - 3) ** 2
        self.live_match_state['legal_balls_remaining'] = 120 - self.live_match_state['legal_balls_in_innings_b4b']
        self.live_match_state['is_first_ball'] = int(self.ball == 0)
        self.live_match_state['is_last_ball'] = int(self.ball == 5)
        self.live_match_state['log_partnership_runs'] = math.log(1 + self.live_match_state['partnership_runs_b4b'], 10)
        self.live_match_state['log_striker_balls_faced'] = math.log(
            1 + self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'], 10)
        self.live_match_state['log_striker_runs'] = math.log(
            1 + self.batting_team.onstrike.current_match_stats['striker_runs_b4b'], 10)
        self.live_match_state['strike_rate_b4b'] = self.batting_team.onstrike.current_match_stats['strike_rate_b4b']
        self.live_match_state['shit_rating_bat'] = self.batting_team.onstrike.historic_career_stats['shit_rating_bat']
        self.live_match_state['bowling_style_bowl'] = self.bowling_team.bowler.historic_career_stats[
            'bowling_style_bowl']
        self.live_match_state['partner_run_diff'] = self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] - \
                                                    self.batting_team.offstrike.current_match_stats['striker_runs_b4b']

        bowler_career_balls = self.bowling_team.bowler.historic_career_stats['cum_balls_bowled_bowl'] + \
                              self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b']
        if bowler_career_balls == 0:
            bowler_career_balls = 1
        batter_career_balls = self.batting_team.onstrike.historic_career_stats['cum_balls_bat'] + \
                              self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
        if batter_career_balls == 0:
            batter_career_balls = 1

        bowler_weight = bowler_career_balls / (bowler_career_balls + batter_career_balls)
        batter_weight = 1 - bowler_weight

        # weight these by bowler/batsman balls
        self.live_match_state['ones_matchup'] = (batter_weight * (
                self.batting_team.onstrike.historic_career_stats['cum_ones_bat'] +
                self.batting_team.onstrike.current_match_stats['striker_1_b4b']) / \
                                                 batter_career_balls) + \
                                                (bowler_weight * (self.bowling_team.bowler.historic_career_stats[
                                                                      'cum_ones_bowl'] +
                                                                  self.bowling_team.bowler.current_match_stats[
                                                                      'bowler_1_b4b']) / \
                                                 bowler_career_balls)

        self.live_match_state['ones_matchup'] = min(max(self.live_match_state['ones_matchup'], self.bounds[1][0]),
                                                    self.bounds[1][1])

        self.live_match_state['twos_matchup'] = (batter_weight * (
                self.batting_team.onstrike.historic_career_stats['cum_twos_bat'] +
                self.batting_team.onstrike.current_match_stats['striker_2_b4b']) / \
                                                 batter_career_balls) + \
                                                (bowler_weight * (self.bowling_team.bowler.historic_career_stats[
                                                                      'cum_twos_bowl'] +
                                                                  self.bowling_team.bowler.current_match_stats[
                                                                      'bowler_2_b4b']) / \
                                                 bowler_career_balls)

        self.live_match_state['twos_matchup'] = min(max(self.live_match_state['twos_matchup'], self.bounds[2][0]),
                                                    self.bounds[2][1])

        self.live_match_state['fours_matchup'] = (batter_weight * (
                self.batting_team.onstrike.historic_career_stats['cum_fours_bat'] +
                self.batting_team.onstrike.current_match_stats['striker_4_b4b']) / \
                                                  batter_career_balls) + \
                                                 (bowler_weight * (self.bowling_team.bowler.historic_career_stats[
                                                                       'cum_fours_bowl'] +
                                                                   self.bowling_team.bowler.current_match_stats[
                                                                       'bowler_4_b4b']) / \
                                                  bowler_career_balls)

        self.live_match_state['fours_matchup'] = min(max(self.live_match_state['fours_matchup'], self.bounds[4][0]),
                                                     self.bounds[4][1])

        self.live_match_state['sixes_matchup'] = (batter_weight * (
                self.batting_team.onstrike.historic_career_stats['cum_sixes_bat'] +
                self.batting_team.onstrike.current_match_stats['striker_6_b4b']) / \
                                                  batter_career_balls) + \
                                                 (bowler_weight * (self.bowling_team.bowler.historic_career_stats[
                                                                       'cum_sixes_bowl'] +
                                                                   self.bowling_team.bowler.current_match_stats[
                                                                       'bowler_6_b4b']) / \
                                                  bowler_career_balls)

        self.live_match_state['wickets_matchup'] = (batter_weight * (
            self.batting_team.onstrike.historic_career_stats['cum_outs_b4m']) / batter_career_balls) + \
                                                   (bowler_weight * (self.bowling_team.bowler.historic_career_stats[
                                                                         'cum_wickets_b4m_bowl'] +
                                                                     self.bowling_team.bowler.current_match_stats[
                                                                         'bowler_wickets_b4b']) / bowler_career_balls)

        self.live_match_state['sixes_matchup'] = min(max(self.live_match_state['sixes_matchup'], self.bounds[6][0]),
                                                     self.bounds[6][1])

        self.live_match_state['wickets_matchup'] = min(
            max(self.live_match_state['wickets_matchup'], self.bounds['W'][0]),
            self.bounds['W'][1])

        self.live_match_state['log_sixes_matchup'] = math.log(self.live_match_state['sixes_matchup'], 2)

        if self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] > 0:
            self.bowling_team.bowler.current_match_stats['bowler_er_b4b'] = \
                6 * self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] / \
                self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b']
            self.live_match_state['prop_bowler_wides_in_game'] = min(
                max(self.bowling_team.bowler.current_match_stats['bowler_wides_in_game_b4b'] / \
                    self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'], 0), 1)
        else:
            self.bowling_team.bowler.current_match_stats['bowler_er_b4b'] = 0
            self.live_match_state['prop_bowler_wides_in_game'] = 0
        if self.live_match_state['legal_balls_in_innings_b4b'] > 0:
            self.live_match_state['run_rate_b4b'] = 6 * (self.live_match_state['innings_runs_b4b']
                                                         / self.live_match_state['legal_balls_in_innings_b4b'])
        else:
            self.live_match_state['run_rate_b4b'] = 0

        if self.innings == 2:
            self.live_match_state['required_run_rate'] = 6 * (self.live_match_state['runs_required'] /
                                                              self.live_match_state['legal_balls_remaining'])
            self.live_match_state['rrr_capped'] = min(self.live_match_state['required_run_rate'], 20)
            self.live_match_state['distance_from_normal_rrr'] = abs(self.live_match_state['rrr_capped'] - 6)
            self.live_match_state['match_heat'] = min(self.live_match_state['run_rate_b4b'],
                                                      self.live_match_state['required_run_rate'])
            self.live_match_state['match_heat_distance'] = abs(self.live_match_state['match_heat'] - 5)

        self.regressors = self.live_match_state.copy()
        self.regressors.update(self.bowling_team.bowler.historic_career_stats)  # - these could be in the over section
        self.regressors.update(self.bowling_team.bowler.current_match_stats)
        self.regressors.update(self.batting_team.onstrike.historic_career_stats)
        self.regressors.update(self.batting_team.onstrike.current_match_stats)

        # select relevant models - at this point I need to have gathered all the state.
        # the model that we pick is unlikely to change by ball, so can move out of critical loop.

        # wide
        p_wide = calculate_logit_model_probability(self.regressors, self.wide_model)
        # nb
        p_nb = calculate_logit_model_probability(self.regressors, self.nb_model)
        # wickets
        p_wicket = calculate_logit_model_probability(self.regressors, self.wicket_model)

        p_three = calculate_logit_model_probability(self.regressors, self.threes_model)

        p_runs = calculate_mnlogit_model_probabilities(self.regressors, self.runs_model)

        # now normalise runs
        p_runs = [r * (1 - (p_nb + p_wide + p_wicket + p_three)) for r in p_runs]

        # note that p_runs + p_wicket + p_wide + p_nb = 1, and the runs model must be adjusted for this!
        probabilities = np.append(p_runs, [p_wide, p_nb, p_wicket, p_three])
        outcome = choices(self.outcomes, probabilities)[0]

        if self.debug:
            print(self.over, self.ball)

            er = 1 * p_runs[1] + 2 * p_runs[2] + 3 * p_three + 4 * p_runs[3] + 6 * p_runs[4]

            print(self.live_match_state)

            print([round(p, 3) for p in probabilities], round(er, 2))

        # todo, our historic definition of balls faced is slightly wrong (wides are not a ball faced, no balls are)

        self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] += 1
        self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1

        if outcome == '0':
            self.ball += 1
            # self.bowling_team.bowler.current_match_stats['bowler_dots_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_0_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['striker_0_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']

        elif outcome == '1':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_1_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['striker_1_b4b'] += 1
            self.live_match_state['over_runs_b4b'] += 1
            self.live_match_state['innings_runs_b4b'] += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1
            self.live_match_state['partnership_runs_b4b'] += 1
            self.batting_team.partnership_runs += 1
            self.batting_team.change_ends()
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 1

        elif outcome == '2':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 2
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 2
            self.bowling_team.bowler.current_match_stats['bowler_2_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['striker_2_b4b'] += 1
            self.live_match_state['over_runs_b4b'] += 2
            self.live_match_state['innings_runs_b4b'] += 2
            self.batting_team.bat_total += 2
            self.bowling_team.bwl_total += 2
            self.batting_team.partnership_runs += 2
            self.live_match_state['partnership_runs_b4b'] += 2
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 2

        elif outcome == '3':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 3
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 3
            self.live_match_state['over_runs_b4b'] += 3
            self.live_match_state['innings_runs_b4b'] += 3
            self.batting_team.bat_total += 3
            self.bowling_team.bwl_total += 3
            self.batting_team.partnership_runs += 3
            self.live_match_state['partnership_runs_b4b'] += 3
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 3
            self.batting_team.change_ends()

        elif outcome == '4':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 4
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 4
            self.bowling_team.bowler.current_match_stats['bowler_4_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['striker_4_b4b'] += 1
            self.live_match_state['over_runs_b4b'] += 4
            self.live_match_state['innings_runs_b4b'] += 4
            self.batting_team.bat_total += 4
            self.bowling_team.bwl_total += 4
            self.batting_team.partnership_runs += 4
            self.live_match_state['partnership_runs_b4b'] += 4
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 4

        elif outcome == '6':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 6
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 6
            self.bowling_team.bowler.current_match_stats['bowler_6_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['striker_6_b4b'] += 1
            self.live_match_state['over_runs_b4b'] += 6
            self.live_match_state['innings_runs_b4b'] += 6
            self.batting_team.bat_total += 6
            self.bowling_team.bwl_total += 6
            self.batting_team.partnership_runs += 6
            self.live_match_state['partnership_runs_b4b'] += 6
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 6

        elif outcome == 'W':
            # 1 in 250 balls is a run out, in in 3 of these goes for a single...
            self.ball += 1
            self.bowling_team.bwl_wkts += 1
            self.bowling_team.bowler.current_match_stats['bowler_wickets_b4b'] += 1
            self.batting_team.wicket()
            self.live_match_state['partnership_runs_b4b'] = 0

        elif outcome in ['w', 'nb']:

            self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] -= 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] -= 1
            if self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] != 0:
                self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                    100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] / \
                    self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            else:
                self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = 0

            if outcome == 'nb':
                nb_dist = [0.625, 0.375]
                run_outcome = choices(self.nb_outcomes, nb_dist)[0]
            else:
                self.bowling_team.bowler.current_match_stats['bowler_wides_in_game_b4b'] += 1
                wide_dist = [0.91, 0.045, 0.045]
                run_outcome = choices(self.wide_outcomes, wide_dist)[0]

            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += run_outcome
            self.bowling_team.bowler.current_match_stats['bowler_extras'] += run_outcome
            self.live_match_state['over_runs_b4b'] += run_outcome
            self.live_match_state['innings_runs_b4b'] += run_outcome
            self.batting_team.bat_total += run_outcome
            self.bowling_team.bwl_total += run_outcome
            self.batting_team.partnership_runs += run_outcome
            self.live_match_state['partnership_runs_b4b'] += run_outcome
            if self.innings == 2:
                self.live_match_state['runs_required'] -= run_outcome

        return outcome

    def change_inns(self):
        # module to swap bowling and batting sides after 1st innings
        self.live_match_state['runs_required'] = self.batting_team.bat_total + 1
        temp = self.batting_team
        self.batting_team = self.bowling_team
        self.bowling_team = temp
        self.batting_team.bat_bwl = 'bat'
        self.bowling_team.bat_bwl = 'bwl'
        self.over = 1
        self.ball = 0
        self.innings = 2
        self.live_match_state['implied_batting_team_prob'] \
            = self.historic_match_data[lambda x: x.innings == self.innings]['implied_batting_team_prob'].iloc[0]
        self.bowling_plan = self.sim_bowlers_for_innings()
        self.live_match_state['innings_runs_b4b'] = 0
        self.live_match_state['partnership_runs_b4b'] = 0

    def sim_bowlers_for_innings(self):
        # module to simulate bowlers who will bowl throughout the innings.
        # NB this simple at the moment, we don't change in response to the progression of the innings yet, we just
        # assume the captain decides on all bowlers at start of innings and sticks with this plan.
        max_possible_overs = 4
        # bowled_over_cols = ['bowled_over_{}_bowl'.format(i) for i in range(1, 21)]
        # overs_bowled_cols = ['overs_bowled_after_{}_bowl'.format(i) for i in range(1, 21)]
        bowled_prev_match_cols = ['bowled_over_{}_prev_match_bowl'.format(i) for i in range(1, 21)]

        potential_bowlers = self.bowling_team.bowlers.copy()  # {name: Bowler}
        # bowler_careers = {k: v for k, v in self.career_bowling_data_dict.items() if k in potential_bowlers}

        for b in potential_bowlers.values():
            for c in bowled_prev_match_cols:
                if np.isnan(b.historic_career_stats[c]):
                    b.historic_career_stats[c] = 0

        # special case is very first ball, no one has been picked to bowl
        if (self.over == 1) & (self.ball == 0):
            counter = 0
            bowling_plan = []
        else:
            # look for which bowler bowled the current over irl
            # outcome = [b for b, v in potential_bowlers.items() if
            # v.historic_career_stats['bowled_over_{}_bowl'.format(self.over)] == 1][0]
            outcome = self.bowling_team.bowler
            counter = self.over
            bowling_plan = [outcome]
            potential_bowlers = {k: v for k, v in potential_bowlers.items() if
                                 potential_bowlers[k].current_match_stats[
                                     'overs_bowled_after_{}_bowl'.format(self.over)] <
                                 max_possible_overs}

        for i in range(counter + 1, 21):
            model = self.bowling_models['bowling_model_{}'.format(i)]

            if i == 1:
                p_b = []
                for n, b in potential_bowlers.items():
                    p_b = np.append(p_b, calculate_probit_model_probability(b.historic_career_stats, model))
                bowler_prob = p_b / sum(p_b)
                outcome = choices(list(potential_bowlers.keys()), bowler_prob)[0]
                for n, b in potential_bowlers.items():
                    if n == outcome:
                        b.current_match_stats['bowled_over_{}_bowl'.format(i)] = 1
                        b.current_match_stats['overs_bowled_after_{}_bowl'.format(i)] = 1
                    else:
                        b.current_match_stats['bowled_over_{}_bowl'.format(i)] = 0
                        b.current_match_stats['overs_bowled_after_{}_bowl'.format(i)] = 0
            else:
                previous_bowler = outcome
                p_b = []
                temp = {k: v for k, v in potential_bowlers.items() if k != previous_bowler}
                for n, b in temp.items():
                    reg = b.historic_career_stats.copy()
                    reg.update(b.current_match_stats)
                    p_b = np.append(p_b, calculate_probit_model_probability(reg, model))
                    # want to temporarily drop bowler who bowled the last over,
                    # and perma-drop anyone who has bowled 4 overs.
                bowler_prob = p_b / sum(p_b)
                outcome = choices(list(temp.keys()), bowler_prob)[0]
                for n, b in potential_bowlers.items():
                    if n == outcome:
                        b.current_match_stats['bowled_over_{}_bowl'.format(i)] = 1
                        b.current_match_stats['overs_bowled_after_{}_bowl'.format(i)] = \
                            b.current_match_stats['overs_bowled_after_{}_bowl'.format(i - 1)] + \
                            b.current_match_stats['bowled_over_{}_bowl'.format(i)]

                if potential_bowlers[outcome].current_match_stats['overs_bowled_after_{}_bowl'.format(i)] \
                        == max_possible_overs:
                    del potential_bowlers[outcome]
            bowling_plan.append(self.bowling_team.bowlers[outcome])

        return bowling_plan

    # for an historic match, during the second innings, what is p(win|state of the game) for each ball in the innings?
    # note we cannot SavGol smooth these probabilities since this would use future information.

    def historic_second_innings_sim(self, n, verbose=False, switch_teams=False):
        self.innings = 2
        second_innings_data = self.historic_match_data[lambda x: x.innings == self.innings].to_dict(orient='records')
        if switch_teams:
            temp = self.batting_team
            self.batting_team = self.bowling_team
            self.bowling_team = temp
            self.batting_team.bat_bwl = 'bat'
            self.bowling_team.bat_bwl = 'bwl'
        j = 0
        winner = []
        second_innings_win_pct = OrderedDict()
        balls_so_far = []
        for ball in second_innings_data:
            balls_so_far.append(ball)
            while j < n:
                x = self.sim_match('match', balls_so_far)
                j += 1
                winner.append(x[0])
            c = Counter(winner)
            if verbose:
                print('Chasing win % from ball {} is {}'.format(j, c[ball['batting_team']] / (
                        c[ball['bowling_team']] + c[ball['batting_team']] + c['Tie'])))
            #             second_innings_win_pct[ball['ball']] = c[ball['batting_team']]/(c[ball['bowling_team']]+c[ball['batting_team']]+c['Tie'])
            sample_proportion = c[ball['batting_team']] / (c[ball['bowling_team']] + c[ball['batting_team']] + c['Tie'])
            sample_std_dev = np.sqrt(sample_proportion * (1 - sample_proportion) / n)
            second_innings_win_pct[ball['ball']] = (sample_proportion, sample_std_dev)
            j = 0
            winner = []
        return second_innings_win_pct

    # for a hardcoded array of first innings scores, what's the simulated probability the chasing team will chase them?

    def precalc_win_probs_for_score_array(self, n, smooth=True, verbose=False):
        self.innings = 2
        temp = self.batting_team
        self.batting_team = self.bowling_team
        self.bowling_team = temp
        self.batting_team.bat_bwl = 'bat'
        self.bowling_team.bat_bwl = 'bwl'
        j = 0
        winner = []
        scores = np.arange(40, 280)
        ball = [self.historic_match_data[lambda x: x.innings == self.innings].to_dict(orient='records')[0]]  # sorry
        score_to_prob_map = OrderedDict()
        for score in scores:
            while j < n:
                x = self.sim_match('match', ball, score)
                winner.append(x[0])
                j += 1
            c = Counter(winner)
            if verbose:
                print('Chasing win % from ball {} is {}'.format(j, c[ball[0]['batting_team']] / (
                        c[ball[0]['bowling_team']] + c[ball[0]['batting_team']] + c['Tie'])))
            j = 0
            winner = []
            sample_proportion = c[ball[0]['batting_team']] / (c[ball[0]['bowling_team']] +
                                                              c[ball[0]['batting_team']] + c['Tie'])
            sample_std_dev = np.sqrt(sample_proportion * (1 - sample_proportion) / n)
            score_to_prob_map[score] = (sample_proportion, sample_std_dev)
        if smooth:
            score_to_prob_map = self.smooth_probabilities(score_to_prob_map, n)
        return score_to_prob_map

    @staticmethod
    def smooth_probabilities(score_to_prob_map, n):
        prob_array = np.array([p[0] for p in score_to_prob_map.values()])
        filtered_probabilities = np.clip(savgol_filter(prob_array, 21, 3), 0, 1)
        for i, score in enumerate(score_to_prob_map):
            sample_std_dev = np.sqrt(filtered_probabilities[i] * (1 - filtered_probabilities[i]) / n)
            score_to_prob_map[score] = (filtered_probabilities[i], sample_std_dev)
        return score_to_prob_map

    # for each ball in the first innings of an historic match, simulate until the end of the innings
    # and record the distribution of scores - eventually multiply this with score_map to get a probability of winning
    # for each ball in the first innings.

    def first_innings_scores(self, n):
        j = 0
        scores = []
        simulated_first_innings_scores = OrderedDict()
        first_innings_data = self.historic_match_data[lambda x: x.innings == 1].to_dict(orient='records')
        balls_so_far = []
        for ball in first_innings_data:
            balls_so_far.append(ball)
            while j < n:
                x = self.sim_match('innings', balls_so_far)
                j += 1
                scores.append(max(min(x[1], 280), 40))
            simulated_first_innings_scores[ball['ball']] = scores
            j = 0
            scores = []
        return simulated_first_innings_scores

    def prep_obj(self):
        self.innings = 2
        temp = self.batting_team
        self.batting_team = self.bowling_team
        self.bowling_team = temp
        self.batting_team.bat_bwl = 'bat'
        self.bowling_team.bat_bwl = 'bwl'

    def parallel_function_tgt(self, live_match_state):
        winner_per_score = {}
        scores = np.arange(40, 280)
        mc = copy.deepcopy(self)
        for s in scores:
            sim = mc.sim_live_match('match', live_match_state, s)
            if sim == self.setting_team:
                winner = 0
            else:
                winner = 1
            winner_per_score[s] = winner
        return winner_per_score


if __name__ == '__main__':
    career_batting_data = pd.read_pickle('/Users/julianbennettlongley/batting_careers.pkl')
    career_bowling_data = pd.read_pickle('/Users/julianbennettlongley/bowling_careers.pkl')
    with open('/Users/julianbennettlongley/wickets_last_attempt.pkl', 'rb') as f:
        wickets = cloudpickle.load(f)

    with open('/Users/julianbennettlongley/wides_glm_over.pkl', 'rb') as f:
        wides = cloudpickle.load(f)

    with open('/Users/julianbennettlongley/runs_models_ex_threes_last_attempt.pkl', 'rb') as f:
        runs = cloudpickle.load(f)

    with open('/Users/julianbennettlongley/runs_models_threes_over.pkl', 'rb') as f:
        threes = cloudpickle.load(f)

    with open('/Users/julianbennettlongley/nbs_glm_over.pkl', 'rb') as f:
        nbs = cloudpickle.load(f)

    with open('/Users/julianbennettlongley/bowling_models_playing_role.pkl', 'rb') as f:
        bowling_models = cloudpickle.load(f)

    bounds = pd.read_pickle('/Users/julianbennettlongley/winsorisation_bounds.pkl')

    for k, v in bowling_models.items():
        bowling_models[k] = SlimRegModel(None, v)

    pms = pd.read_pickle('/Users/julianbennettlongley/sl_ind_wmn_pregame.pkl')
    in_game = pd.read_pickle('/Users/julianbennettlongley/sl_ind_wmn_ingame.pkl')

    pre_game = PreMatchState(pms)
    lms = LiveMatchState(pre_game)
    # for i in range(78):
    #     lms.update(in_game[i])

    lm_sim = LiveMatchSimulator('1307297', '1307289', pre_game, career_bowling_data,
                                career_batting_data, wickets, runs, threes, wides,
                                nbs, bowling_models, bounds, debug=False)

    # start with the generic sim stuff:

    n = 20
    lm_sim.prep_obj()
    lms.change_innings(pre_game)
    winner = {}
    for i in range(n):
        winner[i] = lm_sim.parallel_function_tgt(lms)
        print(i)

    df = pd.DataFrame(winner)
    prob_per_score = (df.sum(axis=1)/len(df.columns)).to_dict()

    prob_per_score
    # self.pre

    # lm_sim.prep_obj()
    # lms.change_innings(pre_game)
    # sim_object = copy.deepcopy(lm_sim)
    # sim = sim_object.sim_live_match('match', lms, score)
    # print(sim)
    # r = lm_sim.sim_live_match('innings', lms)
