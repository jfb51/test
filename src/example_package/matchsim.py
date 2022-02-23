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
        self.bowler = None
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
        # self.bowling_style_dict = self.create_historic_bowling_style()
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
            self.batting_team = SimpleHistoricTeam(toss_loser, self.match_row)
            self.bowling_team = SimpleHistoricTeam(toss_winner, self.match_row)
        else:
            self.batting_team = SimpleHistoricTeam(toss_winner, self.match_row)
            self.bowling_team = SimpleHistoricTeam(toss_loser, self.match_row)
        self.setting_team = self.batting_team.name
        self.chasing_team = self.bowling_team.name

        self.comm = []
        self.winner = ''
        self.tan_dict = dict(zip(np.arange(0, 120), np.tan(np.arange(0, 120) / 120)))

    def sim_match(self, match_or_innings, initial_match_state=None, simulated_target=None):

        if initial_match_state:
            self.innings = initial_match_state['innings']
            self.over = initial_match_state['over']
            self.ball = initial_match_state['legal_balls_in_innings_b4b'] % 6
            self.batting_team = SimpleHistoricTeam(initial_match_state['batting_team'],
                                                   self.match_row, initial_match_state, simulated_target)
            # what's the first innings total in this case?
            self.bowling_team = SimpleHistoricTeam(initial_match_state['bowling_team'],
                                                   self.match_row, initial_match_state, simulated_target)

            if self.innings == 1:
                self.setting_team = self.batting_team.name
                self.chasing_team = self.bowling_team.name
            else:
                self.chasing_team = self.batting_team.name
                self.setting_team = self.bowling_team.name

        self.bowling_plan = self.sim_bowlers_for_innings() #returns a list of bowlers to bowl out the remainder

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
        #         bowler = self.bowling_team.bowler
        batter = self.batting_team.onstrike
        # bwl_stats = self.bowling_team.get_probs(bowler, 'bwl')
        # bat_stats = self.batting_team.get_probs(batter, 'bat')
        self.wickets_in_innings_b4b = int(self.batting_team.bat_wkts)
        self.legal_balls_in_innings_b4b = (self.over - 1) * 6 + self.ball
        self.legal_balls_remaining_in_innings = 120 - self.legal_balls_in_innings_b4b
        self.is_first_ball = int(self.ball == 0)
        self.is_powerplay = int(self.over <= 6)
        self.ball_regressor = self.tan_dict[self.legal_balls_in_innings_b4b]

        outcomes = ['0', '1', '2', '4', '6', 'w', 'nb', 'W']

        inn = [self.innings == 2]
        if self.innings == 1:
            inn1_score = 0
        else:
            inn1_score = self.bowling_team.bat_total

        # select relevant models

        # wides
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

        # increment balls faced for batter
        # self.t_bat.ply_stats[self.t_bat.onstrike]['balls'] += 1

        # update match and team state based on ball result
        if outcome == '0':
            self.ball += 1

        elif outcome == '1':
            self.ball += 1
            # self.t_bat.ply_stats[self.t_bat.onstrike]['runs'] += 1
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1
            self.batting_team.change_ends()

        elif outcome == '2':
            self.ball += 1
            # self.t_bat.ply_stats[self.t_bat.onstrike]['runs'] += 2
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 2
            self.batting_team.bat_total += 2
            self.bowling_team.bwl_total += 2

        # TODO: reincorporate 3's at some point

        # elif res == 'res_3':
        #     self.ball += 1
        #     self.t_bat.ply_stats[self.t_bat.onstrike]['runs'] += 3
        #     self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 3
        #     self.t_bat.bat_total += 3
        #     self.t_bwl.bwl_total += 3
        #     self.t_bat.change_ends()

        elif outcome == '4':
            self.ball += 1
            # self.t_bat.ply_stats[self.t_bat.onstrike]['runs'] += 4
            # self.t_bat.ply_stats[self.t_bat.onstrike]['4s'] += 1
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 4
            self.batting_team.bat_total += 4
            self.bowling_team.bwl_total += 4

        elif outcome == '6':
            self.ball += 1
            # self.t_bat.ply_stats[self.t_bat.onstrike]['runs'] += 6
            # self.t_bat.ply_stats[self.t_bat.onstrike]['6s'] += 1
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 6
            self.batting_team.bat_total += 6
            self.bowling_team.bwl_total += 6

        elif outcome == 'W':
            self.ball += 1
            self.bowling_team.bwl_wkts += 1
            # self.t_bat.ply_stats[self.t_bat.onstrike]['out'] = 1
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['wickets'] += 1
            self.batting_team.wicket()

        elif outcome in ['w', 'nb']:
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['runs_off'] += 1
            # self.t_bwl.ply_stats[self.t_bwl.bowler]['wides'] += 1
            self.batting_team.bat_total += 1
            self.bowling_team.bwl_total += 1

        return outcome

    def sim_over(self):
        # module to simulate an over
        while (self.ball < 6) and (self.batting_team.bat_wkts < 10) and \
                ((self.innings == 1) or (self.batting_team.bat_total <= self.bowling_team.bat_total)):

            self.bowler = self.bowling_plan[self.over-1]
            # self.batting_team.onstrike
            self.sim_ball()

        self.ball = 0

        self.batting_team.new_over()
        self.bowling_team.new_over()

        self.over += 1

    # def toss(self):
    #     # module to simulate the coin toss
    #     if np.random.uniform() > 0.5:
    #         temp = self.t_bat
    #         self.t_bat = self.t_bwl
    #         self.t_bwl = temp
    #     self.t_bat.bat_bwl = 'bat'
    #     self.t_bwl.bat_bwl = 'bwl'
    #     if self.verbose:
    #         if np.random.uniform() > 0.5:
    #             won_toss = self.t_bat.name
    #         else:
    #             won_toss = self.t_bwl.name
    #         print('The {} have won the toss!'.format(won_toss))
    #         print('{} will bat first. {} to bowl.'.format(self.t_bat.name, self.t_bwl.name))

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

    # def create_historic_bowling_style(self):
    #     match_dict = self.historic_match_data.to_dict(orient='records')
    #     bowling_style_dict = {}
    #     for element in match_dict:
    #         bowling_style_dict[(element['innings'], element['over'])] = element['is_spin']
    #     return bowling_style_dict

    def sim_bowlers_for_innings(self):
        # module to simulate bowlers who will bowl throughout the innings.
        # NB this simple at the moment, we don't change in response to the progression of the innings yet.
        max_possible_overs = 4
        bowled_over_cols = ['bowled_over_{}'.format(i) for i in range(1, 21)]
        overs_bowled_cols = ['overs_bowled_after_{}'.format(i) for i in range(1, 21)]
        irl_columns = ['bowled_over_{}_irl'.format(i) for i in range(1, 21)]
        irl_ob_columns = ['overs_bowled_after_{}_irl'.format(i) for i in range(1, 21)]

        if self.innings == 1:
            potential_bowlers = self.match_row['chasing_bowlers']
        else:
            potential_bowlers = self.match_row['setting_bowlers']

        potential_bowlers = [bowler['name'] for bowler in potential_bowlers]
        bowler_careers = self.career_bowling_data[lambda x: x.index.isin(potential_bowlers)]

        for column in bowled_over_cols:
            bowler_careers = bowler_careers.rename(columns={column: '{}_irl'.format(column)})

        # special case is very first ball, no one has been picked to bowl
        if ~(self.over == 1 & self.ball == 0):
            bowler_careers[bowled_over_cols[:self.over]] = bowler_careers[irl_columns[:self.over]]
            bowler_careers[overs_bowled_cols[:self.over]] = bowler_careers[irl_ob_columns[:self.over]]
            counter = 0
        else:
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
            remaining_bowlers.append(outcome)

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
