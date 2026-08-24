# coding=UTF-8
# ==============================================================================
#
# PROJECT REALITY ADMIN SETTINGS (formerly AD Framework)
#
# WARNING: If logging is enabled, a folder must be created under /admin/logs/, or they will not be recorded
#
# $Id: realityconfig_admin.py 20838 2013-06-24 02:41:19Z bloodydeed $
#
#
# ==============================================================================
# dont touch this import
import realityconstants as c

# GLOBAL SETTINGS
#
# If false, the entire RealityAdmin is disabled.
# Default is True
RAEnabled = True
#
# Display a sponsor message.
# Default is False
sponsorMessageEnabled = True
#
# The "sponsormessage" will be displayed every [interval] seconds.
# Default is 600 seconds
sponsorMessage = "§C1001***§C1001 Lee las reglas en nuestro servidor de Discord -->§C1001 discord.gg/latamsquad ***§C1001"
sponsorMessageInterval = 600
#
# Are admins alerted about game notifications? (E.g. FOB Destruction via radio).
# Default is True
gameNotificationsEnabled = True
#
#
# ==============================================================================
# Squads SETTINGS
#
# Seconds after round start until allowed to create squads. 
# sqd_noSquadsBefore is subtracted from the number of seconds set in 'PRROUNDSTARTDELAY' var via
# realityconfig_common.py in order to get the SquadCreationTime.
# Default is 90

sqd_noSquadsBefore = 120
#
# Resign early
# Default is False
sqd_resignEarly = True
#
# Amount of failed attempts before kick
# Default is 0 (disabled)
sqd_kickLimit = 3
#
# Kick squadless
# Default is False (disabled)
sqd_kickSquadLess = True
#
# Time until squadless players are kicked
# Default is 30 seconds
sqd_kickSquadLessTime = 300
#
#
# Kick unassigned AFK players
# Default is True (enabled)
sqd_kickSquadLessAFK = True
#
#
# Kick unassigned afk players after the specified number of seconds.
# 1200 seconds (20 mins) default
sqd_kickSquadLessAFKTime = 1200
#
#
# Only kick players once the server reaches this full 0.9 (90%) default
sqd_kickAFKPercent = 0.9
#
# Kick AFK players *in a squad*
# Default is False (disabled)
sqd_kickSquadedAFK = False
#
# Kick AFK players that are in a squad after the specified number of seconds.
# 1500 seconds (25 mins) default - give at least 15 mins (900 sec) for players in a squad to allow for timers
sqd_kickSquadedAFKTime = 1500
#
#
#
# ==============================================================================
# SMARTBALANCE SETTINGS
#
# Enable/disable smartbalancing.
# Default is True
smb_enabled = True
#
# Perform smart balance when the difference of the teams is x or more.
# Default is 2
smb_difference = 2
#
# A list of (partial) playernames and/or (clan)tags that get excluded from smart balancing.
# If tag is part of name, you need to define position (front/back) by using * as wild card.
# E.g. to add [R-DEV]PRBot you need to add "[R-DEV]*"
smb_excludeList = []
# If set to True, it will teamswap everyone on round startup.
# Some people don't (or can't) have modmanager to do this for them.
# Default is True
smb_swapTeamsOnStart = True
#
# 
# If set to true, teams will be scrambled at the start of each round
smb_scrambleTeamsOnStart = False
# If set to true, when a player joins the server they will join onto a random team.
# Joining players will still be subject to any smartbalancing.
# By default players always load in on blufor. Default is False.
smb_randomiseJoinTeam = False
# If set to True, players might get teamswitched for balance when they go dead-dead
# Might switch anyone who is not SL/CO or on switch list
# Default is True
smb_balanceOnDeath = False

# Keep same IP players on the same team
# Default is False
smb_antiGhost = True

# Disallow mid round !switches
# Default is False (off)
smb_disableSwitchNow = False

# Force players onto the same team on reconnect
# Default is True (on)
smb_forceRejoinTeamswitch = True

#
#
# ==============================================================================
# LOGS SETTINGS
#
# Date format for logging
# Default is "%Y%m%d_%H%M"
log_date_format = "%d-%m-%Y %H:%M"
#
# Time format for logging
# Default is "%H:%M:S"
log_time_format = "%H:%M:%S"
#
# Enable/disable chat logging
# Default is True
log_chat = True
#
# Enable/disable player connect/disconnect logging. Written into chatlog
# Default is True
log_connects = True
#
# Enable/disable player team switch logging. Written into chatlog
# Default is False
log_changeTeam = True
#
# Chat log file name.
# Default is "chatlog_%Y-%m-%d_%H%Ms.txt"
log_chat_file = "chatlog_%d-%m-%Y_%H%M.txt"
#
# Chat log file name.
# Default is "admin/logs"
log_chat_path = "admin/logs"
#
# Enable/disable teamkill logging. Saved in chatlog
# Default is True
log_teamkills = True
#
# Enable/Disable logging of players who play from the same IP at the same time.
# Default is True
log_coincident_IPs = True
#
# Enable/disable kill logging. Saved in chatlog
# Default is False
log_kills = False
#
# Enable/disable admin command logging. Saved in continues file.
# Default is True
log_admins = True
#
# Enable/disable logging of bans. Saved in continues file.
# Default is True
log_bans = True
#
# Enable/disable logging of tickets on round end. Saved in continues file.
# Default is True
log_tickets = True
#
# Filename of the admin log file
# Default is "ra_adminlog.txt"
log_admins_file = "ra_adminlog.txt"
#
# Path relative to PR root (not mod root) of admin log file
# Default is "admin/logs"
log_admins_path = "admin/logs"
#
# Filename of the admin log file
# Default is "banlist_info.log"
log_bans_file = "banlist_info.log"
#
# Path relative to PR root (not mod root) of ban log file. [MOD] gets replaced by current mod directory
# Default is "[MOD]/settings/"
log_bans_path = "[MOD]/settings/"
#
# Filename of the coincident IP address file
# default is "IPcoincidences.log"
log_IP_coincidence_file = "IPcoincidences.log"
#
# Path relative to PR root (not mod root) of IP coincidence log. [MOD] gets replaced by current mod directory
# Default is "[MOD]/settings/"
log_IP_coincidence_path = "[MOD]/settings/"
#
# Filename of the tickets log file
# Default is "tickets.log"
log_tickets_file = "tickets.log"
# Path relative to PR root (not mod root) of tickets log file
# Default is "admin/logs"
log_tickets_path = "admin/logs"
#
#
#
# ==============================================================================
# ANNOUNCER SETTINGS
#
# Tip: Text preceded by §C1001 will make it orange. §3 makes it big. §C1001§3 makes it orange and big.
# Enable/disable announcer.
# Default is True
ann_enabled = True
#
# Enable/disable dislpaying a message when a player joins the server (spawns for the first time).
# Default is True
ann_joinMessageEnabled = True
#
# Message to send to the player (this is a PM).
# If you want the message to contain a name, make sure to insert [playername] somewhere.
ann_joinMessage = "§C1001Bienvenido a LATAMSQUAD, [playername]!"
#
# If True, a message is displayed when a player disconnects from the server.
# Default is False
ann_disconnectMessageEnabled = True
#
# This message is displayed when a player disconnects from the server.
ann_disconnectMessage = "[playername] ha abandonado el servidor."
#
# Enable/disable displaying timed messages.
# Default is False
ann_timedMessagesEnabled = True
#
# Timed servermessages.
# Usage: Interval: Message
ann_timedMessages = {
    300:  "Para reportar usa !rp. Su mal uso sera sancionado / To report an user type !rp. Misuse will be punished.",
    420:  "Cansado de hacer largas filas? Puedes donar y usar el slot reservado. Mas info en latamsquad.org",
    540:  "Para apelaciones por baneo u otro motivo, ingresa a (discord.gg/latamsquad) seccion #soporte.",
    900:  "Transcurrido 15 minutos no se permite cambiar de equipo a menos que hayas entrado recien.",
   1200:  "Si se te dio vuelta un vehiculo o estas atrapado, pide a un admin que te ayude con !flip - !push - !fly",
}
#
#
# ==============================================================================
# ADMIN SETTINGS
#
# Enable/disable admincommands.
# Default is True
adm_enabled = True
#
# Enable/disable to show PRISM users in !admins command.
# Default is True
adm_show_prism = True
#
# If true, as soon as the last admin leaves autoadmin will be activated.
# Default is False
adm_autoAdmin = True
#
# If true, admins will get notified about players switching teams.
# Default is False
adm_notifyChangeTeam = True
#
# If true, send a message on each teamkill containing
# weapon and distance between the players
# Default is True
adm_sendTeamKillMessage = True
#
# If true, will notify all admins that a player has connected with
# the same IP as another player currently on the server.
# Default is True
adm_notifySameIP = True
#
# Time in minutes a player is temp banned (if you use the temp-ban command, normal ban is forever!).
# Note: if the server is restarted, the ban is lifted.
# Default is 180
adm_banTime = 180
#
# Admin command symbol.
# Default is !
adm_commandSymbol = "!"
#
# Symbol to indicate you want to target player ID instead of name.
# Default is @
adm_idPrefix = "@"
#
# Symbol to indicate you want to target a squad instead of name.
# Default is #
adm_squadPrefix = "#"
#
# Define the maximum altitude (used in the fly-command).
# Default is 1000
adm_maxAltitude = 10000
#
# Define the maximum distance (used in the push-command).
# Default is 1000
adm_maxPush = 10000
#
# Time how long a mapvote will take.
# Default is 60
adm_mvoteDuration = 90
#
# Time between the !mvote message pops up in the upper left corner.
# Default is 10
adm_mvoteRecurrence = 10
#
# The maximum number of ropes a player can have active
# Default is 10
adm_maxRopes = 10
#
# If !givelead should work in coop
# Default is true
adm_coopGiveLead = True
#
# Array in which the names of the administrators will be saved.
# ASEGURATE QUE NO HAYA DUPLICADOS! ORDENAR ALFABETICAMENTE!
adm_adminHashes = {
    "0161096bb0984d11bccc7f6f776e2e82":    2,    # _JORGE           --Moderador
    "f5064ec675ad4d90aa824da880de03ae":    2,    # Aatrix_          --Moderador
    "bcf835f6633f40888d5e33055e7cb511":    2,    # binkydadrinky    --Moderador
    "0e09df30a7cd440983c22f8e2fefe9b3":    2,    # Calestic-.       --Moderador
    "e91963580cab4c5995570164b4a0dc4e":    2,    # Chaman           --Moderador
    "792eb21803b84249a43c27752f9bd0e7":    0,    # Chaziz           --Directivo
    "4d070fb29faf4d27844d93535c8ba5ee":    2,    # CHEINFIERNO      --Moderador   
    "57b9f059e7744f248a98d98a498cb8a5":    2,    # Enzo.            --Moderador
    "e3bbb6de64c74a0eaf2388d32554649c":    2,    # EclipseS         --Moderador
    "905d96703b3a43f7bd00e351eca9ba6d":    2,    # halocapo177      --Moderador
    "c71d90158ad14f6689e90573856e6a4e":    2,    # Har-             --Moderador      
    "6da8d35fd158481e8f0e8e7195781c06":    2,    # Mizzar           --Moderador
    "97918d9fd1d74a93b0dddb132c570264":    0,    # NascimentoWAR    --Supervisor
    "5106ccbe505548d1b446c358cdd9b5d9":    2,    # NotGenius        --Moderador
    "025a490b9cfe4b028a92f4aec5899037":    0,    # Sunfiree         --Supervisor    
    "501eb007fef44c8ead5c951c03740991":    0,    # Tosky2712        --Supervisor   
    "bc0b80c909d24bfd97008d196b1be294":    0,    # Zxrro            --Directivo
}
#
# Array in which the liteadmins are saved.
# Leave it empty if you dont want to use this functionality.
adm_liteAdminHashes = {
    # "ENTER_LITE_ADMIN_HASHES_HERE":    2,    # comment , Liteadmin
}
#
# Command aliases
# Specify aliases for long commands here.
adm_commandAliases = {
    "k":        "kick",
    "tb":       "tempban",
    "rb":       "roundban",
    "b":        "ban",
    "r":        "report",
    "rp":       "reportplayer",
    "w":        "warn",
    "s":        "say",
    "m":        "message",
    "st":       "sayteam",
    "ub":       "unban",
    "mvote":    "mapvote",
    "mv":       "mapvote",
    "lastmap":  "history",
    "lastmaps": "history",
    "ug":       "ungrief",
    "a":        "admins",
    "sn":       "setnext",
    "sw":       "switch",
}
#
# Rights management.
# The lower the powerlevel, the more power one has.
# Two powerlevels are defined by default, but you can define as many as you want.
adm_adminPowerLevels = {
    # 0: Superadmin, can do everything.
    # 1: Moderator, can't do everything.
    # 2: Meant to use for liteadmins.
    # 777: used for commands that everyone can use.
    #
    # Reload the current map.
    # Default is 1
    "reload": 2,
    #
    # Run the next map.
    # Default is 2
    "runnext": 2,
    #
    # Set a next map.
    # Default is 2
    "setnext": 2,
    #
    # Initializes a global server mapvote between 2-3 maps.
    # People can then vote with either writing 1,2 or 3 in chat.
    # All admins will receive a message which map won after a configured time.
    # Default is 2
    "mapvote": 777,
    #
    # Sends a message to a specified player.
    # Similar to !warn but without the STOP DOING THAT and is private.
    "message": 2,
    #
    # Diplays the ticket count of both teams.
    "tickets": 2,
    #
    # Player control
    # Ban a player.
    # Default is 1
    "ban": 2,
    #
    # Ban a player for a specified amount of time.
    # Default is 1
    "timeban": 2,
    #
    # Ban a player for a round
    # Default is 1
    "roundban": 2,
    #
    # Unbans the latest banned player.
    # Default is 1
    "unban": 1,
    #
    # Send a player up in the air.
    # Default is 0
    "fly": 2,
    #
    # Push a player forward.
    # Default is 0
    "push": 2,
    #
    # Gives pilot kit (only for test maps)
    # Default is 777
    "pilot": 777,
    #
    # Retrieves the hash of certain player.
    # Default is 2
    "hash": 2,
    #
    # Kick a player.
    # Default is 2
    "kick": 2,
    #
    # Kill a player.
    # Default is 1
    "kill": 2,
    #
    # Resign a player from being squad leader or commander.
    # Default is 2
    "resign": 2,
    #
    # Resign a player from being squad leader or commander.
    # Default is 2
    "resignall": 2,
    #
    # Teamswitch a player.
    # Default is 2
    "switch": 777,
    #
    # Temporary ban a player (basically extended 'kick').
    # Default is 1
    "tempban": 2,
    #
    # Warn a player.
    # Default is 2
    "warn": 2,
    #
    # Text messages
    # Show help about commands.
    # Default is 2
    "help": 2,
    #
    # Send a message to everybody.
    # Default is 2
    "say": 2,
    #
    # Same as !s, but for one team only.
    # Default is 2
    "sayteam": 2,
    #
    # Server- and Pythoncommands
    # Enable/disable smart balancing (ab = autobalance, people call it that).
    # Default is 1
    "ab": 2,
    # Reload some settings.
    # Default is 2
    "init": 2,
    #
    # Swap the teams.
    # Default is 0
    "swapteams": 2,
    #
    # Scramble the teams.
    # Default is 0
    "scramble": 2,
    #
    # Stops the server.
    # Default is 1
    "stopserver": 1,
    #
    # Enable/disable autoadmin.
    # Default is 1
    "aa": 0,
    # 
    # Displays a list of the last n maps that were played on the server (Configurable count)
    # Default is 2
    "history": 777,
    #
    # Open commands
    # Please note that 777 is a fixed value for "open" commands!
    # This means everybody on the server can use them.
    # Returns a list of online admins.
    # Default is 777
    "admins": 777,
    #
    # Report a player.
    # Default is 777
    "reportplayer": 777,
    #
    # Send a message to the admins.
    # Default is 777
    "report": 777,
    #
    # Shows the serverrules.
    # Default is 777
    "rules": 777,
    #
    # Show the next map.
    # Default is 777
    "shownext": 777,
    #
    # Give squad lead to another player.
    # Default is 777
    "givelead": 777,
    #
    # shows if Battlerecorder is activated and which quality its running with.
    # Default is 777
    "br": 777,
    #
    # Displays a link to the server website.
    # Default is 777
    "website": 777,
    #
    # Flip a player vehicle.
    # Default is 2
    "flip": 2,
    #
    # Teleport a player.
    # Teleport with coordinates X Y Z
    "tp": 2,
    #
    # Teleport to a player.
    # Teleport with playername
    "tpto": 2,
    #
    # Mute a player.
    # Default is 2
    "mute": 2,
    #
    # Heal a player.
    # Default is 2
    "heal": 2,
    #
    # Rearms a player.
    # Default is 2
    "rearm": 2,
    # Ungrief
    #
    "ungrief": 2,
    #
    # Reset squads - may fix squad bug
    "resetsquads": 2,
    #
    # Server Entrance control
    # handle whitelist and join permissions to the server
    "ec": 0,
    #
    # Player info
    # Print IP, Account ID ("hash"), level, and whitelist status of a player
    "info": 2,
    #
    # Player idle time
    # Print 5 longest afk players
    "showafk": 2,
    #
    # Ban a player by hash
    "banid": 2,
    #
    # Temp Ban a player by hash
    "timebanid": 2,
    #
    # Unban a player by hash
    "unbanid": 1,
    #
    # Unban a player by name
    "unbanname": 1,
    #
    # Make a player leader of their squad
    "assignlead": 2,
    #
    #

}
#
# This text will be sent to the player issueing !website.
adm_website = "§C1001latamsquad.org /// discord.gg/latamsquad"
#
# Predefined reasons, so you only have to type a keyword as a reason.
# The script will automatically replace it with the reason you enter below.
# Note: only use lowercase in the reason "keys", you can use all cases in the reason itself.
adm_reasons = {
    "afk?":         "Estas AFK? Responde por !r",
    "afk":          "Estas AFK",
    "all":          "El uso de AllChat se limita solamente a las disculpas por TK y comunicacion con la administracion",
    "asset":        "Desperdicio de asset, debes practicar antes de usar nuestros activos!",
    "dc":           "Cualquier problema, duda o reporte puedes hacerlo en nuestro discord.gg/latamsquad",
    "ddos":         "Estamos bajo ataque DDOS, pedimos paciencia. Los microfonos estaran desactivados hasta que se mitigue el ataque",
    "gros":         "Cuidado con el lenguaje!",
    "heli":         "El helicoptero debe ser conducido de manera defensiva, cualquier intento por provocar o no evitar su destruccion sera sancionado",
    "heli2":        "Has perdido 3 helicopteros. Seras resignado y tienes prohibido pilotear por el resto de partida",
    "kit":          "Ese kit es de importancia para el equipo, no lo utilice si no sabe usarlo!",
    "locked":       "No cumples los requisitos para tener cerrada la escuadra, debes abrirla",
    "logi":         "El vehiculo logistico no se puede utilizar como transporte personal",
    "main":         "Esta totalmente prohibido disparar o tirar granadas en la base principal",
    "mapa":         "Quejarse del mapa actual o mapvote es motivo de kick. Repetidas quejas pueden terminar en ban",
    "mc":           "No se permite el DOD Camping a menos que la ultima bandera enemiga haya sido tomada",
    "mic":          "Debes comunicarte activamente con tu microfono o seras resignado",
    "mono":         "Esta prohibido monotripular ese vehiculo, devuelvelo a la base principal INMEDIATAMENTE!",
    "racismo":      "Cualquier tipo de racismo no sera tolerado en este server, cuida tus palabras o seras baneado",
    "robo":         "Estas robando un vehiculo, devuelvelo a su escuadra INMEDIATAMENTE!",
    "rp":           "Para reportar a un usuario utiliza !rp. Su mal uso sera severamente sancionado",
    "sl":           "Lideres de Escuadra deben usar obligatoriamente kit de Oficial y hablar espanol o ingles",
    "sl2":          "No crees una escuada sin intencion de liderarla o seras sancionado",
    "spam":         "Para de spamear ahora mismo!",
    "sq":           "Si no entras a una escuadra el server te kickeara automaticamente!",
    "st":           "Squad time, guarda silencio para que las escuadras se coordinen!",
    "sw":           "Transcurrido 15 minutos no se permite cambiar de equipo a menos que hayas entrado recien",
    "objetivo":     "Concentrate en ayudar a tu equipo capturando los objetivos", 
    "tk":           "Recuerda disculparte por los teamkill tanto por voz como por chat, podrias ser sancionado si no lo haces",
    "vip":          "Cansado de hacer largas filas? Puedes donar y usar el slot reservado. Mas informacion en discord.gg/latamsquad VIP",
    "vote":         "En breve realizaremos la votacion para el siguiente mapa. Para votar, escribe el numero en tu chat de escuadron (L)",  
    "alleng":       "Use of AllChat is limited only to TK apologies and communication with management",
    "asseteng":     "Waste of asset, you must practice before using our assets!",
    "groseng":      "Watch your language!",
    "logieng":      "The logistics vehicle cannot be used as personal transportation",
    "maineng":      "It's strictly prohibited to shoot or throw grenades in the main base",
    "mceng":        "DOD Camping is not permitted unless the last enemy flag has been taken",
    "monoeng":      "It's prohibited to single-drive that vehicle, return it to the main base IMMEDIATELY!",
    "racismoeng":   "Any type of racism will not be tolerated on this server, watch your words or you will be banned",
    "roboeng":      "You are stealing a vehicle, return it to its squad IMMEDIATELY!",
    "sleng":        "Squad leaders must have an Officer's kit and speak Spanish or English",
    "sl2eng":       "Do not create a squad without the intention of leading it or you will be sanctioned",
    "steng":        "Squad time, be silent so the squads can coordinate!",
    "tkeng":        "Remember to apologize for the teamkills both by voice and chat, you could be penalized if you don't", 
    "fl":           "Quieres aprender a liderar una escuadra en Project Reality? FORJANDO LIDERES es para ti! Busca la sección Forjando Lideres en nuestro servidor de Discord: discord.gg/latamsquad",
}
#
# Enable displaying rules.
# Default is False
adm_rulesEnabled = True
#
# Array in which the rules of the server will be saved.
# Five rules is the max, the player can't see more than five lines. Remove lines if desired.
adm_rules = [
    "La incitacion al odio, el racismo y los ataques personales no seran tolerados en ninguna forma",
    "El uso de AllChat se limita solamente a las disculpas por TK y comunicacion con la administracion",
    "Evitar sonidos molestos en momentos donde la comunicacion es crucial",
    "Disculpate por teamkills (fuego amigo) en AllChat.",
    "Respeta la cadena de mando",
]
#
# Modify this if you want to add additional maps. You do NOT need to add official maps.
# Example:
# "asad_khal|gpm_cq|inf",
# "asad_khal|gpm_cq|alt",
# "asad_khal|gpm_cq|std",
# "asad_khal|gpm_cq|lrg"
adm_mapListCustom = [
    # "mapname|gamemode|layer",
]

# Give reserved slots for the following groups
# available groups: ["CON", "DEV", "RETIRED", "TESTER"]
adm_devReservedSlots = ["CON", "DEV", "RETIRED", "TESTER"]

# PRISM: See realitymod.com/prism for help.
rcon_enabled = True

# Rcon welcome message
rcon_welcome = 'Bienvenido a PRISM de LATAMSQUAD!'

# Powerlevels for the commands
rcon_commandPowerLevels = {
    # PRISM user management
    'getusers':        0,
    'adduser':         0,
    'changeuser':      0,
    'deleteuser':      0,
    # Game management
    'mapplayers':      2,
    'mapgameplay':     2,
    'readbanlist':     2,
    'setbanlist':      2,
    'readmaplist':     2,
    'setmaplist':      2,
    'apiadmin':        2,
    # Do not change these
    'listplayers':     777,
    'serverdetails':   777,
    'gameplaydetails': 777,
}

# ACSYS Asset Claim SYStem (commented out for now, future patch)
acsys_enable = True  # Enforce squads in acsys_assets name uniqueness
acsys_low_pop_limit = 1  # enforce a minimum number of players before using assets, set to 0 to disable
# c.VEHICLE_TYPE_UNKNOWN
# c.VEHICLE_TYPE_ARMOR  # TANK
# c.VEHICLE_TYPE_AAV  # Anti Air
# c.VEHICLE_TYPE_APC
# c.VEHICLE_TYPE_IFV
# c.VEHICLE_TYPE_JET
# c.VEHICLE_TYPE_HELI
# c.VEHICLE_TYPE_HELIATTACK
# c.VEHICLE_TYPE_TRANSPORT
# c.VEHICLE_TYPE_RECON
# c.VEHICLE_TYPE_STATIC
# c.VEHICLE_TYPE_SOLDIER
# c.VEHICLE_TYPE_ASSET
# c.VEHICLE_TYPE_SHIP
# c.VEHICLE_TYPE_TURBOPROP
# c.VEHICLE_TYPE_AFV # open top shitboxes Armoured Fighting Vehicle
# c.VEHICLE_TYPE_ALC  # Armoured Logistics Carrier
# c.VEHICLE_TYPE_UAV
acsys_assets = {
    "APC": {
        "squadname_contains": ["APC"],  # squad contains this string
        "squad_controls": [c.VEHICLE_TYPE_APC, c.VEHICLE_TYPE_IFV],  # _type_
        "exclude": [],  # templateName string list to exclude
    },
    "TANK": {
        "squadname_contains": ["TANK"],
        "squad_controls": [c.VEHICLE_TYPE_ARMOR],
        "exclude": [],
    },
    "CAS": {
        "squadname_contains": ["CAS"],
        "squad_controls": [c.VEHICLE_TYPE_JET, c.VEHICLE_TYPE_HELIATTACK, c.VEHICLE_TYPE_TURBOPROP],
        "exclude": [],
    },
    "TRANS": {
        "squadname_contains": ["TRANS"],
        "squad_controls": [c.VEHICLE_TYPE_HELI],
        "exclude": [],
    },
}
acsys_low_pop = {  # additional types and template names to exclude from low pop servers
    "vehicle_type": [c.VEHICLE_TYPE_APC, c.VEHICLE_TYPE_IFV, c.VEHICLE_TYPE_ARMOR,
        c.VEHICLE_TYPE_JET, c.VEHICLE_TYPE_HELIATTACK, c.VEHICLE_TYPE_AAV, c.VEHICLE_TYPE_TURBOPROP],
    "include": ["civ_trk_dumpster_bomber", "civ_atm_technical"],
}

# Prism TCP port to listen on
rcon_port = 4714

# Entrance control
# Possible values are 0, 1, 2
# 0 Means everyone
# 1 Means some trust
# 2 Means high trust
ec_minimumTrust = 0

# Allow VAC banned users to join the server if they're not on whitelist
ec_allowVacBanned = True

# Report this as your external IP to the master server.
# Do not touch unless you have multiple interfaces
sv_externalIP = "172.84.94.108"

# Shared secret between gameserver and murmur. Prevents players that are not on the server from speaking on mumble.
# Gameserver and murmur should set this to the same secret value.
# (on murmur, set at PRMurmur\mumo\modules-enabled\prbf2.ini, at [prbf2]/secret)
# You must make sure the clock of the gameserver host and the murmur host are synchronized (different timezones are
# considered)
# Does nothing if the feature is not enabled on murmur.
mum_mumbleSecret = "mxAHnselUb0leC9lCq83"

# Country flag to display on PRSPY.
# Must be 2 letters of the country, such as "US" or "RU".
sv_countryflag = "x1"

# Record admin and player squad chat that is prefixed with ! into tracker files
track_commandchat = True

# Display the name of the admin who kicked or banned a player to the player along with the kick reason.
display_kickAdmin = True

testscramble = True

# Prevent these IDs from being caught in related bans, useful for genuinely shared computers etc
# whitelisted_player_ids = ["77ff5fecc0e648249bd6b01fdba02242"]
whitelisted_player_ids = []

# Disables all-chat input for clients (clients can still send messages in team-chat and squad-chat)
# Default is false
disable_allchat = False

# Locations relative to the mod directory for sqlite3 ban database, uncomment to apply. Absolute, non-standard locations NOT SUPPORTED
bans_sqlite3 = "C:/prbf2_db/bans.sqlite3"

#
# ALLCHAT
# Disable all-chat input for clients (clients can still send messages in team-chat and squad-chat)
# This is a final setting. If this is set to true it will disable allchat, period.
# Default is false
disable_allchat = False

# This is allchat enabling/disabling based on player count. The above setting must be set to false for these to be in effect.
# If the player count is greater than or equal to the disable_threshold, allchat is disabled.
# If the player count is truly lower than the enable_threshold, allchat is enabled.
# Make sure you have a certain difference between them. Eg. set disable_threshold to 60 and enable_threshold to 40.
# Otherwise allchat will be constantly enabled and disabled when the player count rises and falls by a single count.
# Default is 999 for both (which has the effect that these are ignored)
allchat_disable_threshold = 999
allchat_enable_threshold = 999
