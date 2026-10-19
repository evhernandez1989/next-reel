#!/usr/bin/env python3
"""The Next Reel catalog: edit the table below, then run `python3 catalog.py`
to rewrite static/catalog.json.

Availability is a hand-kept snapshot (SNAPSHOT), not a feed. Studio windows
are fairly stable (Universal -> Peacock, Warner -> HBO Max, Paramount ->
Paramount+, Neon -> Hulu, a streamer's own originals stay home); licensed
catalog titles rotate monthly. The app says so on every card and links out
to check.

Row: id, title, year, kind (m/t), genres, tags, minutes-or-seasons, rating,
scare (0-5, 0 = not horror), subscriptions, free services, rent price
(None = not for rent), blurb. TV is bought by the season, so every
non-original show is marked buyable.
"""
import json
from pathlib import Path

SNAPSHOT = "2026-10"

SERVICES = {
    # id: (name, kind) - kind: sub (paid subscription), free (free with ads or a library card), store (rent/buy)
    "netflix": ("Netflix", "sub"), "hulu": ("Hulu", "sub"), "max": ("HBO Max", "sub"),
    "disney": ("Disney+", "sub"), "prime": ("Prime Video", "sub"), "appletv": ("Apple TV+", "sub"),
    "peacock": ("Peacock", "sub"), "paramount": ("Paramount+", "sub"), "shudder": ("Shudder", "sub"),
    "amcplus": ("AMC+", "sub"), "mgmplus": ("MGM+", "sub"), "starz": ("Starz", "sub"), "mubi": ("MUBI", "sub"),
    "tubi": ("Tubi", "free"), "pluto": ("Pluto TV", "free"), "roku": ("The Roku Channel", "free"),
    "kanopy": ("Kanopy", "free"), "plex": ("Plex", "free"), "youtube": ("YouTube (free)", "free"),
    "apple": ("Apple TV store", "store"), "amazon": ("Prime Video store", "store"),
    "google": ("Google Play / YouTube", "store"), "fandango": ("Fandango at Home", "store"),
}
# Owning the left one gets you the right one's library too.
INCLUDES = {"amcplus": ["shudder"]}

GENRES = ["horror", "thriller", "comedy", "scifi", "fantasy", "mystery", "drama", "action",
          "crime", "animation", "family", "romance", "documentary"]
TAGS = ["halloween", "cozy", "slasher", "supernatural", "haunted", "folk", "creature", "zombie",
        "vampire", "witch", "psychological", "found-footage", "horror-comedy", "classic", "international"]

R = 3.99    # catalog rental
N = 5.99    # recent release rental
_ = None

ROWS = [
    # ---- Halloween night & cozy spooky ---------------------------------------------------------------
    ("hocus-pocus", "Hocus Pocus", 1993, "m", "comedy,fantasy,family", "halloween,cozy,witch", 96, "PG", 1, "disney", "", R, "Three witch sisters get resurrected on Halloween night in Salem and want to stay young forever."),
    ("hocus-pocus-2", "Hocus Pocus 2", 2022, "m", "comedy,fantasy,family", "halloween,cozy,witch", 103, "PG", 1, "disney", "", _, "The Sanderson sisters are back, and two Salem teens have one night to stop them."),
    ("halloweentown", "Halloweentown", 1998, "m", "fantasy,family", "halloween,cozy,witch", 84, "TV-G", 1, "disney", "", _, "A girl learns her grandmother is a witch and follows her to a town where it's always Halloween."),
    ("nightmare-before-christmas", "The Nightmare Before Christmas", 1993, "m", "animation,family,fantasy", "halloween,cozy", 76, "PG", 1, "disney", "", R, "The Pumpkin King gets bored of Halloween and decides to take over Christmas."),
    ("great-pumpkin", "It's the Great Pumpkin, Charlie Brown", 1966, "m", "animation,family", "halloween,cozy,classic", 25, "TV-G", 0, "appletv", "", _, "Linus waits all night in the pumpkin patch while everyone else goes trick-or-treating."),
    ("trick-r-treat", "Trick 'r Treat", 2007, "m", "horror,comedy", "halloween,horror-comedy,supernatural", 82, "R", 3, "max,shudder", "", R, "Four Halloween stories in one town, tied together by a small trick-or-treater who enforces the rules."),
    ("hubie-halloween", "Hubie Halloween", 2020, "m", "comedy", "halloween,cozy", 102, "PG-13", 1, "netflix", "", _, "Salem's most mocked volunteer tries to keep Halloween safe when people start disappearing."),
    ("totally-killer", "Totally Killer", 2023, "m", "horror,comedy,scifi", "halloween,horror-comedy,slasher", 106, "R", 2, "prime", "", _, "A teen goes back to 1987 to stop the Halloween killer before he starts."),
    ("beetlejuice", "Beetlejuice", 1988, "m", "comedy,fantasy", "cozy,supernatural,horror-comedy", 92, "PG", 1, "max", "", R, "A newly dead couple hires a freelance 'bio-exorcist' to scare off the family who bought their house."),
    ("beetlejuice-beetlejuice", "Beetlejuice Beetlejuice", 2024, "m", "comedy,fantasy", "cozy,supernatural,horror-comedy", 104, "PG-13", 1, "max", "", R, "Three generations of Deetzes, a family death, and someone saying his name three times again."),
    ("addams-family", "The Addams Family", 1991, "m", "comedy,family", "cozy,horror-comedy", 99, "PG-13", 1, "paramount", "", R, "A con man poses as long-lost Uncle Fester to get at the Addams family fortune."),
    ("addams-family-values", "Addams Family Values", 1993, "m", "comedy,family", "cozy,horror-comedy", 94, "PG-13", 1, "paramount", "", R, "A new nanny with a body count sets her sights on Fester, while Wednesday survives summer camp."),
    ("corpse-bride", "Corpse Bride", 2005, "m", "animation,fantasy,romance", "cozy", 77, "PG", 1, "max", "", R, "A nervous groom practices his vows in the woods and accidentally marries a dead woman."),
    ("coraline", "Coraline", 2009, "m", "animation,fantasy,family", "cozy,supernatural", 100, "PG", 2, "", "", R, "A girl finds a door to a better version of her home, where her other mother has buttons for eyes."),
    ("paranorman", "ParaNorman", 2012, "m", "animation,family,comedy", "cozy,zombie,halloween", 92, "PG", 1, "", "", R, "The boy who talks to the dead is the only one who can stop a witch's curse."),
    ("frankenweenie", "Frankenweenie", 2012, "m", "animation,family", "cozy,classic", 87, "PG", 1, "disney", "", R, "A young scientist brings his dog back to life, and the neighborhood kids want to do the same."),
    ("haunted-mansion-2023", "Haunted Mansion", 2023, "m", "comedy,family,fantasy", "cozy,haunted", 123, "PG-13", 1, "disney", "", R, "A single mom hires a tour guide, a psychic, a priest and a historian to clear out her house."),
    ("gremlins", "Gremlins", 1984, "m", "horror,comedy", "cozy,creature,horror-comedy", 106, "PG", 2, "max", "", R, "Three rules for a new pet: no bright light, no water, and never feed it after midnight."),
    ("ghostbusters", "Ghostbusters", 1984, "m", "comedy,fantasy", "cozy,supernatural", 105, "PG", 1, "", "", R, "Three fired parapsychologists start a ghost-catching business just as New York needs one."),
    ("practical-magic", "Practical Magic", 1998, "m", "fantasy,romance,drama", "cozy,witch", 104, "PG-13", 1, "max", "", R, "Two witch sisters live with a curse that kills any man who loves them."),
    ("the-craft", "The Craft", 1996, "m", "horror,fantasy,drama", "witch", 101, "R", 2, "", "", R, "A new girl joins three outcasts who are discovering that their spells actually work."),
    ("scooby-doo-2002", "Scooby-Doo", 2002, "m", "comedy,family,mystery", "cozy", 87, "PG", 0, "max", "", R, "Mystery Inc. reunites on a spooky island resort that is stealing its visitors' souls."),
    ("goosebumps-series", "Goosebumps", 2023, "t", "horror,family,mystery", "cozy,supernatural", 2, "TV-PG", 2, "disney,hulu", "", _, "Five teens free a ghost's spirit and their small town starts coming apart."),
    ("over-the-garden-wall", "Over the Garden Wall", 2014, "t", "animation,fantasy", "cozy,folk", 1, "TV-PG", 1, "hulu", "", _, "Two half-brothers lost in a strange autumn forest try to find their way home."),
    ("wendell-wild", "Wendell & Wild", 2022, "m", "animation,fantasy,comedy", "cozy,supernatural", 105, "PG-13", 1, "netflix", "", _, "Two demon brothers make a deal with a girl who wants her parents back."),
    ("kpop-demon-hunters", "KPop Demon Hunters", 2025, "m", "animation,action,family", "cozy,supernatural", 96, "PG", 1, "netflix", "", _, "A K-pop girl group uses its voices to keep demons out of the human world."),
    ("rocky-horror", "The Rocky Horror Picture Show", 1975, "m", "comedy,scifi", "cozy,classic,horror-comedy", 100, "R", 1, "hulu,disney", "", R, "A stranded couple knocks on the door of a castle hosting a very strange party."),
    ("young-frankenstein", "Young Frankenstein", 1974, "m", "comedy", "cozy,classic,horror-comedy", 106, "PG", 0, "", "", R, "Dr. Frankenstein's grandson insists his name is pronounced Fronkensteen, until he finds the notes."),
    ("edward-scissorhands", "Edward Scissorhands", 1990, "m", "fantasy,romance,drama", "cozy", 105, "PG-13", 1, "disney", "", R, "An unfinished man with scissors for hands is adopted by a suburban Avon lady."),
    ("wednesday", "Wednesday", 2022, "t", "comedy,mystery,fantasy", "cozy,supernatural", 2, "TV-14", 2, "netflix", "", _, "Wednesday Addams solves a murder mystery at a school for outcasts."),
    ("agatha-all-along", "Agatha All Along", 2024, "t", "fantasy,comedy", "cozy,witch", 1, "TV-PG", 1, "disney", "", _, "A powerless witch gathers a coven to walk the Witches' Road and get her magic back."),
    ("werewolf-by-night", "Werewolf by Night", 2022, "m", "horror,action", "creature,classic", 53, "TV-14", 2, "disney", "", _, "Monster hunters gather in a castle to compete for a powerful relic, black-and-white style."),
    ("what-we-do-shadows", "What We Do in the Shadows", 2019, "t", "comedy,horror", "vampire,horror-comedy,cozy", 6, "TV-MA", 1, "hulu", "", _, "Four vampire roommates on Staten Island try, and fail, to take over the New World."),

    # ---- Slashers ------------------------------------------------------------------------------------
    ("halloween-1978", "Halloween", 1978, "m", "horror", "halloween,slasher,classic", 91, "R", 4, "shudder,amcplus", "", R, "On Halloween night, Michael Myers comes home to Haddonfield, and a babysitter notices."),
    ("halloween-2018", "Halloween", 2018, "m", "horror", "halloween,slasher", 106, "R", 4, "peacock", "", R, "Forty years later, Laurie Strode has been preparing for one night. So has he."),
    ("halloween-kills", "Halloween Kills", 2021, "m", "horror", "halloween,slasher", 105, "R", 4, "peacock", "", R, "Haddonfield forms a mob to finish Michael Myers the same night he walks out of the fire."),
    ("halloween-ends", "Halloween Ends", 2022, "m", "horror", "halloween,slasher", 111, "R", 4, "peacock", "", R, "Four years on, Laurie writes her memoir while a new evil grows in town."),
    ("scream-1996", "Scream", 1996, "m", "horror,mystery", "slasher,classic", 111, "R", 4, "paramount", "", R, "A killer who knows the rules of horror movies starts calling the teens of Woodsboro."),
    ("scream-2022", "Scream", 2022, "m", "horror,mystery", "slasher", 114, "R", 4, "paramount", "", R, "Twenty-five years later, a new Ghostface targets the relatives of the original survivors."),
    ("scream-6", "Scream VI", 2023, "m", "horror,mystery", "slasher", 123, "R", 4, "paramount", "", R, "The Woodsboro survivors move to New York. Ghostface follows."),
    ("nightmare-elm-street", "A Nightmare on Elm Street", 1984, "m", "horror", "slasher,supernatural,classic", 91, "R", 4, "max", "", R, "If he gets you in your dreams, you die for real."),
    ("terrifier", "Terrifier", 2016, "m", "horror", "halloween,slasher", 85, "Unrated", 5, "", "tubi", R, "Two friends leaving a Halloween party cross paths with Art the Clown. Extremely gory."),
    ("fear-street-1994", "Fear Street: 1994", 2021, "m", "horror,mystery", "slasher,supernatural", 107, "R", 3, "netflix", "", _, "Teens in cursed Shadyside learn the town's killers are connected across centuries."),
    ("fear-street-1978", "Fear Street: 1978", 2021, "m", "horror", "slasher", 109, "R", 4, "netflix", "", _, "Summer camp, color war, and an axe murderer: the curse's 1978 chapter."),
    ("fear-street-1666", "Fear Street: 1666", 2021, "m", "horror", "folk,witch,supernatural", 114, "R", 3, "netflix", "", _, "The trilogy ends where the curse began: a colonial town and a woman accused of witchcraft."),
    ("texas-chain-saw", "The Texas Chain Saw Massacre", 1974, "m", "horror", "slasher,classic", 83, "R", 5, "", "tubi", R, "Five friends on a road trip pick up a hitchhiker and find the wrong farmhouse."),
    ("happy-death-day", "Happy Death Day", 2017, "m", "horror,comedy,mystery", "slasher,horror-comedy", 96, "PG-13", 2, "peacock", "", R, "A college student relives the day of her murder until she figures out who did it."),
    ("freaky", "Freaky", 2020, "m", "horror,comedy", "slasher,horror-comedy", 102, "R", 3, "peacock", "", R, "A teen and a serial killer wake up in each other's bodies."),
    ("pearl", "Pearl", 2022, "m", "horror,drama", "slasher,psychological", 102, "R", 4, "max", "", R, "A farm girl in 1918 dreams of stardom and will not take no for an answer."),
    ("x-2022", "X", 2022, "m", "horror", "slasher", 105, "R", 5, "max", "", R, "A film crew rents a Texas farmhouse in 1979 and the elderly hosts take an interest."),
    ("final-destination-bloodlines", "Final Destination Bloodlines", 2025, "m", "horror", "supernatural", 110, "R", 4, "max", "", N, "A student's recurring nightmare is a warning: death skipped her family, and it's back for them."),
    ("saw", "Saw", 2004, "m", "horror,thriller", "psychological", 103, "R", 5, "", "", R, "Two men wake up chained in a bathroom with a tape recorder and a saw."),
    ("chucky-series", "Chucky", 2021, "t", "horror,comedy", "slasher,horror-comedy", 3, "TV-MA", 3, "peacock", "", _, "A vintage Chucky doll turns up at a suburban yard sale. The town is not ready."),

    # ---- Supernatural & haunted ----------------------------------------------------------------------
    ("the-conjuring", "The Conjuring", 2013, "m", "horror", "haunted,supernatural", 112, "R", 4, "max", "", R, "Ed and Lorraine Warren help a family terrorized by a presence in their Rhode Island farmhouse."),
    ("conjuring-last-rites", "The Conjuring: Last Rites", 2025, "m", "horror", "haunted,supernatural", 135, "R", 4, "max", "", N, "The Warrens take one last case, and this one follows them home."),
    ("the-exorcist", "The Exorcist", 1973, "m", "horror", "supernatural,classic", 122, "R", 5, "max", "", R, "A mother turns to two priests when her daughter's illness stops looking medical."),
    ("exorcist-believer", "The Exorcist: Believer", 2023, "m", "horror", "supernatural", 111, "R", 3, "peacock", "", R, "Two girls vanish in the woods and come back three days later, changed."),
    ("the-shining", "The Shining", 1980, "m", "horror,thriller", "haunted,psychological,classic", 146, "R", 4, "max", "", R, "A writer takes his family to a mountain hotel for the winter as its caretaker."),
    ("poltergeist", "Poltergeist", 1982, "m", "horror", "haunted,supernatural,classic", 114, "PG", 3, "max", "", R, "A suburban family's youngest daughter starts talking to the TV, and the TV talks back."),
    ("hereditary", "Hereditary", 2018, "m", "horror,drama", "supernatural,psychological", 127, "R", 5, "max", "", R, "After grandma's death, a family discovers what she had been part of."),
    ("talk-to-me", "Talk to Me", 2023, "m", "horror", "supernatural,international", 95, "R", 4, "max", "", R, "Teens get high on letting spirits possess them through an embalmed hand. Ninety seconds, max."),
    ("heretic", "Heretic", 2024, "m", "horror,thriller", "psychological", 111, "R", 4, "max", "", R, "Two young missionaries knock on the wrong door and get drawn into a game of faith."),
    ("smile", "Smile", 2022, "m", "horror,mystery", "supernatural,psychological", 115, "R", 4, "paramount", "", R, "A therapist witnesses a patient's death and starts seeing smiling people everywhere."),
    ("smile-2", "Smile 2", 2024, "m", "horror", "supernatural,psychological", 127, "R", 4, "paramount", "", R, "A pop star on the eve of a world tour picks up the curse."),
    ("insidious", "Insidious", 2010, "m", "horror", "haunted,supernatural", 103, "PG-13", 4, "", "", R, "It isn't the house that's haunted. It's their son."),
    ("sinister", "Sinister", 2012, "m", "horror,mystery", "supernatural,found-footage", 110, "R", 5, "", "", R, "A true-crime writer finds a box of home movies in his new attic."),
    ("the-ring", "The Ring", 2002, "m", "horror,mystery", "supernatural", 115, "PG-13", 4, "paramount", "", R, "Watch the tape and the phone rings. Seven days later, you die."),
    ("the-babadook", "The Babadook", 2014, "m", "horror,drama", "supernatural,psychological,international", 94, "Unrated", 4, "shudder,amcplus", "kanopy", R, "A widowed mother reads her son a picture book that should not exist."),
    ("it-follows", "It Follows", 2014, "m", "horror", "supernatural", 100, "R", 4, "", "", R, "After one encounter, a slow-walking presence follows her, and it never stops."),
    ("black-phone", "The Black Phone", 2021, "m", "horror,thriller", "supernatural", 103, "R", 4, "peacock", "", R, "A kidnapped boy gets calls from the killer's previous victims on a disconnected phone."),
    ("weapons", "Weapons", 2025, "m", "horror,mystery", "supernatural", 128, "R", 4, "max", "", N, "Every kid in one classroom except one ran out of their homes at 2:17 a.m. and vanished."),
    ("late-night-devil", "Late Night with the Devil", 2023, "m", "horror", "supernatural,found-footage", 93, "R", 3, "shudder,amcplus", "", R, "A 1977 talk show's Halloween special books a possessed girl for ratings. Live on air."),
    ("when-evil-lurks", "When Evil Lurks", 2023, "m", "horror", "supernatural,international", 99, "Unrated", 5, "shudder,amcplus", "", R, "Two brothers in rural Argentina find a man 'rotting' with a demon and make it worse."),
    ("host", "Host", 2020, "m", "horror", "supernatural,found-footage", 57, "Unrated", 4, "shudder,amcplus", "", R, "Six friends hold a séance over Zoom in lockdown. Someone doesn't take it seriously."),
    ("skinamarink", "Skinamarink", 2022, "m", "horror", "supernatural,psychological", 100, "Unrated", 3, "shudder,amcplus", "", R, "Two children wake at night to find their father gone and the doors of the house missing."),
    ("lake-mungo", "Lake Mungo", 2008, "m", "horror,mystery", "supernatural,found-footage,international", 87, "R", 3, "shudder,amcplus", "tubi", R, "A documentary about a family who began seeing their drowned daughter in photographs."),
    ("hell-house-llc", "Hell House LLC", 2015, "m", "horror", "halloween,haunted,found-footage", 93, "Unrated", 4, "shudder,amcplus", "tubi", R, "A haunted-house attraction crew sets up in an abandoned hotel. Opening night goes wrong."),
    ("deadstream", "Deadstream", 2022, "m", "horror,comedy", "haunted,found-footage,horror-comedy", 87, "Unrated", 3, "shudder,amcplus", "", R, "A disgraced streamer livestreams a night alone in a haunted house for a comeback."),
    ("salems-lot-2024", "Salem's Lot", 2024, "m", "horror", "vampire", 113, "R", 3, "max", "", _, "A writer returns to his Maine hometown as its residents start dying and coming back."),
    ("sinners", "Sinners", 2025, "m", "horror,action,drama", "vampire", 137, "R", 4, "max", "", N, "Twin brothers open a juke joint in 1932 Mississippi. Something is drawn by the music."),
    ("nosferatu-2024", "Nosferatu", 2024, "m", "horror,drama", "vampire,classic", 132, "R", 4, "peacock", "", R, "A young wife in 1838 is haunted by an ancient vampire infatuated with her."),
    ("nosferatu-1922", "Nosferatu", 1922, "m", "horror", "vampire,classic", 94, "NR", 2, "", "tubi,kanopy,youtube,plex", _, "The silent original: Count Orlok buys a house across from a young couple."),
    ("night-of-living-dead", "Night of the Living Dead", 1968, "m", "horror", "zombie,classic", 96, "NR", 3, "", "tubi,pluto,youtube,plex,roku", _, "Strangers barricade a farmhouse as the dead rise across Pennsylvania. Public domain."),
    ("carnival-of-souls", "Carnival of Souls", 1962, "m", "horror,mystery", "supernatural,classic", 78, "NR", 2, "", "tubi,kanopy,youtube,plex", _, "After surviving a car crash, an organist is drawn to an abandoned lakeside pavilion."),
    ("house-on-haunted-hill", "House on Haunted Hill", 1959, "m", "horror,mystery", "haunted,classic", 75, "NR", 2, "", "tubi,pluto,youtube,plex", _, "Vincent Price offers $10,000 to anyone who survives the night in his house."),
    ("abigail", "Abigail", 2024, "m", "horror,comedy,thriller", "vampire,horror-comedy", 109, "R", 4, "peacock", "", R, "Kidnappers grab a ballerina for ransom and lock themselves in with her. Bad idea."),
    ("barbarian", "Barbarian", 2022, "m", "horror,thriller", "creature", 102, "R", 5, "hulu", "", R, "A woman arrives at her Airbnb to find it double-booked. The basement is worse."),
    ("longlegs", "Longlegs", 2024, "m", "horror,thriller,crime", "supernatural,psychological", 101, "R", 4, "hulu", "", R, "An FBI agent with a sixth sense hunts a killer who leaves coded letters at family murders."),
    ("together-2025", "Together", 2025, "m", "horror,romance", "psychological", 102, "R", 4, "hulu", "", N, "A couple moves to the countryside and starts, quite literally, growing together."),
    ("bring-her-back", "Bring Her Back", 2025, "m", "horror", "supernatural,international", 104, "R", 5, "max", "", N, "Two foster siblings are placed with a woman whose daughter drowned. She has a plan."),
    ("mama", "Mama", 2013, "m", "horror", "supernatural", 100, "PG-13", 3, "", "", R, "Two girls found in a cabin after five years alone were not alone."),

    # ---- Folk, creature, zombie, psychological -------------------------------------------------------
    ("the-witch", "The Witch", 2015, "m", "horror,drama", "folk,witch", 92, "R", 4, "max", "", R, "A Puritan family banished to the edge of the woods starts losing children."),
    ("midsommar", "Midsommar", 2019, "m", "horror,drama", "folk,psychological", 148, "R", 5, "max", "", R, "A grieving woman joins her boyfriend at a Swedish midsummer festival held every 90 years."),
    ("apostle", "Apostle", 2018, "m", "horror,thriller", "folk", 130, "TV-MA", 5, "netflix", "", _, "In 1905, a man infiltrates an island cult to rescue his sister."),
    ("his-house", "His House", 2020, "m", "horror,drama", "haunted,international", 93, "TV-14", 4, "netflix", "", _, "Refugees from South Sudan get a house in England. Something came with them."),
    ("hush", "Hush", 2016, "m", "horror,thriller", "slasher", 82, "R", 4, "netflix", "", _, "A deaf writer alone in the woods realizes a masked man is outside."),
    ("geralds-game", "Gerald's Game", 2017, "m", "horror,thriller", "psychological", 103, "TV-MA", 4, "netflix", "", _, "A weekend getaway goes wrong and a woman is left handcuffed to a bed, alone."),
    ("bird-box", "Bird Box", 2018, "m", "horror,thriller,scifi", "creature", 124, "R", 3, "netflix", "", _, "If you see them, you die. A mother leads two kids downriver blindfolded."),
    ("the-platform", "The Platform", 2019, "m", "horror,scifi,thriller", "psychological,international", 94, "TV-MA", 4, "netflix", "", _, "A vertical prison feeds its inmates from one platform that descends floor by floor."),
    ("a-quiet-place", "A Quiet Place", 2018, "m", "horror,scifi,drama", "creature", 90, "PG-13", 4, "paramount", "", R, "A family survives by living in silence, because the creatures hunt by sound."),
    ("a-quiet-place-2", "A Quiet Place Part II", 2020, "m", "horror,scifi", "creature", 97, "PG-13", 4, "paramount", "", R, "The Abbotts leave the farm and learn who else is still out there."),
    ("quiet-place-day-one", "A Quiet Place: Day One", 2024, "m", "horror,scifi", "creature", 99, "PG-13", 3, "paramount", "", R, "Day one of the invasion, in the loudest city on Earth."),
    ("alien", "Alien", 1979, "m", "horror,scifi", "creature,classic", 117, "R", 4, "hulu", "", R, "A commercial crew answers a distress call. They bring something back aboard."),
    ("alien-romulus", "Alien: Romulus", 2024, "m", "horror,scifi", "creature", 119, "R", 4, "hulu", "", R, "Young colonists scavenge a derelict station and find what's been waiting."),
    ("prey", "Prey", 2022, "m", "action,horror,scifi", "creature", 99, "R", 3, "hulu", "", _, "A young Comanche warrior in 1719 tracks a hunter that is not from here."),
    ("no-one-will-save-you", "No One Will Save You", 2023, "m", "horror,scifi", "creature", 93, "PG-13", 4, "hulu", "", _, "A town outcast fights off an alien home invasion almost without a word of dialogue."),
    ("nope", "Nope", 2022, "m", "horror,scifi,mystery", "creature", 130, "R", 3, "peacock", "", R, "Ranch siblings in California try to catch something in the sky on camera."),
    ("get-out", "Get Out", 2017, "m", "horror,thriller,mystery", "psychological", 104, "R", 3, "peacock", "", R, "A weekend meeting his girlfriend's parents gets stranger by the hour."),
    ("us", "Us", 2019, "m", "horror,thriller", "psychological", 116, "R", 4, "peacock", "", R, "A family's beach vacation is interrupted by four strangers who look exactly like them."),
    ("m3gan", "M3GAN", 2022, "m", "horror,scifi,comedy", "horror-comedy", 102, "PG-13", 2, "peacock", "", R, "A robotics engineer gives her orphaned niece an AI doll that takes protection too far."),
    ("five-nights-freddys", "Five Nights at Freddy's", 2023, "m", "horror,mystery", "creature", 109, "PG-13", 2, "peacock", "", R, "A night guard at an abandoned pizzeria learns the animatronics move after dark."),
    ("wolf-man-2025", "Wolf Man", 2025, "m", "horror", "creature", 103, "R", 3, "peacock", "", R, "A family at a remote Oregon farmhouse is attacked by something, and dad is changing."),
    ("cocaine-bear", "Cocaine Bear", 2023, "m", "comedy,thriller", "creature,horror-comedy", 95, "R", 2, "peacock", "", R, "A black bear eats a drug smuggler's lost cargo in a Georgia forest. Chaos follows."),
    ("jaws", "Jaws", 1975, "m", "thriller,horror", "creature,classic", 124, "PG", 3, "peacock", "", R, "A police chief, a scientist and a shark hunter go after a great white."),
    ("the-thing", "The Thing", 1982, "m", "horror,scifi", "creature,classic,psychological", 109, "R", 5, "peacock", "", R, "An Antarctic research team learns something can imitate any of them."),
    ("psycho", "Psycho", 1960, "m", "horror,thriller", "slasher,classic,psychological", 109, "R", 3, "peacock", "", R, "A secretary on the run checks into a quiet motel run by a young man and his mother."),
    ("shaun-of-the-dead", "Shaun of the Dead", 2004, "m", "comedy,horror", "zombie,horror-comedy,international", 99, "R", 2, "peacock", "", R, "A London slacker plans to win back his girlfriend, sort out his mum, and wait it out at the pub."),
    ("train-to-busan", "Train to Busan", 2016, "m", "horror,action", "zombie,international", 118, "Unrated", 4, "", "tubi", R, "A zombie outbreak hits South Korea while a father and daughter are on the high-speed train."),
    ("28-years-later", "28 Years Later", 2025, "m", "horror,thriller", "zombie,international", 115, "R", 4, "netflix", "", N, "Survivors on a quarantined island send a boy to the mainland for the first time."),
    ("evil-dead-rise", "Evil Dead Rise", 2023, "m", "horror", "supernatural", 97, "R", 5, "max", "", R, "Two sisters in an LA apartment find a book in the parking garage. Do not read it aloud."),
    ("one-cut-of-dead", "One Cut of the Dead", 2017, "m", "comedy,horror", "zombie,horror-comedy,international", 96, "NR", 1, "shudder,amcplus", "", R, "A low-budget zombie shoot in one take. Stick with it past the first 30 minutes."),
    ("ready-or-not", "Ready or Not", 2019, "m", "horror,comedy,thriller", "horror-comedy", 95, "R", 3, "hulu", "", R, "A bride's new in-laws have a wedding-night tradition: hide and seek, to the death."),
    ("cabin-in-woods", "The Cabin in the Woods", 2011, "m", "horror,comedy", "horror-comedy,creature", 95, "R", 3, "", "", R, "Five friends go to a remote cabin, and people in an underground office are watching."),
    ("tucker-dale", "Tucker & Dale vs. Evil", 2010, "m", "comedy,horror", "horror-comedy,slasher", 89, "R", 2, "", "tubi", R, "Two sweet hillbillies on vacation are mistaken by college kids for killers."),
    ("zombieland", "Zombieland", 2009, "m", "comedy,action", "zombie,horror-comedy", 88, "R", 2, "", "", R, "A rule-following survivor, a Twinkie-hunting cowboy and two sisters road-trip the apocalypse."),
    ("rosemarys-baby", "Rosemary's Baby", 1968, "m", "horror,drama", "supernatural,psychological,classic", 137, "R", 3, "paramount", "", R, "A young wife's new neighbors take a very close interest in her pregnancy."),
    ("carrie-1976", "Carrie", 1976, "m", "horror", "supernatural,classic", 98, "R", 3, "prime", "", R, "A bullied, sheltered girl discovers her telekinesis just in time for prom."),
    ("silence-of-lambs", "The Silence of the Lambs", 1991, "m", "thriller,crime,horror", "psychological,classic", 118, "R", 3, "prime", "", R, "An FBI trainee asks a jailed cannibal psychiatrist for help catching a killer."),
    ("suspiria-2018", "Suspiria", 2018, "m", "horror", "witch,supernatural", 152, "R", 4, "prime", "", R, "An American joins a Berlin dance company run by a coven."),
    ("the-substance", "The Substance", 2024, "m", "horror,scifi,drama", "psychological", 141, "R", 5, "mubi", "", R, "A fading star tries a black-market drug that makes a younger copy of her. Body horror."),
    ("companion", "Companion", 2025, "m", "horror,thriller,scifi", "psychological", 97, "R", 3, "max", "", R, "A weekend at a lake house with friends, and a girlfriend who turns out to be a lot more."),
    ("mandy", "Mandy", 2018, "m", "horror,action", "psychological", 121, "Unrated", 4, "shudder,amcplus", "", R, "A cult takes everything from a lumberjack in 1983. He forges an axe."),
    ("huesera", "Huesera: The Bone Woman", 2022, "m", "horror,drama", "supernatural,international", 97, "Unrated", 4, "shudder,amcplus", "", R, "A pregnant woman in Mexico City is followed by a twisted presence."),
    ("v-h-s-94", "V/H/S/94", 2021, "m", "horror", "found-footage", 100, "Unrated", 5, "shudder,amcplus", "", R, "A SWAT team raids a warehouse full of televisions playing very wrong tapes."),
    ("speak-no-evil-2024", "Speak No Evil", 2024, "m", "horror,thriller", "psychological", 110, "R", 4, "peacock", "", R, "An American family accepts a weekend invitation from a couple they met on holiday."),

    # ---- Horror TV -----------------------------------------------------------------------------------
    ("stranger-things", "Stranger Things", 2016, "t", "scifi,horror,drama", "supernatural,creature", 5, "TV-14", 2, "netflix", "", _, "A boy vanishes in 1983 Indiana and his friends find a girl with powers and a gate to elsewhere."),
    ("hill-house", "The Haunting of Hill House", 2018, "t", "horror,drama", "haunted,supernatural", 1, "TV-MA", 4, "netflix", "", _, "Siblings who grew up in America's most famous haunted house are pulled back to it."),
    ("bly-manor", "The Haunting of Bly Manor", 2020, "t", "horror,romance,drama", "haunted,supernatural", 1, "TV-MA", 2, "netflix", "", _, "An American au pair takes a job at an English estate where the children see things."),
    ("midnight-mass", "Midnight Mass", 2021, "t", "horror,drama", "supernatural,vampire", 1, "TV-MA", 3, "netflix", "", _, "A charismatic young priest arrives on a dying island and miracles start happening."),
    ("house-of-usher", "The Fall of the House of Usher", 2023, "t", "horror,drama,mystery", "supernatural", 1, "TV-MA", 4, "netflix", "", _, "A pharma dynasty's heirs die one by one, each in a way Poe would recognize."),
    ("cabinet-of-curiosities", "Guillermo del Toro's Cabinet of Curiosities", 2022, "t", "horror,fantasy", "supernatural,creature", 1, "TV-MA", 3, "netflix", "", _, "Eight standalone horror stories, each from a different director."),
    ("kingdom", "Kingdom", 2019, "t", "horror,action,drama", "zombie,international", 2, "TV-MA", 4, "netflix", "", _, "In Joseon-era Korea, a crown prince investigates a plague that raises the dead."),
    ("all-of-us-are-dead", "All of Us Are Dead", 2022, "t", "horror,action", "zombie,international", 1, "TV-MA", 4, "netflix", "", _, "Students trapped in their high school during a zombie outbreak."),
    ("last-of-us", "The Last of Us", 2023, "t", "drama,horror,scifi", "zombie", 2, "TV-MA", 3, "max", "", _, "A smuggler escorts a teenager across a fungus-ravaged America."),
    ("welcome-to-derry", "IT: Welcome to Derry", 2025, "t", "horror", "supernatural", 1, "TV-MA", 4, "max", "", _, "1962 in Derry, Maine: the town learns what lives under it, long before the Losers Club."),
    ("lovecraft-country", "Lovecraft Country", 2020, "t", "horror,drama,fantasy", "supernatural,creature", 1, "TV-MA", 3, "max", "", _, "A Korean War vet road-trips through 1950s Jim Crow America looking for his missing father."),
    ("american-horror-story", "American Horror Story", 2011, "t", "horror,drama", "supernatural,haunted", 12, "TV-MA", 4, "hulu", "", _, "Each season a new nightmare: murder house, asylum, coven, hotel and more."),
    ("buffy", "Buffy the Vampire Slayer", 1997, "t", "fantasy,horror,drama", "vampire,cozy", 7, "TV-PG", 2, "hulu", "", _, "A high schooler is the one girl in all the world chosen to fight vampires."),
    ("x-files", "The X-Files", 1993, "t", "scifi,mystery,horror", "supernatural,classic", 11, "TV-14", 2, "hulu", "", _, "Two FBI agents, one believer, one skeptic, investigate the unexplained."),
    ("yellowjackets", "Yellowjackets", 2021, "t", "drama,horror,mystery", "psychological", 3, "TV-MA", 3, "paramount", "", _, "A girls' soccer team survives 19 months in the wilderness. Twenty-five years later, it isn't over."),
    ("evil", "Evil", 2019, "t", "horror,drama,mystery", "supernatural", 4, "TV-MA", 3, "paramount,netflix", "", _, "A psychologist, a priest-in-training and a contractor assess claims of possession for the Church."),
    ("servant", "Servant", 2019, "t", "horror,drama,mystery", "psychological,supernatural", 4, "TV-MA", 3, "appletv", "", _, "A grieving Philadelphia couple hires a young nanny to care for a doll that replaced their son."),
    ("interview-vampire", "Interview with the Vampire", 2022, "t", "horror,drama,romance", "vampire", 3, "TV-MA", 2, "amcplus", "", _, "A vampire tells his life story, and his romance with Lestat, to a journalist."),
    ("walking-dead", "The Walking Dead", 2010, "t", "horror,drama,action", "zombie", 11, "TV-MA", 3, "amcplus", "", _, "A sheriff's deputy wakes from a coma into a zombie apocalypse."),
    ("creepshow-series", "Creepshow", 2019, "t", "horror", "supernatural,horror-comedy", 4, "TV-MA", 3, "shudder,amcplus", "", _, "The comic-book anthology: two short horror tales an episode, hosted by the Creep."),
    ("from", "From", 2022, "t", "horror,mystery,scifi", "supernatural,creature", 3, "TV-MA", 4, "mgmplus", "", _, "A town in middle America traps everyone who enters. At night, things come out of the woods."),
    ("hannibal", "Hannibal", 2013, "t", "crime,horror,thriller", "psychological", 3, "TV-14", 4, "prime", "", _, "An FBI profiler and his psychiatrist, a cannibal, form a beautiful and dangerous bond."),
    ("twilight-zone-1959", "The Twilight Zone", 1959, "t", "scifi,mystery,fantasy", "classic,supernatural", 5, "TV-PG", 1, "paramount", "pluto", _, "Rod Serling's anthology of the strange, the uncanny, and the twist ending."),
    ("penny-dreadful", "Penny Dreadful", 2014, "t", "horror,drama,fantasy", "supernatural,classic", 3, "TV-MA", 3, "paramount", "", _, "Frankenstein, Dorian Gray and a medium cross paths in the dark corners of Victorian London."),
    ("ash-vs-evil-dead", "Ash vs Evil Dead", 2015, "t", "horror,comedy", "horror-comedy,supernatural", 3, "TV-MA", 3, "starz", "", _, "Thirty years later, Ash reads from the book again while high, and the Deadites return."),
    ("grotesquerie", "Grotesquerie", 2024, "t", "horror,crime,mystery", "psychological", 1, "TV-MA", 4, "hulu", "", _, "A detective believes a run of gruesome crimes is personally aimed at her."),

    # ---- Not horror: the rest of the year ------------------------------------------------------------
    ("glass-onion", "Glass Onion", 2022, "m", "mystery,comedy", "", 139, "PG-13", 0, "netflix", "", _, "Benoit Blanc joins a tech billionaire's private-island murder-mystery party."),
    ("wake-up-dead-man", "Wake Up Dead Man", 2025, "m", "mystery,comedy", "", 144, "PG-13", 0, "netflix", "", _, "Benoit Blanc takes on an impossible crime in a small-town church."),
    ("squid-game", "Squid Game", 2021, "t", "thriller,drama", "international", 3, "TV-MA", 0, "netflix", "", _, "Hundreds of people in debt play children's games for a fortune. Losing is fatal."),
    ("black-mirror", "Black Mirror", 2011, "t", "scifi,thriller,drama", "psychological", 7, "TV-MA", 0, "netflix", "", _, "Standalone stories about technology and what it does to us."),
    ("dark", "Dark", 2017, "t", "scifi,mystery,drama", "international", 3, "TV-MA", 0, "netflix", "", _, "A missing child sends four German families into a time-travel mystery."),
    ("arcane", "Arcane", 2021, "t", "animation,action,fantasy", "", 2, "TV-14", 0, "netflix", "", _, "Two sisters end up on opposite sides of a war between a rich city and its undercity."),
    ("adolescence", "Adolescence", 2025, "t", "drama,crime", "international", 1, "TV-MA", 0, "netflix", "", _, "A 13-year-old is arrested for murder. Four episodes, each one unbroken take."),
    ("nimona", "Nimona", 2023, "m", "animation,family,fantasy", "", 101, "PG", 0, "netflix", "", _, "A knight framed for a crime teams up with a shapeshifting teen he's supposed to fight."),
    ("the-bear", "The Bear", 2022, "t", "drama,comedy", "", 4, "TV-MA", 0, "hulu", "", _, "A fine-dining chef comes home to run his late brother's Chicago sandwich shop."),
    ("only-murders", "Only Murders in the Building", 2021, "t", "comedy,mystery", "cozy", 5, "TV-MA", 0, "hulu", "", _, "Three true-crime fans in one building start a podcast about a death down the hall."),
    ("shogun", "Shōgun", 2024, "t", "drama,action", "international", 1, "TV-MA", 0, "hulu", "", _, "An English sailor shipwrecked in 1600 Japan becomes a pawn in a war for power."),
    ("abbott-elementary", "Abbott Elementary", 2021, "t", "comedy", "cozy", 5, "TV-PG", 0, "hulu", "", _, "Teachers at an underfunded Philadelphia school, and the camera crew following them."),
    ("white-lotus", "The White Lotus", 2021, "t", "drama,comedy,mystery", "", 3, "TV-MA", 0, "max", "", _, "Guests and staff at a luxury resort over one week, and a body by the end."),
    ("the-pitt", "The Pitt", 2025, "t", "drama", "", 1, "TV-MA", 0, "max", "", _, "One 15-hour shift in a Pittsburgh emergency room, an hour per episode."),
    ("hacks", "Hacks", 2021, "t", "comedy,drama", "", 4, "TV-MA", 0, "max", "", _, "A Las Vegas comedy legend and a canceled young writer, forced to work together."),
    ("dune-2", "Dune: Part Two", 2024, "m", "scifi,action,drama", "", 166, "PG-13", 0, "max", "", R, "Paul Atreides joins the Fremen and moves toward a future he fears."),
    ("andor", "Andor", 2022, "t", "scifi,action,drama", "", 2, "TV-14", 0, "disney", "", _, "A thief becomes a rebel in the years before Rogue One."),
    ("inside-out-2", "Inside Out 2", 2024, "m", "animation,family,comedy", "cozy", 96, "PG", 0, "disney", "", R, "Riley turns 13, and Anxiety moves into headquarters."),
    ("coco", "Coco", 2017, "m", "animation,family,fantasy", "cozy,halloween", 105, "PG", 0, "disney", "", R, "On Día de Muertos, a boy who wants to be a musician ends up in the Land of the Dead."),
    ("the-boys", "The Boys", 2019, "t", "action,comedy,drama", "", 4, "TV-MA", 0, "prime", "", _, "Vigilantes take on superheroes who abuse their fame and power. Very violent."),
    ("fallout", "Fallout", 2024, "t", "scifi,action,comedy", "", 1, "TV-MA", 0, "prime", "", _, "A vault dweller heads up into nuclear-blasted Los Angeles for the first time."),
    ("invincible", "Invincible", 2021, "t", "animation,action,drama", "", 3, "TV-MA", 0, "prime", "", _, "The teenage son of Earth's strongest hero gets his powers, and learns the truth about his dad."),
    ("severance", "Severance", 2022, "t", "scifi,thriller,mystery", "psychological", 2, "TV-MA", 0, "appletv", "", _, "Office workers have their work memories surgically split from their lives outside."),
    ("ted-lasso", "Ted Lasso", 2020, "t", "comedy,drama", "cozy", 3, "TV-MA", 0, "appletv", "", _, "An American football coach takes over an English soccer club, knowing nothing about soccer."),
    ("slow-horses", "Slow Horses", 2022, "t", "thriller,drama", "international", 5, "TV-MA", 0, "appletv", "", _, "MI5's washed-up agents, banished to a dead-end office, keep stumbling into real cases."),
    ("silo", "Silo", 2023, "t", "scifi,mystery,drama", "", 2, "TV-14", 0, "appletv", "", _, "Ten thousand people live in a buried silo. Asking why is forbidden."),
    ("the-office", "The Office", 2005, "t", "comedy", "cozy", 9, "TV-14", 0, "peacock", "", _, "Life at a Scranton paper company, filmed as a documentary."),
    ("poker-face", "Poker Face", 2023, "t", "mystery,comedy,crime", "cozy", 2, "TV-MA", 0, "peacock", "", _, "A woman who can always tell when someone is lying keeps landing next to murders."),
    ("wicked", "Wicked", 2024, "m", "fantasy,romance,drama", "witch", 160, "PG", 0, "peacock", "", R, "The untold story of the witches of Oz, from Shiz University onward."),
    ("oppenheimer", "Oppenheimer", 2023, "m", "drama", "", 180, "R", 0, "peacock", "", R, "The physicist who led the Manhattan Project, and what came after."),
    ("wild-robot", "The Wild Robot", 2024, "m", "animation,family,scifi", "cozy", 102, "PG", 0, "peacock", "", R, "A robot washed up on an island learns to survive and raises an orphaned gosling."),
    ("top-gun-maverick", "Top Gun: Maverick", 2022, "m", "action,drama", "", 130, "PG-13", 0, "paramount", "", R, "Maverick returns to train a new class of pilots for an impossible mission."),
    ("strange-new-worlds", "Star Trek: Strange New Worlds", 2022, "t", "scifi,action", "", 3, "TV-PG", 0, "paramount", "", _, "Captain Pike and the Enterprise crew in classic one-mission-an-episode Trek."),
    ("knives-out", "Knives Out", 2019, "m", "mystery,comedy,crime", "", 130, "PG-13", 0, "", "", R, "A detective investigates a wealthy crime novelist's death at his family's estate."),
    ("free-solo", "Free Solo", 2018, "m", "documentary", "", 100, "PG-13", 0, "disney", "", R, "Alex Honnold attempts to climb El Capitan with no ropes."),
    ("my-octopus-teacher", "My Octopus Teacher", 2020, "m", "documentary", "", 85, "TV-G", 0, "netflix", "", _, "A filmmaker spends a year visiting the same octopus in a South African kelp forest."),
    ("paddington-2", "Paddington 2", 2017, "m", "family,comedy", "cozy", 103, "PG", 0, "", "", R, "Paddington takes odd jobs to buy a pop-up book and gets framed for its theft."),
    ("everything-everywhere", "Everything Everywhere All at Once", 2022, "m", "scifi,comedy,action", "", 139, "R", 0, "max", "", R, "A laundromat owner being audited learns she must save the multiverse."),
    ("his-girl-friday", "His Girl Friday", 1940, "m", "comedy,romance", "classic", 92, "NR", 0, "", "tubi,kanopy,youtube,plex", _, "A newspaper editor schemes to keep his ex-wife, his best reporter, from remarrying."),
]


def build():
    titles = []
    seen = set()
    for row in ROWS:
        (tid, title, year, kind, genres, tags, size, cert, scare, subs, free, rent, blurb) = row
        assert tid not in seen, tid
        seen.add(tid)
        g = [x for x in genres.split(",") if x]
        tg = [x for x in tags.split(",") if x]
        s = [x for x in subs.split(",") if x]
        f = [x for x in free.split(",") if x]
        for x in s:
            assert SERVICES[x][1] == "sub", (tid, x)
        for x in f:
            assert SERVICES[x][1] == "free", (tid, x)
        stores = [k for k, v in SERVICES.items() if v[1] == "store"]
        # Anything a store rents it also sells. Shows are sold by the season, except
        # Netflix and Apple originals, which never reach the stores.
        buyable = bool(rent) or (kind == "t" and s[:1] not in (["netflix"], ["appletv"]))
        t = {"id": tid, "title": title, "year": year, "kind": "movie" if kind == "m" else "tv",
             "genres": g, "tags": tg, "rating": cert, "scare": scare, "blurb": blurb, "subs": s, "free": f,
             "rent": stores if rent else [], "rentFrom": rent, "buy": stores if buyable else [],
             "others": [], "poster": None, "link": None}
        if kind == "m":
            t["minutes"] = size
        else:
            t["seasons"] = size
        titles.append(t)
    return {"snapshot": SNAPSHOT, "genres": GENRES, "tags": TAGS, "includes": INCLUDES,
            "services": [{"id": k, "name": v[0], "kind": v[1]} for k, v in SERVICES.items()],
            "titles": titles}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "public" / "catalog.json"
    out.parent.mkdir(exist_ok=True)
    data = build()
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("%d titles (%d horror) -> %s" % (len(data["titles"]),
          sum("horror" in t["genres"] for t in data["titles"]), out))
