
class StatsReference:
    
    # General
    PERM_FA_ROLE_NAME = "permFA"
    LEAGUE_ROLE_NAME = "League"

    DONE = "Done"
    NO_FA_STATS_MSG = "Unfortunately player stats can only be\nretrieved for rostered players at this time."
    
    # Awards
    TROPHY_EMOJI = "\U0001F3C6" # :trophy:
    GOLD_MEDAL_EMOJI = "\U0001F3C5" # gold medal
    FIRST_PLACE_EMOJI = "\U0001F947" # first place medal
    STAR_EMOJI = "\U00002B50" # :star:
    LEAGUE_AWARDS = [TROPHY_EMOJI, GOLD_MEDAL_EMOJI, FIRST_PLACE_EMOJI, STAR_EMOJI]

    # Stats Specific
    TEAM_LEAGUE_INFO = [
        "franchise", "gm", "conference", "division"
    ]
    INCLUDE_TEAM_STATS = [
        "gamesPlayed", "wins", "loss", "rank", "winPct", "goals", "assists", "saves",
        "shots", "shotPct", "points", "goalDiff", "oppGoals", "oppAssists", "oppShots",
        "oppShotPct", "oppShots", "oppPoints"
    ]
    INCLUDE_PLAYER_STATS = [
        "gp", "gw", "gl", "wPct", "pts", "goals", "assists", "saves",
        "shots", "shotPct", "ppg", "cycles", "hatTricks", "playmakers", "saviors"
    ]
    DATA_CODE_NAME_MAP = {
        # General
        "gm": "GM",

        # Player
        "gp": "GP",
        "gw": "Wins",
        "gl": "Losses",
        "hattricks": "Hat Tricks",
        "playmakers": "Play Makers",
        "goals": "Goals",
        "assists": "Assists",
        "shots": "Shots",
        "cycles": "Cycles",
        "saves": "Saves",
        "ppg": "PPG",
        "pts": "Points",
        "wpct": "Win%",
        "shotpct": "Shooting%",

        # Team
        "rank": "Rank",
        "gamesplayed": "GP",
        "wins": "Wins",
        "loss": "Losses",
        "winpct": "Win%",
        "points": "Points",
        "goaldiff": "Goal Diff.",
        "oppgoals": "OPP. Goals",
        "oppassists": "OPP. Assists",
        "oppshots": "OPP. Shots",
        "oppshotpct": "OPP. Shot%",
        "opppoints": "OPP. Points"
    }

