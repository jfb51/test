import numpy as np

#once we know the XI players and toss outcome, we do this ting
class LiveTeam:
    def __init__(self, name, pre_match_state, career_bowling_data, career_batting_data):
        self.pre_match_state = pre_match_state #this is pre-match state, most import
        self.name = name

        self.batters = {name: LiveBatter(data) for name, data
                        in career_batting_data.items()} # the pp needs to include cricinfo id
        self.bowlers = {name: LiveBowler(data) for name, data
                        in career_bowling_data.items()}

        self.batting_order = {i + 1: x for i, x in enumerate(self.batters.values())}
        # not sure how this will work in practise.

        # batting innings state
        self.bat_total = 0
        self.bat_wkts = 0
        self.partnership_runs = 0

        # bowling innings state
        self.bwl_total = 0
        self.bwl_wkts = 0

        self.onstrike = self.batting_order[1] #local Batter object =
        self.onstrike.current_match_stats['batting_position_bat'] = 1
        self.offstrike = self.batting_order[2]
        self.offstrike.current_match_stats['batting_position_bat'] = 2
        self.bat_bwl = ''

    def populate_with_initial_state(self, live_match_state, simulated_target=None):
        self.simulated_target = simulated_target
        # if I'm the batting team
        if self.name == live_match_state.batting_team:
            self.onstrike = self.batters[live_match_state.striker.name]
            self.offstrike = self.batters[live_match_state.non_striker.name]
            off_strike_stats = live_match_state.non_striker
            # check this case, unsure...
            self.offstrike.insert_initial_stats(off_strike_stats)
                # this is a corner case when batters have crossed after a wicket and
                # the off-strike batter has not faced a ball
#             self.offstrike.current_match_stats['batting_position_bat'] = \
#                     live_match_state.wickets + 2
            self.onstrike.insert_initial_stats(live_match_state.striker)
            # and it's the first innings, then I haven't bowled
            if live_match_state.innings == 1:
                self.bat_total = live_match_state.innings_runs
                self.bat_wkts = live_match_state.wickets_in_innings
                self.partnership_runs = live_match_state.partnership_runs
                self.bat_bwl = 'bat'
                self.bwl_total = 0
                self.bwl_wkts = 0
            # and it's the second innings, I've already bowled and am chasing
            else:
                self.bat_total = live_match_state.innings_runs
                self.bat_wkts = live_match_state.wickets_in_innings
                self.partnership_runs = live_match_state.partnership_runs
                if self.simulated_target is not None:
                    self.bwl_total = self.simulated_target
                else:
                    self.bwl_total = live_match_state.target - 1
                self.bwl_wkts = 'N/A'  # can get this if necessary
                self.bat_bwl = 'bat'
        # if I'm the bowling team
        else:
            # names
            cf_bowlers_so_far = [b for b in live_match_state.bowlers if b.bowler_balls_bowled > 0]
            bowler_names_so_far = [b.name for b in cf_bowlers_so_far]
            jbl_bowlers_so_far = {name: b for name, b in self.bowlers.items() if name in bowler_names_so_far}
            for name, bowler in jbl_bowlers_so_far.items():
                # last ball the bowler has bowled
                # instantiate a new bowler class with the current stats
                bowler.insert_initial_stats([b for b in cf_bowlers_so_far if b.name==name][0])
            # and it's the first innings, then I'm bowling
            if latest_ball['innings'] == 1:
                self.bat_total = 0
                self.bat_wkts = 0
                self.bat_bwl = 'bowl'
                self.bwl_total = live_match_state.innings_runs
                self.bwl_wkts = live_match_state.wickets_in_innings
                self.bowler = self.bowlers[live_match_state.bowler.name] #bowler instance
                self.onstrike = self.batting_order[1]
                self.onstrike.current_match_stats['batting_position_bat'] = 1
                self.offstrike = self.batting_order[2]
                self.offstrike.current_match_stats['batting_position_bat'] = 2
            # and it's the second innings, then I've batted already
            else:
                if self.simulated_target is not None:
                    self.bat_total = self.simulated_target
                else:
                    self.bat_total = live_match_state.target - 1
                self.bat_wkts = 'N/A'
                self.bat_bwl = 'bowl'
                self.bwl_total = live_match_state.innings_runs
                self.bwl_wkts = live_match_state.wickets_in_innings
                self.bowler = self.bowlers[live_match_state.bowler.name]
                self.onstrike = self.batting_order[1]
                self.onstrike.current_match_stats['batting_position_bat'] = 1
                self.offstrike = self.batting_order[2]
                self.offstrike.current_match_stats['batting_position_bat'] = 2

    def zero_all_stats(self):
        for b in self.bowlers.values():
            b.zero_stats()
        for b in self.batters.values():
            b.zero_stats()

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