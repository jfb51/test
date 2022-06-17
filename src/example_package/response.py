import msgspec
from typing import List, Any, Optional


class Team(msgspec.Struct):
    id: int
    name: str


class MatchTeam(msgspec.Struct):
    team: Team
    isHome: bool


class Ground(msgspec.Struct):
    id: int
    name: str


class Match(msgspec.Struct):
    startTime: str
    tossWinnerTeamId: Optional[int]
    tossWinnerChoice: Optional[int]
    state: Optional[str]
    liveInning: Optional[int]
    teams: List[MatchTeam]
    liveOvers: Optional[float]
    liveBalls: Optional[int]  # this doesn't exist pre-game it seems
    ground: Ground


class Player(msgspec.Struct):
    id: int
    name: str
    playingRole: Optional[str]
    longBowlingStyles: List[Any]  # incorrect for wicketkeeper


class Players(msgspec.Struct):
    playerRoleType: str
    player: Player


class TeamPlayers(msgspec.Struct):
    type: str  # this == 'SQUAD' pre match vs 'PLAYING' once live...
    team: Team
    players: List[Players]


class MatchPlayers(msgspec.Struct):
    teamPlayers: List[TeamPlayers]


class LiveBatter(msgspec.Struct):
    player: Player
    runs: int
    balls: int
    fours: int
    sixes: int
    strikerate: float


class LiveBowler(msgspec.Struct):
    player: Player
    overs: float
    balls: int
    dots: int
    conceded: int
    wickets: int
    economy: float


class LivePerformance(msgspec.Struct):
    batsmen: list[LiveBatter]
    bowlers: list[LiveBowler]


class Over(msgspec.Struct):
    overNumber: int
    overRuns: Optional[int]
    overWickets: Optional[int]
    totalRuns: int
    totalWickets: Optional[int]
    target: Optional[int]
    overLimit: Optional[int]
    ballLimit: Optional[int]
    isComplete: Optional[bool]
    isSuperOver: Optional[bool]


class Dismissal(msgspec.Struct):
    short: Optional[str]
    long: Optional[str]
    commentary: Optional[str]


class Comment(msgspec.Struct):
    _uid: int
    id: int
    inningNumber: int
    ballsActual: Optional[int]
    ballsUnique: Optional[int]
    oversUnique: float
    oversActual: float
    overNumber: int
    ballNumber: int
    totalRuns: int
    batsmanRuns: int
    isFour: bool
    isSix: bool
    isWicket: bool
    byes: int
    legbyes: int
    wides: int
    noballs: int
    timestamp: Optional[str]
    batsmanPlayerId: int
    bowlerPlayerId: int
    totalInningRuns: int
    title: str
    dismissalType: Optional[int]
    dismissalText: Optional[Dismissal]
    over: Optional[Over]


class RecentBallCommentary(msgspec.Struct):
    ballComments: List[Comment]


class Partnership(msgspec.Struct):
    player1: Player
    player2: Player
    outPlayerId: Optional[int]
    player1Runs: int
    player1Balls: int
    player2Runs: int
    player2Balls: int
    runs: int
    balls: int
    overs: float
    isLive: bool


class InningOver(msgspec.Struct):
    overNumber: int
    overRuns: int
    overWickets: int
    isComplete: bool
    totalBalls: int
    totalRuns: int
    totalWickets: int
    requiredRunRate: float
    requiredRuns: int
    remainingBalls: int


class ScorecardBatter(msgspec.Struct):
    player: Player
    battedType: str
    runs: Optional[int]
    balls: Optional[int]
    fours: Optional[int]
    sixes: Optional[int]
    strikerate: Optional[float]
    isOut: bool
    fowOrder: Optional[int]
    fowWicketNum: Optional[int]
    fowRuns: Optional[int]
    fowBalls: Optional[int]
    fowOvers: Optional[float]
    currentType: Optional[int]


class ScorecardBowler(msgspec.Struct):
    player: Player
    bowledType: str
    overs: Optional[float]
    balls: Optional[int]
    conceded: Optional[int]
    wickets: Optional[int]
    economy: Optional[float]
    dots: Optional[int]
    fours: Optional[int]
    sixes: Optional[int]
    wides: Optional[int]
    noballs: Optional[int]
    currentType: Optional[int]


class Inning(msgspec.Struct):
    inningNumber: int
    team: Team
    isBatted: bool
    runs: int
    wickets: int
    lead: int
    target: int
    overs: float
    balls: int
    inningBatsmen: List[ScorecardBatter]
    inningBowlers: List[ScorecardBowler]
    inningPartnerships: List[Partnership]
    inningOvers: List[InningOver]


class Scorecard(msgspec.Struct):
    innings: List[Inning]


# class Group(msgspec.Struct):
#     team: Team

# class Notes(msgspec.Struct):
#     groups: List[Group]

class LatestResponse(msgspec.Struct):
    match: Match
    matchPlayers: MatchPlayers
    livePerformance: Optional[LivePerformance]
    recentBallCommentary: Optional[RecentBallCommentary]
    scorecard: Optional[Scorecard]
#     notes: Notes