class Strings:
    challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at **time slot {time_slot}**. "
        "Please respond to this request in the **#{channel}** channel with one of the following:"
        "\n\t - To accept: `[p]streamapp accept {match_day}`"
        "\n\t - To reject: `[p]streamapp reject {match_day}`"
        "\nThis stream application will not be considered until you respond.")

    gm_challenged_msg = ("You have been asked to play **match day {match_day}** ({home} vs. {away}) on stream at **time slot {time_slot}**. "
        "Please respond to this request in the **#{channel}** channel with one of the following:"
        "\n\t - To accept: `[p]streamapp accept {match_day} {gm_team}`"
        "\n\t - To reject: `[p]streamapp reject {match_day} {gm_team}`"
        "\nThis stream application will not be considered until you respond.")

    challenge_accepted_msg = (":white_check_mark: Your stream application for **match day {match_day}** ({home} vs. {away}) has been accepted by your opponents, and is "
        "now pending league approval. An additional message will be sent when a decision is made regarding this application.")

    challenge_rejected_msg = (":x: Your stream application for **match day {match_day}** ({home} vs. {away}) has been rejected by your opponents, and will "
        "not be considered moving forward.")

    league_approved_msg = ("**Congratulations!** You have been selected to play **match day {match_day}** ({home} vs. {away}) on stream at "
        "the **{slot} time slot**. You may use the `[p]match {match_day}` in your designated bot input channel see updated "
        "details of this match. We look forward to seeing you on the stream listed below!\n\nLive Stream Page: {live_stream}")

    league_rejected_msg = ("Your application to play **match day {match_day}** ({home} vs. {away}) on stream has been denied. "
        "Your application will be kept on file in the event that an on-stream match has been rescheduled.")

    rescinded_msg = ("Your match that was scheduled to be played on stream (Match Day {match_day}: **{home}** vs. **{away}**) has been **rescinded**. This match will no longer be played"
        "on stream, and will be played as it was originally scheduled. \n\nYou may use the `[p]match {match_day}` command to see your updated match information for match day {match_day}.")