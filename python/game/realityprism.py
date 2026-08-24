import datetime
import hashlib
import time
import bf2
import host
import realityadmin
import realityassets as rassets
import realityconfig_admin
import realitycore as rcore
import realitydebug as rdebug
import realitynetwork
import realityserver
import realitytimer as rtimer
SERVER_VERSION = 1
isReady = False
auth_users = {}
users = {}
hardcoded_users = {'superuser': []}
userFileName = 'admin/rconUsers.dat'
suFileName = 'admin/rconSuperuser.dat'
rconCommands = {}
chatBuffer = ''
killBuffer = ''
cachedUsers = {}
playerIPs = []
serverDetailsCache = {}
serverMapCache = {'mapReady': False,
 'mapSent': False,
 'updateSent': False,
 'cps': '',
 'fobs': '',
 'rallies': '',
 'caches': '',
 'objectives': ''}
serverRallyCache = {}
playersAtEndOfRound = None
haveGotEndGameDisconnects = False
serverStartTime = None
serverStatus = None
serverRoundStart = None
serverLayer = None
serverRoundWarmup = None
serverRoundLength = None
serverDebugMode = False
prismIndexCounter = 0
rconServer = None

def init():
    global rconCommands
    global rconServer
    warnAboutOldConfiguration()
    if not realityconfig_admin.rcon_enabled:
        return
    rconServer = realitynetwork.NetworkServer(realityconfig_admin.rcon_port, handleRconCommand)
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('ChatMessage', onRconChatMessage, 1)
    host.registerHandler('PlayerSpawn', onPlayerSpawn, 1)
    host.registerHandler('PlayerKilled', onPlayerKilled, 1)
    host.registerHandler('VehicleDestroyed', onVehicleDestroyed, 1)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    host.registerHandler('PlayerDisconnect', onPlayerDisconnect, 1)
    host.registerHandler('RallyCreated', rallyCreated, 1)
    host.registerHandler('RallyDelete', rallyDeleted, 1)
    rtimer.repeatingTask(update, interval=1.0)
    rtimer.repeatingTask(bigUpdate, interval=10.0)
    rtimer.Timer(pollNetworkServerAndChat, delta=1, alwaysTrigger=1).setRecurring(0.2)
    readUsers()
    rconCommands = {'getusers': ListRCONUsers,
     'adduser': AddRCONUser,
     'changeuser': ChangeRCONUser,
     'deleteuser': DeleteRCONUser,
     'listplayers': ListPlayers,
     'gameplaydetails': ListMapDetails,
     'serverdetails': ListServerDetails,
     'readmaplist': ReadMapList,
     'readbanlist': ReadBanList,
     'apiadmin': RunAdminCommand,
     'serverdetailsalways': ListServerDetailsAlways}


def warnAboutOldConfiguration():
    if host.rcon_invoke('sv.adminscript').strip().lower() == 'prism':
        host.rcon_invoke('echo "PRISM ERROR: sv.adminscript is no longer the way to enable prism"')
        host.rcon_invoke('echo "Check the prism config under realityconfig_admin.py to enable prism"')


def pollNetworkServerAndChat(data = None):
    if rconServer:
        rconServer.update()
    SendBuffers()


def update(data = None):
    UpdatePlayerList()


def bigUpdate(data = None):
    UpdateServerDetails()
    UpdateMapDetails()


def SendBuffers():
    global auth_users
    global chatBuffer
    global killBuffer
    if chatBuffer == '' and killBuffer == '':
        return
    for user in auth_users.values():
        user.writeBack('chat', chatBuffer)
        user.writeBack('kill', killBuffer)

    chatBuffer = ''
    killBuffer = ''


def UpdateServerDetails():
    message = GetServerDetails()
    if not message:
        return
    for _id in auth_users:
        if not auth_users[_id].isReadyServer():
            continue
        auth_users[_id].writeBack('updateserverdetails', message)


def UpdateMapDetails():
    message = GetMapDetails()
    if not message:
        return
    for _id in auth_users:
        if not auth_users[_id].isReadyMap():
            continue
        auth_users[_id].writeBack('gameplaydetails', message)


def UpdatePlayerList():
    global cachedUsers
    if len(auth_users) == 0:
        return
    messageString = ''
    messageStringNoPos = ''
    for p in bf2.playerManager.getPlayers():
        if p.getName() not in cachedUsers:
            cachedUsers[p.getName()] = CachedPlayer()
            out = cachedUsers[p.getName()].getAllValues(p)
            messageString += GetPlayerHeader(p) + out[0]
            messageStringNoPos += GetPlayerHeader(p) + out[1]
        else:
            out = cachedUsers[p.getName()].getChangedValues(p)
            if out:
                messageString += p.getName() + '\x03' + str(p.index) + '\x03' + out[0]
                messageStringNoPos += p.getName() + '\x03' + str(p.index) + '\x03' + out[1]

    if messageString == '':
        return
    for _id in auth_users:
        if not auth_users[_id].isReadyPlayers():
            continue
        if auth_users[_id].power > realityconfig_admin.rcon_commandPowerLevels['mapplayers'] or auth_users[_id].restricted:
            auth_users[_id].writeBack('updateplayers', messageStringNoPos)
        else:
            auth_users[_id].writeBack('updateplayers', messageString)


def GetMapDetails(_all = False):
    try:
        if not serverMapCache['mapReady']:
            return False
        cpString = ''
        fobString = ''
        rallyString = ''
        objectiveString = ''
        if True:
            for cp in rcore.getControlPoints():
                cpString += str(cp.getTemplateProperty('ControlPointID')) + ':' + str(cp.cp_getParam('team')) + '\n'

            serverMapCache['mapSent'] = True
            if len(cpString) > 0:
                cpString = cpString[:-1]
        if True:
            if rcore.reallyPlaying():
                for team in [1, 2]:
                    for obj in rassets.g_asset['outpost'][team]:
                        fobString += str(obj.getPosition()) + ':' + str(team) + '\n'

            if len(fobString) > 0:
                fobString = fobString[:-1]
            else:
                fobString = 'None'
            for key, val in serverRallyCache.items():
                rallyString += val

            if len(rallyString) > 0:
                rallyString = rallyString[:-1]
            else:
                rallyString = 'None'
            serverMapCache['updateSent'] = True
        if not _all:
            if serverMapCache['cps'] != cpString:
                serverMapCache['cps'] = cpString
            else:
                cpString = ''
            if serverMapCache['fobs'] != fobString:
                serverMapCache['fobs'] = fobString
            else:
                fobString = ''
            if serverMapCache['rallies'] != rallyString:
                serverMapCache['rallies'] = rallyString
            else:
                rallyString = ''
            if serverMapCache['caches'] != objectiveString:
                serverMapCache['caches'] = objectiveString
            else:
                objectiveString = ''
        out = '%s\x03%s\x03%s\x03%s\x03' % (cpString,
         fobString,
         rallyString,
         objectiveString)
        if out == '\x03\x03\x03\x03':
            return False
        return out
    except:
        pass


def UpdatePrismUsers():
    message = ''
    for _id in auth_users:
        message += auth_users[_id].adminName + '\n'

    return message[:-1]


def GetServerHeader():
    global serverRoundWarmup
    global serverRoundLength
    global serverStartTime
    return '%s\x03%s\x03%s\x03%s\x03%s\x03%s\x03%s\x03' % (GetServerProperty('sv.serverName'),
     GetServerProperty('sv.serverIP'),
     GetServerProperty('sv.serverPort'),
     str(serverStartTime),
     str(serverRoundWarmup),
     str(serverRoundLength),
     GetServerProperty('sv.maxPlayers'))


def GetServerDetails(_all = False):
    global serverDetailsCache
    global serverRoundStart
    global serverStatus
    global serverLayer
    message = ''
    writeOut = False
    serverDetails = [('status', serverStatus),
     ('map', host.sgl_getMapName()),
     ('mode', host.ss_getParam('gameMode')),
     ('layer', serverLayer),
     ('timeStarted', serverRoundStart),
     ('players', bf2.playerManager.getNumberOfPlayers()),
     ('team1', bf2.gameLogic.getTeamName(1)),
     ('team2', bf2.gameLogic.getTeamName(2)),
     ('tickets1', bf2.gameLogic.getTickets(1)),
     ('tickets2', bf2.gameLogic.getTickets(2)),
     ('rconUsers', UpdatePrismUsers())]
    for det in serverDetails:
        if _all or det[0] not in serverDetailsCache or det[1] != serverDetailsCache[det[0]]:
            writeOut = True
            message += str(det[1])
            if not _all:
                serverDetailsCache[det[0]] = det[1]
        message += '\x03'

    if not writeOut:
        return False
    else:
        return message[:-1]


def GetServerProperty(_property, replace = ''):
    return str(host.rcon_invoke(_property).replace('\n', replace))


def GetPlayerHeader(p):
    try:
        if p.epochJoinTime == '':
            return
    except:
        p.epochJoinTime = str(time.time())

    return '%s\x03%s\x03%s\x03%s\x03%s\x03%s\x03%s\x03' % (p.getName(),
     p.isAIPlayer(),
     realityserver.getPlayerHash(p),
     p.getAddress(),
     p.getProfileId(),
     p.index,
     p.epochJoinTime)


def onGameStatusChanged(status):
    global serverRoundStart
    global playerIPs
    global haveGotEndGameDisconnects
    global prismIndexCounter
    global serverStartTime
    global serverStatus
    if not serverStartTime:
        serverStartTime = time.time()
    serverRoundStart = time.time()
    serverStatus = str(status)
    if status == bf2.GameStatus.Loaded:
        if not haveGotEndGameDisconnects:
            haveGotEndGameDisconnects = True
            for user in auth_users:
                ListPlayers(auth_users[user], None)

            playerIPs = []
            for p in bf2.playerManager.getPlayers():
                playerIPs.append(p.getAddress())

            CheckRemoteUserOnServer()
    if status == bf2.GameStatus.EndGame:
        haveGotEndGameDisconnects = False
        serverMapCache['mapReady'] = False
        serverMapCache['mapSent'] = False
        serverMapCache['updateSent'] = False
        prismIndexCounter = 0
        serverRallyCache.clear()
    return


def onRconChatMessage(playerId, text, channel, flags):
    global chatBuffer
    try:
        try:
            if playerId == -1:
                player = None
            else:
                player = rcore.getPlayerByIndex(playerId)
                player.idle = 0
        except:
            player = None

        _type = -1
        friendlyChannel = ''
        try:
            _type = int(channel)
            if _type == 4:
                friendlyChannel = 'Server'
            elif _type == 5:
                friendlyChannel = 'Response'
            elif _type == 6:
                friendlyChannel = 'Admin Alert'
        except:
            pass

        if channel == 'Global':
            friendlyChannel += 'Global '
        elif channel == 'Team' or channel == 'Squad':
            if player.getTeam() == 2:
                _type = 1
                friendlyChannel += 'BluFor'
            else:
                _type = 0
                friendlyChannel += 'OpFor'
            if channel == 'Squad':
                _type = 2
                friendlyChannel += ' ' + str(player.getSquadId())
        elif channel == 'ServerMessage':
            _type = 3
            friendlyChannel += 'Game'
        elif channel == 'ServerTeamMessage':
            _type = int(flags) - 1
            if flags == 2:
                friendlyChannel += 'Game (BluFor)'
            else:
                friendlyChannel += 'Game (OpFor)'
        elif channel == 'Player':
            return
        if text.find('HUD_CHAT_DEADPREFIX') != -1:
            friendlyChannel += ' *'
        text = text.replace('HUD_TEXT_CHAT_COMMANDER', '')
        text = text.replace('HUD_TEXT_CHAT_TEAM', '')
        text = text.replace('HUD_TEXT_CHAT_SQUAD', '')
        text = text.replace('HUD_CHAT_DEADPREFIX', '')
        text = text.replace('\xc2\xa73', '')
        text = text.replace('\xc2\xa7C1001', '')
        text = text.replace('\xc2\xa7c1001', '')
        try:
            playerName = flags['name']
        except:
            playerName = ''

        if player:
            playerName = player.getName()
        chatBuffer += '%s\x03%s\x03%s\x03%s\x03%s\n' % (str(_type),
         str(time.time()),
         friendlyChannel,
         playerName,
         text)
    except:
        pass

    return


def onPlayerSpawn(p, vehicle):
    global serverStatus
    serverStatus = '0'
    p.joining = False
    p.epochJoinTime = str(time.time())


def onPlayerKilled(victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject):
    global killBuffer
    if not victimPlayerObject or not attackerPlayerObject:
        return
    teamkill = '0\x03'
    weapon = '\x03Killed\n'
    if victimPlayerObject.getTeam() == attackerPlayerObject.getTeam():
        teamkill = '1\x03'
    try:
        weapon = '\x03' + weaponObject.templateName + '\n'
    except:
        pass

    killBuffer += teamkill + str(time.time()) + '\x03' + attackerPlayerObject.getName() + '\x03' + victimPlayerObject.getName() + weapon


def onVehicleDestroyed(vehicle, attacker):
    serverMapCache['updateSent'] = False


def onPlayerConnect(p):
    playerIPs.append(p.getAddress())
    CheckRemoteUserOnServer()


def onPlayerDisconnect(p):
    PlayerLeft(p)


def PlayerLeft(p):
    if p.getName() in cachedUsers:
        del cachedUsers[p.getName()]
    for _id in auth_users:
        if auth_users[_id].isReadyPlayers():
            auth_users[_id].writeBack('playerleave', p.getName())

    try:
        playerIPs.remove(p.getAddress())
        CheckRemoteUserOnServer()
    except:
        pass


def onAdminModuleCommand(subject, args):
    global serverRoundWarmup
    global serverDebugMode
    global serverRoundLength
    global serverLayer
    try:
        if subject == 'msg':
            channel = args[0]
            text = ' '.join(args[1:-1])
            playerName = args[-1].replace(',', ' ')
            onRconChatMessage(-1, text, channel, {'name': playerName})
        elif subject == 'adminResponse':
            cmd = args[0]
            result = args[1]
            adminName = args[2]
            if result:
                sub = 'success'
                cmd = 'Success\x03El comando "' + cmd + '" se completo exitosamente!'
            else:
                sub = 'error'
                cmd = 'Error\x03El comando "' + cmd + '" NO se completo exitosamente.'
            SendToRconAdmin(adminName, sub, cmd)
        elif subject == 'roundStart':
            serverLayer = args[0]
            serverMapCache['mapReady'] = True
        elif subject == 'serverSettings':
            serverRoundWarmup = args[0]
            serverRoundLength = args[1]
        elif subject == 'reload':
            import realityconfig_admin as rasreload
            realityconfig_admin.rcon_welcome = rasreload.rcon_welcome
            realityconfig_admin.rcon_commandPowerLevels = rasreload.rcon_commandPowerLevels
            readUsers()
        elif subject == 'debugOn':
            serverDebugMode = True
            CheckRemoteUserOnServer()
        elif subject == 'debugOff':
            serverDebugMode = False
            CheckRemoteUserOnServer()
    except:
        rdebug.errorMessage()


def rallyCreated(team, squad, position):
    serverRallyCache[str(team) + str(squad)] = str(position) + ':' + str(team) + ':' + str(squad) + '\n'


def rallyDeleted(team, squad):
    serverRallyCache.pop(str(team) + str(squad), None)
    return


def readUsers():
    global users
    try:
        users = {}
        userFile = open(userFileName, 'r')
        lines = userFile.readlines()
        userFile.close()
        for line in lines:
            user = line[:-1].split('\x01')
            users[user[0].lower()] = [user[0],
             user[1],
             user[2],
             user[3]]

        for un in hardcoded_users:
            if un == 'superuser':
                continue
            users[un.lower()] = [un,
             hardcoded_users[un][0],
             hardcoded_users[un][1],
             hardcoded_users[un][2]]

        if len(users) == 0:
            raise Exception('No users found')
    except Exception as e:
        suFile = open(suFileName, 'w')
        salt = generateSalt(8)
        pw = generateSalt(8)
        suFile.write('Username: superuser\r\nPassword: ' + str(pw))
        suFile.close()
        pw = hashlib.sha1(salt + '\x01' + hashlib.sha1(pw).hexdigest()).hexdigest()
        users['superuser'] = ['superuser',
         pw,
         salt,
         0]


def writeUsers():
    currentUser = ''
    userFile = open(userFileName, 'w')
    for name, details in users.iteritems():
        currentUser = name
        if name in hardcoded_users or details[0] == '':
            continue
        line = str(details[0]) + '\x01' + str(details[1]) + '\x01' + str(details[2]) + '\x01' + str(details[3]) + '\n'
        userFile.write(line)

    userFile.close()


def handleRconCommand(client, content, error):
    try:
        clientId = str(client.addr[0]) + ':' + str(client.addr[1])
        authenticated = False
        if error:
            try:
                logout(auth_users[clientId])
                del auth_users[clientId]
            except:
                pass

        try:
            content = content[content.find('\x01') + 1:]
            split = content.split('\x02')
            sub = split[0]
            msg = split[1].split('\x03')
        except:
            return

        try:
            authenticated = auth_users[clientId].isAuthenticated()
        except:
            auth_users[clientId] = AdminObject(client, clientId)

        if not authenticated:
            login(auth_users[clientId], sub, msg)
            return
        for index in range(0, len(msg)):
            msg[index] = ''.join((c for c in msg[index] if ord(c) <= 126 and ord(c) >= 32 or c == '\n'))

        executeSuccess = None
        if sub in rconCommands.keys():
            executeSuccess = executeRcon(auth_users[clientId], sub, msg)
        elif sub in realityadmin.g_adminCommands.keys():
            executeSuccess = executeRACommand(auth_users[clientId], sub, msg)
        if not executeSuccess:
            pass
    except:
        rdebug.errorMessage()

    return


def login(client, subject, msg):
    if subject == 'login1':
        clientVersion = int(msg[0])
        username = msg[1].lower()
        client.clientChallenge = msg[2]
        if username not in users:
            client.writeBack('errorcritical', '3001\x03Invalid username or password', True)
        elif clientVersion != SERVER_VERSION:
            client.writeBack('errorcritical', '3007\x03Client version does not match the server version. (Server Version: %d)' % SERVER_VERSION, True)
        else:
            client.adminName = msg[1]
            client.writeBack('login1', users[username][2] + '\x03' + client.getServerChallenge())
    elif subject == 'login2':
        _hash = hashlib.sha1(client.adminName + '\x03' + client.clientChallenge + '\x03' + client.getServerChallenge() + '\x03' + users[client.adminName.lower()][1]).hexdigest()
        if msg[0] == _hash:
            client.authenticated = True
            client.power = int(users[client.adminName.lower()][3])
            client.writeBack('connected', getWelcomeString(client))
            CheckRemoteUserOnServer(client)
            UpdateRAAdmins(client, True)
            client.writeBack('raconfig', getRAConfig(client))
            bigUpdate()
        else:
            client.writeBack('errorcritical', '3001\x03Invalid username or password', True)
    else:
        client.writeBack('error', '3000\x03Sorry, you are not authenticated.')
        return


def logout(client):
    UpdateRAAdmins(client, False)


def getWelcomeString(client):
    t = time.localtime()
    timezone = time.timezone
    if t.tm_isdst == 1:
        timezone = time.altzone
    tz = ('%+06.2f' % (-float(timezone) / 3600)).replace('.', ':')
    serverTime = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + tz
    return '%s\x03%s\x03%s' % (str(client.power), serverTime, realityconfig_admin.rcon_welcome)


def getRAConfig(user = None):
    commands = ''
    for cmd, level in realityconfig_admin.adm_adminPowerLevels.iteritems():
        commands += str(cmd) + ':' + str(level) + '\n'

    for cmd, level in realityconfig_admin.rcon_commandPowerLevels.iteritems():
        if user and user.restricted:
            if cmd == 'mapplayers' or cmd == 'mapgameplay':
                commands += str(cmd) + ':-1\n'
                continue
        commands += str(cmd) + ':' + str(level) + '\n'

    reasons = ''
    for cmd in realityconfig_admin.adm_reasons:
        reasons += realityconfig_admin.adm_reasons[cmd].replace('\n', ' ') + '\n'

    return commands[:-1] + '\x03' + reasons[:-1] + '\x03' + str(realityconfig_admin.adm_banTime)


def generateSalt(length = 20):
    ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    chars = []
    for i in range(length):
        chars.append(rcore.random.choice(ALPHABET))

    return ''.join(chars)


def executeRcon(adminUser, subject, message):
    if adminUser.power > realityconfig_admin.rcon_commandPowerLevels.get(subject, 0):
        onRconChatMessage(-1, 'Permisos insuficientes.', 5, None)
        return
    else:
        rconCommands[subject](adminUser, message)
        return


def executeRACommand(adminUser, subject, message):
    sayMessageIndex = len(message) - 1
    try:
        if message[sayMessageIndex][0] == realityconfig_admin.adm_commandSymbol and subject in ('say', 'sayteam'):
            split = message[sayMessageIndex].split(' ')
            command = split[0][1:]
            if command in realityconfig_admin.adm_commandAliases:
                command = realityconfig_admin.adm_commandAliases[command]
            if command in realityadmin.g_adminCommands.keys():
                subject = command
                if len(split) > 1:
                    message = split[1:]
                else:
                    message = ['']
        if adminUser.power > realityconfig_admin.adm_adminPowerLevels.get(subject, 0):
            onRconChatMessage(-1, 'Insufficient Permissions', 5, None)
            return
    except:
        onRconChatMessage(-1, 'Error: Bad command', 5, None)
        return

    realityadmin.onPrismAdminCommand(subject.rstrip(), adminUser.getName(), message)
    return


def UpdateRAAdmins(client, connecting):
    if client and client.adminName:
        if connecting:
            realityadmin.prismAdminConnected(client.adminName)
        else:
            realityadmin.prismAdminDisconnected(client.adminName)


def ListRCONUsers(adminUser, args = None):
    output = ''
    for name, details in users.iteritems():
        if name in map(str.lower, hardcoded_users):
            continue
        output += str(details[0]) + '\x03' + str(details[3]) + '\n'

    adminUser.writeBack('getusers', output[:-1])
    return True


def AddRCONUser(adminUser, args, _update = True):
    if args[0].lower() in users.keys() or args[0].lower() in map(str.lower, hardcoded_users):
        adminUser.writeBack('error', '3003\x03El usuario ' + str(args[0]) + ' ya existe.')
        return False
    salt = generateSalt(8)
    pw = hashlib.sha1(salt + '\x01' + args[1]).hexdigest()
    users[args[0].lower()] = [args[0],
     pw,
     salt,
     args[2]]
    if _update:
        writeUsers()
        return ListRCONUsers(adminUser)
    return True


def ChangeRCONUser(adminUser, args):
    if args[0] != args[1]:
        if not AddRCONUser(adminUser, [args[1], args[2], args[3]], False):
            return False
        del users[args[0].lower()]
    else:
        if args[2]:
            salt = generateSalt(8)
            pw = hashlib.sha1(salt + '\x01' + args[2]).hexdigest()
        else:
            pw = users[args[0].lower()][0]
            salt = users[args[0].lower()][1]
        users[args[0].lower()] = [args[0],
         pw,
         salt,
         args[3]]
    writeUsers()
    return ListRCONUsers(adminUser)


def DeleteRCONUser(adminUser, args):
    if args[0] == adminUser.adminName:
        adminUser.writeBack('error', '3004\x03You cannot remove your own account. Delete Bf2Root/' + userFileName + ' to wipe all accounts.')
        return False
    if adminUser.adminName == 'superuser' and len(users) <= 2:
        adminUser.writeBack('error', '3005\x03You cannot remove the last non-superuser account.')
        return False
    try:
        del users[args[0].lower()]
    except:
        adminUser.writeBack('error', '3006\x03This user was already deleted.')
        return False

    writeUsers()
    return ListRCONUsers(adminUser)


def ListServerDetails(adminUser, args, always_send = False):
    if adminUser.readyServer and not always_send:
        return
    message = GetServerHeader() + GetServerDetails(True)
    adminUser.writeBack('serverdetails', message)
    adminUser.readyServer = True


def ListServerDetailsAlways(adminUser, args):
    ListServerDetails(adminUser, args, always_send=True)


def ListMapDetails(adminUser, args):
    if adminUser.readyMap or adminUser.power > realityconfig_admin.rcon_commandPowerLevels['mapgameplay']:
        return
    message = GetMapDetails(True)
    if not message:
        message = '\x03\x03\x03\x03'
    adminUser.writeBack('gameplaydetails', message)
    adminUser.readyMap = True


def ListPlayers(adminUser, args):
    messageString = ''
    messageStringNoPos = ''
    for p in bf2.playerManager.getPlayers():
        if p.getName() not in cachedUsers:
            cachedUsers[p.getName()] = CachedPlayer()
        cacheOutput = cachedUsers[p.getName()].getAllValues(p)
        messageString += GetPlayerHeader(p) + cacheOutput[0]
        messageStringNoPos += GetPlayerHeader(p) + cacheOutput[1]

    if adminUser.power > realityconfig_admin.rcon_commandPowerLevels['mapplayers'] or adminUser.restricted:
        adminUser.writeBack('listplayers', messageStringNoPos)
    else:
        adminUser.writeBack('listplayers', messageString)
    adminUser.readyPlayers = True


def CheckRemoteUserOnServer(adminUser = None):
    if int(host.rcon_invoke('sv.internet').strip()) == 0:
        return
    if not adminUser:
        for userId in auth_users:
            CheckRemoteUserOnServer(auth_users[userId])

    else:
        oldStatus = adminUser.restricted
        if adminUser.ipAddress[:adminUser.ipAddress.find(':')] in playerIPs and not serverDebugMode:
            adminUser.restricted = False
            #for p in bf2.playerManager.getPlayers():
                #if p.getName() == "Chaziz":
                    #adminUser.restricted = False
        else:
            adminUser.restricted = False
        if oldStatus != adminUser.restricted:
            adminUser.writeBack('raconfig', getRAConfig(adminUser))


def ReadMapList(adminUser, args):
    maplistStr = GetServerProperty('admin.currentlevel') + '\x03' + GetServerProperty('admin.nextlevel') + '\x03' + GetServerProperty('maplist.list', '\n')
    adminUser.writeBack('maplist', maplistStr)


def ReadBanList(adminUser, args):
    pass


def RunAdminCommand(adminUser, args):
    if len(args) != 1:
        adminUser.writeBack('error', '4000\x03Admin Command syntax error')
        return
    for char in args[0]:
        if ord(char) < 32 or ord(char) > 127:
            adminUser.writeBack('error', '4000\x03Admin Command syntax error')
            return

    result = host.rcon_invoke('admin.%s' % args[0]).strip()
    adminUser.writeBack('APIAdminResult', result)


def SendToRconAdmin(adminUser, subject, message):
    for _id in auth_users:
        if auth_users[_id].adminName == adminUser or auth_users[_id].getName() == adminUser:
            auth_users[_id].writeBack(subject, message)
            break


class AdminObject(object):
    index = -1
    adminName = ''
    ipAddress = ''
    power = 777
    clientChallenge = ''
    serverChallenge = None
    authenticated = False
    restricted = False
    readyMap = False
    readyServer = False
    readyPlayers = False
    connection = None

    def __init__(self, conn, address):
        self.connection = conn
        self.ipAddress = address

    def getName(self):
        return 'PRISM admin ' + self.adminName

    def getTeam(self):
        return 1

    def isValid(self):
        return True

    def isAuthenticated(self):
        return self.authenticated

    def getServerChallenge(self):
        if self.serverChallenge is None:
            self.serverChallenge = generateSalt()
        return self.serverChallenge

    def isReadyMap(self):
        return self.readyMap

    def isReadyServer(self):
        return self.readyServer

    def isReadyPlayers(self):
        return self.readyPlayers

    def writeBack(self, subject, message, closing = False):
        if not self.authenticated and subject not in ('error', 'login1', 'login2'):
            return
        self.connection.writeBack('\x01%s\x02%s' % (subject, message), closing)


class CachedPlayer(object):
    updatePositionsGreaterThan = 1
    team = None
    squad = None
    kit = None
    vehicle = None
    score = None
    scoreTW = None
    kills = None
    teamkills = None
    deaths = None
    valid = None
    ping = None
    position = None
    positionOld = None
    rotation = None
    bulletsFired = None
    idle = None
    idleOld = None
    alive = None
    joining = None

    def __init__(self):
        pass

    def getAllValues(self, p):
        global prismIndexCounter
        output = ''
        try:
            if p.joining == '':
                return
        except:
            p.joining = True

        team = p.getTeam()
        output += str(team)
        output += '\x03'
        squadID = str(p.getSquadId())
        if squadID != '0':
            if p.isSquadLeader():
                squadID += 'L'
        elif p.isCommander():
            squadID = 'C'
        output += str(squadID)
        output += '\x03'
        try:
            kit = p.getKit().templateName
        except:
            kit = 'None'

        output += str(kit)
        output += '\x03'
        veh = p.getVehicle()
        try:
            if rcore.isSoldier(veh) and rcore.isSoldier(veh.getParent()):
                vehicle = '-1:None'
            else:
                rootVeh = bf2.objectManager.getRootParent(veh)
                if not hasattr(rootVeh, 'prismIndex'):
                    rootVeh.prismIndex = prismIndexCounter
                    prismIndexCounter += 1
                if rcore.isSoldier(veh) and not rcore.isSoldier(veh.getParent()):
                    vehicle = str(rootVeh.prismIndex) + ':' + veh.getParent().templateName
                else:
                    vehicle = str(rootVeh.prismIndex) + ':' + veh.templateName
        except Exception as e:
            vehicle = '-1:Invalid' + str(e).replace(' ', '_')

        output += str(self.vehicle)
        output += '\x03'
        try:
            score = p.score.score
            scoreTW = p.score.rplScore
            kills = p.score.kills
            teamkills = p.score.TKs
            deaths = p.score.deaths
            valid = 1
        except:
            score = 0
            scoreTW = 0
            kills = 0
            teamkills = 0
            deaths = 0
            bulletsFired = 0
            valid = 0

        output += str(score)
        output += '\x03'
        output += str(scoreTW)
        output += '\x03'
        output += str(kills)
        output += '\x03'
        output += str(teamkills)
        output += '\x03'
        output += str(deaths)
        output += '\x03'
        if p.joining:
            output += str(1)
        else:
            output += str(valid)
        output += '\x03'
        output += str(p.getPing())
        output += '\x03'
        if not self.idle or p.joining:
            self.idle = 0
        output += str(self.idle)
        output += '\x03'
        if p.isAlive() and not p.isManDown() and not p.joining:
            alive = True
        else:
            alive = False
        output += str(int(alive))
        output += '\x03'
        output += str(int(p.joining))
        output += '\x03'
        try:
            pos = p.getDefaultVehicle().getPosition()
        except:
            pos = ''

        try:
            rot = +int(p.getVehicle().getRotation()[0])
        except:
            rot = 0

        return (output + str(pos) + '\x03' + str(rot) + '\n', output + '\x03\n')

    def getChangedValues(self, p):
        global prismIndexCounter
        output = ''
        team = p.getTeam()
        if self.team != team:
            self.team = team
        output += str(self.team)
        output += '\x03'
        squadID = str(p.getSquadId())
        if squadID != '0':
            if p.isSquadLeader():
                squadID += 'L'
        elif p.isCommander():
            squadID = 'C'
        if self.squad != squadID:
            self.squad = squadID
            output += str(squadID)
        output += '\x03'
        try:
            kit = p.getKit().templateName
        except:
            kit = 'None'

        if self.kit != kit:
            self.kit = kit
            output += self.kit
        output += '\x03'
        veh = p.getVehicle()
        try:
            if rcore.isSoldier(veh) and rcore.isSoldier(veh.getParent()):
                vehicle = '-1:None'
            else:
                rootVeh = bf2.objectManager.getRootParent(veh)
                if not hasattr(rootVeh, 'prismIndex'):
                    rootVeh.prismIndex = prismIndexCounter
                    prismIndexCounter += 1
                if rcore.isSoldier(veh) and not rcore.isSoldier(veh.getParent()):
                    vehicle = str(rootVeh.prismIndex) + ':' + veh.getParent().templateName
                else:
                    vehicle = str(rootVeh.prismIndex) + ':' + veh.templateName
        except Exception as e:
            vehicle = '-1:Invalid' + str(e).replace(' ', '_')

        if self.vehicle != vehicle:
            self.vehicle = vehicle
        output += vehicle
        output += '\x03'
        try:
            score = p.score.score
            scoreTW = p.score.rplScore
            kills = p.score.kills
            teamkills = p.score.TKs
            deaths = p.score.deaths
            valid = 1
        except Exception as e:
            score = 0
            scoreTW = 0
            kills = 0
            teamkills = 0
            deaths = 0
            bulletsFired = 0
            valid = 0

        if self.score != score:
            self.score = score
            output += str(score)
        output += '\x03'
        if self.scoreTW != scoreTW:
            self.scoreTW = scoreTW
            output += str(scoreTW)
        output += '\x03'
        if self.kills != kills:
            self.kills = kills
            output += str(kills)
        output += '\x03'
        if self.teamkills != teamkills:
            self.teamkills = teamkills
            output += str(teamkills)
        output += '\x03'
        if self.deaths != deaths:
            self.deaths = deaths
            output += str(deaths)
        output += '\x03'
        if self.valid != valid:
            self.valid = valid
            if self.joining:
                output += str(1)
            else:
                output += str(valid)
        output += '\x03'
        if self.ping != p.getPing():
            self.ping = p.getPing()
            output += str(self.ping)
        output += '\x03'
        if not self.idle:
            self.idle = 0
        self.idle += 1
        if self.position != self.positionOld:
            self.idle = 0
            self.positionOld = p.getVehicle().getPosition()
        elif self.rotation != p.getVehicle().getRotation():
            self.idle = 0
            self.rotation = p.getVehicle().getRotation()
        elif self.joining:
            self.idle = 0
        elif p.isManDown():
            self.idle = 0
        if self.idle % 30 == 0 and self.idle != self.idleOld:
            self.idleOld = self.idle
            output += str(self.idle)
        output += '\x03'
        if p.isAlive() and not p.isManDown() and not self.joining:
            alive = True
        else:
            alive = False
        if self.alive != alive:
            self.alive = alive
            output += str(int(self.alive))
        output += '\x03'
        try:
            if self.joining != p.joining:
                self.joining = p.joining
                output += str(int(self.joining))
            output += '\x03'
        except:
            return False

        posString = '\x03'
        try:
            pos = p.getDefaultVehicle().getPosition()
            if not self.position:
                self.position = pos
            if self.position[0] != int(pos[0]) or self.position[2] != int(pos[2]):
                self.position = (int(pos[0]), int(pos[1]), int(pos[2]))
                posString = str(self.position) + '\x03' + str(int(p.getVehicle().getRotation()[0]))
        except:
            pass

        if output == '\x03\x03\x03\x03\x03\x03\x03\x03\x03\x03\x03\x03\x03\x03' and posString == '\x03':
            return False
        else:
            return (output + posString + '\n', output + '\x03\n')


global isReady ## Warning: Unused global