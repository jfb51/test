from example_package.team import SimpleHistoricTeam
import copy
from scipy.signal import savgol_filter
from collections import OrderedDict
import numpy as np
from collections import Counter
from example_package.util import calculate_probit_model_probability, calculate_mnlogit_model_probabilities
from random import choices


class HistoricMatchSimulator:
    def __init__(self, match_id, match_row, historic_match_data, career_bowling_data,
                 career_batting_data, wicket_models, runs_models, wide_models, nb_models, bowling_models):
        self.match_id = str(match_id)
        self.wicket_models = wicket_models
        self.runs_models = runs_models
        self.bowling_models = bowling_models
        self.wide_models = wide_models
        self.nb_models = nb_models
        self.match_row = match_row
        self.historic_match_data = historic_match_data
        self.career_bowling_data = career_bowling_data
        self.career_batting_data = career_batting_data
        self.bowling_plan = []
        self.live_match_state = dict()
        self.live_match_state['event_name'] = self.match_row['event_name']
        self.live_match_state['avg_ground_rpo'] = self.match_row['avg_ground_rpo']
        self.live_match_state['runs_required'] = 0
        self.live_match_state['innings_runs_b4b'] = 0
        self.live_match_state['required_run_rate'] = 0
        self.live_match_state['over_runs_b4b'] = 0
        self.career_bowling_data_dict = self.career_bowling_data.droplevel(1).to_dict(orient='index')

        # initialise match state
        self.innings = 1
        self.over = 1
        self.ball = 0
        toss = self.match_row['toss']
        toss_winner = self.match_row['toss']['winner']
        teams = copy.deepcopy(self.match_row['teams'])
        teams.remove(toss_winner)
        toss_loser = teams[0]
        if toss['decision'] == 'field':
            self.batting_team = SimpleHistoricTeam(toss_loser, self.match_row, self.career_bowling_data,
                                                   self.career_batting_data)
            self.bowling_team = SimpleHistoricTeam(toss_winner, self.match_row, self.career_bowling_data,
                                                   self.career_batting_data)
        else:
            self.batting_team = SimpleHistoricTeam(toss_winner, self.match_row, self.career_bowling_data,
                                                   self.career_batting_data)
            self.bowling_team = SimpleHistoricTeam(toss_loser, self.match_row, self.career_bowling_data,
                                                   self.career_batting_data)
        self.setting_team = self.batting_team.name
        self.chasing_team = self.bowling_team.name

        self.comm = []
        self.winner = ''

    def sim_match(self, match_or_innings, initial_match_state=None, simulated_target=None):

        # initial match state is now a list of 'balls' i.e. rows from dataframe, comprising history of match until now.
        if initial_match_state:
            latest_ball = initial_match_state[-1]
            if simulated_target is None:
                self.live_match_state['runs_required'] = latest_ball['runs_required']
            else:
                self.live_match_state['runs_required'] = simulated_target
            self.innings = latest_ball['innings']
            self.live_match_state['innings_runs_b4b'] = latest_ball['innings_runs_b4b']
            self.live_match_state['over_runs_b4b'] = latest_ball['over_runs_b4b']
            self.live_match_state['wickets_in_innings_b4b'] = latest_ball['wickets_in_innings_b4b']
            self.live_match_state['legal_balls_in_innings_b4b'] = latest_ball['legal_balls_in_innings_b4b']
            self.live_match_state['legal_balls_remaining'] = 120-self.live_match_state['legal_balls_in_innings_b4b']
            self.initial_over = int(latest_ball['over'])
            self.over = int(latest_ball['over'])
            self.ball = int(latest_ball['legal_balls_in_innings_b4b'] % 6)
            self.batting_team.zero_all_stats()
            self.bowling_team.zero_all_stats()
            self.batting_team.populate_with_initial_state(initial_match_state, simulated_target)
            # what's the first innings total in this case?
            self.bowling_team.populate_with_initial_state(initial_match_state, simulated_target)

            if self.innings == 1:
                self.setting_team = self.batting_team.name
                self.chasing_team = self.bowling_team.name
            else:
                self.chasing_team = self.batting_team.name
                self.setting_team = self.bowling_team.name

        self.bowling_plan = self.sim_bowlers_for_innings()

        self.live_match_state['partnership_runs_b4b'] = self.batting_team.partnership_runs
        self.live_match_state['implied_batting_team_prob'] = \
            self.historic_match_data['implied_batting_team_prob'].iloc[0]
        while self.innings == 1:
            while (self.over <= 20) and (self.batting_team.bat_wkts < 10):
                self.sim_over()
            if match_or_innings == 'innings':
                return [self.batting_team.name, self.batting_team.bat_total, self.batting_team.bat_wkts]
            else:
                self.change_inns()

        while (self.over <= 20) and (self.batting_team.bat_wkts < 10) and (self.batting_team.bat_total
                                                                           <= self.bowling_team.bat_total):
            print(self.over, self.ball)
            self.sim_over()

        if self.batting_team.bat_total > self.bowling_team.bat_total:
            self.winner = self.batting_team.name
        elif self.batting_team.bat_total < self.bowling_team.bat_total:
            self.winner = self.bowling_team.name
        else:
            self.winner = 'Tie'
        return [self.winner,
                [self.bowling_team.name, self.bowling_team.bat_total, self.bowling_team.bat_wkts],
                # self.t_bwl.ply_stats],
                [self.batting_team.name, self.batting_team.bat_total, self.batting_team.bat_wkts],
                # self.t_bat.ply_stats]
                [self.over, self.ball]
                ]

    def sim_over(self):
        # module to simulate an over
        for model in self.wide_models:
            if model.condition(self):
                self.wide_model = model

        for model in self.nb_models:
            if model.condition(self):
                self.nb_model = model

        for model in self.wicket_models:
            if model.condition(self):
                self.wicket_model = model

        for model in self.runs_models:
            if model.condition(self):
                self.runs_model = model

        self.live_match_state['is_middle_overs'] = (self.over > 6) & (self.over < 17)
        self.live_match_state['is_death_overs'] = self.over > 16
        self.live_match_state['is_powerplay'] = self.over < 6
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

        self.live_match_state['wickets_in_innings_b4b'] = int(self.batting_team.bat_wkts)
        self.live_match_state['legal_balls_in_innings_b4b'] = (self.over - 1) * 6 + self.ball
        self.live_match_state['legal_balls_remaining'] = 120 - self.live_match_state['legal_balls_in_innings_b4b']
        self.live_match_state['is_first_ball'] = int(self.ball == 0)
        self.live_match_state['is_last_ball'] = int(self.ball == 5)
        self.live_match_state['dots_matchup'] = self.bowling_team.bowler.historic_career_stats['prop_dots_bowl'] + \
                                                self.batting_team.onstrike.historic_career_stats['prop_dots_bat']
        self.live_match_state['ones_matchup'] = self.bowling_team.bowler.historic_career_stats['prop_ones_bowl'] + \
                                                self.batting_team.onstrike.historic_career_stats['prop_ones_bat']
        self.live_match_state['twos_matchup'] = self.bowling_team.bowler.historic_career_stats['prop_twos_bowl'] + \
                                                self.batting_team.onstrike.historic_career_stats['prop_twos_bat']
        self.live_match_state['fours_matchup'] = self.bowling_team.bowler.historic_career_stats['prop_fours_bowl'] + \
                                                self.batting_team.onstrike.historic_career_stats['prop_fours_bat']
        self.live_match_state['sixes_matchup'] = self.bowling_team.bowler.historic_career_stats['prop_sixes_bowl'] + \
                                                self.batting_team.onstrike.historic_career_stats['prop_sixes_bat']

        if self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] > 0:
            self.bowling_team.bowler.current_match_stats['bowler_er_b4b'] = \
                6 * self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] /\
                self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b']
        else:
            self.bowling_team.bowler.current_match_stats['bowler_er_b4b'] = 0
        if self.live_match_state['legal_balls_in_innings_b4b'] > 0:
            self.live_match_state['run_rate_b4b'] = 6 * (self.live_match_state['innings_runs_b4b']
                                                         / self.live_match_state['legal_balls_in_innings_b4b'])
        else:
            self.live_match_state['run_rate_b4b'] = 0

        if self.innings == 2:
            try:
                self.live_match_state['required_run_rate'] = 6 * (self.live_match_state['runs_required'] /
                                                                      self.live_match_state['legal_balls_remaining'])
            except ZeroDivisionError:
                print(self.live_match_state, self.over, self.ball)
                self.live_match_state['required_run_rate'] = 6 * (self.live_match_state['runs_required'] /
                                                                      self.live_match_state['legal_balls_remaining'])

        self.regressors = self.live_match_state.copy()
        self.regressors.update(self.bowling_team.bowler.historic_career_stats)
        self.regressors.update(self.bowling_team.bowler.current_match_stats)
        self.regressors.update(self.batting_team.onstrike.historic_career_stats)
        self.regressors.update(self.batting_team.onstrike.current_match_stats)

        outcomes = ['0', '1', '2', '3', '4', '6', 'w', 'nb', 'W']

        # inn = [self.innings == 2]
        # if self.innings == 1:
        #     inn1_score = 0
        # else:
        #     inn1_score = self.bowling_team.bat_total
        # select relevant models - at this point I need to have gathered all the state.
        # the model that we pick is unlikely to change by ball, so can move out of critical loop.

        # wide
        p_wide = calculate_probit_model_probability(self.regressors, self.wide_model)
        # nb
        p_nb = calculate_probit_model_probability(self.regressors, self.nb_model)
        # wickets
        p_wicket = calculate_probit_model_probability(self.regressors, self.wicket_model)

        p_runs = calculate_mnlogit_model_probabilities(self.regressors, self.runs_model)

        # now normalise runs
        p_runs = [r * (1 - (p_nb + p_wide + p_wicket)) for r in p_runs]

        # note that p_runs + p_wicket + p_wide + p_nb = 1, and the runs model must be adjusted for this!
        probabilities = np.append(p_runs, [p_wide, p_nb, p_wicket])
        # sample from predicted distribution
        outcome = choices(outcomes, probabilities)[0]

        #todo, our historic definition of balls faced is slightly wrong (wides are not a ball faced, no balls are)

    # weird that I'm not including breakdown of bowling/batting stats for the game here - should be included.
    # In other words, means can't use #sixes gone for in this match to predict things... This is because the 'career'
    # figures include the entire match. Need to handle this more intelligently, like the bowling sim.
        self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] += 1

        if outcome == '0':
            self.ball += 1
            self.bowling_team.bowler.current_match_stats['bowler_dots_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']

        elif outcome == '1':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
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
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 2
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
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
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 3
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
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
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 4
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
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
                100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 6
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.live_match_state['over_runs_b4b'] += 6
            self.live_match_state['innings_runs_b4b'] += 6
            self.batting_team.bat_total += 6
            self.bowling_team.bwl_total += 6
            self.batting_team.partnership_runs += 6
            self.live_match_state['partnership_runs_b4b'] += 6
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 6

        elif outcome == 'W':
            self.ball += 1
            self.bowling_team.bwl_wkts += 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_wickets_b4b'] += 1
            self.batting_team.wicket()
            self.live_match_state['partnership_runs_b4b'] = 0

        elif outcome in ['w', 'nb']:
            self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] -= 1
            if self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] != 0:
                self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                    100 * self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                    self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            else:
                self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = 0
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_extras'] += 1
            self.live_match_state['over_runs_b4b'] += 1
            self.live_match_state['innings_runs_b4b'] += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1
            self.batting_team.partnership_runs += 1
            self.live_match_state['partnership_runs_b4b'] += 1
            if self.innings == 2:
                self.live_match_state['runs_required'] -= 1

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

        potential_bowlers = self.bowling_team.bowlers.copy() # {name: Bowler}
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
            outcome = [b for b, v in potential_bowlers.items() if
                       v.historic_career_stats['bowled_over_{}_bowl'.format(self.over)] == 1][0]
            counter = self.over
            bowling_plan = [potential_bowlers[outcome]]
            potential_bowlers = {k: v for k, v in potential_bowlers.items() if
                                 potential_bowlers[k].historic_career_stats['overs_bowled_after_{}_bowl'.format(self.over)] < max_possible_overs}

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
                        b.historic_career_stats['bowled_over_{}_bowl'.format(i)] = 1
                        b.historic_career_stats['overs_bowled_after_{}_bowl'.format(i)] = 1
                    else:
                        b.historic_career_stats['bowled_over_{}_bowl'.format(i)] = 0
                        b.historic_career_stats['overs_bowled_after_{}_bowl'.format(i)] = 0
            else:
                previous_bowler = outcome
                p_b = []
                temp = {k: v for k, v in potential_bowlers.items() if k != previous_bowler}
                for n, b in temp.items():
                    p_b = np.append(p_b, calculate_probit_model_probability(b.historic_career_stats, model))
                    # want to temporarily drop bowler who bowled the last over,
                    # and perma-drop anyone who has bowled 4 overs.
                bowler_prob = p_b / sum(p_b)
                outcome = choices(list(temp.keys()), bowler_prob)[0]
                for n, b in potential_bowlers.items():
                    if n == outcome:
                        b.historic_career_stats['bowled_over_{}_bowl'.format(i)] = 1
                        b.historic_career_stats['overs_bowled_after_{}_bowl'.format(i)] = \
                            b.historic_career_stats['overs_bowled_after_{}_bowl'.format(i - 1)] + \
                            b.historic_career_stats['bowled_over_{}_bowl'.format(i)]
                    else:
                        b.historic_career_stats['bowled_over_{}_bowl'.format(i)] = 0
                        b.historic_career_stats['overs_bowled_after_{}_bowl'.format(i)] = b.historic_career_stats[
                            'overs_bowled_after_{}_bowl'.format(i - 1)]

                if potential_bowlers[outcome].historic_career_stats['overs_bowled_after_{}_bowl'.format(i)] \
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
        ball = [self.historic_match_data[lambda x: x.innings == self.innings].to_dict(orient='records')[0]] #sorry
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
