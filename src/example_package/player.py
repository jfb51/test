class Bowler:
    def __init__(self, name, historic_career_stats, current_match_stats=None):
        bowler_in_game_attributes = ['bowler_extras', 'bowler_runs_b4b', 'bowler_runs',
                                     'bowler_wickets', 'bowler_wickets_b4b', 'bowler_balls_bowled_b4b',
                                     'bowler_balls_bowled', 'bowler_dots', 'bowler_dots_b4b', 'bowler_er',
                                     'bowler_er_b4b']
        self.name = name
        self.historic_career_stats = historic_career_stats.loc[self.name]
        if current_match_stats:
            self.current_match_stats = current_match_stats[bowler_in_game_attributes].to_dict()
        else:
            self.current_match_stats = {c: 0 for c in bowler_in_game_attributes}


class Batter:
    def __init__(self, name, historic_career_stats, current_match_stats=None):
        batter_in_game_attributes = ['batting_position', 'striker_runs', 'striker_runs_b4b', 'striker_balls_faced_b4b',
                                     'striker_balls_faced', 'strike_rate', 'strike_rate_b4b']
        self.name = name
        self.historic_career_stats = historic_career_stats.loc[self.name]
        if current_match_stats:
            self.current_match_stats = current_match_stats[batter_in_game_attributes].to_dict()
        else:
            self.current_match_stats = {c: 0 for c in batter_in_game_attributes}