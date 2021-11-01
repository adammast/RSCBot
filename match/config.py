
class config:
    home_info = ("You are the **home** team. You will create the "
                 "room using the above information. Contact the "
                 "other team when your team is ready to begin the "
                 "match. Do not join a team before the away team does. "
                 "Remember to ask before the match begins if the other "
                 "team would like to switch server region after 2 "
                 "games.")

    away_info = ("You are the **away** team. You will join the room "
                 "using the above information once the other team "
                 "contacts you. Do not begin joining a team until "
                 "your entire team is ready to begin playing.")

    solo_home_info = ("You are on the **home** team. You are the {0} seed. "
                      "You are responsible for hosting the lobby for all of "
                      "your matches with the following lobby information: ")

    solo_away_info = ("You are on the **away** team. You are the {0} seed. "
                      "You will participate in the following matchups: ")

    solo_home_match_info = ("Your {0} will be against `{1}` at {2}.\n\n")

    solo_away_match_info = ("Your {0} will be against `{1}` at "
                            "{2} with the following lobby info: "
                            "\nName: **{3}**"
                            "\nPassword: **{4}**")

    first_match_descr = ("first **one game** match")

    second_match_descr = ("second **one game** match")

    third_match_descr = ("**three game** series")

    first_match_time = ("10:00 pm ET (7:00 pm PT)")

    second_match_time = ("approximately 10:15 pm ET (7:15 pm PT)")

    third_match_time = ("approximately 10:30 pm ET (7:30 pm PT)")

    solo_matchup = ("{away_player:25s} vs.\t{home_player}")

    stream_info = ("**This match is scheduled to play on stream ** "
                   "(Time slot {time_slot}: {time})"
                   "\nYou are the **{home_or_away}** team. "
                   "A member of the Media Committee will inform you when the lobby is ready. "
                   "Do not join the lobby unless you are playing in the upcoming game. "
                   "Players should not join until instructed to do so via in-game chat. "
                   "\nRemember to inform the Media Committee what server "
                   "region your team would like to play on before games begin."
                   "\n\nLive Stream: <{live_stream}>")

    rl_regular_info = ("Be sure that **crossplay is enabled**.")

    rl_upload_info = ("Be sure to save replays and screenshots of the end-of-game scoreboard. "
                      "Do not leave the game until screenshots have been taken. "
                      "These must be uploaded by one member of your team after the {series_type} "
                      "is over.")

    rsc_upload_embed_info = ("Be sure to save replays and screenshots of the end-of-game scoreboard. Do not leave "
                             "the game until screenshots have been taken. These must be uploaded to the "
                             "[RSC Website](https://www.rocketsoccarconfederation.com/replay-and-screenshot-uploads) "
                             "by one member of your team after the {series_type} is over.")
    #  Remember that the deadline to reschedule matches is "
    # "at 10 minutes before the currently scheduled match time. They "
    # "can be scheduled no later than 11:59 PM ET on the original match day.\n\n")

    playoff_info = ("Playoff matches are a best of 5 series for every round until the finals. "
                    "Screenshots and replays do not need to be uploaded to the website for "
                    "playoff matches but you will need to report the scores in #score-reporting.\n\n")

    room_pass = [
        'octane', 'takumi', 'dominus', 'hotshot', 'batmobile', 'mantis',
        'paladin', 'twinmill', 'centio', 'breakout', 'animus', 'venom',
        'xdevil', 'endo', 'masamune', 'merc', 'backfire', 'gizmo',
        'roadhog', 'armadillo', 'hogsticker', 'luigi', 'mario', 'samus',
        'sweettooth', 'cyclone', 'imperator', 'jager', 'mantis', 'nimbus',
        'samurai', 'twinzer', 'werewolf', 'maverick', 'artemis', 'charger',
        'skyline', 'aftershock', 'boneshaker', 'delorean', 'esper',
        'fast4wd', 'gazella', 'grog', 'jeep', 'marauder', 'mclaren',
        'mr11', 'proteus', 'ripper', 'scarab', 'tumbler', 'triton',
        'vulcan', 'zippy',

        'aquadome', 'beckwith', 'champions', 'dfh', 'mannfield',
        'neotokyo', 'saltyshores', 'starbase', 'urban', 'utopia',
        'wasteland', 'farmstead', 'arctagon', 'badlands', 'core707',
        'dunkhouse', 'throwback', 'underpass', 'badlands',

        '20xx', 'biomass', 'bubbly', 'chameleon', 'dissolver', 'heatwave',
        'hexed', 'labyrinth', 'parallax', 'slipstream', 'spectre',
        'stormwatch', 'tora', 'trigon', 'wetpaint',

        'ara51', 'ballacarra', 'chrono', 'clockwork', 'cruxe',
        'discotheque', 'draco', 'dynamo', 'equalizer', 'gernot', 'hikari',
        'hypnotik', 'illuminata', 'infinium', 'kalos', 'lobo', 'looper',
        'photon', 'pulsus', 'raijin', 'reactor', 'roulette', 'turbine',
        'voltaic', 'wonderment', 'zomba',

        'unranked', 'prospect', 'challenger', 'risingstar', 'allstar',
        'superstar', 'champion', 'grandchamp', 'bronze', 'silver', 'gold',
        'platinum', 'diamond',

        'dropshot', 'hoops', 'soccar', 'rumble', 'snowday', 'solo',
        'doubles', 'standard', 'chaos',

        'armstrong', 'bandit', 'beast', 'boomer', 'buzz', 'cblock',
        'casper', 'caveman', 'centice', 'chipper', 'cougar', 'dude',
        'foamer', 'fury', 'gerwin', 'goose', 'heater', 'hollywood',
        'hound', 'iceman', 'imp', 'jester', 'junker', 'khan', 'marley',
        'maverick', 'merlin', 'middy', 'mountain', 'myrtle', 'outlaw',
        'poncho', 'rainmaker', 'raja', 'rex', 'roundhouse', 'sabretooth',
        'saltie', 'samara', 'scout', 'shepard', 'slider', 'squall',
        'sticks', 'stinger', 'storm', 'sultan', 'sundown', 'swabbie',
        'tex', 'tusk', 'viper', 'wolfman', 'yuri'
    ]
