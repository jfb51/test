class Bowler:
    def __init__(self, pp, historic_career_stats):
        self.bowler_in_game_attributes = ['bowler_extras', 'bowler_runs_b4b', 'bowler_wickets_b4b',
                                          'bowler_balls_bowled_b4b', 'bowler_dots_b4b', 'bowler_er_b4b', 'bowler_prop_0',
                                          'bowler_prop_1', 'bowler_prop_2', 'bowler_prop_4', 'bowler_prop_6']
        self.pp = pp
        self.historic_career_stats = historic_career_stats.loc[self.pp['unique_name']].to_dict(orient='records')[0]
        self.historic_career_stats['bowling_style'] = self.pp['simple_bowling']
        self.current_match_stats = {c: 0 for c in self.bowler_in_game_attributes}

    def insert_initial_stats(self, current_match_stats):
        self.current_match_stats = {attr: current_match_stats[attr] for attr in self.bowler_in_game_attributes}

    def zero_stats(self):
        self.current_match_stats = {c: 0 for c in self.bowler_in_game_attributes}


class Batter:
    def __init__(self, pp, historic_career_stats):
        self.batter_in_game_attributes = ['batting_position_bat', 'striker_runs_b4b', 'striker_balls_faced_b4b',
                                          'strike_rate_b4b', 'striker_prop_0', 'striker_prop_1', 'striker_prop_2',
                                          'striker_prop_4', 'striker_prop_6']
        self.pp = pp
        self.historic_career_stats = historic_career_stats.loc[self.pp['unique_name']].to_dict(orient='records')[0]
        self.historic_career_stats['batting_style'] = self.pp['Batting Style']
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}

    def insert_initial_stats(self, current_match_stats):
        self.current_match_stats = {attr: current_match_stats[attr] for attr in self.batter_in_game_attributes}

    def zero_stats(self):
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}
