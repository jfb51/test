class LiveBowler:
    def __init__(self, historic_career_stats):
        self.bowler_in_game_attributes = ['bowler_runs_b4b', 'bowler_wickets_b4b',
                                          'bowler_balls_bowled_b4b', 'bowler_0_b4b',
                                          'bowler_1_b4b', 'bowler_2_b4b', 'bowler_4_b4b', 'bowler_6_b4b',
                                          'bowler_wides_in_game_b4b']

        self.historic_career_stats = historic_career_stats
        self.current_match_stats = {c: 0 for c in self.bowler_in_game_attributes}

    def insert_initial_stats(self, current_match_stats):
        self.current_match_stats = {attr: getattr(current_match_stats, attr[:-4]) for attr in
                                    self.bowler_in_game_attributes}
        # tidy up

    def zero_stats(self):
        self.current_match_stats = {c: 0 for c in self.bowler_in_game_attributes}


class LiveBatter:
    def __init__(self, historic_career_stats):
        self.batter_in_game_attributes = ['batting_position_bat', 'striker_runs_b4b', 'striker_balls_faced_b4b',
                                          'strike_rate_b4b', 'striker_0_b4b', 'striker_1_b4b', 'striker_2_b4b',
                                          'striker_4_b4b', 'striker_6_b4b']

        self.historic_career_stats = historic_career_stats
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}

    def insert_initial_stats(self, current_match_stats):
        self.current_match_stats = {attr: getattr(current_match_stats, attr[:-4]) for attr in
                                    self.batter_in_game_attributes}
        # tidy up

    def zero_stats(self):
        self.current_match_stats = {c: 0 for c in self.batter_in_game_attributes}