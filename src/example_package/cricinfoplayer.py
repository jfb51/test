# we have to update some shit before the next event happens because we find out too late! e.g. bowler, batsmen

# for batter, I get ball n (say 4) and want to simulate from next ball onwards, so the aim
# is to set the state for ball 5 here

# batter object needs instantiation when? start of game you'd think...bowlers trickier

class Batter:
    def __init__(self, player):
        self.id = player.id
        self.playingRole = player.playingRole
        self.name = player.name
        self.batting_position = 0
        self.striker_runs = 0
        self.striker_balls_faced = 0
        self.strike_rate = 0
        self.striker_0 = 0
        self.striker_1 = 0
        self.striker_2 = 0
        self.striker_4 = 0
        self.striker_6 = 0


class Bowler:
    def __init__(self, player):
        self.id = player.id
        self.playingRole = player.playingRole
        self.bowling_style = player.longBowlingStyles
        self.name = player.name
        self.bowler_balls_bowled = 0
        self.bowler_runs = 0
        self.bowler_wides_in_game = 0
        self.bowler_wickets = 0
        self.bowler_0 = 0
        self.bowler_1 = 0
        self.bowler_2 = 0
        self.bowler_4 = 0
        self.bowler_6 = 0


class PreMatchState:
    def __init__(self):
        self.venue = ''
        self.teams = []
        self.setting_team = ''
        self.chasing_team = ''
        self.event_name = ''
        self.setting_players = []
        self.chasing_players = []
        self.avg_ground_rpo = 0

    def update_some_stuff(self, pre_match_object):
        self.venue = pre_match_object.match.ground.name
        self.teams = pre_match_object.match.teams
        toss_winner = pre_match_object.match.tossWinnerTeamId
        toss_choice = pre_match_object.match.tossWinnerChoice
        toss_winning_team = [t for t in self.teams if t.team.id == toss_winner][0]
        toss_losing_team = [t for t in self.teams if t.team.id != toss_winner][0]
        if toss_choice == 1:
            self.setting_team = toss_winning_team.team.name
            self.chasing_team = toss_losing_team.team.name
        else:
            self.setting_team = toss_losing_team.team.name
            self.chasing_team = toss_winning_team.team.name
        self.event_name = 'International'  # not sure yet
        self.setting_players = \
        [t.players for t in pre_match_object.matchPlayers.teamPlayers if t.team.name == self.setting_team][0]
        self.chasing_players = \
        [t.players for t in pre_match_object.matchPlayers.teamPlayers if t.team.name == self.chasing_team][0]
        self.avg_ground_rpo = 8


class LiveMatchState:
    def __init__(self, pre_match_object):  # wut?):
        self.runs_required = 0
        self.innings_runs = 0
        self.required_run_rate = 0
        self.target = 0
        self.run_rate = 0
        self.innings = 1
        self.over = 1
        self.ball = 0
        self.timestamp = 0
        self.wickets_in_innings = 0
        self.batter_id = 0
        self.non_striker_id = 0
        self.bowler_id = 0
        self.batter_runs_on_ball = 0
        self.total_runs_on_ball = 0
        self.wides = 0
        self.no_balls = 0
        self.batters = [Batter(b.player) for b in pre_match_object.setting_players]
        self.bowlers = [Bowler(b.player) for b in pre_match_object.chasing_players]  # handle innings change...
        self.striker = ''
        self.non_striker = ''
        self.bowler = ''
        self.batting_team = pre_match_object.setting_team
        self.bowling_team = pre_match_object.chasing_team  # change over at end of innings
        self.legal_balls_in_innings = 0
        self.legal_balls_remaining_in_innings = 120
        self.batting_position_bat = 0
        self.striker_runs = 0
        self.striker_balls_faced_ = 0
        self.strike_rate = 0
        self.non_striker_runs = 0
        self.non_striker_balls_faced_ = 0
        self.non_striker_strike_rate = 0
        self.bowler_balls_bowled = 0
        self.batting_partners = []
        self.partnership_runs = 0
        self.wicket = 0
        self.runs_inc_blb = 0
        self.is_wide = 0
        self.is_no_ball = 0
        self.bowler_wides_in_game = 0
        self.comm_id = 0

    def update(self, latest_comment):
        latest_ball = latest_comment.recentBallCommentary.ballComments[0]
        self.innings = latest_ball.inningNumber
        latest_scorecard = latest_comment.scorecard.innings[self.innings - 1]
        self.over = latest_ball.overNumber
        self.balls_actual = int(str(latest_ball.oversActual).split('.')[-1])
        self.balls_unique = latest_ball.ballNumber
        self.legal_balls_in_innings = latest_scorecard.balls
        self.legal_balls_remaining_in_innings = 120 - latest_scorecard.balls
        self.timestamp = latest_ball.timestamp
        self.wickets_in_innings = latest_scorecard.wickets
        non_striker_summary = [b for b in latest_scorecard.inningBatsmen if b.currentType == 2][0]
        self.batter_id = latest_ball.batsmanPlayerId
        self.non_striker_id = non_striker_summary.player.id
        self.bowler_id = latest_ball.bowlerPlayerId
        if self.innings == 2:
            self.target = latest_scorecard.target
            self.runs_required = latest_scorecard.target - latest_scorecard.runs
            self.required_run_rate = 6 * (self.runs_required / self.legal_balls_remaining_in_innings)
        self.innings_runs = latest_scorecard.runs
        self.run_rate = (self.innings_runs / self.legal_balls_in_innings) * 6
        self.batter_runs_on_ball = latest_ball.batsmanRuns
        self.total_runs_on_ball = latest_ball.totalRuns
        self.wides = latest_ball.wides
        self.no_balls = latest_ball.noballs
        # this shit breaks when the striker gets out... handle this
        striker = [b for b in self.batters if b.id == self.batter_id][0]
        striker_summary = [b for b in latest_scorecard.inningBatsmen if b.player.id == striker.id][0]
        striker.batting_position_bat = \
        [i for i, b in enumerate(latest_scorecard.inningBatsmen) if b.player.id == self.batter_id][0] + 1
        striker.striker_runs = striker_summary.runs
        striker.striker_balls_faced = striker_summary.balls
        striker.strike_rate = striker_summary.strikerate
        non_striker = [b for b in self.batters if b.id == self.non_striker_id][0]
        non_striker.batting_position_bat = \
        [i for i, b in enumerate(latest_scorecard.inningBatsmen) if b.player.id == self.non_striker_id][0] + 1
        non_striker.striker_runs = non_striker_summary.runs
        non_striker.striker_balls_faced = non_striker_summary.balls
        non_striker.strike_rate = non_striker_summary.strikerate
        bowler = [b for b in self.bowlers if b.id == self.bowler_id][0]
        bowler_summary = [b for b in latest_scorecard.inningBowlers if b.currentType == 1][0]
        bowler.bowler_balls_bowled = bowler_summary.balls
        bowler.bowler_runs = bowler_summary.conceded
        current_partnership = [p for p in latest_scorecard.inningPartnerships if p.isLive == True]
        if len(current_partnership) > 0:
            current_partnership = current_partnership[0]
            self.partnership_runs = current_partnership.runs
        self.batting_partners = [self.striker, self.non_striker]
        self.wicket = int(latest_ball.isWicket)
        self.runs_inc_blb = self.batter_runs_on_ball + latest_ball.byes + latest_ball.legbyes
        self.is_wide = int(latest_ball.wides > 0)
        self.is_no_ball = int(latest_ball.noballs > 0)
        self.comm_id = latest_ball.id
        # looks like this might be kinda broken also, that's OK.
        striker.striker_0 += int(self.batter_runs_on_ball == 0)
        striker.striker_1 += int(self.batter_runs_on_ball == 1)
        striker.striker_2 += int(self.batter_runs_on_ball == 2)
        striker.striker_4 += int(self.batter_runs_on_ball == 4)
        striker.striker_6 += int(self.batter_runs_on_ball == 6)
        bowler.bowler_0 += int(self.batter_runs_on_ball == 0)
        bowler.bowler_1 += int(self.batter_runs_on_ball == 1)
        bowler.bowler_2 += int(self.batter_runs_on_ball == 2)
        bowler.bowler_4 += int(self.batter_runs_on_ball == 4)
        bowler.bowler_6 += int(self.batter_runs_on_ball == 6)
        bowler.bowler_wides_in_game = bowler_summary.wides
        bowler.bowler_wickets = bowler_summary.wickets
        self.striker = striker
        self.non_striker = non_striker
        self.bowler = bowler

    def change_innings(self):
        pass
