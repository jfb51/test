from example_package.team import SimpleHistoricTeam
import copy
from scipy.signal import savgol_filter
from collections import OrderedDict
import numpy as np
from collections import Counter
from operator import attrgetter


class HistoricMatchSimulator:
    def __init__(self, match_id, match_row, historic_match_data, career_bowling_data,
                 career_batting_data, wicket_models, run_models, wide_models, nb_models, bowling_models):
        self.match_id = str(match_id)
        self.wicket_models = wicket_models
        self.run_models = run_models
        self.bowling_models = bowling_models
        self.wide_model = wide_models
        self.nb_models = nb_models
        self.match_row = match_row
        self.historic_match_data = historic_match_data
        self.career_bowling_data = career_bowling_data
        self.career_batting_data = career_batting_data
        self.bowling_plan = []
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
        # self.tan_dict = dict(zip(np.arange(0, 120), np.tan(np.arange(0, 120) / 120)))

    def sim_match(self, match_or_innings, initial_match_state=None, simulated_target=None):

        if initial_match_state:
            self.innings = initial_match_state['innings']
            self.over = initial_match_state['over']
            self.ball = initial_match_state['legal_balls_in_innings_b4b'] % 6
            self.batting_team = SimpleHistoricTeam(initial_match_state['batting_team'],
                                                   self.match_row, self.career_bowling_data, self.career_batting_data,
                                                   initial_match_state, simulated_target)
            # what's the first innings total in this case?
            self.bowling_team = SimpleHistoricTeam(initial_match_state['bowling_team'],
                                                   self.match_row, self.career_bowling_data, self.career_batting_data,
                                                   initial_match_state, simulated_target)

            if self.innings == 1:
                self.setting_team = self.batting_team.name
                self.chasing_team = self.bowling_team.name
            else:
                self.chasing_team = self.batting_team.name
                self.setting_team = self.bowling_team.name

        self.bowling_plan = self.sim_bowlers_for_innings()
        # returns a list of Bowlers to bowl out the remainder

        while self.innings == 1:
            while (self.over <= 20) and (self.batting_team.bat_wkts < 10):
                self.sim_over()
            if match_or_innings == 'innings':
                return [self.batting_team.name, self.batting_team.bat_total, self.batting_team.bat_wkts]
            else:
                self.change_inns()
                self.bowling_plan = self.sim_bowlers_for_innings()

        while (self.over <= 20) and (self.batting_team.bat_wkts < 10) and (self.batting_team.bat_total
                                                                           <= self.bowling_team.bat_total):
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

    def sim_ball(self):
        # module to simulate a ball
        # get model inputs from match state
        # anything above the "outcomes" has to be state as of before the ball is bowled.
        # anything below the "outcomes" is updating state for the next ball, given we now know outcome of this ball.

        self.wickets_in_innings_b4b = int(self.batting_team.bat_wkts)
        self.legal_balls_in_innings_b4b = (self.over - 1) * 6 + self.ball
        self.legal_balls_remaining_in_innings = 120 - self.legal_balls_in_innings_b4b
        self.is_first_ball = int(self.ball == 0)
        self.is_last_ball = int(self.ball == 5)
        self.bowler_er_b4b = self.bowling_team.bowler.current_match_stats['bowler_runs_b4b']/\
                             self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b']
        self.run_rate_b4b = 6 * (self.innings_runs_b4b/self.legal_balls_in_innings_b4b)
        self.bowler_dots_b4b = self.bowling_team.bowler.current_match_stats['bowler_dots_b4b']
        self.bowler_balls_bowled_b4b = self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b']
        self.bowler_runs_b4b = self.bowling_team.bowler.current_match_stats['bowler_runs_b4b']
        self.partnership_runs_b4b = self.batting_team.partnership_runs
        self.striker_balls_faced_b4b = self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
        self.striker_runs_b4b = self.batting_team.onstrike.current_match_stats['striker_runs_b4b']
        self.strike_rate_b4b = self.batting_team.onstrike.current_match_stats['strike_rate_b4b']

        if self.innings == 2:
            self.required_run_rate_b4b = 6 * (self.runs_required/self.legal_balls_remaining_in_innings)

        outcomes = ['0', '1', '2', '3', '4', '6', 'w', 'nb', 'W']

        inn = [self.innings == 2]
        if self.innings == 1:
            inn1_score = 0
        else:
            inn1_score = self.bowling_team.bat_total

        # select relevant models

        for model in self.wide_models:
            if model.condition(self):
                break
        p_wide = model.lookup_dict[attrgetter(*model.model_variables)(self)]

        # nb
        for model in self.nb_models:
            if model.condition(self):
                break
        p_no_ball = model.lookup_dict[attrgetter(*model.model_variables)(self)]

        # wickets
        for model in self.wicket_models:
            if model.condition(self):
                break
        p_wicket = model.lookup_dict[attrgetter(*model.model_variables)(self)]

        # runs
        for model in self.run_models:
            if model.condition(self):
                break
        p_runs = model.lookup_dict[attrgetter(*model.model_variables)(self)]

        # now normalise runs
        p_runs = p_runs * (1 - (p_no_ball + p_wide + p_wicket))

        # note that p_runs + p_wicket + p_wide + p_nb = 1, and the runs model must be adjusted for this!
        probabilities = np.append(p_runs, [p_wide, p_no_ball, p_wicket])  # 10%
        # sample from predicted distribution
        outcome = np.random.choice(a=outcomes, size=1, p=probabilities)  # 38%

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
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']

        elif outcome == '1':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.over_runs_b4b += 1
            self.innings_runs_b4b += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1
            self.batting_team.partnership_runs += 1
            self.batting_team.change_ends()
            if self.innings == 2:
                self.runs_required -= 1

        elif outcome == '2':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 2
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 2
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.over_runs_b4b += 2
            self.innings_runs_b4b += 2
            self.batting_team.bat_total += 2
            self.bowling_team.bwl_total += 2
            self.batting_team.partnership_runs += 2
            if self.innings == 2:
                self.runs_required -= 2

        elif outcome == '3':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 3
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 3
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.over_runs_b4b += 3
            self.innings_runs_b4b += 3
            self.batting_team.bat_total += 3
            self.bowling_team.bwl_total += 3
            self.batting_team.partnership_runs += 3
            if self.innings == 2:
                self.runs_required -= 3
            self.batting_team.change_ends()

        elif outcome == '4':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 4
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 4
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.over_runs_b4b += 4
            self.innings_runs_b4b += 4
            self.batting_team.bat_total += 4
            self.bowling_team.bwl_total += 4
            self.batting_team.partnership_runs += 4
            if self.innings == 2:
                self.runs_required -= 4

        elif outcome == '6':
            self.ball += 1
            self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] += 6
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 6
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.over_runs_b4b += 6
            self.innings_runs_b4b += 6
            self.batting_team.bat_total += 6
            self.bowling_team.bwl_total += 6
            self.batting_team.partnership_runs += 6
            if self.innings == 2:
                self.runs_required -= 6

        elif outcome == 'W':
            self.ball += 1
            self.bowling_team.bwl_wkts += 1
            self.bowling_team.bowler.current_match_stats['bowler_balls_bowled_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_wickets_b4b'] += 1
            self.bowler_wickets_b4b = self.bowling_team.bowler.current_match_stats['bowler_wickets_b4b']
            self.batting_team.wicket()

        elif outcome in ['w', 'nb']:
            self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b'] -= 1
            self.batting_team.onstrike.current_match_stats['strike_rate_b4b'] = \
                self.batting_team.onstrike.current_match_stats['striker_runs_b4b'] /\
                self.batting_team.onstrike.current_match_stats['striker_balls_faced_b4b']
            self.bowling_team.bowler.current_match_stats['bowler_runs_b4b'] += 1
            self.bowling_team.bowler.current_match_stats['bowler_extras'] += 1
            self.bowler_extras = self.bowling_team.bowler.current_match_stats['bowler_extras']
            self.over_runs_b4b += 1
            self.innings_runs_b4b += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1
            self.batting_team.partnership_runs += 1
            if self.innings == 2:
                self.runs_required -= 1

        return outcome

    def sim_over(self):
        # module to simulate an over
        self.is_middle_overs = (self.over > 6) & (self.over < 17)
        self.is_death_overs = self.over > 16
        self.is_powerplay = self.over < 6
        # need to tweak for BBL in 2020, 21 (19?)

        while (self.ball < 6) and (self.batting_team.bat_wkts < 10) and \
                ((self.innings == 1) or (self.batting_team.bat_total <= self.bowling_team.bat_total)):
            self.bowling_team.bowler = self.bowling_plan[self.over - 1] # returns Bowler instance
            self.sim_ball()

        self.ball = 0
        self.batting_team.new_over()
        self.bowling_team.new_over()

        self.over += 1

    def change_inns(self):
        # module to swap bowling and batting sides after 1st innings
        temp = self.batting_team
        self.batting_team = self.bowling_team
        self.bowling_team = temp
        self.batting_team.bat_bwl = 'bat'
        self.bowling_team.bat_bwl = 'bwl'
        self.over = 1
        self.ball = 0
        self.innings = 2

    def sim_bowlers_for_innings(self):
        # module to simulate bowlers who will bowl throughout the innings.
        # NB this simple at the moment, we don't change in response to the progression of the innings yet, we just
        # assume the captain decides on all bowlers at start of innings and sticks with this plan.
        max_possible_overs = 4
        bowled_over_cols = ['bowled_over_{}'.format(i) for i in range(1, 21)]
        overs_bowled_cols = ['overs_bowled_after_{}'.format(i) for i in range(1, 21)]
        irl_columns = ['bowled_over_{}_irl'.format(i) for i in range(1, 21)]
        irl_ob_columns = ['overs_bowled_after_{}_irl'.format(i) for i in range(1, 21)]

        potential_bowlers = [n.name for n in self.bowling_team.bowlers]
        bowler_careers = self.career_bowling_data[lambda x: x.index.isin(potential_bowlers)] #this seems awkward

        for column in bowled_over_cols:
            bowler_careers = bowler_careers.rename(columns={column: '{}_irl'.format(column)})

        # special case is very first ball, no one has been picked to bowl
        if ~(self.over == 1 & self.ball == 0):
            counter = 0
        else:
            bowler_careers[bowled_over_cols[:self.over]] = bowler_careers[irl_columns[:self.over]]
            bowler_careers[overs_bowled_cols[:self.over]] = bowler_careers[irl_ob_columns[:self.over]]
            outcome = bowler_careers[lambda x: x['bowled_over_{}'.format(self.over)]['name']]
            counter = self.over

        # drop any bowlers who have bowled out
        bowler_careers = bowler_careers.drop(
            bowler_careers[bowler_careers['overs_bowled_after_{}'.format(self.over)] == max_possible_overs].index)

        remaining_bowlers = []

        for i in range(counter + 1, 21):
            model = self.bowling_models['bowling_model_{}'.format(i)]
            regressor_names = model.model.exog_names[1:]
            if i == 1:
                bowler_prob = model.predict(bowler_careers[regressor_names].fillna(0))
                bowler_prob = bowler_prob / sum(bowler_prob)
                outcome = np.random.choice(a=bowler_prob.index, size=1, p=bowler_prob.values)[0]
                bowler_careers.loc[outcome, 'bowled_over_{}'.format(i)] = 1
                bowler_careers.loc[outcome, 'overs_bowled_after_{}'.format(i)] = 1
                bowler_careers['bowled_over_{}'.format(i)] = bowler_careers['bowled_over_{}'.format(i)].fillna(0)
                bowler_careers['overs_bowled_after_{}'.format(i)] = bowler_careers[
                    'overs_bowled_after_{}'.format(i)].fillna(0)
            else:
                previous_bowler = outcome
                if previous_bowler in bowler_careers.index:
                    # want to temporarily drop bowler who bowled the last over,
                    # and perma-drop anyone who has bowled 4 overs.
                    bowler_prob = model.predict(bowler_careers.drop(previous_bowler)[regressor_names].fillna(0))
                else:
                    bowler_prob = model.predict(bowler_careers[regressor_names].fillna(0))
                bowler_prob = bowler_prob / sum(bowler_prob)
                outcome = np.random.choice(a=bowler_prob.index, size=1, p=bowler_prob.values)[0]
                bowler_careers.loc[outcome, 'bowled_over_{}'.format(i)] = 1
                bowler_careers['bowled_over_{}'.format(i)] = bowler_careers['bowled_over_{}'.format(i)].fillna(0)
                bowler_careers['overs_bowled_after_{}'.format(i)] = bowler_careers[
                    'overs_bowled_after_{}'.format(i - 1)]
                bowler_careers.loc[outcome, 'overs_bowled_after_{}'.format(i)] = \
                    bowler_careers.loc[outcome, 'overs_bowled_after_{}'.format(i - 1)] + 1
                if bowler_careers.loc[outcome, 'overs_bowled_after_{}'.format(i)] == max_possible_overs:
                    bowler_careers = bowler_careers.drop(outcome)
            remaining_bowlers.append(self.bowlers[outcome])

        return remaining_bowlers

    # for an historic match, during the second innings, what is p(win|state of the game) for each ball in the innings?
    # note we cannot SavGol smooth these probabilities since this would use future information.

    def historic_second_innings_sim(self, n, verbose=False):
        self.innings = 2
        second_innings_data = self.historic_match_data[lambda x: x.innings == self.innings].to_dict(orient='records')
        j = 0
        winner = []
        second_innings_win_pct = OrderedDict()
        for ball in second_innings_data:
            while j < n:
                x = self.sim_match('match', ball)
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
        j = 0
        winner = []
        scores = np.arange(40, 240)
        ball = self.historic_match_data[lambda x: x.innings == self.innings].to_dict(orient='records')[0]
        score_to_prob_map = OrderedDict()
        for score in scores:
            while j < n:
                x = self.sim_match('match', ball, score)
                winner.append(x[0])
                j += 1
            c = Counter(winner)
            if verbose:
                print('Chasing win % from ball {} is {}'.format(j, c[ball['batting_team']] / (
                        c[ball['bowling_team']] + c[ball['batting_team']] + c['Tie'])))
            j = 0
            winner = []
            sample_proportion = c[ball['batting_team']] / (c[ball['bowling_team']] + c[ball['batting_team']] + c['Tie'])
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
        for ball in first_innings_data:
            while j < n:
                x = self.sim_match('innings', ball)
                j += 1
                scores.append(max(min(x[1], 239), 40))
            simulated_first_innings_scores[ball['ball']] = scores
            j = 0
            scores = []
        return simulated_first_innings_scores
