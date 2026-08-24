import bf2
import host
import realitydebug as rdebug
import realitylogger as rlogger
import realitymemory as rmemory
import realityserver
import realityadmin
import realitytimer as rtimer
g_gameState = bf2.GameStatus.Init
g_playing_count = 0
statusEvents = []
events = {'ControlPointChangedOwner': (2, []),
 'PlayerTeamDamagePoint': (2, []),
 'PlayerUnlocksResponse': (3, []),
 'PlayerStatsResponse': (3, []),
 'PlayerGiveAmmoPoint': (2, []),
 'DeployGrapplingHook': (1, []),
 'TicketLimitReached': (2, []),
 'ConsoleSendCommand': (2, []),
 'ChangedSquadLeader': (3, []),
 'PlayerChangedSquad': (3, []),
 'PlayerChangeWeapon': (3, []),
 'PlayerRepairPoint': (2, []),
 'PlayerChangeTeams': (2, []),
 'ChangedCommander': (3, []),
 'PlayerDisconnect': (1, []),
 'TimeLimitReached': (1, []),
 'VehicleDestroyed': (2, []),
 'PlayerHealPoint': (2, []),
 'DeployTactical': (1, []),
 'PlayerRevived': (2, []),
 'PlayerConnect': (1, []),
 'DeployZipLine': (1, []),
 'RemoteCommand': (2, []),
 'ClientCommand': (3, []),
 'EnterVehicle': (3, []),
 'PlayerKilled': (5, []),
 'PlayerBanned': (3, []),
 'PlayerKicked': (1, []),
 'ExitVehicle': (2, []),
 'PlayerSpawn': (2, []),
 'PlayerDeath': (2, []),
 'PlayerScore': (2, []),
 'ChatMessage': (4, []),
 'PickupKit': (2, []),
 'DropKit': (2, []),
 'Reset': (1, []),
 'AttackRequest': (1, []),
 'ExtractRequest': (2, []),
 'MineRequest': (1, []),
 'SupplyRequest': (1, []),
 'AmmoRequest': (1, []),
 'MedicRequest': (1, []),
 'RepairRequest': (1, []),
 'FireRequest': (1, []),
 'MutinyRequest': (1, []),
 'SupportRequest': (2, []),
 'StatusRequest': (2, []),
 'PositionMarked': (4, []),
 'PickupFirstKit': (2, []),
 'DropFirstKit': (2, []),
 'PickupRevivedKit': (2, []),
 'DropRevivedKit': (2, []),
 'PlayerSuicided': (2, []),
 'PlayerKilledFiltered': (5, []),
 'PlayerTeamKilled': (5, []),
 'PlayerEnemyKilled': (5, []),
 'VehicleSpawned': (1, []),
 'VehicleDestroyedFiltered': (2, []),
 'TeamVehicleDestroyed': (2, []),
 'EnemyVehicleDestroyed': (2, []),
 'ChatMessageFiltered': (4, []),
 'TicketsChanged': (3, []),
 'RoundStart': (0, []),
 'RoundEnd': (1, []),
 'ControlPointNeutralized': (3, []),
 'ControlPointCaptured': (3, []),
 'PositionDefended': (2, []),
 'AssetDeployed': (2, []),
 'AssetDefended': (2, []),
 'EnterControlPoint': (2, []),
 'ExitControlPoint': (2, []),
 'PositionsUpdated': (1, []),
 'PlayerForgave': (1, []),
 'PlayerPunished': (1, []),
 'SquadCreated': (4, []),
 'SquadRemoved': (2, []),
 'KitAllocated': (2, []),
 'RallyCreated': (3, []),
 'RallyDelete': (2, []),
 'InsurgencyCacheAdded': (1, []),
 'InsurgencyCacheRevealed': (1, []),
 'InsurgencyCacheDestroyed': (1, []),
 'InsurgencyIntelChanged': (1, []),
 'AssetCreated': (3, []),
 'AssetRemoved': (3, []),
 'PlayerVerified': (1, []),
 'MineCreated': (1, []),
 'RocketCreated': (1, []),
 'MarkerCreated': (1, []),
 'MarkerRemoved': (1, []),
 'FobEnabled': (2, []),
 'FobDisabled': (2, []),
 'RemoteCommandFcs': (3, []),
 'RemoteCommandKitRequest': (3, []),
 'RemoteCommandAssetRequest': (3, []),
 'RemoteCommandRallyRequest': (3, []),
 'RemoteCommandGiveUp': (3, []),
 'RemoteCommandDone': (3, []),
 'RemoteCommandHealth': (3, []),
 'RemoteCommandSize': (3, []),
 'RemoteCommandTemplate': (3, []),
 'RemoteCommandDebug': (3, []),
 'RemoteCommandDestroyables': (3, []),
 'RemoteCommandShovelman': (3, []),
 'RemoteCommandFastCap': (3, []),
 'RemoteCommandDistance': (3, []),
 'RemoteCommandRequestMark': (3, []),
 'RemoteCommandSpottedMark': (3, []),
 'RemoteCommandCheat': (3, []),
 'RemoteCommandClosest': (3, []),
 'RemoteCommandCamera': (3, []),
 'RemoteCommandNinja': (3, []),
 'RemoteCommandKits': (3, []),
 'RemoteCommandOneFaction': (3, []),
 'RemoteCommandDrop': (3, []),
 'RemoteCommandSelectKit': (3, []),
 'RemoteCommandCustomKit': (3, []),
 'RemoteCommandInitKit': (3, []),
 'RemoteCommandLocalization': (3, []),
 'RemoteCommandProfiler': (3, []),
 'RemoteCommandPoints': (3, []),
 'RemoteCommandModded': (3, []),
 'RemoteCommandShutdown': (3, []),
 'RemoteCommandServer': (3, []),
 'RemoteCommandSpawner': (3, []),
 'RemoteCommandVehicles': (3, []),
 'RemoteCommandSpectator': (3, []),
 'RemoteCommandGameplayMark': (3, []),
 'RemoteCommandGameplayRequest': (3, []),
 'RemoteCommandLase': (3, []),
 'RemoteCommandHeartBeat': (3, []),
 'RemoteCommandPosition': (3, []),
 'RemoteCommandPreRoundCamera': (3, []),
 'RemoteCommandIDKFA': (3, []),
 'RemoteCommandRef': (3, []),
 'RemoteCommandStamina': (3, []),
 'RemoteCommandDrag': (3, []),
 'RemoteCommandPhysics': (3, []),
 'RemoteCommandTutorial': (3, []),
 'RemoteCommandMissile': (3, []),
 'RemoteCommandACSYSToggle': (3, []),
 'RemoteCommandVote': (3, []),
 'RemoteCommandHideCurrentAWD': (3, []),
 'RemoteCommandTransferSL': (3, []),
 'RemoteCommandCheckChat': (3, []),
 'RemoteCommandPlayerActive': (3, []),
 'LocalConsoleCommand': (1, [])}

def init(debugger = False):
    global _realitymemory
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('ControlPointChangedOwner', onControlPointChangedOwner, 1)
    host.registerHandler('PlayerTeamDamagePoint', onPlayerTeamDamagePoint, 1)
    host.registerHandler('PlayerUnlocksResponse', onPlayerUnlocksResponse, 1)
    host.registerHandler('PlayerStatsResponse', onPlayerStatsResponse, 1)
    host.registerHandler('PlayerGiveAmmoPoint', onPlayerGiveAmmoPoint, 1)
    host.registerHandler('DeployGrapplingHook', onDeployGrapplingHook, 1)
    host.registerHandler('TicketLimitReached', onTicketLimitReached, 1)
    host.registerHandler('ConsoleSendCommand', onConsoleSendCommand, 1)
    host.registerHandler('ChangedSquadLeader', onChangedSquadLeader, 1)
    host.registerHandler('PlayerChangedSquad', onPlayerChangedSquad, 1)
    host.registerHandler('PlayerChangeWeapon', onPlayerChangeWeapon, 1)
    host.registerHandler('PlayerRepairPoint', onPlayerRepairPoint, 1)
    host.registerHandler('PlayerChangeTeams', onPlayerChangeTeams, 1)
    host.registerHandler('ChangedCommander', onChangedCommander, 1)
    host.registerHandler('PlayerDisconnect', onPlayerDisconnect, 1)
    host.registerHandler('TimeLimitReached', onTimeLimitReached, 1)
    host.registerHandler('VehicleDestroyed', onVehicleDestroyed, 1)
    host.registerHandler('PlayerHealPoint', onPlayerHealPoint, 1)
    host.registerHandler('DeployTactical', onDeployTactical, 1)
    host.registerHandler('PlayerRevived', onPlayerRevived, 1)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    host.registerHandler('DeployZipLine', onDeployZipLine, 1)
    host.registerHandler('RemoteCommand', onRemoteCommand, 1)
    host.registerHandler('ClientCommand', onClientCommand, 1)
    host.registerHandler('EnterVehicle', onEnterVehicle, 1)
    host.registerHandler('PlayerKilled', onPlayerKilled, 1)
    host.registerHandler('PlayerBanned', onPlayerBanned, 1)
    host.registerHandler('PlayerKicked', onPlayerKicked, 1)
    host.registerHandler('ExitVehicle', onExitVehicle, 1)
    host.registerHandler('PlayerSpawn', onPlayerSpawn, 1)
    host.registerHandler('PlayerDeath', onPlayerDeath, 1)
    host.registerHandler('PlayerScore', onPlayerScore, 1)
    host.registerHandler('ChatMessage', onChatMessage, 1)
    host.registerHandler('PickupKit', onPickupKit, 1)
    host.registerHandler('DropKit', onDropKit, 1)
    host.registerHandler('Reset', onReset, 1)
    host.registerHandler('PickupKit', onCustomPickupKit, 1)
    host.registerHandler('PickupKit', onRevivedPickupKit, 1)
    host.registerHandler('DropKit', onCustomDropKit, 1)
    host.registerHandler('DropKit', onRevivedDropKit, 1)
    host.registerHandler('RemoteCommand', onFilteredRemoteCommand, 1)
    host.registerHandler('ClientCommand', onPunishmentCommand, 1)
    host.registerHandler('ChatMessage', onFilteredChatMessage, 1)
    host.registerHandler('VehicleDestroyed', onVehicleSpawned, 1)
    host.registerHandler = newRegisterHandler
    host.unregisterHandler = unregisterHandler
    host.registerGameStatusHandler = newRegisterGameStatusHandler
    host.unregisterGameStatusHandler = newUnregisterGameStatusHandler
    if not rmemory.isWindowsListenServer:
        import _realitymemory
        _realitymemory.initializeProjectileCreatedHook(preProjectileCreated)
        _realitymemory.initializeObjectSpawnerHook(onObjectSpawned)


def newRegisterHandler(event, function, optional = 0):
    global events
    if event not in events:
        if rdebug.isDebugEnabled():
            rdebug.debugMessage('events: ERROR! ' + event + ' event does not exist')
        return
    for handler in events[event][1]:
        if handler[0] == function:
            if rdebug.isDebugEnabled('events'):
                rdebug.debugMessage('already registered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')
            return

    handler = (function, optional)
    events[event][1].append(handler)
    if rdebug.isDebugEnabled('events'):
        rdebug.debugMessage('registered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')


def unregisterHandler(function):
    for event in events.items():
        for handler in event[1][1]:
            if handler[0] == function:
                try:
                    event[1][1].remove(handler)
                    if rdebug.isDebugEnabled('events'):
                        rdebug.debugMessage('unregistered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')
                    return
                except:
                    rdebug.errorMessage()

    if rdebug.isDebugEnabled():
        rdebug.debugMessage('events: ERROR! Unregister ' + function.func_name + ' does not exist')


def newRegisterGameStatusHandler(function):
    global statusEvents
    if function.func_code.co_argcount != 1 and function.__class__ == init.__class__:
        if rdebug.isDebugEnabled():
            rdebug.debugMessage('events: ERROR! ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename) + ' wrong # of args')
        return
    if function in statusEvents:
        if rdebug.isDebugEnabled('events'):
            rdebug.debugMessage('already registered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')
        return
    statusEvents.append(function)
    if rdebug.isDebugEnabled('events'):
        rdebug.debugMessage('registered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')


def newUnregisterGameStatusHandler(function):
    if function in statusEvents:
        statusEvents.remove(function)
        if rdebug.isDebugEnabled('events'):
            rdebug.debugMessage('unregistered ' + function.func_name + ' in ' + getFileName(function.func_code.co_filename), 'events')
        return
    if rdebug.isDebugEnabled():
        rdebug.debugMessage('events: ERROR! Unregister ' + function.func_name + ' does not exist')


g_onplaying_objectspawners = tuple()

def sendGameStatusChanged(status):
    global g_onplaying_objectspawners
    if status == bf2.GameStatus.Playing:
        g_onplaying_objectspawners = bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.ObjectSpawner')
    for function in statusEvents:
        try:
            function(status)
        except:
            rdebug.errorMessage()


def getOnPlayingObjectSpawners():
    return g_onplaying_objectspawners


def getFileName(path):
    s = '\\'
    if path.count(s) == 0:
        s = '/'
    arr = path.split(s)
    return str(arr.pop())


def sendToHandlers(event, *args):
    global g_gameState
    profiler = bool(rdebug.isDebugEnabled('profiler'))
    total = 0.0
    for function in event[1]:
        if g_gameState in [bf2.GameStatus.Loading, bf2.GameStatus.EndGame] and function[1] != 1:
            continue
        try:
            if profiler:
                start = rdebug.clockFunc()
                function[0](*args)
                time = rdebug.clockFunc() - start
                total += time
                rlogger.RealityLogger['profiler'].logLine('%s.%s\t%s' % (function[0].__module__, function[0].__name__, '{0:.7f}'.format(time * 1000)))
            else:
                function[0](*args)
        except:
            rdebug.errorMessage()

    if profiler:
        rlogger.RealityLogger['profiler'].logLine('Event total:\t%s' % '{0:.7f}'.format(total * 1000))


PLAYING = 1
ENDGAME = 2
PREGAME = 3

def onGameStatusChanged(status):
    global g_gameState
    global g_playing_count
    if g_gameState == bf2.GameStatus.Init:
        if status == PLAYING:
            g_gameState = bf2.GameStatus.Loaded
            sendGameStatusChanged(g_gameState)
        else:
            g_gameState = bf2.GameStatus.Loading
            sendGameStatusChanged(g_gameState)
    elif g_gameState == bf2.GameStatus.Loading:
        if status == PLAYING:
            g_gameState = bf2.GameStatus.Loaded
            sendGameStatusChanged(g_gameState)
    elif g_gameState == bf2.GameStatus.Loaded:
        if status == PLAYING:
            if bf2.gameLogic.isAIGame():
                g_playing_count += 1
            if g_playing_count % 2 == 0:
                g_gameState = bf2.GameStatus.Playing
                sendGameStatusChanged(g_gameState)
                rtimer.fireOnce(briefingEnd, realityserver.C('STARTDELAY'))
                g_playing_count = 0
        elif status == ENDGAME:
            g_gameState = bf2.GameStatus.EndGame
            sendGameStatusChanged(g_gameState)
    elif g_gameState == bf2.GameStatus.Playing:
        if status == ENDGAME:
            g_gameState = bf2.GameStatus.EndGame
            sendGameStatusChanged(g_gameState)
    elif g_gameState == bf2.GameStatus.EndGame:
        if status == PREGAME:
            g_gameState = bf2.GameStatus.Loading
            sendGameStatusChanged(g_gameState)


def briefingEnd(args):
    event = getEvents('RoundStart')
    sendToHandlers(event)


def getEvents(name):
    try:
        return events[name]
    except:
        rdebug.debugMessage('Unknown event %s' % name)


def requestSpamBlocker(player):
    if not player or not player.isValid():
        return
    times = int(host.timer_getWallTime())
    reset = False
    if not player.lastRequest:
        reset = True
    elif player.canRequest == 1 and times - player.lastRequest > realityserver.C('SPAM_INTERVAL'):
        reset = True
    elif player.canRequest == 0 and times - player.lastRequest > realityserver.C('SPAM_PENALTY'):
        reset = True
    if reset:
        player.lastRequest = times
        player.requestCounter = 0
        player.canRequest = 1
    if player.requestCounter >= realityserver.C('SPAM_LIMIT'):
        return
    player.requestCounter += 1
    if player.requestCounter == realityserver.C('SPAM_LIMIT'):
        player.canRequest = 0
        player.lastRequest = times
        if rdebug.isDebugEnabled('events'):
            rdebug.debugMessage('spam blocked ' + player.getName(), 'events')
        return True


def onPlayerConnect(player):
    event = getEvents('PlayerConnect')
    sendToHandlers(event, player)


def onPlayerSpawn(player, soldier):
    event = getEvents('PlayerSpawn')
    sendToHandlers(event, player, soldier)


def onRemoteCommand(playerId, cmd):
    event = getEvents('RemoteCommand')
    sendToHandlers(event, playerId, cmd)


def onPlayerChangeTeams(playerObject, humanHasSpawned):
    event = getEvents('PlayerChangeTeams')
    sendToHandlers(event, playerObject, humanHasSpawned)


def onPlayerChangeWeapon(playerObject, oldWeaponObject, newWeaponObject):
    event = getEvents('PlayerChangeWeapon')
    sendToHandlers(event, playerObject, oldWeaponObject, newWeaponObject)


def onPlayerChangedSquad(playerObject, oldSquadID, newSquadID):
    if oldSquadID == newSquadID and oldSquadID == 0:
        return
    event = getEvents('PlayerChangedSquad')
    sendToHandlers(event, playerObject, oldSquadID, newSquadID)


def onPlayerScore(playerObject, difference):
    event = getEvents('PlayerScore')
    sendToHandlers(event, playerObject, difference)


def onPlayerHealPoint(givingPlayerObject, receivingSoldierObject):
    event = getEvents('PlayerHealPoint')
    sendToHandlers(event, givingPlayerObject, receivingSoldierObject)


def onPlayerRepairPoint(givingPlayerObject, receivingVehicleObject):
    event = getEvents('PlayerRepairPoint')
    sendToHandlers(event, givingPlayerObject, receivingVehicleObject)


def onPlayerGiveAmmoPoint(givingPlayerObject, receivingPhysicalObject):
    event = getEvents('PlayerGiveAmmoPoint')
    sendToHandlers(event, givingPlayerObject, receivingPhysicalObject)


def onPlayerTeamDamagePoint(playerObject, victimSoldierObject):
    event = getEvents('PlayerTeamDamagePoint')
    sendToHandlers(event, playerObject, victimSoldierObject)


def onPlayerKilled(victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject):
    event = getEvents('PlayerKilled')
    sendToHandlers(event, victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject)


def onPlayerRevived(revivedPlayerObject, medicPlayerObject):
    event = getEvents('PlayerRevived')
    sendToHandlers(event, revivedPlayerObject, medicPlayerObject)


def onPlayerDeath(playerObject, soldierObject):
    event = getEvents('PlayerDeath')
    sendToHandlers(event, playerObject, soldierObject)


def onEnterVehicle(player, vehicle, freeSoldier = False):
    event = getEvents('EnterVehicle')
    sendToHandlers(event, player, vehicle, freeSoldier)


def onExitVehicle(player, vehicle):
    event = getEvents('ExitVehicle')
    sendToHandlers(event, player, vehicle)


def onPlayerBanned(playerObject, times, typ):
    event = getEvents('PlayerBanned')
    sendToHandlers(event, playerObject, times, typ)


def onPlayerKicked(playerObject):
    event = getEvents('PlayerKicked')
    sendToHandlers(event, playerObject)


def onPlayerDisconnect(playerObject):
    event = getEvents('PlayerDisconnect')
    sendToHandlers(event, playerObject)


def onVehicleDestroyed(vehicleObject, attackerObject):
    event = getEvents('VehicleDestroyed')
    sendToHandlers(event, vehicleObject, attackerObject)


def onPickupKit(playerObject, kitObject):
    event = getEvents('PickupKit')
    sendToHandlers(event, playerObject, kitObject)


def onDropKit(playerObject, kitObject):
    event = getEvents('DropKit')
    sendToHandlers(event, playerObject, kitObject)


def onReset(data):
    event = getEvents('Reset')
    sendToHandlers(event, data)


def onChangedCommander(teamID, oldCommanderPlayerObject, newCommanderPlayerObject):
    event = getEvents('ChangedCommander')
    sendToHandlers(event, teamID, oldCommanderPlayerObject, newCommanderPlayerObject)


def onChangedSquadLeader(squadID, oldLeaderPlayerObject, newLeaderPlayerObject):
    event = getEvents('ChangedSquadLeader')
    sendToHandlers(event, squadID, oldLeaderPlayerObject, newLeaderPlayerObject)


def onControlPointChangedOwner(controlPointObject, attackingTeamID):
    event = getEvents('ControlPointChangedOwner')
    sendToHandlers(event, controlPointObject, attackingTeamID)


def onTimeLimitReached(value):
    event = getEvents('TimeLimitReached')
    sendToHandlers(event, value)


def onTicketLimitReached(team, limitID):
    event = getEvents('TicketLimitReached')
    sendToHandlers(event, team, limitID)


def onConsoleSendCommand(command, args):
    event = getEvents('ConsoleSendCommand')
    sendToHandlers(event, command, args)


def onClientCommand(command, issuerPlayerObject, args):
    event = getEvents('ClientCommand')
    sendToHandlers(event, command, issuerPlayerObject, args)


def onPlayerUnlocksResponse(succeeded, player, unlocks):
    event = getEvents('PlayerUnlocksResponse')
    sendToHandlers(event, succeeded, player, unlocks)


def onChatMessage(playerId, text, channel, flags):
    event = getEvents('ChatMessage')
    sendToHandlers(event, playerId, text, channel, flags)


def onPlayerStatsResponse(succeeded, player, response):
    event = getEvents('PlayerStatsResponse')
    sendToHandlers(event, succeeded, player, response)


def onDeployGrapplingHook(player):
    event = getEvents('DeployGrapplingHook')
    sendToHandlers(event, player)


def onDeployZipLine(player):
    event = getEvents('DeployZipLine')
    sendToHandlers(event, player)


def onDeployTactical(player):
    event = getEvents('DeployTactical')
    sendToHandlers(event, player)


def onFilteredChatMessage(playerId, text, channel, flags):
    if playerId == -1:
        playerId = 255
    try:
        player = bf2.playerManager.getPlayerByIndex(playerId)
        if not player or not player.isValid():
            return
    except:
        return

    text = text.replace('HUD_TEXT_CHAT_COMMANDER', '')
    text = text.replace('HUD_TEXT_CHAT_TEAM', '')
    text = text.replace('HUD_TEXT_CHAT_SQUAD', '')
    text = text.replace('HUD_CHAT_DEADPREFIX', '')
    text = text.replace('* ', '')
    text = text.strip()
    args = text.lower().split(' ')
    try:
        if args[0] != 'rcon':
            event = getEvents('ChatMessageFiltered')
            sendToHandlers(event, playerId, text, channel, flags)
        else:
            text = text.replace('rcon ', '')
            onFilteredRemoteCommand(playerId, text)
    except:
        pass


remoteCommands = {'health': ('RemoteCommandHealth',
            True,
            False,
            False),
 'size': ('RemoteCommandSize',
          True,
          False,
          False),
 'tmp': ('RemoteCommandTemplate',
         True,
         False,
         False),
 'destroyables': ('RemoteCommandDestroyables',
                  True,
                  False,
                  False),
 'fastcap': ('RemoteCommandFastCap',
             True,
             False,
             False),
 'localization': ('RemoteCommandLocalization',
                  True,
                  False,
                  False),
 'profiler': ('RemoteCommandProfiler',
              True,
              False,
              False),
 'points': ('RemoteCommandPoints',
            True,
            False,
            False),
 'modded': ('RemoteCommandModded',
            True,
            False,
            False),
 'shutdown': ('RemoteCommandShutdown',
              True,
              False,
              False),
 'sv': ('RemoteCommandServer',
        True,
        False,
        False),
 'spawner': ('RemoteCommandSpawner',
             True,
             False,
             False),
 'vehicles': ('RemoteCommandVehicles',
              True,
              False,
              False),
 'exit': ('RemoteCommandVehicles',
          True,
          False,
          False),
 'damage': ('RemoteCommandVehicles',
            True,
            False,
            False),
 'oneman': ('RemoteCommandVehicles',
            True,
            False,
            False),
 'shovelman': ('RemoteCommandShovelman',
               True,
               False,
               False),
 'start': ('RemoteCommandVehicles',
           True,
           False,
           False),
 'light': ('RemoteCommandVehicles',
           True,
           False,
           False),
 'heavy': ('RemoteCommandVehicles',
           True,
           False,
           False),
 'disable': ('RemoteCommandVehicles',
             True,
             False,
             False),
 'prbot': ('RemoteCommandSpectator',
           True,
           False,
           False),
 'prbot2': ('RemoteCommandSpectator',
            True,
            False,
            False),
 'prbot3': ('RemoteCommandSpectator',
            True,
            False,
            False),
 'prbot4': ('RemoteCommandSpectator',
            True,
            False,
            False),
 'prbot_alt': ('RemoteCommandSpectator',
               True,
               False,
               False),
 'ninja': ('RemoteCommandNinja',
           True,
           False,
           False),
 'kits': ('RemoteCommandKits',
          True,
          False,
          False),
 'onefaction': ('RemoteCommandOneFaction',
                True,
                False,
                False),
 'teleport': ('RemoteCommandCheat',
              True,
              False,
              False),
 'ready': ('RemoteCommandCheat',
           True,
           False,
           False),
 'arty': ('RemoteCommandCheat',
          True,
          False,
          False),
 'idkfa': ('RemoteCommandIDKFA',
           True,
           False,
           False),
 'rearm': ('RemoteCommandIDKFA',
           True,
           False,
           False),
 'ref': ('RemoteCommandRef',
         True,
         False,
         False),
 'reference': ('RemoteCommandRef',
               True,
               False,
               False),
 'stamina': ('RemoteCommandStamina',
             True,
             False,
             False),
 'physics': ('RemoteCommandPhysics',
             True,
             False,
             False),
 'tutorial': ('RemoteCommandTutorial',
              False,
              False,
              False),
 'missile': ('RemoteCommandMissile',
             False,
             False,
             False),
 'acsys': ('RemoteCommandACSYSToggle',
           False,
           False,
           False),
 'vote': ('RemoteCommandVote',
          False,
          False,
          False),
 'hideawd': ('RemoteCommandHideCurrentAWD',
             False,
             False,
             False),
 'transfersl': ('RemoteCommandTransferSL',
                False,
                False,
                False),
 'chatenablerequest': ('RemoteCommandCheckChat',
                       False,
                       False,
                       False),
 'debug': ('RemoteCommandDebug',
           False,
           True,
           False),
 'camera': ('RemoteCommandCamera',
            False,
            True,
            False),
 'request': ('RemoteCommandRequestMark',
             False,
             False,
             True),
 'mark': ('RemoteCommandSpottedMark',
          False,
          False,
          True),
 'drop': ('RemoteCommandDrop',
          False,
          False,
          True),
 'attack': ('RemoteCommandGameplayRequest',
            False,
            False,
            True),
 'extract': ('RemoteCommandGameplayRequest',
             False,
             False,
             True),
 'support': ('RemoteCommandGameplayRequest',
             False,
             False,
             True),
 'supply': ('RemoteCommandGameplayRequest',
            False,
            False,
            True),
 'repair': ('RemoteCommandGameplayRequest',
            False,
            False,
            True),
 'ammo': ('RemoteCommandGameplayRequest',
          False,
          False,
          True),
 'medic': ('RemoteCommandGameplayRequest',
           False,
           False,
           True),
 'fire': ('RemoteCommandGameplayRequest',
          False,
          False,
          True),
 'mutiny': ('RemoteCommandGameplayRequest',
            False,
            False,
            True),
 'status': ('RemoteCommandGameplayRequest',
            False,
            False,
            True),
 'mine': ('RemoteCommandGameplayRequest',
          False,
          False,
          True),
 'spawn': ('RemoteCommandKitRequest',
           False,
           False,
           True),
 'fcs': ('RemoteCommandFcs',
         False,
         False,
         False),
 'cmdr': ('RemoteCommandAssetRequest',
          False,
          False,
          True),
 'rally': ('RemoteCommandRallyRequest',
           False,
           False,
           True),
 'distance': ('RemoteCommandDistance',
              False,
              False,
              False),
 'closest': ('RemoteCommandClosest',
             False,
             False,
             False),
 'select': ('RemoteCommandSelectKit',
            False,
            False,
            False),
 'custom': ('RemoteCommandCustomKit',
            False,
            False,
            False),
 'initkit': ('RemoteCommandInitKit',
             False,
             False,
             False),
 'delete': ('RemoteCommandGameplayMark',
            False,
            False,
            True),
 'uav': ('RemoteCommandGameplayMark',
         False,
         False,
         True),
 'lz': ('RemoteCommandGameplayMark',
        False,
        False,
        True),
 'target': ('RemoteCommandGameplayMark',
            False,
            False,
            True),
 'mortar': ('RemoteCommandGameplayMark',
            False,
            False,
            True),
 'cas': ('RemoteCommandGameplayMark',
         False,
         False,
         True),
 'demolish': ('RemoteCommandGameplayMark',
              False,
              False,
              True),
 'minefield': ('RemoteCommandGameplayMark',
               False,
               False,
               True),
 'spotted': ('RemoteCommandGameplayMark',
             False,
             False,
             True),
 'giveup': ('RemoteCommandGiveUp',
            False,
            False,
            False),
 'done': ('RemoteCommandDone',
          False,
          False,
          False),
 'lase': ('RemoteCommandLase',
          False,
          False,
          False),
 'heartbeat': ('RemoteCommandHeartBeat',
               False,
               False,
               False),
 'position': ('RemoteCommandPosition',
              True,
              False,
              False),
 'preroundcamera': ('RemoteCommandPreRoundCamera',
                    False,
                    False,
                    False),
 'drag': ('RemoteCommandDrag',
          False,
          False,
          False),
 'notafk': ('RemoteCommandPlayerActive',
            False,
            False,
            False)}

def onFilteredRemoteCommand(playerId, text):
    try:
        text = text.lower()
        args = text.split(' ')
        if playerId == -1:
            event = getEvents('LocalConsoleCommand')
            sendToHandlers(event, args)
            playerId = 255
        player = bf2.playerManager.getPlayerByIndex(playerId)
        if not player or not player.isValid() or player.isAIPlayer():
            return
        text = text.lower()
        args = text.split(' ')
        cmd = args[0]
        args.pop(0)
        if cmd not in remoteCommands:
            return
        e, debug, dev, spam = remoteCommands[cmd]
        if rdebug.isDebugEnabled('events'):
            rdebug.debugMessage(text + ' --> ' + e, 'events')
        if spam:
            if requestSpamBlocker(player):
                if not player.dead:
                    host.sgl_sendMedalEvent(player.index, 1031406, 1)
            if player.canRequest == 0 and not rdebug.isDebugEnabled():
                if rdebug.isDebugEnabled('events'):
                    rdebug.debugMessage(player.getName() + ' is spam blocked', 'events')
                return
        if dev or debug:
            if not rdebug.canExecute(player, debug, dev):
                return
            realityadmin.adminPM('\xc2\xa7c1001 *LATAM_DBG* \xc2\xa7c1001 %s uso el comando - rcon %s ' % (player.getName(), cmd))
        event = getEvents(e)
        sendToHandlers(event, player, cmd, args)
    except:
        return


def onPunishmentCommand(command, player, args):
    if int(command) == 100:
        event = getEvents('PlayerPunished')
        sendToHandlers(event, player)
        return
    if int(command) == 101:
        event = getEvents('PlayerForgave')
        sendToHandlers(event, player)
        return


def onRevivedPickupKit(player, kit):
    if player.revived is False:
        return
    event = getEvents('PickupRevivedKit')
    sendToHandlers(event, locals())


def onRevivedDropKit(player, kit):
    if player.revived is False:
        return
    event = getEvents('DropRevivedKit')
    sendToHandlers(event, player, kit)


def onCustomPickupKit(player, kit):
    if not hasattr(player, 'pickupKit'):
        player.pickupKit = 0
    player.pickupKit += 1
    if player.pickupKit > 1:
        return
    event = getEvents('PickupFirstKit')
    sendToHandlers(event, player, kit)


def onCustomDropKit(player, kit):
    if player.pickupKit > 1:
        return
    event = getEvents('DropFirstKit')
    sendToHandlers(event, player, kit)


def onVehicleSpawned(vehicle, attacker):
    if vehicle.templateName != 'SpawnerEvent':
        return
    realSpawn = vehicle.getParent()
    event = getEvents('VehicleSpawned')
    sendToHandlers(event, realSpawn)


import realitygunnerlagcompensation
import realitycore
objectSpawnedCallback = set()
spawnedObjects = realitycore.ObjectSet()

def registerObjectSpawnedCallback(callback):
    if rmemory.isWindowsListenServer:
        return
    objectSpawnedCallback.add(callback)


def registerObjectSpawnedTemplate(templateName):
    if rmemory.isWindowsListenServer:
        return
    _realitymemory.addObjectSpawnerTemplate(templateName)


def onObjectSpawned(obj):
    spawnedObjects.addObject(obj)
    for callback in objectSpawnedCallback:
        try:
            if bool(rdebug.isDebugEnabled('profiler')):
                start = rdebug.clockFunc()
                callback(obj)
                time = rdebug.clockFunc() - start
                rlogger.RealityLogger['profiler'].logLine('%s.%s\t%s' % (callback.__module__, callback.__name__, '{0:.7f}'.format(time * 1000)))
            else:
                callback(obj)
        except:
            rdebug.errorMessage()


def preProjectileCreated(weapon, mat, vel):
    realitygunnerlagcompensation.preProjectileCreated(weapon, mat, vel)