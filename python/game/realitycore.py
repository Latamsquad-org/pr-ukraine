import math
import random
import _realitycore
import bf2
import host
import realityadmin as radmin
import realityconstants as CONSTANTS
import realitydebug as rdebug
import realityevents as revents
import realitylocalization as rlocalization
import realitymemory as rmemory
import realityrally as rrally
import realityserver
import realitytimer as rtimer
BIGTEXT = '\xc2\xa73'
COLOREDTEXT = '\xc2\xa7c1001'
BIGCOLOREDTEXT = BIGTEXT + COLOREDTEXT
HQ = COLOREDTEXT + '** ' + rlocalization.t('HQ') + ' ** ' + COLOREDTEXT
LOAD_OBJECT_DELAY = 1
g_controlPoints = []
g_cmdPosts = {}
g_vehicleDepots = {}
g_positions_timer = None
g_last_positions = {}
g_squads = {}
g_squadLeaders = {}
g_squadNames = {}
g_kill_timer = {}
g_mapLayer = 0
g_mapArea = 0
g_mapTeams = {}
g_mapNames = {}
g_spawnPenalty = {}
g_spawnPenaltyTemp = {}
g_tmp_name = None
g_tmp_properties = {}
g_tmp_default = {}
g_runningState = 0
g_roundStarted = False
g_roundStartTime = 0

class ObjectSet:

    def __init__(self):
        self.set = set()
        host.registerGameStatusHandler(self.onGameStatusChanged)

    def onGameStatusChanged(self, status):
        if status == bf2.GameStatus.EndGame:
            self.set.clear()

    def addObject(self, obj):
        self.set.add(obj)

    def getObjects(self):
        for obj in list(self.set):
            if not obj.isValid():
                self.set.discard(obj)

        return self.set


g_supply_objects = ObjectSet()

def updateSupplySet(obj):
    if getObjectType(obj.templateName).lower() == 'supplyobject':
        g_supply_objects.addObject(obj)
        rdebug.debugMessage('Added supply object %s' % obj.templateName, 'gameplay')


def updateSupplySetProj(weapon, obj):
    updateSupplySet(obj)


def copy(variable):
    return variable


def init():
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('PlayerKilled', onPlayerKilled)
    host.registerHandler('EnterVehicle', onEnterVehicle)
    host.registerHandler('ExitVehicle', onExitVehicle)
    host.registerHandler('ChangedCommander', onChangedCommander)
    host.registerHandler('PlayerSpawn', onPlayerSpawn)
    host.registerHandler('PlayerRevived', onPlayerRevived)
    host.registerHandler('PlayerSuicided', onPlayerSuicided)
    host.registerHandler('PlayerTeamKilled', onPlayerTeamKilled)
    host.registerHandler('PlayerForgave', onPlayerForgave)
    host.registerHandler('PlayerPunished', onPlayerPunished)
    host.registerHandler('PlayerDeath', onPlayerDeath)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    host.registerHandler('PlayerChangedSquad', onPlayerChangedSquad)
    host.registerHandler('PlayerChangeTeams', onPlayerChangeTeams)
    host.registerHandler('ChangedSquadLeader', onChangedSquadLeader)
    host.registerHandler('PlayerDeath', applySpawnPenalty)
    host.registerHandler('RemoteCommandGiveUp', onPlayerGiveUp)
    host.registerHandler('RemoteCommandDone', onPlayerDone)
    host.registerHandler('RemoteCommandHealth', onRemoteHealthCommand)
    host.registerHandler('RemoteCommandSize', onRemoteSizeCommand)
    host.registerHandler('RemoteCommandTemplate', onRemoteTemplateCommand)
    revents.registerObjectSpawnedCallback(updateSupplySet)
    resetSquads()
    oldrcon_invoke = host.rcon_invoke

    def newrcon_invoke(string):
        for c in string:
            if ord(c) < 32:
                return ''

        return oldrcon_invoke(string)

    host.rcon_invoke = newrcon_invoke
    if not rmemory.isWindowsListenServer:
        import _realitymemory as _rmemory
        _rmemory.initializeAmmoCompRearmHook()
        _rmemory.initializeSetSpawnGroupHook(onSpawngroupChanged)
    print 'realitycore.py initialized'


def onGameStatusChanged(status):
    global g_mapLayer
    global g_kill_timer
    global g_mapArea
    global g_roundStarted
    global g_spawnPenalty
    global g_last_positions
    global g_runningState
    global g_spawnPenaltyTemp
    global g_mapTeams
    global g_positions_timer
    global g_vehicleDepots
    global g_mapNames
    global g_roundStartTime
    global g_controlPoints
    global g_cmdPosts
    g_roundStarted = False
    g_runningState = 0
    if not g_mapNames:
        g_mapNames = rlocalization.parseLocalizationFile('HUD_LEVELNAME_', 'prmaps.utxt', 'english', True)
    try:
        for player in getPlayers():
            onPlayerConnect(player)
            player.invalidCommander = False
            player.invalidSquadLeader = False
            player.spawnedThisRound = False

    except:
        pass

    if status == bf2.GameStatus.Loaded:
        g_mapLayer = 0
        g_mapArea = 0
        g_mapTeams[1] = bf2.gameLogic.getTeamName(1).lower()
        g_mapTeams[2] = bf2.gameLogic.getTeamName(2).lower()
        last = -999
        first = 999
        bases = True
        for cp in cleanListOfObjects(bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.ControlPoint'), True, True):
            g_controlPoints.append(cp)
            cp.text = cp.templateName
            try:
                only = int(cp.cp_getParam('onlyTakeableByTeam'))
            except:
                only = None

            for team in [1, 2]:
                if only in (1, 2) and only != team:
                    cp.cp_setParam('allowCaptureByTeam', team, False)
                else:
                    cp.cp_setParam('allowCaptureByTeam', team, True)

            cp.lastAttackingTeam = 0
            if cp.cp_getParam('team') > 0:
                cp.flagPosition = CONSTANTS.Top
            else:
                cp.flagPosition = CONSTANTS.Bottom
            try:
                maplistArray = host.rcon_invoke('maplist.list').split('\n')
                currentlevel = int(host.rcon_invoke('admin.currentlevel').split('\n')[0])
                g_mapLayer = int(maplistArray[currentlevel].split(' ')[3])
            except:
                rdebug.debugMessage('Could not parse map layer normally')
                if cp.templateName.find('16_') != -1:
                    g_mapLayer = 16
                if cp.templateName.find('32_') != -1:
                    g_mapLayer = 32
                if cp.templateName.find('64_') != -1:
                    g_mapLayer = 64
                if cp.templateName.find('128_') != -1:
                    g_mapLayer = 128

            cp.sgid = 0
            cp.random = 0
            cp.route = 0
            try:
                sgids = str(cp.cp_getParam('supplyGroupId'))
                if int(sgids) == -1:
                    continue
            except:
                bases = False
                continue

            if len(sgids) == 5:
                sgids = '0' + sgids
            if len(sgids) == 6:
                length = 2
            else:
                length = 1
            try:
                cp.sgid = int(sgids[0 * length:1 * length])
            except:
                pass

            try:
                cp.random = int(sgids[1 * length:2 * length])
            except:
                pass

            try:
                cp.route = int(sgids[2 * length:3 * length])
            except:
                pass

            if cp.sgid < first:
                first = cp.sgid
            if cp.sgid > last:
                last = cp.sgid

        cps = rlocalization.parseLocalizationFile(getCPNamePrefix(), 'prmaps.utxt')
        for cp in g_controlPoints:
            try:
                cp.text = cps[cp.templateName]
            except:
                pass

        world = bf2.gameLogic.getWorldSize()
        area = world[0] * world[1]
        if area > 64000000:
            g_mapArea = CONSTANTS.INSANE
            debug = 'insane'
        elif area > 16000000:
            g_mapArea = CONSTANTS.HUGE
            debug = 'huge'
        elif area > 4000000:
            g_mapArea = CONSTANTS.BIG
            debug = 'big'
        elif area > 1000000:
            g_mapArea = CONSTANTS.MEDIUM
            debug = 'medium'
        elif area > 250000:
            g_mapArea = CONSTANTS.SMALL
            debug = 'small'
        else:
            g_mapArea = CONSTANTS.TINY
            debug = 'tiny'
        updateAmmoSourceTeams()
        if rdebug.isDebugEnabled('gamemode'):
            rdebug.debugMessage('map layer = ' + str(g_mapLayer), 'gamemode')
            rdebug.debugMessage('map area = ' + str(debug), 'gamemode')
            rdebug.debugMessage('close relative = ' + str(getRelativeDistance(CONSTANTS.DISTANCE_CLOSE)), 'gamemode')
    elif status == bf2.GameStatus.Playing:
        rtimer.fireOnce(checkCommandPosts, 1)
        rtimer.fireOnce(checkVehicleDepots, 2)
        g_runningState = now()
        resetSquads()
        g_positions_timer = rtimer.Timer(checkPositions, realityserver.C('STARTDELAY') + 12, 1)
        g_positions_timer.setRecurring(10)
        g_roundStartTime = host.timer_getWallTime()
        if not rmemory.isWindowsListenServer:
            import _realitymemory

            def registerSpawnAndFire(template):
                revents.registerObjectSpawnedTemplate(template)
                _realitymemory.addProjectileCreatedTemplate(template, updateSupplySetProj)

            for config in ['KIT_SUPPLY_OBJECTS', 'KIT_SUPPLY_OBJECTS_OPEN', 'SUPPLIES_TEMPLATES_TEAMLOCKED']:
                rdebug.debugMessage(config)
                for team, supplies in realityserver.C(config).items():
                    for supply in supplies:
                        registerSpawnAndFire(supply)

            for team, supplies in realityserver.C('SUPPLIES_TEMPLATES').items():
                for supply in supplies:
                    registerSpawnAndFire(supply[0])

            registerSpawnAndFire('supply_small')
            registerSpawnAndFire('supply_small_insurgent')
            registerSpawnAndFire('supply_small_ww2ger')
            registerSpawnAndFire('supply_small_ww2rus')
            registerSpawnAndFire('supply_small_ww2usa')

            def ammoBagProxy(weapon, ammobag):
                try:
                    supplybundle = getFirstChild(ammobag, lambda obj: obj.templateName == 'ammokit_supply')
                    supplyinf = getFirstChild(supplybundle, lambda obj: obj.templateName == 'ammokit_sup')
                    updateSupplySet(supplyinf)
                except:
                    rdebug.errorMessage()

            _realitymemory.addProjectileCreatedTemplate('ammokit_projectile', ammoBagProxy)
            _realitymemory.addProjectileCreatedTemplate('ammocan_Projectile', ammoBagProxy)
            _realitymemory.addProjectileCreatedTemplate('ammocan_ger_Projectile', ammoBagProxy)
            _realitymemory.addProjectileCreatedTemplate('ammocan_ru_Projectile', ammoBagProxy)
            _realitymemory.addProjectileCreatedTemplate('ammokit_space_Projectile', ammoBagProxy)
            _realitymemory.addProjectileCreatedTemplate('ammokit_space_red_Projectile', ammoBagProxy)
    elif status == bf2.GameStatus.EndGame:
        destroyPositionsTimer()
        destroyMapListTimer()
        for index in g_kill_timer.keys():
            destroyKillTimer(index)

        g_kill_timer.clear()
        g_spawnPenalty.clear()
        g_spawnPenaltyTemp.clear()
        g_mapTeams.clear()
        g_cmdPosts.clear()
        g_vehicleDepots.clear()
        g_last_positions.clear()
        del g_controlPoints[:]
    return


def getTimeSinceRoundStart():
    if revents.g_gameState != bf2.GameStatus.Playing:
        return 0.0
    return host.timer_getWallTime() - g_roundStartTime


def findClosestObj(pos, objects, minimumSquared = 80):
    nearest = None
    for o in objects:
        posobj = o.getPosition()
        if abs(posobj[0] - pos[0]) > 50:
            continue
        currentdist = _realitycore.calcDistanceSquared(pos, posobj)
        if currentdist < minimumSquared:
            minimumSquared = currentdist
            nearest = o

    return nearest


def findClosestPosCustom(pos, objects, posGetter, minimumSquared = 80):
    nearest = None
    for o in objects:
        currentdist = _realitycore.calcDistanceSquared(pos, posGetter(o))
        if currentdist < minimumSquared:
            minimumSquared = currentdist
            nearest = o

    return nearest


def getFirstChild(object, childPredicate = lambda x: True):
    for child in object.getChildren():
        if childPredicate(child):
            return child


def getFirstChildRecursive(object, childPredicate = lambda x: True):
    for child in object.getChildren():
        if childPredicate(child):
            return child
        res = getFirstChildRecursive(child, childPredicate)
        if res:
            return res


def getAllChildRecursive(object, childPredicate = lambda x: True):
    return _getAllChildRecursiveRec(object, childPredicate, [])


def _getAllChildRecursiveRec(object, childPredicate, result):
    for child in object.getChildren():
        if childPredicate(child):
            result.append(child)
        _getAllChildRecursiveRec(child, childPredicate, result)

    return result


def destroyMapListTimer():
    global g_mapList_timer
    global g_mapListMessage_timer
    try:
        if g_mapList_timer:
            g_mapList_timer.destroy()
            g_mapList_timer = None
    except:
        pass

    try:
        if g_mapListMessage_timer:
            g_mapListMessage_timer.destroy()
            g_mapListMessage_timer = None
    except:
        pass

    return


def destroyPositionsTimer():
    global g_positions_timer
    try:
        if g_positions_timer:
            g_positions_timer.destroy()
            g_positions_timer = None
    except:
        pass

    return


def updateAmmoSourceTeams():
    for team in [1, 2]:
        teamName = getTeamName(team)
        if teamName not in realityserver.C('SUPPLIES_TEMPLATES_TEAMLOCKED'):
            continue
        for template in realityserver.C('SUPPLIES_TEMPLATES_TEAMLOCKED')[teamName]:
            setTemplateProperties(template, {'team': team}, 'SupplyObject')


def getCPNamePrefix():
    _map = getMapName()
    mode = getGameMode()
    layer = getMapLayer()
    prefix = 'cpname_'
    if _map:
        prefix += str(_map) + '_'
        if mode:
            if mode == 'cq':
                prefix += 'aas'
            else:
                prefix += str(mode)
            if layer:
                prefix += str(layer) + '_'
    return prefix


def checkCommandPosts(data = ''):
    global g_cmdPosts
    g_cmdPosts = {1: None,
     2: None}
    for team in [1, 2]:
        teamName = getTeamName(team)
        if teamName not in realityserver.C('COMMANDPOST_TEMPLATES'):
            continue
        for template in realityserver.C('COMMANDPOST_TEMPLATES')[teamName]:
            for obj in getObjectsOfTemplate(template):
                if template.startswith('deployable_commandpost') or template.lower() == 'ru_ship_andreev_lpd_atc' or template.lower() == 'ch_ship_type75_lpd_atc':
                    g_cmdPosts[team] = obj
                else:
                    for child in obj.getChildren():
                        if child.templateName.lower() == 'acv_tent':
                            g_cmdPosts[team] = child
                            break

                break

    return


def checkVehicleDepots(data = ''):
    global g_vehicleDepots
    g_vehicleDepots = {1: None,
     2: None}
    for team in [1, 2]:
        teamName = getTeamName(team)
        if teamName not in realityserver.C('VEHICLE_SUPPLY_DEPOT_TEMPLATES'):
            continue
        for template in realityserver.C('VEHICLE_SUPPLY_DEPOT_TEMPLATES')[teamName]:
            for obj in cleanListOfObjects(bf2.objectManager.getObjectsOfTemplate(template), True, False):
                g_vehicleDepots[team] = obj

    return


def checkPositions(data = ''):
    global g_last_positions
    g_last_positions.clear()
    g_last_positions = {1: {},
     2: {}}
    for player in getPlayers():
        if player.killed or player.dead:
            continue
        template = player.getVehicle().templateName
        if '_the_' in template or '_ahe_' in template or '_jet_' in template:
            continue
        try:
            pos = player.getDefaultVehicle().getPosition()
        except:
            continue

        g_last_positions[player.getTeam()][player.index] = pos

    event = revents.getEvents('PositionsUpdated')
    revents.sendToHandlers(event, g_last_positions)


def getLastPositions(team):
    if team in g_last_positions:
        return g_last_positions[team]
    return {}


def getCoordinates(grid, keypad = 5):
    """
    Return a position for a given map grid
    :param grid: a string eg "A13"
    :param keypad: an integer 1-9
    :return: a 3d vector position (x, y, z) with y set to 0 #TODO heightmap?
    """
    try:
        alpha = ord(grid[0].upper()) - ord('A') - 6
        keypad = int(keypad)
        digit_offset = {'1': 6,
         '2': 5,
         '3': 4,
         '4': 3,
         '5': 2,
         '6': 1,
         '7': 0,
         '8': -1,
         '9': -2,
         '10': -3,
         '11': -4,
         '12': -5,
         '13': -6}
        if len(grid) == 2:
            digit = digit_offset[grid[1]]
        elif len(grid) == 3:
            digit = digit_offset[grid[1:3]]
        else:
            rdebug.debugMessage('Bad grid input to rcore.getCoordinates')
            return None
        if keypad < 1 or keypad > 9:
            rdebug.debugMessage('Bad keypad input to rcore.getCoordinates')
            return None
        if alpha < -6 or alpha > 6:
            rdebug.debugMessage('Bad input to rcore.getCoordinates')
            return None
        squaresize = bf2.gameLogic.getWorldSize()[0] / 13.64
        keypadoffsets = {1: (-1, -1),
         2: (0, -1),
         3: (1, -1),
         4: (-1, 0),
         5: (0, 0),
         6: (1, 0),
         7: (-1, 1),
         8: (0, 1),
         9: (1, 1)}
        return (squaresize * alpha + keypadoffsets[keypad][0] * squaresize / 3.0, 0, squaresize * digit + keypadoffsets[keypad][1] * squaresize / 3.0)
    except KeyError:
        rdebug.debugMessage('Bad input to rcore.getCoordinates')
        return None
    except Exception as error:
        rdebug.debugMessage('unhandled exception in rcore.getCoordinates' + str(error))
        return None

    return None


def getCloseProximity(playerPositions, objectPositions, number = 2, distance = CONSTANTS.DISTANCE_CLOSE, relative = True, horiz = False, vehicles = False, vehiclesCount = False):
    if relative:
        distance_relative = getRelativeDistance(distance)
        number_relative = getRelativeMultiplier(number)
    else:
        distance_relative = distance
        number_relative = number
    objects = {}
    for item, position in objectPositions.items():
        indexes = []
        indexes_relative = []
        for index, pos in playerPositions.items():
            if horiz:
                dis = getSquareHorizDistance(position, pos)
            else:
                dis = getSquareVectorDistance(position, pos)
            if dis > distance_relative ** 2:
                continue
            if dis <= distance ** 2:
                indexes.append(index)
            else:
                indexes_relative.append(index)

        if number_relative != number:
            checks = {number: indexes,
             number_relative: indexes_relative}
        else:
            checks = {number: indexes}
        for num, indexeses in checks.items():
            count = 0
            for ind in indexeses:
                player = getPlayerByIndex(ind)
                if not player:
                    continue
                if isInsideVehicle(player):
                    if not vehicles:
                        continue
                    elif vehiclesCount:
                        count += num
                count += 1
                if count >= num and item not in objects:
                    objects[item] = count
                    break

    return objects


def resetSquads():
    global g_squadNames
    global g_squads
    global g_squadLeaders
    g_squads.clear()
    g_squadLeaders.clear()
    g_squadNames.clear()
    for team in [1, 2]:
        g_squads[team] = {}
        g_squadLeaders[team] = {}
        g_squadNames[team] = {}
        for squad in range(1, 10):
            g_squads[team][squad] = []
            g_squadLeaders[team][squad] = None
            g_squadNames[team][squad] = None

    try:
        for player in getPlayers():
            player.oldSqd = 0
            team = player.getTeam()
            squad = player.getSquadId()
            if squad == 0:
                continue
            g_squads[team][squad].append(player.index)
            if player.isSquadLeader():
                g_squadLeaders[team][squad] = player.index

    except:
        pass

    return


def onPlayerChangedSquad(player, oldSquad, newSquad):
    if player.isAIPlayer() and oldSquad > 0 and newSquad > 0:
        oldSquad = 0
    if player.spawnedThisRound and (not player.isAlive() or player.isManDown()):
        player.allowSpawnOnRally = False
    team = player.getTeam()
    if oldSquad > 0:
        if player.index in g_squads[team][oldSquad]:
            g_squads[team][oldSquad].remove(player.index)
            if len(g_squads[team][oldSquad]) == 0:
                g_squadLeaders[team][oldSquad] = None
                player.invalidSquadLeader = False
                g_squadNames[team][oldSquad] = None
                event = revents.getEvents('SquadRemoved')
                revents.sendToHandlers(event, team, oldSquad)
        player.oldSqd = oldSquad
    if newSquad > 0:
        didChangeSquad = player.leftSquad and (not hasattr(player, 'oldSqd') or player.oldSqd != newSquad)
        g_squads[team][newSquad].append(player.index)
        if len(g_squads[team][newSquad]) == 1:
            event = revents.getEvents('SquadCreated')
            name = getSquadName(team, newSquad)
            revents.sendToHandlers(event, player, team, newSquad, name)
        elif didChangeSquad and roundStarted():
            player.changedSquad = now()
            rdebug.debugMessage('Player changed squad to %s' % newSquad)
    else:
        player.leftSquad = now()
    if player.dead:
        checkPlayerSpawnGroup(player)
    radmin.checkSuicideAndLeaveSquad(player)
    return


def onPlayerChangeTeams(player, human):
    if isInsideVehicle(player):
        player.setTeam(getOtherTeam(player.getTeam()))
        sendMessageToPlayer(player, 1032415, 3)
        return
    if player.getTimeToSpawn() < realityserver.C('DEAD_TIME'):
        player.setTimeToSpawn(realityserver.C('DEAD_TIME'))


def getMapLayer():
    return g_mapLayer


def getMapLayerName(layer = None):
    if not layer:
        layer = getMapLayer()
    if layer == 128:
        return 'Large'
    if layer == 64:
        return 'Standard'
    if layer == 32:
        return 'Alternative'
    if layer == 16:
        return 'Infantry'


def getMapLayerNameAbbr(layer = None):
    if not layer:
        layer = getMapLayer()
    if layer == 128:
        return 'Lrg'
    if layer == 64:
        return 'Std'
    if layer == 32:
        return 'Alt'
    if layer == 16:
        return 'Inf'


def getMapArea():
    try:
        return g_mapArea
    except:
        return 0


def getMapName(p_map = None, localized = False):
    if not p_map:
        p_map = bf2.gameLogic.getMapName()
    if not localized:
        return p_map
    elif p_map not in g_mapNames:
        return p_map.replace('_', ' ').title()
    else:
        return g_mapNames[p_map]


def getMapViewDistance():
    try:
        return int(host.rcon_invoke('GameLogic.MaximumLevelViewDistance').replace('\n', ''))
    except:
        pass


def getGameMode():
    mode = bf2.serverSettings.getGameMode()
    if mode.startswith('gpm_'):
        return mode[4:]
    return mode


def getGameModeName(mode = None):
    if not mode:
        mode = getGameMode().lower()
    if mode.startswith('gpm_'):
        mode = mode[4:]
    return {'cq': 'AAS',
     'skirmish': 'Skirmish',
     'training': 'Training',
     'vehicles': 'Vehicle Warfare',
     'coop': 'Co-op',
     'cnc': 'Command and Control',
     'counter': 'Counter-Attack',
     'scenario': 'Scenario',
     'insurgency': 'Insurgency',
     'gungame': 'Gungame'}.get(mode, 'Unknown')


def modeNameToMode(mode):
    return {'Command and Control': 'cnc',
     'Training': 'training',
     'Co-op': 'coop',
     'Scenario': 'scenario',
     'Insurgency': 'insurgency',
     'Counter-Attack': 'counter',
     'AAS': 'cq',
     'Skirmish': 'skirmish',
     'Vehicle Warfare': 'vehicles',
     'Gungame': 'gungame'}.get(mode)


def getTeamName(team):
    try:
        return g_mapTeams[team]
    except:
        return ''


def getTeamNames(numbers = False):
    if numbers:
        return g_mapTeams.items()
    return g_mapTeams.values()


def getTeamNumber(teamName):
    for team, name in getTeamNames(True):
        if name == teamName:
            return team


def getPlayers(team = None, squad = None):
    for player in bf2.playerManager.getPlayers():
        if team and player.getTeam() != team:
            continue
        if squad and player.getSquadId() != squad:
            continue
        yield player


def getAlivePlayers(team = None, mandown = False):
    players = []
    for player in getPlayers(team):
        if player.killed and (not mandown or mandown and not player.isManDown()):
            continue
        players.append(player)

    return players


def getPlayerSquadName(player):
    return getSquadName(player.getTeam(), player.getSquadId())


def getAreAllSquadsLockedOrFull(team):
    squads = host.rcon_invoke('squadManager.listSquads ' + str(team)).split('\n')[:-1]
    for line in squads:
        squadnum = int(line[3])
        if squadnum == 0:
            continue
        if numPlayersOfSquad(team, squadnum) == 0:
            continue
        if numPlayersOfSquad(team, squadnum) == 8:
            continue
        if line.endswith('e.'):
            continue
        return False

    return True


def getLockedSquads(team):
    s = []
    squads = host.rcon_invoke('squadManager.listSquads ' + str(team)).split('\n')[:-1]
    for line in squads:
        if line.endswith('e.'):
            s.append(int(line[3]))

    return s


def getIsSquadLocked(team, squad):
    squads = host.rcon_invoke('squadManager.listSquads ' + str(team)).split('\n')[:-1]
    for line in squads:
        if int(line[3]) == squad:
            return line.endswith('e.')


def getSquadName(team, squad):
    if squad == 0:
        return 'Unassigned'
    elif numPlayersOfSquad(team, squad) == 0:
        return ''
    else:
        if g_squadNames[team][squad] is None:
            squads = host.rcon_invoke('squadManager.listSquads ' + str(team)).split('\n')[:-1]
            for line in squads:
                if int(line[3]) == squad:
                    name = ' '.join(line.split(' ')[1:-2])
                    g_squadNames[team][squad] = name
                    break

        return g_squadNames[team][squad]


def deleteControlPoints(cps):
    for cp in cps:
        if cp in g_controlPoints:
            g_controlPoints.remove(cp)
            deleteObject(cp)


def getControlPoints(team = None):
    if team is None:
        try:
            return g_controlPoints
        except:
            return []

    try:
        if g_controlPoints:
            pass
    except:
        return []

    arr = []
    for cp in g_controlPoints:
        if cp.cp_getParam('team') == team:
            arr.append(cp)

    return arr


def getPlayerRole(player):
    if player.isCommander():
        return CONSTANTS.COMMANDER
    if player.isSquadLeader():
        return CONSTANTS.SQUADLEADER
    if player.getSquadId() > 0:
        return CONSTANTS.SQUADMEMBER
    return CONSTANTS.LONEWOLF


def getRole(role):
    if role == 'commander':
        return CONSTANTS.COMMANDER
    elif role == 'squadleader':
        return CONSTANTS.SQUADLEADER
    elif role == 'squadmember':
        return CONSTANTS.SQUADMEMBER
    elif role == 'lonewolf':
        return CONSTANTS.LONEWOLF
    else:
        return None


def onPlayerConnect(player):
    player.isInsideVehicle = False
    SpawnBlockHandler.resetPlayer(player)
    try:
        cached = getPlayerByIndex(player.index)
        if not cached:
            return
    except:
        return

    cached.leftSquad = None
    cached.changedSquad = None
    cached.killed = True
    cached.dead = True
    cached.revived = False
    cached.suicided = False
    cached.forgave = None
    cached.teamkilled = 0
    cached.teamkiller = None
    cached.isInsideVehicle = False
    cached.canRequest = 1
    cached.lastRequest = None
    cached.requestCounter = 0
    cached.invalidKit = False
    cached.pickupKit = 0
    cached.lastTimeToSpawn = None
    cached.lastTimeToSpawnTime = None
    cached.spawnBlockReason = None
    cached.spawnBlocks = {}
    cached.penalize = True
    cached.lastSpawn = None
    cached.lastRevive = None
    cached.enemyPresence = False
    cached.pr_blackscreen = False
    cached.allowSpawnOnRally = True
    cached.spawnedThisRound = False
    return


def blackScreen(player, fast = False):
    if player.isAIPlayer():
        return
    if fast:
        bf2.gameLogic.sendGameEvent(player, 10, 131331)
    else:
        bf2.gameLogic.sendGameEvent(player, 10, 65795)
    player.pr_blackscreen = True


def clearScreen(player):
    if player.isAIPlayer():
        return
    bf2.gameLogic.sendGameEvent(player, 10, 259)
    player.pr_blackscreen = False


def getSpawnPenalty(player):
    try:
        return roundToInt(g_spawnPenalty[player.index])
    except:
        return 0


def setSpawnPenalty(player, penalty, debug = 'attrition'):
    index = player.index
    if penalty == 0:
        g_spawnPenalty[index] = 0
    else:
        try:
            g_spawnPenalty[index] += penalty
        except:
            g_spawnPenalty[index] = 0

    if g_spawnPenalty[index] > realityserver.C('SPAWN_PENALTY_CAP'):
        g_spawnPenalty[index] = realityserver.C('SPAWN_PENALTY_CAP')
    if g_spawnPenalty[index] < 0:
        g_spawnPenalty[index] = 0
    if rdebug.isDebugEnabled('penalty') and penalty != 0:
        rdebug.debugMessage(player.getName() + ' ' + str(debug) + ' fixed spawn penalty ' + str(penalty), 'penalty')


def getTemporarySpawnPenalty(player):
    try:
        return roundToInt(g_spawnPenaltyTemp[player.index])
    except:
        return 0


def setTemporarySpawnPenalty(player, penalty, debug = 'attrition'):
    index = player.index
    if penalty == 0:
        g_spawnPenaltyTemp[index] = 0
    else:
        try:
            g_spawnPenaltyTemp[index] += penalty
        except:
            g_spawnPenaltyTemp[index] = 0

    if g_spawnPenaltyTemp[index] < 0:
        g_spawnPenaltyTemp[index] = 0
    if rdebug.isDebugEnabled('penalty') and penalty != 0:
        rdebug.debugMessage(player.getName() + ' ' + str(debug) + ' temporary spawn penalty ' + str(penalty), 'penalty')


def applySpawnPenalty(player, vehicle):
    if player.isAIPlayer():
        return
    totalSpawnTime = player.getTimeToSpawn() - (realityserver.C('WOUNDED_TIME') - realityserver.C('DEAD_TIME'))
    if rdebug.isDebugEnabled('penalty'):
        rdebug.debugMessage(player.getName() + ' spawn time ' + str(totalSpawnTime), 'penalty')
    if player.penalize:
        totalSpawnTime += getSpawnPenalty(player)
        totalSpawnTime += getTemporarySpawnPenalty(player)
    elif rdebug.isDebugEnabled('penalty'):
        rdebug.debugMessage(player.getName() + ' spawn penalties not applied for this kill', 'penalty')
    totalSpawnTime = max(min(totalSpawnTime, realityserver.C('MAX_PENALTY')), 5)
    player.setTimeToSpawn(totalSpawnTime)
    SpawnBlockHandler.pauseSpawnTime(player, SpawnBlockHandler.SPAWNBLOCKED_SPAWNPOINT_NOTSELECTED)


def onPlayerRevived(player, medic):
    player.lastRevive = now()
    player.killed = False
    player.revived = True
    player.forgave = None
    player.allowSpawnOnRally = True
    try:
        setPlayerDamage(player, realityserver.C('REVIVE_HEALTH'))
    except:
        pass

    return


def onPlayerTeamKilled(victim, attacker, weapon, assists, obj):
    victim.teamkiller = attacker


def onPlayerForgave(player):
    if not player.teamkiller:
        return
    else:
        player.teamkiller = None
        if player.killed and not player.dead:
            player.forgave = True
        return


def onPlayerPunished(player):
    if not player.teamkiller:
        return
    player.teamkiller.teamkilled += 1
    if player.killed and not player.dead:
        player.forgave = False
    if rdebug.isDebugEnabled('penalty'):
        rdebug.debugMessage(player.teamkiller.getName() + ' teamkilled ' + player.getName() + ' total teamkills = ' + str(player.teamkiller.teamkilled), 'penalty')


def onPlayerSuicided(victim, weapon):
    victim.suicided = True
    radmin.checkSuicideAndLeaveSquad(victim)


def getOtherTeam(team):
    return 3 - team


def onPlayerSpawn(player, soldier):
    global g_roundStarted
    g_roundStarted = True
    clearScreen(player)
    onPlayerConnect(player)
    player.allowSpawnOnRally = True
    player.spawnedThisRound = True
    player.killed = False
    player.dead = False
    player.lastSpawn = now()
    setTemporarySpawnPenalty(player, 0)
    checkInvalidCommander(player)
    checkInvalidSquadLeader(player)


def onPlayerDeath(victim, vehicle):
    if victim is None:
        return
    else:
        blackScreen(victim, fast=True)
        victim.killed = True
        if not victim.isManDown():
            victim.dead = True
        if victim.teamkilled > 0:
            setTemporarySpawnPenalty(victim, victim.teamkilled * realityserver.C('TEAMKILL_PENALTY'), 'teamkill')
        if not victim.teamkiller:
            setSpawnPenalty(victim, realityserver.C('SPAWN_PENALTY_DEATH'), 'death')
        if victim.suicided:
            setTemporarySpawnPenalty(victim, realityserver.C('SUICIDE_PENALTY'), 'suicide')
        return


def onChangedSquadLeader(squadId, oldSL, newSL):
    if oldSL:
        g_squadLeaders[oldSL.getTeam()][squadId] = None
        oldSL.invalidSquadLeader = False
    if newSL:
        g_squadLeaders[newSL.getTeam()][squadId] = newSL.index
    return


def getPlayerByIndex(index):
    try:
        player = bf2.playerManager.getPlayerByIndex(index)
        if player and player.isValid():
            return player
    except:
        return


def getPlayersByIndex(indexes, wrong = False):
    players = []
    for index in indexes:
        player = getPlayerByIndex(index)
        if player:
            players.append(player)
        elif wrong:
            players.append(index)

    return players


def getPlayersNames(players):
    names = []
    for player in players:
        try:
            names.append(str(player.getName()))
        except:
            names.append(str(player))

    return names


def getSquadLeader(team, squad):
    if squad > 0:
        return getPlayerByIndex(g_squadLeaders[team][squad])


def getCommander(team):
    return bf2.playerManager.getCommander(team)


def onChangedCommander(team, oldCmd, newCmd):
    if oldCmd:
        oldCmd.invalidCommander = False
        if roundStarted():
            oldCmd.changedSquad = now()
            oldCmd.leftSquad = now()
    if newCmd:
        pass


def checkInvalidCommander(player):
    try:
        if player.invalidCommander and not player.killed:
            sendMessageToPlayer(player, 1031619, 1)
            killPlayer(player, False)
    except:
        player.invalidCommander = False


def setInvalidCommander(player, msg = None):
    if not player.isCommander():
        player.invalidCommander = False
        return
    if msg:
        player.invalidCommander = msg
    else:
        player.invalidCommander = True
    checkInvalidCommander(player)


def checkInvalidSquadLeader(player):
    try:
        if player.invalidSquadLeader and not player.killed:
            sendMessageToPlayer(player, 1031119, 1)
            killPlayer(player, False)
    except:
        player.invalidSquadLeader = False


def setInvalidSquadLeader(player, msg = None):
    if not player.isSquadLeader():
        player.invalidSquadLeader = False
        return
    if msg:
        player.invalidSquadLeader = msg
    else:
        player.invalidSquadLeader = True
    checkInvalidSquadLeader(player)


def checkInvalidKit(player):
    try:
        if player.invalidKit and not player.killed:
            sendMessageToPlayer(player, 1031120, 1)
            killPlayer(player, False)
    except:
        player.invalidKit = False


def setInvalidKit(player, msg = None):
    if player.killed:
        return
    if msg:
        player.invalidKit = msg
    else:
        player.invalidKit = True
    checkInvalidKit(player)


def onEnterVehicle(player, vehicle, freeSoldier = False):
    player.isInsideVehicle = True


def onExitVehicle(player, vehicle):
    player.isInsideVehicle = False


def damagePlayer(player, percentage = 0.5):
    if percentage <= 0.0 or percentage > 1.0:
        return
    playerHealth = player.getDefaultVehicle().getDamage()
    playerDamage = int(playerHealth - 100 * percentage)
    if playerDamage <= 0:
        playerDamage = 1e-07
    elif playerDamage < 10:
        playerDamage = 10
    setPlayerDamage(player, playerDamage)


def setPlayerDamage(player, damage):
    soldier = player.getDefaultVehicle()
    if damage == 0:
        if not player.isManDown():
            damage = 1e-07
            if soldier is not player.getVehicle():
                rmemory.clickPlayerEnterButton(player)
    if soldier:
        soldier.setDamage(damage)


def numPlayersInSquad(player):
    return numPlayersOfSquad(player.getTeam(), player.getSquadId())


def numPlayersOfSquad(team, squad):
    if squad > 0:
        return len(g_squads[team][squad])
    return 0


def getPlayersInSquad(player, p_all = True):
    if p_all:
        return getPlayersOfSquad(player.getTeam(), player.getSquadId())
    else:
        return getPlayersOfSquad(player.getTeam(), player.getSquadId(), player)


def getPlayersOfSquad(team, squad, exception = None):
    if squad == 0:
        return []
    players = []
    for index in g_squads[team][squad]:
        player = getPlayerByIndex(index)
        if exception and player == exception:
            continue
        if player:
            players.append(player)

    return players


def isInsideVehicle(player):
    if not hasattr(player, 'isInsideVehicle') or player.isInsideVehicle is False:
        return False
    if isClimbing(player):
        return False
    return True


def isClimbing(player):
    return isClimbingVehicle(player.getVehicle())


def isClimbingVehicle(vehicle):
    try:
        vehicleTemplate = vehicle.templateName.lower()
    except:
        return False

    if vehicleTemplate.find('ladder') != -1 or vehicleTemplate.find('grapplinghook') != -1:
        return True
    return False


def killPlayer(player, penalize = True):
    if player.killed:
        return
    player.penalize = penalize
    setPlayerDamage(player, 0)
    g_kill_timer[player.index] = rtimer.Timer(onKillPlayerTimer, 1, 1, player.index)


def destroyKillTimer(playerId):
    if playerId not in g_kill_timer:
        return
    else:
        try:
            if g_kill_timer[playerId]:
                g_kill_timer[playerId].destroy()
                g_kill_timer[playerId] = None
        except:
            return

        try:
            del g_kill_timer[playerId]
        except:
            return

        return


def onKillPlayerTimer(playerId):
    destroyKillTimer(playerId)
    player = getPlayerByIndex(playerId)
    if not player:
        return
    if player.isManDown() and player.getTimeToSpawn() > 0:
        player.setTimeToSpawn(0)


def getCommandPost(team):
    if team in g_cmdPosts and g_cmdPosts[team] and g_cmdPosts[team].isValid():
        return g_cmdPosts[team]
    else:
        return None
        return None


def getVehicleDepot(team):
    if team in g_vehicleDepots and g_vehicleDepots[team]:
        return g_vehicleDepots[team]


def deleteObjectsOfTemplate(templateName, typ = None):
    for obj in getObjectsOfTemplate(templateName, typ):
        deleteObject(obj)


def deleteObject(obj):
    return deleteObjectId(getObjectId(obj))


def deleteObjectId(p_id):
    if p_id:
        host.rcon_invoke('Object.active id' + str(p_id))
        res = host.rcon_invoke('Object.delete').replace('\n', '')
        if res.find('Unauthorised method!') != -1:
            if rdebug.isDebugEnabled():
                rdebug.debugMessage('core: deleteObjectId() failure')
            return False
    else:
        return False
    return True


def createObject(template, position = None, rotation = None):
    res = host.rcon_invoke('Object.create ' + template).replace('\n', '')
    if res.find('Unauthorised method!') != -1:
        if rdebug.isDebugEnabled():
            rdebug.debugMessage('core: createObject() failure')
        return
    index = res.replace('id', '')
    if position or rotation:
        editObject(index, position, rotation)
    return index


def editObject(index, position = None, rotation = None):
    if not index or not position and not rotation:
        return False
    host.rcon_invoke('Object.active id' + str(index))
    if position:
        host.rcon_invoke('Object.absolutePosition %s/%s/%s' % (position[0], position[1], position[2]))
    if rotation:
        host.rcon_invoke('Object.rotation %s/%s/%s' % (rotation[0], rotation[1], rotation[2]))
    return True


def activateTemplate(name, typ = 'objectSpawner'):
    res = host.rcon_invoke('ObjectTemplate.activeSafe ' + typ + ' ' + name).replace('\n', '')
    if res in ('Unauthorised method!', 'Unknown object or method!'):
        return False
    return True


def setTemplateProperties(name, properties = None, typ = 'objectSpawner'):
    if not properties:
        properties = {}
    if len(properties) == 0:
        return
    if not activateTemplate(name, typ):
        return
    for p, v in properties.items():
        if p in ('position', 'rotation', 'delay', 'template'):
            continue
        try:
            v = str(v)
            if v != '':
                host.rcon_invoke('ObjectTemplate.%s %s' % (p, v))
        except:
            pass

    return True


def getTemplateProperty(template, name, typ = 'objectSpawner'):
    if not name:
        return
    if not activateTemplate(template, typ):
        return
    try:
        v = host.rcon_invoke('ObjectTemplate.' + name).replace('\n', '')
        if v not in ('Unauthorised method!', 'Unknown object or method!'):
            return str(v)
    except:
        pass


def getTemplateProperties(template, properties = None, typ = 'objectSpawner'):
    if not properties:
        properties = []
    arr = {}
    for p in properties:
        v = getTemplateProperty(template, p, typ)
        if v:
            arr[p.lower()] = v

    return arr


def getObjectsOfTemplates(templateIteratable, type):
    objs = bf2.objectManager.getObjectsOfType(type)
    return filter(lambda obj: obj.templateName.lower() in templateIteratable, objs)


def getObjectsOfTemplate(templateName, type = None):
    templateName = templateName.lower()
    if type is None:
        type = getObjectTypeFullName(getObjectType(templateName))
    if type is None:
        try:
            listObjects = bf2.objectManager.getObjectsOfTemplate(templateName)
            if not listObjects or len(listObjects) == 0:
                return []
            return listObjects
        except:
            return []

    else:
        objs = bf2.objectManager.getObjectsOfType(type)
        return filter(lambda obj: obj.templateName.lower() == templateName, objs)
    return


def printObjectTree(obj, level = 0):
    if not obj:
        return
    _str = '*'
    for i in range(0, level):
        _str += '*'

    _str += ' %s - %x' % (obj.templateName, rmemory._getObjectPtr(obj))
    rdebug.debugMessage(_str)
    for child in obj.getChildren():
        printObjectTree(child, level + 1)


def isValidPlayer(player):
    if player.isConnected() and player.isValid() and player.isAlive():
        return True
    return False


def isPlayerDead(player):
    if not player.killed or player.isManDown():
        return False
    return True


def isPlayerLeader(player):
    if player.isSquadLeader() or player.isCommander():
        return True
    return False


def sendSquadRequirementMessageToPlayer(player, num):
    if num == 1:
        return sendMessageToPlayer(player, 3240301)
    if num == 2:
        return sendMessageToPlayer(player, 2190308)
    if num == 3:
        return sendMessageToPlayer(player, 2190703)
    if num == 4:
        return sendMessageToPlayer(player, 1031105, 2)
    if num == 5:
        return sendMessageToPlayer(player, 1031113, 2)
    if num == 6:
        return sendMessageToPlayer(player, 1032415, 2)


def sendNearSquadRequirementMessageToPlayer(player, num):
    if num == 1:
        return sendMessageToPlayer(player, 1031109, 1)
    if num == 2:
        return sendMessageToPlayer(player, 1190601, 2)
    if num == 3:
        return sendMessageToPlayer(player, 1190507, 2)
    if num == 4:
        return sendMessageToPlayer(player, 1191819, 2)
    if num == 5 or num == 6:
        return sendMessageToPlayer(player, 1190304, 2)


def clearMessages(size = 5):
    for i in range(0, size + 1):
        sendMessageToAll(' ')


def sendMessageToAll(msg):
    try:
        host.rcon_invoke('game.sayAll "' + msg + '"')
    except:
        pass


def sendMessageToTeam(team, msg):
    try:
        host.rcon_invoke('game.sayTeam ' + str(team) + ' ' + '"' + msg + '"')
    except:
        pass


def sendMessageToPlayerTeam(player, msg, prefix = HQ):
    sendMessageToTeam(player.getTeam(), str(prefix) + player.getName() + ', ' + str(msg))


def sendMessageToPlayer(player, p_id, level = 0):
    if player and not player.dead:
        sendMedalEvent(player, p_id, level, True)


def sendMessageToSquadLeader(team, squad, p_id, level = 0):
    sendMessageToPlayer(getSquadLeader(team, squad), p_id, level)


def sendMessageToCommander(team, p_id, level = 0):
    sendMessageToPlayer(getCommander(team), p_id, level)


def sendMedalEvent(player, p_id, level, pr = False):
    if pr is False or player.isAIPlayer():
        return
    return host.sgl_sendMedalEvent(player.index, int(p_id), int(level))


projectileTemplateCache = {}

def getWeaponProjectileTemplate(weapon):
    temp = weapon.templateName
    if temp not in projectileTemplateCache:
        host.rcon_invoke('ObjectTemplate.active %s' % temp)
        projectileTemplateCache[temp] = host.rcon_invoke('ObjectTemplate.projectileTemplate').strip().lower()
    return projectileTemplateCache[temp]


getObjectTypeCache = {}

def getObjectType(objname):
    if type(objname) is not str:
        raise Exception('This function expects template name, not object!')
    if objname not in getObjectTypeCache:
        host.rcon_invoke('ObjectTemplate.active %s' % objname)
        getObjectTypeCache[objname] = host.rcon_invoke('ObjectTemplate.type').strip()
    return getObjectTypeCache[objname]


objectTypesFullNames = {'controlpoint': 'dice.hfe.world.ObjectTemplate.ControlPoint',
 'playercontrolobject': 'dice.hfe.world.ObjectTemplate.PlayerControlObject',
 'objectspawner': 'dice.hfe.world.ObjectTemplate.ObjectSpawner',
 'soldier': 'dice.hfe.world.ObjectTemplate.Soldier',
 'kit': 'dice.hfe.world.ObjectTemplate.Kit',
 'destroyableobject': 'dice.hfe.world.ObjectTemplate.DestroyableObject',
 'genericfirearm': 'dice.hfe.world.ObjectTemplate.GenericFireArm',
 'supplyobject': 'dice.hfe.world.ObjectTemplate.SupplyObject',
 'targetobject': 'dice.hfe.world.ObjectTemplate.TargetObject'}

def getObjectTypeFullName(type):
    return objectTypesFullNames.get(type.lower(), None)


def getObjectId(obj):
    if hasattr(obj, 'index'):
        return obj.index
    elif not obj.isValid():
        return None
    else:
        rootObject = bf2.objectManager.getRootParent(obj)
        if hasattr(rootObject, 'index'):
            return rootObject.index
        try:
            id = rmemory.getObjectId(rootObject)
            rootObject.index = id
            return id
        except:
            rdebug.errorMessage()
            return None

        return None


def getRelativeMultiplier(number = 1):
    area = getMapArea()
    if area >= CONSTANTS.HUGE:
        return int(3 * number)
    elif area >= CONSTANTS.BIG:
        return int(2 * number)
    else:
        return int(1 * number)


def getRelativeDistance(distance = CONSTANTS.DISTANCE_CLOSE, squared = False):
    distance *= getRelativeMultiplier()
    if squared:
        return distance ** 2
    return distance


def isClose(main, target, distance = CONSTANTS.DISTANCE_CLOSE, horiz = False):
    if not main or not target:
        return False
    elif main == target:
        return False
    try:
        mainPos = main.getDefaultVehicle().getPosition()
    except:
        try:
            mainPos = main.getPosition()
        except:
            return False

    try:
        targetPos = target.getDefaultVehicle().getPosition()
    except:
        try:
            targetPos = target.getPosition()
        except:
            return False

    if horiz:
        return _realitycore.isCloseHoriz(mainPos, targetPos, distance)
    else:
        return _realitycore.isClose(mainPos, targetPos, distance)


def getCameraRotation(camera):
    rot = [0.0, 0.0, 0.0]
    obj = camera
    while obj is not None:
        current = obj.getRotation()
        for i in (0, 1, 2):
            rot[i] += current[i]

        obj = obj.getParent()

    return tuple(rot)


def getCameraYaw(camera):
    obj = camera
    yaw = 0.0
    while obj is not None:
        yaw += obj.getRotation()[0]
        obj = obj.getParent()

    return yaw


def findCameraRecursive(veh):
    for child in veh.getChildren():
        typ = getObjectType(child.templateName)
        if typ == 'PlayerControlObject':
            continue
        if typ == 'Camera':
            return child
        camera = findCameraRecursive(child)
        if camera is not None:
            return camera

    return


def getVehicleCamera(veh):
    if veh is None:
        return
    else:
        if not hasattr(veh, 'camera'):
            veh.camera = None
            if 'camera' in getObjectType(veh.templateName).lower():
                veh.camera = veh
                return veh.camera
            veh.camera = findCameraRecursive(veh)
        return veh.camera


def getPositionFromPlayer(player, distance = 0):
    if not player.isValid():
        return (0.0, 0.0, 0.0)
    veh = player.getVehicle()
    if veh is None:
        return (0.0, 0.0, 0.0)
    camera = getVehicleCamera(veh)
    if camera is None:
        rdebug.debugMessage("Could not get position from %s, can't find camera" % player.getName())
        return getPositionFromPositionAndRotation(veh.getPosition(), veh.getRotation(), distance)
    else:
        return getPositionFromPositionAndRotation(veh.getPosition(), (getCameraYaw(camera), 0, 0), distance)


def getPositionFromObject(obj, distance = 0):
    try:
        position = obj.getPosition()
        rotation = obj.getRotation()
    except:
        return (0, 0, 0)

    return getPositionFromPositionAndRotation(position, rotation, distance)


def getPositionFromPositionAndRotationWithPitch(position, rotation, distance = 0):
    if distance == 0:
        return position
    yaw = math.radians(rotation[0])
    pitch = math.radians(rotation[1])
    xzLen = math.cos(pitch)
    x = xzLen * math.sin(yaw)
    y = -math.sin(pitch)
    z = xzLen * math.cos(yaw)
    return (position[0] + x * distance, position[1] + y * distance, position[2] + z * distance)


def getPositionFromPositionAndRotation(position, rotation, distance = 0):
    if distance == 0:
        return position
    return _realitycore.calcPosFromPosRot(position, rotation, distance)


def getVectorDistance(pos1, pos2):
    return _realitycore.calcDistance(pos1, pos2)


def getSquareVectorDistance(pos1, pos2):
    return _realitycore.calcDistanceSquared(pos1, pos2)


def getSquareVectorVehicleDistance(rot, pos1, pos2, onlyBack = True):
    if not onlyBack:
        return getSquareVectorDistance(pos1, pos2)
    back_pos = _realitycore.calcPosFromPosRot(pos1, rot, -3)
    return _realitycore.calcDistanceSquared(back_pos, pos2)


def getSquareHorizDistance(pos1, pos2):
    return _realitycore.calcHorizDistanceSquared(pos1, pos2)


def normalizeVector(vec):
    vmag = magnitudeVector(vec)
    if vmag == 0:
        return (0.0, 0.0, 0.0)
    return tuple((vec[i] / vmag for i in range(len(vec))))


def magnitudeVector(vec):
    return _realitycore.calcDistance(vec, (0, 0, 0))


def getVectorHorizDistance(pos1, pos2):
    return _realitycore.calcHorizDistance(pos1, pos2)


def getAreaPosition(obj, p_min = -100, p_max = 100):
    pos = obj.getPosition()
    x = random.randint(p_min, p_max)
    z = random.randint(p_min, p_max)
    return (pos[0] + x, pos[1], pos[2] + z)


def getAreaPositionFromPosition(pos, p_min = -100, p_max = 100):
    x = random.randint(p_min, p_max)
    z = random.randint(p_min, p_max)
    return checkMapBounds(pos, x, z)


def checkMapBounds(pos, x, z):
    width, height = bf2.gameLogic.getWorldSize()
    wx = int(width / 200.0) * 100
    wz = int(height / 200.0) * 100
    if pos[0] + x + wx < 0 or pos[0] + x - wx > 0:
        addX = -1 * x
    else:
        addX = x
    if pos[2] + z - wz > 0 or pos[2] + z + wz < 0:
        addZ = -1 * z
    else:
        addZ = z
    return (pos[0] + addX, pos[1], pos[2] + addZ)


def roundToInt(x):
    return int(round(x))


def cleanListOfObjects(objects, wreck = False, zero = False):
    for obj in objects:
        if not obj.isValid():
            continue
        if not wreck:
            if obj.isPlayerControlObject and obj.getIsWreck():
                continue
        if not zero:
            if obj.getPosition() == (0, 0, 0):
                continue
        yield obj


def isObjectActive(obj):
    if not obj.isValid():
        return False
    if obj.isPlayerControlObject and obj.getIsWreck():
        return False
    if obj.getPosition() == (0, 0, 0):
        return False
    return True


def onRemoteSizeCommand(player, cmd, args):
    area = getMapArea()
    if area == CONSTANTS.INSANE:
        areaSize = 'insane'
    elif area == CONSTANTS.HUGE:
        areaSize = 'huge'
    elif area == CONSTANTS.BIG:
        areaSize = 'big'
    elif area == CONSTANTS.MEDIUM:
        areaSize = 'medium'
    elif area == CONSTANTS.SMALL:
        areaSize = 'small'
    else:
        areaSize = 'tiny'
    rdebug.debugMessage('%s %s %s %s relative %s close %sm' % (getMapName(),
     getMapLayer(),
     areaSize,
     bf2.gameLogic.getWorldSize(),
     getRelativeMultiplier(),
     getRelativeDistance()))


def onRemoteHealthCommand(player, cmd, args):
    players = []
    health = None
    count = len(args)
    if count >= 2:
        try:
            health = float(args[1])
        except:
            pass

    if count >= 1:
        players = getPlayersByName(args[0])
    if len(players) == 0:
        players = [player]
    for p in players:
        if health:
            setPlayerDamage(p, health)
        rdebug.debugMessage(p.getName() + ' health ' + str(p.getDefaultVehicle().getDamage()))

    return


def isSoldier(vehicle):
    if not vehicle:
        return True
    if CONSTANTS.getVehicleType(vehicle.templateName) == CONSTANTS.VEHICLE_TYPE_SOLDIER:
        return True
    return False


def onPlayerGiveUp(player, cmd, args):
    if player.dead is True or player.killed is False:
        return
    if rdebug.isDebugEnabled('penalty'):
        rdebug.debugMessage(player.getName() + ' gave up', 'penalty')
    try:
        setPlayerDamage(player, 0)
    except:
        pass

    player.setTimeToSpawn(0)


def onSpawngroupChanged(playerid, group):
    try:
        p = bf2.playerManager.getPlayerByIndex(playerid)
        if p is not None and hasattr(p, 'dead') and p.dead:
            checkPlayerSpawnGroup(p)
    except:
        rdebug.errorMessage()

    return


def checkPlayerSpawnGroup(player):
    spawngroup = player.getSpawnGroup()
    if spawngroup <= 0:
        rdebug.debugMessage(player.getName() + ' did not select spawn group', 'penalty')
        return False
    else:
        rally = rrally.getRallyFromSpawngroup(spawngroup)
        if rally is not None:
            if not player.allowSpawnOnRally:
                SpawnBlockHandler.pauseSpawnTime(player, SpawnBlockHandler.SPAWNBLOCKED_SPAWNPOINT_JOINEDWHILEDEAD)
                rdebug.debugMessage(player.getName() + ' is not allowed to spawn on a rally', 'penalty')
                radmin.personalMessage('Te uniste a la escuadra estando muerto, no puedes usar este rallypoint sin antes haber spawneado.', player)
                return False
            if rally.squad != player.getSquadId() and rally.squad != 0:
                SpawnBlockHandler.pauseSpawnTime(player, SpawnBlockHandler.SPAWNBLOCKED_SPAWNPOINT_WRONGRALLY)
                rdebug.debugMessage(player.getName() + " select other squad's rally", 'penalty')
                radmin.personalMessage("Seleccionaste el rallpoint de la squad %s, no puedes hacer spawn aqui." % rally.squad, player)
                return False
        return True


def onPlayerDone(player, cmd, args):
    if not player.dead:
        return
    if not checkPlayerSpawnGroup(player):
        return
    SpawnBlockHandler.continueSpawnTime(player, 'spawnpoint')


def onRemoteTemplateCommand(player, cmd, args):
    global g_tmp_properties
    global g_tmp_default
    global g_tmp_name
    if len(args) == 0 and g_tmp_name:
        rdebug.debugMessage('tmp: ' + g_tmp_name)
        for p, v in g_tmp_properties.items():
            rdebug.debugMessage('tmp: %s %s' % (p, v))

    elif len(args) == 1 and args[0].find(':') != -1:
        arr = args[0].split(':')
        if arr[0] == 'pco':
            arr[0] = 'playercontrolobject'
        elif arr[0] == 'weapon':
            arr[0] = 'genericfirearm'
        elif arr[0] == 'supply':
            arr[0] = 'supplyobject'
        name = arr[0] + ' ' + arr[1]
        host.rcon_invoke('ObjectTemplate.activeSafe ' + name)
        rdebug.debugMessage('tmp: active ' + name)
        g_tmp_name = name
        g_tmp_properties.clear()
    elif len(args) == 1 and args[0] == 'reset' and g_tmp_name:
        host.rcon_invoke('ObjectTemplate.activeSafe ' + g_tmp_name)
        rdebug.debugMessage('tmp: ' + g_tmp_name)
        for p, v in g_tmp_default.items():
            host.rcon_invoke('ObjectTemplate.%s %s' % (p, v))
            rdebug.debugMessage('tmp: %s %s' % (p, v))
            try:
                if p in g_tmp_properties:
                    del g_tmp_properties[p]
            except:
                pass

        g_tmp_default.clear()
    elif g_tmp_name:
        p = args[0]
        args.pop(0)
        v = ' '.join(args)
        v = v.strip()
        if not v or not p:
            return
        host.rcon_invoke('ObjectTemplate.activeSafe ' + g_tmp_name)
        default = False
        if p not in g_tmp_default:
            dv = host.rcon_invoke('ObjectTemplate.%s' % p).split('\n')
            dv.pop()
            dval = dv[0].strip()
            if len(dv) == 1 and dval != '' and dval.find('Too few arguments') == -1 and dval.find('Unauthorised method') == -1:
                g_tmp_default[p] = dval
                default = True
        else:
            default = True
        host.rcon_invoke('ObjectTemplate.%s %s' % (p, v))
        rdebug.debugMessage('tmp: %s %s --- reset = %s' % (p, v, default))
        g_tmp_properties[p] = v


def getPlayersByName(name):
    name = name.lower()
    found = []
    for player in getPlayers():
        playerName = player.getName().lower()
        if playerName.find(name) > -1:
            found.append(player)

    return found


def now():
    return int(host.timer_getWallTime())


def getTimeAsString(seconds):
    seconds = roundToInt(seconds)
    if seconds > 60:
        times = int(seconds / 60)
        if times > 1:
            _type = rlocalization.t('minutes')
        else:
            _type = rlocalization.t('minute')
    else:
        times = int(seconds)
        if times > 1:
            _type = rlocalization.t('seconds')
        else:
            _type = rlocalization.t('second')
    return str(times) + ' ' + _type


def getListAsString(p_list, join = 'or'):
    s = ''
    num = len(p_list)
    for i in range(num):
        if i > 0:
            if i < num - 1:
                s += ', '
            else:
                s += ' ' + str(join) + ' '
        s = s + p_list[i]

    return s


def isRunning():
    if g_runningState == 0:
        return False
    return True


def runningState():
    return g_runningState


def reallyPlaying():
    return revents.g_gameState == bf2.GameStatus.Playing


def roundStarted():
    return g_roundStarted


def roundsPerMap():
    return int(host.rcon_invoke('sv.roundsPerMap').replace('\n', ''))


def currentRound():
    return int(host.rcon_invoke('gameLogic.roundNr').replace('\n', ''))


def isFirstRound():
    if currentRound() == 1:
        return True
    return False


def isLastRound():
    if currentRound() == roundsPerMap():
        return True
    return False


def silentlyEndGame(winner, victory):
    event = revents.getEvents('RoundEnd')
    revents.sendToHandlers(event, winner)
    bf2.gameLogic.setTicketState(1, 0)
    bf2.gameLogic.setTicketState(2, 0)
    bf2.gameLogic.setTicketChangePerSecond(1, 0)
    bf2.gameLogic.setTicketChangePerSecond(2, 0)
    host.sgl_endGame(winner, victory)


def onPlayerKilled(victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject):
    if not victimPlayerObject or not victimPlayerObject.isValid():
        return
    else:
        victimPlayerObject.killed = True
        victimPlayerObject.teamkiller = None
        if not attackerPlayerObject:
            if weaponObject is None and victimSoldierObject is not None:
                if hasattr(victimSoldierObject, 'lastDrivingPlayerIndex') and not victimSoldierObject.getIsWreck():
                    try:
                        attackerPlayerObject = getPlayerByIndex(victimSoldierObject.lastDrivingPlayerIndex)
                    except:
                        attackerPlayerObject = None

        event = revents.getEvents('PlayerKilledFiltered')
        revents.sendToHandlers(event, victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject)
        if not attackerPlayerObject or attackerPlayerObject == victimPlayerObject:
            event = revents.getEvents('PlayerSuicided')
            revents.sendToHandlers(event, victimPlayerObject, weaponObject)
        elif not attackerPlayerObject:
            pass
        elif attackerPlayerObject.getTeam() == victimPlayerObject.getTeam():
            event = revents.getEvents('PlayerTeamKilled')
            revents.sendToHandlers(event, victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject)
        else:
            event = revents.getEvents('PlayerEnemyKilled')
            revents.sendToHandlers(event, victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject)
        if victimPlayerObject.lastRevive and now() - victimPlayerObject.lastRevive < realityserver.C('REVIVE_TIME'):
            victimPlayerObject.getDefaultVehicle().setDamage(0)
            victimPlayerObject.setTimeToSpawn(0)
        return


def isPlayerLookingAtPoint(player, point, degreesError):
    if player is None or point is None:
        return False
    elif not player.isAlive() or player.isManDown():
        return False
    else:
        soldier = player.getDefaultVehicle()
        soldierPos = soldier.getPosition()
        camera = getVehicleCamera(soldier)
        yaw = getCameraYaw(camera)
        directionVector = (point[0] - soldierPos[0], point[2] - soldierPos[2])
        pointDirection = math.degrees(math.atan2(directionVector[0], directionVector[1]))
        diff = yaw - pointDirection
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        return abs(diff) < degreesError


def rotate2d(vector, angle):
    sin = math.sin(angle)
    cos = math.cos(angle)
    return (vector[0] * cos + vector[1] * sin, vector[0] * -sin + vector[1] * cos)


def rotate3dyawonly(vector, angle):
    sin = math.sin(angle)
    cos = math.cos(angle)
    return (vector[0] * cos + vector[2] * sin, 0, vector[0] * -sin + vector[2] * cos)


def eulerToQuaternion(a, p, r):
    """
    Transform Euler angles into a quaternion
    :param a: azimuth in deg is rotation around y axis
    :param p: pitch in deg is rotation around x axis
    :param r: roll in deg is rotation around z axis
    :return: (w, x, y, z) rotation quaternion
    NOTE: BF2 uses a coordinate system where the Y axis represents altitude
    https://projects.uturista.pt/bf2tech/index.php/BF2_Coordinates
    """
    azimuth, pitch, roll = math.radians(a), math.radians(p), math.radians(r)
    cos_azimuth = math.cos(azimuth * 0.5)
    cos_pitch = math.cos(pitch * 0.5)
    cos_roll = math.cos(roll * 0.5)
    sin_azimuth = math.sin(azimuth * 0.5)
    sin_pitch = math.sin(pitch * 0.5)
    sin_roll = math.sin(roll * 0.5)
    return (cos_azimuth * cos_pitch * cos_roll + sin_azimuth * sin_pitch * sin_roll,
     sin_azimuth * cos_pitch * sin_roll + cos_azimuth * sin_pitch * cos_roll,
     sin_azimuth * cos_pitch * cos_roll - cos_azimuth * sin_pitch * sin_roll,
     cos_azimuth * cos_pitch * sin_roll - sin_azimuth * sin_pitch * cos_roll)


def vectorToQuaternion(vector):
    """
    Transform a vector into a quaternion
    :param vector: a 3d vector (x, y, z)
    :return: a quaternion (w, x, y, z)
    """
    return (0,
     vector[0],
     vector[1],
     vector[2])


def pureQuaternionToVector(pvector):
    """
    Transform a pure quaternion into a normal vector
    :param pvector: a quaternion point vector (w, x, y, z)
    :return: a 3d vector (x, y, z)
    """
    return (pvector[1], pvector[2], pvector[3])


def vectorAddition(vector1, vector2):
    """
    Add two vectors
    :param vector1: a vector (x, y, z)
    :param vector2: a vector (x, y, z)
    :return: a vector v1+v2
    """
    return (vector1[0] + vector2[0], vector1[1] + vector2[1], vector1[2] + vector2[2])


def vectorDot(vector1, vector2):
    """
    Dot product of two vectors
    :param vector1: a vector (x, y, z)
    :param vector2: a vector (x, y, z)
    :return: a vector v1+v2
    """
    return vector1[0] * vector2[0] + vector1[1] * vector2[1] + vector1[2] * vector2[2]


def vectorSub(vector1, vector2):
    """
    Subtracts vector 2 from vector 1
    :param vector1: a vector (x, y, z)
    :param vector2: a vector (x, y, z)
    :return: a vector v1-v2
    """
    return (vector1[0] - vector2[0], vector1[1] - vector2[1], vector1[2] - vector2[2])


def vectorCross(vector1, vector2):
    """
    vector 1 CROSS vector 2
    :param vector1: a vector (x, y, z)
    :param vector2: a vector (x, y, z)
    :return: a vector v1 X v2
    """
    return (vector1[1] * vector2[2] - vector1[2] * vector2[1], vector1[2] * vector2[0] - vector1[0] * vector2[2], vector1[0] * vector2[1] - vector1[1] * vector2[0])


def vectorScaling(vector, scalar):
    """
    Multiply a vector by a scalar
    :param vector: 3d vector (x, y, z)
    :param scalar: int or float
    :return: product of vector (x, y, z) multiplied by scalar
    """
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


def quaternionMultiplication(q1, q2):
    """
    :param q1: quaternion (w, x, y, z)
    :param q2: quaternion (w, x, y, z)
    :return: result of multiplying q1 and q2 (w, x, y, z)
    Multiply two quaternions together
    Quaternion multiplication is non communicative. q1 * q2 != q2 * q1
    ref: https://personal.utdallas.edu/~sxb027100/dock/quaternion.html
    """
    q1_w, q1_x, q1_y, q1_z = (q1[0],
     q1[1],
     q1[2],
     q1[3])
    q2_w, q2_x, q2_y, q2_z = (q2[0],
     q2[1],
     q2[2],
     q2[3])
    return (q1_w * q2_w - q1_x * q2_x - q1_y * q2_y - q1_z * q2_z,
     q1_w * q2_x + q1_x * q2_w + q1_y * q2_z - q1_z * q2_y,
     q1_w * q2_y - q1_x * q2_z + q1_y * q2_w + q1_z * q2_x,
     q1_w * q2_z + q1_x * q2_y - q1_y * q2_x + q1_z * q2_w)


def quaternionConjugate(q):
    """
    Get the conjugate of a quaternion (w, -x, -y, -z)
    :param q: a quaternion (w, z, y, z)
    :return: the conjugate of the quaternion
    """
    w, x, y, z = (q[0],
     q[1],
     q[2],
     q[3])
    return (w,
     -x,
     -y,
     -z)


def normalizeQuaternion(q):
    """
    Normalize a quaternion to be used by other functions
    :param q: a quaternion (w, x, y, z)
    :return: a normalized quaternion (w, x, y, z)
    """
    w, x, y, z = (q[0],
     q[1],
     q[2],
     q[3])
    d = math.sqrt(w ** 2 + x ** 2 + y ** 2 + z ** 2)
    if d == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (w / d,
     x / d,
     y / d,
     z / d)


def quaternionRotateVector3d(rot, vector, invert = False):
    """
    Rotate a vector in 3 dimensions using quaternions
    :param rot: a Euler angle (y, x, z)
    :param vector: a 3d vector (x, y, z)
    :param invert: change to True to do an inverted rotation
    :return: vector rotated by rot (z, y, x)
    """
    q = normalizeQuaternion(eulerToQuaternion(rot[0], rot[1], rot[2]))
    scalar = magnitudeVector(vector)
    qv = vectorToQuaternion(normalizeVector(vector))
    if invert:
        qt = quaternionMultiplication(quaternionMultiplication(quaternionConjugate(q), qv), q)
    else:
        qt = quaternionMultiplication(quaternionMultiplication(q, qv), quaternionConjugate(q))
    vector = pureQuaternionToVector(qt)
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


def vectorRotateFromAxisAngle(vector, axis, angle):
    rotHalfAngleCos = math.cos(angle / 2.0)
    rotHalfAngleSin = math.sin(angle / 2.0)
    quat = (rotHalfAngleCos,
     axis[0] * rotHalfAngleSin,
     axis[1] * rotHalfAngleSin,
     axis[2] * rotHalfAngleSin)
    return quaternionRotateVector3dFromQuat(quat, vector)


def quaternionRotateVector3dFromQuat(q, vector, invert = False):
    """
    Rotate a vector in 3 dimensions using quaternions
    :param q: a quaternion
    :param vector: a 3d vector (x, y, z)
    :param invert: change to True to do an inverted rotation
    :return: vector rotated by rot (z, y, x)
    """
    scalar = magnitudeVector(vector)
    qv = vectorToQuaternion(normalizeVector(vector))
    if invert:
        qt = quaternionMultiplication(quaternionMultiplication(quaternionConjugate(q), qv), q)
    else:
        qt = quaternionMultiplication(quaternionMultiplication(q, qv), quaternionConjugate(q))
    vector = pureQuaternionToVector(qt)
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


def rotMatrixTranspose(mat):
    return (mat[0],
     mat[3],
     mat[6],
     mat[1],
     mat[4],
     mat[7],
     mat[2],
     mat[5],
     mat[8])


def rotMatrixMulVector(mat, vec):
    return (mat[0] * vec[0] + mat[1] * vec[1] + mat[2] * vec[2], mat[3] * vec[0] + mat[4] * vec[1] + mat[5] * vec[2], mat[6] * vec[0] + mat[7] * vec[1] + mat[8] * vec[2])


def getWeaponOwner(weapon):
    current = weapon.getParent()
    while current is not None:
        rdebug.debugMessage('Found parent of weapons %s' % current.templateName)
        typ = getObjectType(current.templateName).lower()
        currentIsSoldier = typ == 'soldier'
        currentIsVehicle = typ == 'playercontrolobject'
        if not currentIsSoldier and not currentIsVehicle:
            current = current.getParent()
            continue
        if currentIsSoldier:
            vehicle = current.getParent()
            if vehicle is not None:
                current = vehicle
        players = current.getOccupyingPlayers()
        if len(players) > 0:
            return players[0]
        return

    return


def playSoundForPlayer(player, soundid):
    bf2.gameLogic.sendGameEvent(player, 10, soundid << 16 | 260)


class SpawnBlockHandler:
    SPAWNBLOCKED_KIT_NEWTOSQUAD = ('kit', 1)
    SPAWNBLOCKED_KIT_TOOMANYINSQUAD = ('kit', 2)
    SPAWNBLOCKED_KIT_TOOMANYINTEAM = ('kit', 3)
    SPAWNBLOCKED_KIT_SQUADTOOSMALL = ('kit', 4)
    SPAWNBLOCKED_KIT_NOTSQUADLEADER = ('kit', 5)
    SPAWNBLOCKED_KIT_UNAVAILABLEFORTEAM = ('kit', 6)
    SPAWNBLOCKED_KIT_NOTINSQUAD = ('kit', 7)
    SPAWNBLOCKED_SPAWNPOINT_NOTSELECTED = ('spawnpoint', 16)
    SPAWNBLOCKED_SPAWNPOINT_WRONGRALLY = ('spawnpoint', 17)
    SPAWNBLOCKED_SPAWNPOINT_JOINEDWHILEDEAD = ('spawnpoint', 18)

    @classmethod
    def pauseSpawnTime(cls, player, blockTuple):
        """
        Pause spawn time for player. blockTuple is one of the tuples above.
        
        There can only one reason per category at a time.
        calling pauseSpawnTime will overwrite the previous reason of the given category.
        """
        if player.isAlive() or player.isAIPlayer():
            return
        else:
            category, reason = blockTuple
            if player.spawnBlocks.get(category, None) == reason:
                return
            player.spawnBlocks[category] = reason
            cls._updateSpawnBlockReason(player)
            if rdebug.isDebugEnabled('penalty'):
                rdebug.debugMessage(player.getName() + ' spawn time blocked by ' + str(category), 'penalty')
            if len(player.spawnBlocks) > 1:
                return
            player.setTimeToSpawn(cls._resetSpawnTime(player))
            player.lastTimeToSpawn = math.ceil(player.getTimeToSpawn())
            player.lastTimeToSpawnTime = math.ceil(now())
            if rdebug.isDebugEnabled('penalty'):
                rdebug.debugMessage(player.getName() + ' spawn time paused with ' + str(player.lastTimeToSpawn) + ' seconds', 'penalty')
            player.setTimeToSpawn(CONSTANTS.HUGE_TTS)
            return

    @classmethod
    def continueSpawnTime(cls, player, category):
        """
        Clear a specific category, no matter the reason.
        """
        if player.isAlive() or player.isAIPlayer():
            return
        elif category not in player.spawnBlocks:
            return
        else:
            if rdebug.isDebugEnabled('penalty'):
                rdebug.debugMessage(player.getName() + ' spawn time unblocked by ' + str(category), 'penalty')
            del player.spawnBlocks[category]
            cls._updateSpawnBlockReason(player)
            if len(player.spawnBlocks) > 0:
                return
            times = cls._resetSpawnTime(player)
            if rdebug.isDebugEnabled('penalty'):
                rdebug.debugMessage(player.getName() + ' spawn time continued with ' + str(times) + ' seconds', 'penalty')
            player.lastTimeToSpawn = None
            player.lastTimeToSpawnTime = None
            player.setTimeToSpawn(times)
            return

    @classmethod
    def _resetSpawnTime(cls, player):
        if player.isAIPlayer():
            return 0
        else:
            if player.lastTimeToSpawnTime is None or player.lastTimeToSpawn is None:
                if not roundStarted():
                    times = 0
                else:
                    times = int(player.getTimeToSpawn())
            else:
                times = int(player.lastTimeToSpawn - int(math.ceil(now()) - player.lastTimeToSpawnTime))
            if times > realityserver.C('MAX_PENALTY'):
                times = CONSTANTS.HUGE_TTS - player.getTimeToSpawn()
                if not roundStarted():
                    times = realityserver.C('STARTDELAY') - times
                elif player.isManDown():
                    times = realityserver.C('WOUNDED_TIME') - times
                else:
                    times = realityserver.C('DEAD_TIME') - times
            if times <= 0:
                times = 0
            return math.ceil(times)

    @classmethod
    def _updateSpawnBlockReason(cls, player):
        reason = 0
        if 'kit' in player.spawnBlocks:
            reason = player.spawnBlocks['kit']
        elif 'spawnpoint' in player.spawnBlocks:
            reason = player.spawnBlocks['spawnpoint']
        rdebug.debugMessage('Spawn block reason: %s' % str(reason), 'penalty')
        if reason != player.spawnBlockReason:
            player.spawnBlockReason = reason
            bf2.gameLogic.sendGameEvent(player, 10, reason << 16 | 258)

    @classmethod
    def resetPlayer(cls, player):
        bf2.gameLogic.sendGameEvent(player, 10, 258)