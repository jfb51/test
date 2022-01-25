import numpy as np


class SimpleHistoricTeam:
    def __init__(self, name, player_info, match_row, initial_match_state=None,
                 simulated_target=None):
        self.name = name  # team name
        self.bat_order = player_info[self.name]
        self.match_row = match_row
        self.order = {i + 1: x for i, x in enumerate(self.bat_order)}  # batting order
        self.initial_match_state = initial_match_state
        self.simulated_target = simulated_target

        if self.initial_match_state is None:
            # batting innings state
            self.bat_total = 0
            self.bat_wkts = 0

            # bowling innings state
            self.bwl_total = 0
            self.bwl_wkts = 0

            self.onstrike = self.order[1]
            self.offstrike = self.order[2]
            self.bat_bwl = ''

        else:
            # if I'm the batting team
            if self.name == self.initial_match_state['batting_team']:
                # and it's the first innings, then I haven't bowled
                if self.initial_match_state['innings'] == 1:
                    self.bat_total = self.initial_match_state['innings_runs_b4b']
                    self.bat_wkts = self.initial_match_state['wickets_in_innings_b4b']
                    self.onstrike = self.initial_match_state['striker']
                    self.offstrike = self.initial_match_state['non_striker']
                    self.bat_bwl = 'bat'
                    self.bwl_total = 0
                    self.bwl_wkts = 0
                # and it's the second innings, I've already bowled and am chasing
                else:
                    self.bat_total = self.initial_match_state['innings_runs_b4b']
                    self.bat_wkts = self.initial_match_state['wickets_in_innings_b4b']
                    self.onstrike = self.initial_match_state['striker']
                    self.offstrike = self.initial_match_state['non_striker']
                    if self.simulated_target is not None:
                        self.bwl_total = self.simulated_target
                    else:
                        self.bwl_total = self.match_row.first_innings_score
                    self.bwl_wkts = 'N/A'  # can get this if necessary
                    #                     self.bowler = self.initial_match_state.bowler
                    self.bat_bwl = 'bat'
            # if I'm the bowling team
            else:
                # and it's the first innings, then I'm bowling
                if self.initial_match_state['innings'] == 1:
                    self.bat_total = 0
                    self.bat_wkts = 0
                    self.bat_bwl = 'bowl'
                    self.bwl_total = self.initial_match_state['innings_runs_b4b']
                    self.bwl_wkts = self.initial_match_state['wickets_in_innings_b4b']
                    self.bowler = self.initial_match_state['bowler']
                    self.onstrike = self.order[1]
                    self.offstrike = self.order[2]
                # and it's the second innings, then I've batted already
                else:
                    if self.simulated_target is not None:
                        self.bat_total = self.simulated_target
                    else:
                        self.bat_total = self.match_row.first_innings_score
                    self.bat_wkts = 'N/A'
                    self.bat_bwl = 'bowl'
                    self.bwl_total = self.initial_match_state['innings_runs_b4b']
                    self.bwl_wkts = self.initial_match_state['wickets_in_innings_b4b']
                    self.onstrike = self.order[1]
                    self.offstrike = self.order[2]


    def nxt_bowler(self, first_over=False):
        # module to choose next bowler
        if first_over:
            lst_bwler = ''
        else:
            lst_bwler = self.bowler

        pids = []
        probs = []
        for pid in self.ply_stats:
            if (pid != lst_bwler) and (self.ply_stats[pid]['overs'] < 4):
                pids.append(pid)
                probs.append(self.ply_stats[pid]['ave_overs'])

        return np.random.choice(a=pids, size=1, p=np.array(probs) / sum(probs))[0]

    def wicket(self):
        # module for updating the team after a wicket
        self.bat_wkts += 1
        if self.bat_wkts < 10:
            self.onstrike = self.order[self.bat_wkts + 2]

    def new_over(self):
        # module to start a new over
        if self.bat_bwl == 'bat':
            self.change_ends()

    def change_ends(self):
        # module to change the on-strike batter between overs
        temp = self.onstrike
        self.onstrike = self.offstrike
        self.offstrike = temp
