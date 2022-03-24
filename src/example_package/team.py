import numpy as np
from example_package.player import Batter, Bowler


class SimpleHistoricTeam:
    def __init__(self, name, match_row, career_bowling_data, career_batting_data, initial_match_state=None,
                 simulated_target=None):
        self.match_row = match_row
        self.name = name  # team name
        self.career_bowling_data = career_bowling_data
        self.career_batting_data = career_batting_data
        self.initial_match_state = initial_match_state
        self.simulated_target = simulated_target

        if self.name == self.match_row['setting_team']:
            self.batters = [Batter(name, pp, career_batting_data) for name, pp
                            in self.match_row['setting_players'].items()]
            self.bowlers = [Bowler(name, pp, career_bowling_data) for name, pp in self.match_row['setting_bowlers'].items()]
        else:
            self.batters = [Batter(name, pp, career_batting_data) for name, pp
                            in self.match_row['chasing_players'].items()]
            self.bowlers = [Bowler(name, pp, career_bowling_data) for name, pp in self.match_row['chasing_bowlers'].items()]

        self.batting_order = {i + 1: x for i, x in enumerate(self.batters)}  # batting order

            # batting innings state
        self.bat_total = 0
        self.bat_wkts = 0
        self.partnership_runs = 0

        # bowling innings state
        self.bwl_total = 0
        self.bwl_wkts = 0

        self.onstrike = self.batting_order[1]
        self.onstrike.current_match_stats['batting_position_bat'] = 1
        self.offstrike = self.batting_order[2]
        self.offstrike.current_match_stats['batting_position_bat'] = 2
        self.bat_bwl = ''

        if self.initial_match_state is not None:
            latest_ball = self.initial_match_state[-1]
            # if I'm the batting team
            if self.name == latest_ball['batting_team']:
                off_strike_stats = \
                    [b for b in self.initial_match_state if b['striker'] == latest_ball['non_striker']]
                if len(off_strike_stats) > 0:
                    off_strike_stats = off_strike_stats[-1]
                else:
                    off_strike_stats = None
                if self.name == self.match_row['setting_team']:
                    players = self.match_row['setting_players']
                else:
                    players = self.match_row['chasing_players']
                    self.onstrike.insert_initial_stats(latest_ball)
                    self.offstrike.insert_initial_stats(off_strike_stats)
                # and it's the first innings, then I haven't bowled
                if latest_ball['innings'] == 1:
                    self.bat_total = latest_ball['innings_runs_b4b']
                    self.bat_wkts = latest_ball['wickets_in_innings_b4b']
                    self.partnership_runs = latest_ball['partnership_runs_b4b']
                    self.bat_bwl = 'bat'
                    self.bwl_total = 0
                    self.bwl_wkts = 0
                # and it's the second innings, I've already bowled and am chasing
                else:
                    self.bat_total = latest_ball['innings_runs_b4b']
                    self.bat_wkts = latest_ball['wickets_in_innings_b4b']
                    self.partnership_runs = latest_ball['partnership_runs_b4b']
                    if self.simulated_target is not None:
                        self.bwl_total = self.simulated_target
                    else:
                        self.bwl_total = self.match_row['first_innings_score']
                    self.bwl_wkts = 'N/A'  # can get this if necessary
                    self.bat_bwl = 'bat'
            # if I'm the bowling team
            else:
                # names
                bowler_names_so_far = set([b['bowler'] for b in self.initial_match_state])
                bowlers_so_far = [b for b in self.bowlers if b.name in bowler_names_so_far]
                for bowler in bowlers_so_far:
                    # last ball the bowler has bowled
                    other_bowler_stats = [b for b in self.initial_match_state if b['bowler'] == bowler.name][-1]
                    # instantiate a new bowler class with the current stats
                    bowler.insert_initial_stats(other_bowler_stats)
                # and it's the first innings, then I'm bowling
                if latest_ball['innings'] == 1:
                    self.bat_total = 0
                    self.bat_wkts = 0
                    self.bat_bwl = 'bowl'
                    self.bwl_total = latest_ball['innings_runs_b4b']
                    self.bwl_wkts = latest_ball['wickets_in_innings_b4b']
                    self.bowler = [b for b in self.bowlers if b.name == latest_ball['bowler']][0]
                    self.onstrike = self.batting_order[1]
                    self.onstrike.current_match_stats['batting_position_bat'] = 1
                    self.offstrike = self.batting_order[2]
                    self.offstrike.current_match_stats['batting_position_bat'] = 2
                # and it's the second innings, then I've batted already
                else:
                    if self.simulated_target is not None:
                        self.bat_total = self.simulated_target
                    else:
                        self.bat_total = self.match_row['first_innings_score']
                    self.bat_wkts = 'N/A'
                    self.bat_bwl = 'bowl'
                    self.bwl_total = latest_ball['innings_runs_b4b']
                    self.bwl_wkts = latest_ball['wickets_in_innings_b4b']
                    self.bowler = [b for b in self.bowlers if b.name == latest_ball['bowler']][0]
                    self.onstrike = self.batting_order[1]
                    self.onstrike.current_match_stats['batting_position_bat'] = 1
                    self.offstrike = self.batting_order[2]
                    self.offstrike.current_match_stats['batting_position_bat'] = 2

    def wicket(self):
        # module for updating the team after a wicket
        self.bat_wkts += 1
        self.partnership_runs = 0
        if self.bat_wkts < 10:
            self.onstrike = self.batting_order[self.bat_wkts + 2]
            self.onstrike.current_match_stats['batting_position_bat'] = self.bat_wkts + 2

    def new_over(self):
        # module to start a new over
        if self.bat_bwl == 'bat':
            self.change_ends()

    def change_ends(self):
        # module to change the on-strike batter between overs
        temp = self.onstrike
        self.onstrike = self.offstrike
        self.offstrike = temp
