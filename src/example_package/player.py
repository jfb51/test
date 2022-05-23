class Bowler:
    def __init__(self, pp, historic_career_stats):
        self.bowler_in_game_attributes = ['bowler_extras', 'bowler_runs_b4b', 'bowler_wickets_b4b',
                                          'bowler_balls_bowled_b4b', 'bowler_dots_b4b', 'bowler_er_b4b', 'bowler_0_b4b',
                                          'bowler_1_b4b', 'bowler_2_b4b', 'bowler_4_b4b', 'bowler_6_b4b',
                                          'bowler_wides_in_game']
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
                                          'strike_rate_b4b', 'striker_0_b4b', 'striker_1_b4b', 'striker_2_b4b',
                                          'striker_4_b4b', 'striker_6_b4b']
        self.pp = pp
        self.historic_career_stats = historic_career_stats.loc[self.pp['unique_name']].to_dict(orient='records')[0]
        self.historic_career_stats['batting_style'] = self.pp['Batting Style']
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}

    def insert_initial_stats(self, current_match_stats):
        self.current_match_stats = {attr: current_match_stats[attr] for attr in self.batter_in_game_attributes}

    def zero_stats(self):
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}
