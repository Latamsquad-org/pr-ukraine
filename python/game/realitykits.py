import bf2
import host
import realityconstants as CONSTANTS
import realitycore as rcore
import realitydebug as rdebug
import realityevents as revents
import realitygamemode as rgamemode
import realitylocalization as rlocalization
import realitymemory as rmemory
import realityscoring as rscoring
import realityserver
import realityspawner as rspawner
import realitytimer as rtimer
import realityvehicles_settings as rvehicles_settings
g_kits_used = {}
g_kits_allocated = {}
g_kits_dropped = {}
g_kits_squads = {}
g_kits_squads_selects = {}
g_kits_wrong = {}
g_kits_limits = {}
g_kits_limits_factions = {}
g_kits_limits_squads = {}
g_kits_reset_timer = None
g_kits_variants = {}
g_kits_slots = {1: [None,
     None,
     None,
     None,
     None,
     None,
     None],
 2: [None,
     None,
     None,
     None,
     None,
     None,
     None]}
g_mapid = ''
g_kitrequest_objects = None
g_kitrequest_templates = set()
g_expected_kits = {}

def addKitRequestObject(obj):
    global g_kitrequest_objects
    if obj.templateName not in g_kitrequest_templates:
        return
    g_kitrequest_objects.addObject(obj)
    rdebug.debugMessage('Added kit request object %s' % obj.templateName, 'kits')


def addKitRequestObjectProj(weapon, obj):
    addKitRequestObject(obj)


class KitSlot:

    def __init__(self):
        self.Name = ''
        self.Primary = ''
        self.Secondary = ''
        self.Soldier = ''
        self.LimitationsEnabled = True


def getKitName(kit):
    try:
        return kitNames[kit]
    except:
        try:
            return kitNames[getKitTypeString(kit, True)]
        except:
            try:
                return kitNames[getKitTypeString(kit, False)]
            except:
                return kit


def getKitTypeFast(kit):
    start = kit.find('_') + 1
    if start == -1:
        return kit
    else:
        end = kit.find('_', start)
        if end == -1:
            return kit[start:]
        return kit[start:end]


def getKitTypeString(kit, team = False, alt = False):
    if kit.find('_') == -1:
        return kit
    try:
        kit = kit.split('_')
        _type = ''
        if team:
            _type = kit[0] + '_'
        _type += kit[1]
        if alt:
            try:
                if kit[2] == 'alt':
                    _type += '_alt'
            except:
                pass

        return _type
    except:
        return kit


def getFactionVariants(faction):
    factions = faction.split('_')
    variants = []
    for variant in ['ziptie',
     'night',
     'para',
     'sp',
     'iron',
     'pickup']:
        if variant in factions:
            variants.append(variant)

    return variants


def getKitObjectType(kit):
    if not kit:
        return None
    else:
        if not hasattr(kit, 'kitType'):
            type = getKitTypeString(kit.templateName)
            kit.kitType = type
        return kit.kitType


def getKitTeam(kit):
    try:
        kit = kit.split('_')
        if rcore.getTeamName(1) == kit[0]:
            return 1
        if rcore.getTeamName(2) == kit[0]:
            return 2
    except:
        return 0


def getKitTeamVariants(team):
    global g_kits_variants
    return g_kits_variants[team]


def getKitTemplate(kit, team, variants = False, alt = False):
    teamName = rcore.getTeamName(team)
    template = teamName + '_' + kit
    altKit = getAltObjectExists(template)
    if alt and altKit is not None:
        template = altKit
    if variants:
        variantsTemplate = template + getKitTeamVariants(team)
        if kitExists(variantsTemplate):
            return variantsTemplate
        else:
            return template
    else:
        return template
    return


def getKitLimit(team, kit):
    global g_kits_limits
    n = bf2.playerManager.getNumberOfPlayersInTeam(team)
    if n >= 32:
        size = 44
    elif n >= 24:
        size = 32
    elif n >= 16:
        size = 24
    elif n >= 8:
        size = 16
    else:
        size = 8
    try:
        return g_kits_limits[team][size][kit]
    except:
        return None

    return None


def getKitLimitFaction(faction, kit):
    global g_kits_limits_factions
    try:
        return g_kits_limits_factions[faction][kit]
    except:
        return None

    return None


def getKitsAllocated(kit):
    global g_kits_allocated
    if kit in g_kits_allocated:
        _now = rcore.now()
        g_kits_allocated[kit][:] = [ time for time in g_kits_allocated[kit] if _now <= time ]
        return len(g_kits_allocated[kit])
    return 0


def getKitsAllocatedSquad(team, squad, kit):
    global g_kits_squads
    if kit in g_kits_squads[team][squad]:
        _now = rcore.now()
        g_kits_squads[team][squad][kit][:] = [ time for time in g_kits_squads[team][squad][kit] if _now <= time ]
        return len(g_kits_squads[team][squad][kit])
    return 0


def getKitsDropped(kit):
    global g_kits_dropped
    if kit in g_kits_dropped:
        _now = rcore.now()
        g_kits_dropped[kit][:] = [ time for time in g_kits_dropped[kit] if _now <= time ]
        return len(g_kits_dropped[kit])
    return 0


def getKitLimitSquad(kit):
    global g_kits_limits_squads
    try:
        return g_kits_limits_squads[kit]
    except:
        return None

    return None


def getKitSlot(team, slot = 2):
    global g_kits_slots
    try:
        if g_kits_slots[team][slot].LimitationsEnabled:
            return g_kits_slots[team][slot].Name
        return None
    except:
        try:
            if g_kits_slots[team][2].LimitationsEnabled:
                return g_kits_slots[team][2].Name
            return None
        except:
            return None

    return None


def isNinja(player):
    try:
        if getKitTypeString(player.getKit().templateName) == 'ninja':
            return True
    except:
        return False


def isKitTeamkiller(player, kit):
    try:
        penalty = player.tkLimitedKit[kit]
    except:
        return False

    if not penalty:
        return False
    elif rcore.now() >= penalty:
        player.tkLimitedKit[kit] = None
        if rdebug.isDebugEnabled('penalty'):
            rdebug.debugMessage('removed ' + player.getName() + ' penalty for tk ' + kit, 'penalty')
        return False
    else:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(player.getName() + ' is ' + kit + ' kit teamkiller', 'kits')
        return True


def isKitReservable(team, squad, kit):
    if not team or not squad or kit not in spawnableKits or kit in unlimitedKits:
        return False
    return True


def isKitReserved(team, squad, kit):
    global g_kits_squads_selects
    if not isKitReservable(team, squad, kit):
        return False
    selected = g_kits_squads_selects[team][squad][kit]
    if len(selected) == 0:
        return False
    limit = getKitLimitSquad(kit)
    if not limit:
        return False
    elif len(selected) < limit:
        return False
    else:
        return True


def isKitReservedByPlayer(team, squad, kit, player):
    if not isKitReservable(team, squad, kit):
        return False
    selected = g_kits_squads_selects[team][squad][kit]
    if len(selected) == 0:
        return False
    return player.index in selected


def isKitSelectable(player, kit, current = True, allocation = True):
    if not kit or kit not in spawnableKits or player.isAIPlayer():
        return True
    if realityserver.C('KIT_FACTION_LOCKED') != 1:
        return True
    team = player.getTeam()
    squad = player.getSquadId()
    if not validTeamKit(team, kit):
        return True
    if not isValidKit(player, kit, current, allocation, False, False):
        return False
    if not isKitReservedByPlayer(team, squad, kit, player) and isKitReserved(team, squad, kit):
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' kit is not valid for ' + player.getName() + ' - currently reserved', 'kits')
        player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_TOOMANYINSQUAD
        return False
    return True


def isValidKit(player, kit, current = True, allocation = True, messages = True, checkSquadAllocation = True):
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('check valid kit ' + kit + ' for ' + player.getName(), 'kits')
    if not player:
        return False
    team = player.getTeam()
    teamName = rcore.getTeamName(team)
    if not validSquadChange(player, kit):
        player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_NEWTOSQUAD
        if messages:
            rcore.sendMessageToPlayer(player, 3212201)
        return False
    if not player.dead and current:
        try:
            playerKit = getKitTypeString(player.getKit().templateName)
            if playerKit == kit:
                if rdebug.isDebugEnabled('kits'):
                    rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - requesting current kit', 'kits')
                if messages:
                    rcore.sendMessageToPlayer(player, 2190303)
                return False
        except:
            pass

    if not validSquadNumbers(player, kit, messages):
        return False
    if allocation:
        if not validTeamAllocation(player, kit, messages):
            return False
        if not validSquadAllocation(player, kit, messages, checkSquadAllocation):
            return False
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage(str(kit) + ' kit valid for ' + player.getName(), 'kits')
    return True


spawnableKits = ['sniper',
 'marksman',
 'aa',
 'at',
 'support',
 'officer',
 'tanker',
 'pilot',
 'riflemanat',
 'assault',
 'engineer',
 'medic',
 'riflemanap',
 'specialist',
 'rifleman',
 'mg',
 'spotter',
 'insurgent1',
 'insurgent2',
 'insurgent3',
 'insurgent4',
 'sapper']
teamkilledKits = ['medic']
unlimitedKits = ['officer',
 'tanker',
 'pilot',
 'rifleman',
 'insurgent1',
 'insurgent2',
 'insurgent3',
 'insurgent4',
 'sapper']
unlockedPickupKits = ['unarmed', 'pickup_camera']
vehicleKits = ['tanker', 'pilot']
kitNames = {'sniper': rlocalization.t('kits_sniper'),
 'marksman': rlocalization.t('kits_marksman'),
 'aa': rlocalization.t('kits_aa'),
 'at': rlocalization.t('kits_at'),
 'support': rlocalization.t('kits_support'),
 'specialist': rlocalization.t('kits_specialist'),
 'officer': rlocalization.t('kits_officer'),
 'tanker': rlocalization.t('kits_crewman'),
 'pilot': rlocalization.t('kits_pilot'),
 'engineer': rlocalization.t('kits_engineer'),
 'medic': rlocalization.t('kits_medic'),
 'riflemanat': rlocalization.t('kits_riflemanat'),
 'assault': rlocalization.t('kits_assault'),
 'sapper': rlocalization.t('kits_sapper'),
 'riflemanap': rlocalization.t('kits_riflemanap'),
 'mg': rlocalization.t('kits_mg'),
 'spotter': rlocalization.t('kits_spotter')}

def init():
    global g_kitrequest_objects
    g_kitrequest_objects = rcore.ObjectSet()
    host.registerGameStatusHandler(onGameStatusChanged)
    findLostKits.init()
    host.registerHandler('PickupFirstKit', onPickupInvalidSelectKit)
    host.registerHandler('PickupKit', onPickupTeamKilledKit)
    host.registerHandler('PickupKit', onPickupKit)
    host.registerHandler('DropKit', onDropKit)
    host.registerHandler('RemoteCommandKitRequest', onRemoteKitRequestCommand)
    host.registerHandler('RemoteCommandDrop', onRemoteDropCommand)
    host.registerHandler('ConsoleSendCommand', onConsoleSendCommand, 1)
    host.registerHandler('RemoteCommandCustomKit', onCustomKitSelect)
    host.registerHandler('RemoteCommandSelectKit', onKitSelected)
    host.registerHandler('PlayerSpawn', onPlayerSpawn)
    host.registerHandler('ExitVehicle', onExitVehicle)
    host.registerHandler('PlayerKilled', onPlayerKilled)
    host.registerHandler('PlayerDeath', onPlayerDeath)
    host.registerHandler('PlayerChangeTeams', onPlayerChangeTeams)
    host.registerHandler('PlayerChangedSquad', onPlayerChangedSquad)
    host.registerHandler('ChangedCommander', onChangedCommander)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    host.registerHandler('PlayerDisconnect', onPlayerDisconnect, 1)
    host.registerHandler('PlayerRevived', onPlayerRevived, 1)
    host.registerHandler('RemoteCommandCamera', onRemoteCameraCommand)
    host.registerHandler('RemoteCommandNinja', onRemoteNinjaCommand)
    host.registerHandler('RemoteCommandKits', onRemoteKitsCommand)
    host.registerHandler('RemoteCommandOneFaction', onRemoteOneFactionCommand)
    revents.registerObjectSpawnedCallback(addKitRequestObject)
    revents.registerObjectSpawnedCallback(kitSpawned)
    rtimer.repeatingTask(checkLockedKits, 10)
    print 'realitykits.py initialized'


def onGameStatusChanged(status):
    global g_kits_used
    global g_mapid
    global g_kits_reset_timer
    global g_kits_wrong
    global g_kits_allocated
    global g_kits_dropped
    if status == bf2.GameStatus.Loaded:
        mapid = '%s|%s|%s' % (rcore.getMapName(), rcore.getGameMode(), rcore.getMapLayer())
        if g_mapid != mapid:
            g_mapid = mapid
            for player in bf2.playerManager.getPlayers():
                player.customSelection = {1: [0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0],
                 2: [0,
                     0,
                     0,
                     0,
                     0,
                     0,
                     0]}

        setupKitLimits()
        g_kits_used = {}
        g_kits_wrong = {}
        g_kits_allocated = {}
        g_kits_dropped = {}
        g_expected_kits.clear()
        for team in [1, 2]:
            g_kits_squads[team] = {}
            g_kits_squads_selects[team] = {}
            for kit in spawnableKits:
                if kit in realityserver.C('KIT_LIMIT_44'):
                    g_kits_used[getKitTemplate(kit, team)] = 0
                    g_kits_allocated[getKitTemplate(kit, team)] = []
                    g_kits_dropped[getKitTemplate(kit, team)] = []

            for squad in range(1, 10):
                g_kits_squads[team][squad] = {}
                g_kits_squads_selects[team][squad] = {}
                for kit in spawnableKits:
                    g_kits_squads[team][squad][kit] = []
                    g_kits_squads_selects[team][squad][kit] = []

        g_kits_reset_timer = rtimer.Timer(resetKits, 1, 1, '')
    elif status == bf2.GameStatus.Playing:
        rtimer.fireOnce(initializeMapKitRequestAssets, 4)
    elif status == bf2.GameStatus.EndGame:
        destroyKitResetTimer()
        g_kits_used.clear()
        g_kits_allocated.clear()
        g_kits_dropped.clear()
        g_kits_squads.clear()
        g_kits_squads_selects.clear()
        g_kits_variants.clear()
        g_kits_wrong.clear()
        g_kits_limits.clear()
        g_kits_limits_factions.clear()
        g_kits_limits_squads.clear()
        g_kitrequest_templates.clear()


def onPickupInvalidSelectKit(player, kit):
    if realityserver.isCoopServer():
        return
    if player.spawnKitOverridden:
        return
    team = player.getTeam()
    squad = player.getSquadId()
    kit = getKitTypeString(kit.templateName)
    if not player.selectedKit:
        player.selectedKit = kit
    if not player.selectedKit or player.selectedKit == kit:
        return
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage(str(kit) + ' is not valid kit for ' + player.getName() + ' - selected kit is not ' + str(player.selectedKit), 'kits')
    rcore.setInvalidKit(player)


def onPickupTeamKilledKit(player, kit):
    if realityserver.C('KIT_PICKUP_ANY') != 1:
        return
    try:
        if isKitTeamkiller(player, getKitTypeString(kit.templateName)) > 0:
            if rdebug.isDebugEnabled('penalty'):
                rdebug.debugMessage('die teamkiller bastard', 'penalty')
            rcore.killPlayer(player)
    except:
        pass


def onPickupLockedKit(player, kit):
    if realityserver.C('KIT_FACTION_LOCKED') != 1:
        return False
    try:
        k = getKitTypeString(kit.templateName, True)
        team = k.split('_')[0]
        temp = k.split('_')[1]
    except:
        return False

    if team == rcore.getTeamName(player.getTeam()):
        return False
    if rgamemode.getCurrentGameModeType() == 'insurgency' and rgamemode.getCurrentGameMode().isInsurgent(player):
        if team != rcore.getTeamName(rcore.getOtherTeam(player.getTeam())):
            return False
    if temp in unlockedPickupKits:
        return False
    g_kits_wrong[player.index] = rcore.now()
    rtimer.fireOnce(checkLockedKits, 0.25, player)
    return True


def onDropLockedKit(player, kit):
    try:
        if player.index in g_kits_wrong:
            del g_kits_wrong[player.index]
            if not player.killed:
                rcore.clearScreen(player)
            return True
    except:
        pass

    return False


def onPickupKit(player, kit):
    if player.isAIPlayer():
        return
    if onPickupLockedKit(player, kit):
        return
    tmp = kit.templateName
    kit = getKitTypeString(tmp, True)
    if kit not in g_kits_used:
        return
    g_kits_used[kit] += 1
    if getKitsDropped(kit) > 0:
        g_kits_dropped[kit].pop()
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('%s removed from ground - total %s' % (kit, getKitsDropped(kit)), 'kits')
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('%s pickup by %s team %s (%s) - %s' % (kit,
         player.getName(),
         player.getTeam(),
         g_kits_used[kit],
         tmp), 'kits')


def onPlayerRevived(revivedP, medicP):
    if revivedP.isAIPlayer():
        return
    else:
        rcore.clearScreen(revivedP)
        if revivedP.lastKit is not None:
            rtimer.fireOnce(pickUpKitUnsafe, 0.1, (revivedP, revivedP.lastKit))
        return


def onDropKit(player, kit):
    if player.isAIPlayer():
        return
    player.lastKit = kit
    if onDropLockedKit(player, kit):
        return
    tmp = kit.templateName
    kit = getKitTypeString(tmp, True)
    if kit not in g_kits_used:
        return
    g_kits_used[kit] -= 1
    if kit in g_kits_dropped:
        g_kits_dropped[kit].append(rcore.now() + 300)
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('%s added to ground - total %s' % (kit, getKitsDropped(kit)), 'kits')
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('%s drop by %s team %s (%s) - %s' % (kit,
         player.getName(),
         player.getTeam(),
         g_kits_used[kit],
         tmp), 'kits')


def initializeMapKitRequestAssets(args):
    global mapSupplyTemplates
    global mapSupplyVehicleKits
    mapSupplyTemplates = {1: {},
     2: {}}
    mapSupplyVehicleKits = {}
    for vehicle in rvehicles_settings.getVehicleSettingsOfMap():
        kits = vehicle.getRequiredKits()
        for kit in kits:
            if kit not in mapSupplyVehicleKits:
                mapSupplyVehicleKits[kit] = {1: {},
                 2: {}}
            template = vehicle.getTemplate()
            for team in [1, 2]:
                mapSupplyVehicleKits[kit][team][template] = (CONSTANTS.DISTANCE_PICKUP * 3) ** 2
                g_kitrequest_templates.add(template)

    for team in [1, 2]:
        teamName = rcore.getTeamName(team)
        for template in realityserver.C('KIT_SUPPLY_OBJECTS_VEHICLES').get(teamName, []):
            mapSupplyTemplates[team][template] = CONSTANTS.DISTANCE_PICKUP ** 2
            g_kitrequest_templates.add(template)

        for template in realityserver.C('KIT_SUPPLY_OBJECTS').get(teamName, []):
            mapSupplyTemplates[team][template] = realityserver.C('KIT_SUPPLY_OBJECTS')[teamName][template] ** 2
            g_kitrequest_templates.add(template)

        for template in realityserver.C('KIT_SUPPLY_OBJECTS_OPEN').get(teamName, []):
            mapSupplyTemplates[team][template] = realityserver.C('KIT_SUPPLY_OBJECTS_OPEN')[teamName][template] ** 2
            g_kitrequest_templates.add(template)

    if not rmemory.isWindowsListenServer:
        import _realitymemory
        for template in g_kitrequest_templates:
            revents.registerObjectSpawnedTemplate(template.lower())
            _realitymemory.addProjectileCreatedTemplate(template.lower(), addKitRequestObjectProj)

        supplies = bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.SupplyObject')
        PCOs = bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.PlayerControlObject')
        for obj in supplies:
            addKitRequestObject(obj)

        for obj in PCOs:
            addKitRequestObject(obj)


def onRemoteKitRequestCommand(player, cmd, args):
    rtimer.task(onRemoteKitRequestCommand_task, -1000.0, (player, cmd, args))


def onRemoteKitRequestCommand_task(args):
    player, cmd, args = args
    if not player.isValid():
        return
    if len(args) == 0:
        return
    kit = args[0].strip()
    alt = len(args) > 1 and args[1].strip() == 'alt'
    if rcore.isInsideVehicle(player) or rcore.isClimbing(player):
        return
    if player.lastKitAllocation and rcore.now() - player.lastKitAllocation <= realityserver.C('KIT_REQUEST_INTERVAL'):
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - too soon to request again ' + str(rcore.now() - player.lastKitAllocation) + ' < ' + str(realityserver.C('KIT_REQUEST_INTERVAL')), 'kits')
        return rcore.sendMessageToPlayer(player, 3241213)
    if not isKitRequestable(player, kit):
        return
    playerVehicle = player.getDefaultVehicle()
    if not playerVehicle:
        return
    playerPosition = playerVehicle.getPosition()
    team = player.getTeam()
    SupplyTemplates = {}
    if kit in mapSupplyVehicleKits:
        SupplyTemplates.update(mapSupplyVehicleKits[kit][team])
    SupplyTemplates.update(mapSupplyTemplates[team])
    gm = rgamemode.getCurrentGameMode()
    if not gm.checkKitRequestRestrictions(kit, player):
        rcore.sendMessageToPlayer(player, 2020719)
        rdebug.debugMessage('Gamemode blocked kit request')
        return
    if rmemory.isWindowsListenServer:
        Supplies = rcore.getObjectsOfTemplates(SupplyTemplates, 'dice.hfe.world.ObjectTemplate.SupplyObject')
        for Supply in Supplies:
            template = Supply.templateName
            if validSupplyObject(playerPosition, Supply, template, team, SupplyTemplates[template], vehicle=False):
                rdebug.debugMessage('found close supplyobject:' + template, 'kits')
                if not payForKitFromCrate(Supply, kit):
                    continue
                spawnKitforPlayer(player, kit, alt)
                return

        PCOs = rcore.getObjectsOfTemplates(SupplyTemplates, 'dice.hfe.world.ObjectTemplate.PlayerControlObject')
        for PCO in PCOs:
            template = PCO.templateName
            if validSupplyObject(playerPosition, PCO, template, team, SupplyTemplates[template], vehicle=True):
                rdebug.debugMessage('found close PCO:' + template, 'kits')
                spawnKitforPlayer(player, kit, alt)
                return

    else:
        for obj in g_kitrequest_objects.getObjects():
            if obj.templateName not in SupplyTemplates:
                continue
            template = obj.templateName
            if validSupplyObject(playerPosition, obj, template, team, SupplyTemplates[template], vehicle=obj.isPlayerControlObject == 1):
                if rcore.getObjectType(obj.templateName).lower() == 'supplyobject':
                    if not payForKitFromCrate(obj, kit):
                        continue
                rdebug.debugMessage('found close kitsupply obj:' + template, 'kits')
                spawnKitforPlayer(player, kit, alt)
                return

    if validCommandPostRequest(playerPosition, team, kit):
        spawnKitforPlayer(player, kit, alt)
        return
    rcore.sendMessageToPlayer(player, 1190601, 1)


KITAMMOCOST = {'rifleman': 250}
KITAMMOCOST_DEFAULT = 250

def payForKitFromCrate(crate, kitName):
    current = rmemory.getSupplyCrateAmmo(crate)
    kitType = getKitTypeString(kitName)
    cost = KITAMMOCOST.get(kitType, KITAMMOCOST_DEFAULT)
    remains = current - cost
    rmemory.setSupplyCrateAmmo(crate, remains)
    rdebug.debugMessage('paid %s supplies from %s for kit %s, remaining %s' % (cost,
     crate.templateName,
     kitName,
     remains), 'kits')
    return True


def isKitRequestable(player, kit, current = True, allocation = True):
    if not kit or kit not in spawnableKits:
        return False
    team = player.getTeam()
    squad = player.getSquadId()
    if squad == 0 and not player.isCommander():
        return rcore.sendMessageToPlayer(player, 3240301)
    if not validTeamKit(team, kit) or rcore.getTeamName(team) in realityserver.C('KIT_REQUEST_BLOCK'):
        return rcore.sendMessageToPlayer(player, 3240703)
    if not isValidKit(player, kit, current, allocation):
        return False
    if not isKitReservedByPlayer(team, squad, kit, player) and isKitReserved(team, squad, kit):
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' kit is not valid for ' + player.getName() + ' - currently reserved', 'kits')
        return rcore.sendMessageToPlayer(player, 2191319)
    return True


def spawnKitforPlayer(player, kit, alt):
    try:
        playerPos = player.getDefaultVehicle().getPosition()
        team = player.getTeam()
    except:
        return

    spawnerKit(player, playerPos, getKitTemplate(kit, team, True, alt), team)
    addKitAllocation(player, kit)


def onRemoteDropCommand(player, cmd, args):
    if player.killed:
        return
    team = player.getTeam()
    gm = rgamemode.getCurrentGameMode()
    kit = rcore.getTeamName(team) + '_unarmed'
    if not gm.checkKitRequestRestrictions(player, kit):
        rdebug.debugMessage('Gamemode blocked kit request')
        return rcore.sendMessageToPlayer(player, 2020719)
    if player.lastUnarmedDropKit and rcore.now() - player.lastUnarmedDropKit <= realityserver.C('KIT_REQUEST_INTERVAL'):
        return rcore.sendMessageToPlayer(player, 1031121, 1)
    try:
        playerPos = player.getDefaultVehicle().getPosition()
    except:
        return

    spawnerKit(player, playerPos, kit, team)
    player.lastUnarmedDropKit = rcore.now()


def onConsoleSendCommand(cmd, args):
    if cmd == 'initkit':
        onKitInit(cmd, args)
        return
    if cmd == 'initvariants':
        onVariantsInit(cmd, args)
        return


def onKitInit(cmd, args):
    team = int(args[0])
    kitIndex = int(args[1])
    kitSlot = KitSlot()
    kitSlot.Primary = args[2]
    kitSlot.Secondary = args[3]
    kitSlot.Soldier = args[4]
    if rcore.getGameMode() == 'vehicles':
        kitSlot.LimitationsEnabled = False
    else:
        kitSlot.LimitationsEnabled = True
    if kitSlot.Primary.find('_') != -1:
        kitSlot.Name = kitSlot.Primary.split('_')[1]
    rdebug.debugMessage('set kitslot %s %s to %s' % (team, kitIndex, kitSlot.Primary))
    g_kits_slots[team][kitIndex] = kitSlot


def onVariantsInit(cmd, args):
    team = int(args[0])
    faction = args[1]
    variantString = ''
    for variant in getFactionVariants(faction):
        variantString += '_' + variant

    g_kits_variants[team] = variantString


def onCustomKitSelect(player, cmd, args):
    if not player.isValid() or player.isAIPlayer():
        return
    team = player.getTeam()
    player.customSelection[team][int(args[0])] = int(args[1])


def onKitSelected(player, cmd, args):
    if not player.isValid() or player.isAIPlayer():
        return
    try:
        slot = int(args[0].strip())
    except:
        return

    team = player.getTeam()
    squad = player.getSquadId()
    inherit = False
    kit = getKitSlot(team, slot)
    if isKitReservedByPlayer(team, squad, player.selectedKit, player):
        removeKitReservations(player)
        inherit = rcore.copy(player.selectedKit)
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('------ %s selected kit %s team %s squad %s' % (player.getName(),
         kit,
         team,
         squad), 'kits')
    player.selectedKit = kit
    checkSelectedKit(player)
    if inherit:
        checkSelectedKitSquad(team, squad, inherit, player)


def onPlayerSpawn(player, soldier):
    if player.isAIPlayer():
        return
    if not rgamemode.getCurrentGameMode().overrideModifySpawn(player):
        modifySpawn(player)
        player.spawnKitOverridden = False
    else:
        player.spawnKitOverridden = True
    player.lastUnarmedDropKit = rcore.now() - realityserver.C('KIT_REQUEST_INTERVAL') + 15
    times = True
    if player.selectedKit in unlimitedKits:
        times = False
    addKitAllocation(player, player.selectedKit, times)


def onPlayerChangeTeams(player, human):
    player.oldTeam = rcore.getOtherTeam(player.getTeam())
    removeKitReservations(player)
    onPlayerConnect(player)
    rcore.SpawnBlockHandler.continueSpawnTime(player, 'kit')
    player.selectedKit = getKitSlot(player.getTeam())
    checkSelectedKit(player)


def onPlayerConnect(player):
    player._kit_spawnblockreason = None
    cached = rcore.getPlayerByIndex(player.index)
    if not cached:
        return
    else:
        cached.customSelection = {1: [0,
             0,
             0,
             0,
             0,
             0,
             0],
         2: [0,
             0,
             0,
             0,
             0,
             0,
             0]}
        cached.allocatedKit = None
        cached.lastKitAllocation = None
        cached.lastUnarmedDropKit = None
        cached.tkLimitedKit = {}
        cached.selectedKit = None
        cached.spawnKitOverridden = False
        return


def onPlayerDisconnect(player):
    team = player.getTeam()
    squad = player.getSquadId()
    kit = player.selectedKit
    index = player.index
    try:
        removeKitReservations(player)
    except:
        pass

    player.customSelection = {}
    player.allocatedKit = None
    player.lastKitAllocation = None
    player.lastUnarmedDropKit = None
    player.tkLimitedKit = {}
    player.selectedKit = None
    return


def onPlayerTeamKilled(victim, attacker, weapon, assists, obj):
    if realityserver.C('KIT_TK_PENALTY') == 0:
        return
    team = attacker.getTeam()
    teamName = rcore.getTeamName(team)
    try:
        victimKit = getKitTypeString(victim.getKit().templateName)
        attackerKit = getKitTypeString(attacker.getKit().templateName)
    except:
        return

    if victimKit in teamkilledKits:
        return
    try:
        if weapon:
            weaponName = weapon.templateName.lower()
        else:
            weaponName = attacker.getVehicle().templateName.lower()
    except:
        weaponName = ''

    if weaponName in rscoring.WEAPONS_NO_PUNISH:
        return
    try:
        if len(attacker.tkLimitedKit):
            pass
    except:
        attacker.tkLimitedKit = {}

    if rdebug.isDebugEnabled('penalty'):
        rdebug.debugMessage(attacker.getName() + ' penalized for tk ' + victimKit, 'penalty')
    attacker.tkLimitedKit[victimKit] = rcore.now() + realityserver.C('KIT_TK_PENALTY')


def onExitVehicle(player, vehicle):
    player.lastUnarmedDropKit = rcore.now() - realityserver.C('KIT_REQUEST_INTERVAL') + 15


def onPlayerKilled(victim, attacker, weapon, assists, obj):
    victim.lastKit = None
    return


def onPlayerDeath(player, vehicle):
    checkSelectedKit(player)


def onChangedCommander(team, oldCmd, newCmd):
    if newCmd:
        checkSelectedKit(newCmd)
    if oldCmd:
        checkSelectedKit(oldCmd)


def onPlayerChangedSquad(player, oldSquad, newSquad):
    if player.isAIPlayer():
        return
    if oldSquad:
        removeKitReservations(player)
        checkSelectedKitSquad(player.getTeam(), oldSquad)
    if newSquad:
        checkSelectedKitSquad(player.getTeam(), newSquad)
    checkSelectedKit(player)


def onRemoteCameraCommand(player, cmd, args):
    if player.killed:
        return
    try:
        playerPos = player.getDefaultVehicle().getPosition()
    except:
        return

    spawnerKit(player, playerPos, 'pickup_camera', player.getTeam())
    rdebug.debugMessage('camera kit deployed', 'kits')
    
def pilotKit(player,team):
    if player.killed:
        return
    try:
        playerPos = player.getDefaultVehicle().getPosition()
    except:
        return
    if str(rcore.getMapName()) == 'test_airfield':
        if team == 1:
            spawnerKit(player, playerPos, 'ch_pilot', player.getTeam())
            return True
        elif team == 2:
            spawnerKit(player, playerPos, 'gb_pilot', player.getTeam())
            return True
    else:
        return False


def onRemoteOneFactionCommand(player, cmd, args):
    if realityserver.C('KIT_FACTION_LOCKED') == 1:
        realityserver.C('KIT_FACTION_LOCKED', 0)
        rdebug.debugMessage('kit faction requirements system disabled...')
    else:
        realityserver.C('KIT_FACTION_LOCKED', 1)
        rdebug.debugMessage('kit faction requirements system enabled...')


def onRemoteKitsCommand(player, cmd, args):
    if player.killed:
        return
    else:
        try:
            team = int(args[0])
            if team not in (1, 2):
                team = player.getTeam()
        except:
            team = player.getTeam()

        teamName = rcore.getTeamName(team)
        if teamName not in realityserver.C('KIT_LIMITS'):
            return
        kits = []
        for _type in realityserver.C('KIT_LIMITS')[teamName].keys():
            kits.append(getKitTemplate(_type, team, True))
            kits.append(getKitTemplate(_type, team, True, True))

        if teamName == 'meinsurgent':
            meinsurgentKitTypes = ['insurgent1',
             'insurgent2',
             'insurgent3',
             'insurgent4',
             'sapper',
             'aa_pickup',
             'engineer_pickup',
             'marksman_pickup',
             'sniper_alt_pickup',
             'sniper_pickup',
             'support_alt_pickup',
             'support_pickup',
             'riflemanat_pickup']
            for _type in meinsurgentKitTypes:
                kits.append(getKitTemplate(_type, team))

        else:
            for _type in ['rifleman']:
                kits.append(getKitTemplate(_type, team, True))
                kits.append(getKitTemplate(_type, team, True, True))

        kits.sort()
        final = []
        for kit in kits:
            if kit not in final:
                final.append(kit)

        count = 2
        for kit in final:
            if rdebug.isDebugEnabled('kits'):
                rdebug.debugMessage('spawning kit %s' % kit, 'kits')
            spawnerKit(None, rcore.getPositionFromPlayer(player, count), kit, team, sound=False, rconkits=True)
            count += 2

        return


def onRemoteNinjaCommand(player, cmd, args):
    if player.killed:
        return
    tmp = 'pickup_ninja'
    try:
        if int(args[0].strip()) == 1:
            tmp += '_alt, _sp'
    except:
        pass

    try:
        playerPos = player.getDefaultVehicle().getPosition()
    except:
        return

    spawnerKit(player, playerPos, tmp, player.getTeam())
    rdebug.debugMessage('ninja kit deployed', 'kits')


def destroyKitResetTimer():
    global g_kits_reset_timer
    try:
        if g_kits_reset_timer:
            g_kits_reset_timer.destroy()
            g_kits_reset_timer = None
    except:
        pass

    return


def resetKits(data = ''):
    destroyKitResetTimer()
    try:
        for player in rcore.getPlayers():
            onPlayerConnect(player)
            checkSelectedKit(player)

    except:
        pass


def checkLockedKits(forPlayer = None):
    if not rcore.roundStarted():
        return
    else:
        for index, times in g_kits_wrong.items():
            player = rcore.getPlayerByIndex(index)
            if forPlayer is not player and forPlayer is not None:
                continue
            if not player or player.killed:
                try:
                    if index in g_kits_wrong:
                        del g_kits_wrong[index]
                except:
                    pass

                continue
            rcore.sendMessageToPlayer(player, 1191819, 3)
            if not times:
                rcore.killPlayer(player)
            elif rcore.now() - times > 5:
                g_kits_wrong[index] = None
                rcore.blackScreen(player)

        return


def setupKitLimits():
    defaults = {8: realityserver.C('KIT_LIMIT_8'),
     16: realityserver.C('KIT_LIMIT_16'),
     24: realityserver.C('KIT_LIMIT_24'),
     32: realityserver.C('KIT_LIMIT_32'),
     44: realityserver.C('KIT_LIMIT_44')}
    g_kits_limits.clear()
    g_kits_limits_factions.clear()
    g_kits_limits_squads.clear()
    for team in [1, 2]:
        g_kits_limits[team] = {}
        for num in defaults.keys():
            g_kits_limits[team][num] = {}
            for kit, limit in defaults[num].items():
                g_kits_limits[team][num][kit] = limit

    for team in realityserver.C('KIT_LIMITS').keys():
        g_kits_limits_factions[team] = {}
        for kit, num in realityserver.C('KIT_LIMITS')[team].items():
            g_kits_limits_factions[team][kit] = num

    for kit, num in realityserver.C('KIT_LIMITS_SQUAD').items():
        g_kits_limits_squads[kit] = num

    map_name = rcore.getMapName()
    if map_name not in realityserver.C('KIT_LIMITS_MAPOVERRIDE'):
        return
    for team_number in [1, 2]:
        team_name = rcore.getTeamName(team_number)
        layerstr = 'gpm_%s_%i_team_%i' % (rcore.getGameMode(), rcore.getMapLayer(), team_number)
        if layerstr not in realityserver.C('KIT_LIMITS_MAPOVERRIDE')[map_name]:
            continue
        team_override = realityserver.C('KIT_LIMITS_MAPOVERRIDE')[map_name][layerstr]
        for kit in team_override:
            g_kits_limits_factions[team_name][kit] = team_override[kit]


def addKitAllocation(player, kit, times = True):
    if not kit or kit not in spawnableKits or player.isAIPlayer():
        return
    team = player.getTeam()
    squad = player.getSquadId()
    player.allocatedKit = kit
    if times:
        player.lastKitAllocation = rcore.now()
    if kit in unlimitedKits:
        return
    addTeamAllocation(team, kit)
    addSquadAllocation(team, squad, kit)
    event = revents.getEvents('KitAllocated')
    revents.sendToHandlers(event, player, kit)


def addTeamAllocation(team, kit):
    template = getKitTemplate(kit, team)
    if template not in g_kits_allocated:
        return
    delay = 0
    if kit in realityserver.C('KIT_ALLOCATION_DELAY'):
        delay = int(realityserver.C('KIT_ALLOCATION_DELAY')[kit])
    if delay:
        g_kits_allocated[template].append(rcore.now() + delay)
    g_kits_dropped[template].append(rcore.now() + 300)
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('added kit team allocation %s team %s' % (template, team), 'kits')


def addSquadAllocation(team, squad, kit):
    if not squad or kit not in realityserver.C('KIT_LIMITS_SQUAD') or not getKitLimitSquad(kit):
        return
    delay = 0
    if kit in realityserver.C('KIT_ALLOCATION_DELAY'):
        delay = int(realityserver.C('KIT_ALLOCATION_DELAY')[kit])
    if delay:
        g_kits_squads[team][squad][kit].append(rcore.now() + delay)
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('added kit squad allocation %s team %s squad %s' % (kit, team, squad), 'kits')


def addKitReservation(team, squad, kit, player):
    if isKitReservable(team, squad, kit) and not isKitReservedByPlayer(team, squad, kit, player):
        g_kits_squads_selects[team][squad][kit].append(player.index)
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('addded reservation %s kit %s team %s squad %s' % (player.getName(),
             kit,
             team,
             squad), 'kits')


def removeKitReservations(player):
    for team in [1, 2]:
        for squad in range(1, 10):
            for kit in spawnableKits:
                removeKitReservation(team, squad, kit, player)


def removeKitReservation(team, squad, kit, player):
    if isKitReservable(team, squad, kit) and isKitReservedByPlayer(team, squad, kit, player):
        g_kits_squads_selects[team][squad][kit].remove(player.index)
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('removed reservation %s kit %s team %s squad %s' % (player.getName(),
             kit,
             team,
             squad), 'kits')


def checkSelectedKitSquad(team, squad, kit = None, player = None):
    for p in rcore.getPlayersOfSquad(team, squad, player):
        if kit and p.selectedKit and p.selectedKit != kit:
            continue
        checkSelectedKit(p)


def checkSelectedKit(player):
    if player.isAIPlayer():
        return
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('--- check %s selected kit %s' % (player.getName(), player.selectedKit), 'kits')
    team = player.getTeam()
    squad = player.getSquadId()
    kit = player.selectedKit
    if isKitSelectable(player, kit):
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' kit is selectable by ' + player.getName(), 'kits')
        if player.dead:
            rcore.SpawnBlockHandler.continueSpawnTime(player, 'kit')
        addKitReservation(team, squad, kit, player)
    else:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' kit is not selectable by ' + player.getName(), 'kits')
        if player.dead:
            rcore.SpawnBlockHandler.pauseSpawnTime(player, player._kit_spawnblockreason)
        removeKitReservation(team, squad, kit, player)


def validTeamKit(team, kit):
    teamName = rcore.getTeamName(team)
    if teamName not in realityserver.C('KIT_LIMITS') or kit not in realityserver.C('KIT_LIMITS')[teamName]:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is not valid team kit for ' + teamName, 'kits')
        return False
    else:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is valid team kit for ' + teamName, 'kits')
        return True


def validSquadChange(player, kit):
    if realityserver.C('KIT_SQUAD_DELAY') == 0:
        return True
    if hasattr(player, 'oldTeam') and player.oldTeam != player.getTeam():
        rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - different team for last squad change', 'kits')
        return True
    if hasattr(player, 'changedSquad') and player.changedSquad and kit not in unlimitedKits:
        delta = rcore.now() - player.changedSquad
        if delta < realityserver.C('KIT_SQUAD_DELAY'):
            if rdebug.isDebugEnabled('kits'):
                rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - squad change', 'kits')
            return False
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - old last squad change', 'kits')
    return True


def validSquadNumbers(player, kit, messages = True):
    if kit in ('officer',) and player.isCommander():
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - he is the commander', 'kits')
        return True
    elif kit in ('officer',) and not player.isCommander() and not player.isSquadLeader():
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - he is not a squad leader or commander', 'kits')
        if messages:
            rcore.sendMessageToPlayer(player, 2190318)
        player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_NOTSQUADLEADER
        return False
    else:
        neededSquadMembers = getKitLimitFaction(rcore.getTeamName(player.getTeam()), kit)
        if neededSquadMembers is None:
            if messages:
                rcore.sendMessageToPlayer(player, 3240703)
            player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_SQUADTOOSMALL
            return False
        elif neededSquadMembers == 0:
            if rdebug.isDebugEnabled('kits'):
                rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - it is not limited by squad number', 'kits')
            return True
        numSquadMembers = rcore.numPlayersInSquad(player)
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('check squad numbers - %s members %s needed' % (numSquadMembers, neededSquadMembers), 'kits')
        elif numSquadMembers < neededSquadMembers:
            if rdebug.isDebugEnabled('kits'):
                rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - not enough squad members', 'kits')
            if messages:
                rcore.sendSquadRequirementMessageToPlayer(player, neededSquadMembers)
            if numSquadMembers == 0:
                player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_NOTINSQUAD
            else:
                player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_SQUADTOOSMALL
            return False
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - good squad number', 'kits')
        return True


def validSquadAllocation(player, kit, messages = True, checkIssued = True):
    if kit not in realityserver.C('KIT_LIMITS_SQUAD'):
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - no squad allocation needed', 'kits')
        return True
    limit = getKitLimitSquad(kit)
    if not limit:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - no squad allocation needed', 'kits')
        return True
    issued = 0
    used = 0
    team = player.getTeam()
    squad = player.getSquadId()
    try:
        issued = getKitsAllocatedSquad(team, squad, kit)
    except:
        pass

    if issued <= limit:
        for member in rcore.getPlayersInSquad(player):
            if member.killed or player.isAIPlayer():
                continue
            try:
                if kit == getKitTypeString(member.getKit().templateName):
                    used += 1
            except:
                pass

    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage('check squad limits - %s issued %s used %s limit' % (issued, used, limit), 'kits')
    if checkIssued and issued >= limit or used >= limit:
        if rdebug.isDebugEnabled('kits'):
            if used >= limit:
                rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - squad usage', 'kits')
            if issued >= limit:
                rdebug.debugMessage(str(kit) + ' is not valid for ' + player.getName() + ' - squad allocation ', 'kits')
        if messages:
            rcore.sendMessageToPlayer(player, 2191319)
        player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_TOOMANYINSQUAD
        return False
    if rdebug.isDebugEnabled('kits'):
        rdebug.debugMessage(str(kit) + ' is valid for ' + player.getName() + ' - good squad allocation', 'kits')
    return True


def validTeamAllocation(player, kit, messages = True):
    team = player.getTeam()
    limit = getKitLimit(team, kit)
    _kit = getKitTemplate(kit, team)
    if limit is None:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(_kit) + ' is valid for ' + player.getName() + ' - unlimited kit', 'kits')
        return True
    elif limit < 1:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(_kit) + ' is not valid for ' + player.getName() + ' - unavailable for team right now', 'kits')
        if messages:
            rcore.sendMessageToPlayer(player, 2020719)
        player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_UNAVAILABLEFORTEAM
        return False
    else:
        try:
            used = g_kits_used[_kit]
        except:
            used = 0

        try:
            allocated = getKitsAllocated(_kit)
        except:
            allocated = 0

        try:
            used += getKitsDropped(_kit)
        except:
            pass

        if used > allocated:
            num = used
        else:
            num = allocated
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('check team allocation - %s used %s allocated %s limit' % (used, allocated, limit), 'kits')
        if num >= limit:
            if rdebug.isDebugEnabled('kits'):
                rdebug.debugMessage(str(_kit) + ' is not valid for ' + player.getName() + ' - team allocation', 'kits')
            if messages:
                rcore.sendMessageToPlayer(player, 2191608)
            player._kit_spawnblockreason = rcore.SpawnBlockHandler.SPAWNBLOCKED_KIT_TOOMANYINTEAM
            return False
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage(str(_kit) + ' is valid for ' + player.getName() + ' - good team allocation', 'kits')
        return True


def validCommandPostRequest(pos, team, kit):
    cmdPost = rcore.getCommandPost(team)
    if cmdPost:
        try:
            if rcore.getSquareVectorDistance(cmdPost.getPosition(), pos) < CONSTANTS.DISTANCE_SPAWN ** 2:
                rdebug.debugMessage('next to command post', 'kits')
                return True
        except:
            return False


def validSupplyObject(pos, o, template, team, dist, vehicle = False):
    try:
        if rdebug.isDebugEnabled('kits'):
            rdebug.debugMessage('checking name %s dist %s' % (o.templateName, dist), 'kits')
        if not o.isValid():
            return False
        if hasattr(o, 'getIsWreck') and o.getIsWreck():
            return False
        if o.getPosition() == (0, 0, 0):
            return False
        if hasattr(o, 'getTeam'):
            oTeam = o.getTeam()
            if oTeam != 0 and oTeam != team:
                return False
    except Exception as e:
        rdebug.debugMessage('validsupplyobject ' + str(e))
        return False

    if vehicle and template not in realityserver.C('KIT_SUPPLY_OBJECTS_VEHICLES_SIDEDOORS'):
        if rcore.getSquareVectorVehicleDistance(o.getRotation(), o.getPosition(), pos) < dist:
            return True
    elif rcore.getSquareVectorDistance(o.getPosition(), pos) < dist:
        return True


def kitSpawned(obj):
    if obj.templateName.lower() not in g_expected_kits:
        return
    try:
        player = g_expected_kits[obj.templateName].pop()
        if len(g_expected_kits[obj.templateName]) == 0:
            del g_expected_kits[obj.templateName]
        rtimer.fireOnce(pickUpKitUnsafe, 0.1, (player, obj))
    except:
        pass


def pickUpKitUnsafe(args):
    """
    Unsafe. Do not call this during event handling.
    It is safe for timer callbacks.
    @param args:
    @return:
    """
    player, obj = args
    try:
        if player.getKit() is not obj:
            rmemory.pickUpKit(player, obj)
    except:
        pass


def listenServerGetSpawnedKit(args):
    player, pos, template = args
    if template.lower() not in g_expected_kits:
        return
    else:
        kits = rcore.getObjectsOfTemplates((template,), 'dice.hfe.world.ObjectTemplate.Kit')
        kit = rcore.findClosestObj(pos, kits)
        if kit is None:
            return
        try:
            player = g_expected_kits[template].pop()
            if len(g_expected_kits[template]) == 0:
                del g_expected_kits[template]
            pickUpKitUnsafe((player, kit))
        except:
            pass

        return


def spawnerKit(player, position, template, team, sound = True, rconkits = False):
    if player is None and not rconkits:
        return
    else:
        template = template.lower()
        yoffset = -1.0
        spawnPos = (position[0], position[1] + yoffset, position[2])
        if not rconkits:
            if not rmemory.isWindowsListenServer:
                spawnPos = (0, 5000, 0)
                revents.registerObjectSpawnedTemplate(template)
            else:
                rtimer.fireOnce(listenServerGetSpawnedKit, 0.1, (player, position, template))
            if template in g_expected_kits:
                g_expected_kits[template].append(player)
            else:
                g_expected_kits[template] = [player]
        rdebug.debugMessage('Spawned kit template is %s' % str(template))
        properties = {'team': team,
         'timeToLive': '300',
         'distance': '0',
         'damageWhenLost': '',
         'template': template,
         'position': spawnPos,
         'rotation': (0, 0, 0)}
        rspawner.createSpawner(template + '_spawner_%s' % str(int(position[0]) + int(position[1]) + int(position[2])), properties)
        if not rconkits:
            if sound:
                rcore.playSoundForPlayer(player, 0)
            rmemory.setKitTimeStampNow(player, extratime=0.25)
        return


def spawnPlayerKit(player, typ):
    try:
        position = player.getDefaultVehicle().getPosition()
    except:
        return

    template = getKitTemplate(typ, player.getTeam())
    spawnerKit(player, position, template, player.getTeam())


def modifySpawn(player):
    team = player.getTeam()
    for kitIndex in range(7):
        if g_kits_slots[team][kitIndex] is None:
            continue
        kit = g_kits_slots[team][kitIndex].Primary
        if player.customSelection[team][kitIndex] == 1:
            kit = g_kits_slots[team][kitIndex].Secondary
        soldier = g_kits_slots[team][kitIndex].Soldier
        if kit == 'empty':
            continue
        host.rcon_invoke('gameLogic.setKit %s %s %s %s' % (team,
         kitIndex,
         kit,
         soldier))

    return


class findLostKits:

    @classmethod
    def init(cls):
        host.registerHandler('DropKit', cls._onDropKitFindLostKit)

    @classmethod
    def _onDropKitFindLostKit(cls, p, kit):
        soldier = p.getDefaultVehicle()
        if soldier.getParent() is not None:
            return
        else:
            rtimer.fireNextTick(cls._onDropNextTick, (soldier.getPosition(), kit))
            return

    @classmethod
    def _onDropNextTick(cls, args):
        soldierPos, kit = args
        if not kit.isValid():
            return
        elif kit.getParent() is not None:
            return
        else:
            kitPos = kit.getPosition()
            if kitPos == (0, 0, 0):
                return
            distY = soldierPos[1] - kitPos[1]
            if distY < 3.0:
                return
            kit.setPosition((soldierPos[0], soldierPos[1] - 1.0, soldierPos[2]))
            rdebug.debugMessage('Fixing kit position for %s, distance %s' % (kit.templateName, distY), 'kits')
            return


def kitExists(kitName):
    """
    returns True if the kit template exists, otherwise False
    :param kitName: str(kit template)
    :return: bool True|False
    """
    host.rcon_invoke('ObjectTemplate.active %s' % kitName)
    if 'kit' in host.rcon_invoke('ObjectTemplate.type').lower():
        return True
    return False


def getAltObjectExists(kitName):
    """
     <faction>_<type>_alt_<suffix>
    :param kitName: a kit template name
    :return: None if alt kit not found, or str(kitname) if found
    """
    variant = getKitTeamVariants(getKitTeam(kitName))
    if variant is None:
        variant = 'alt'
    else:
        variant = 'alt%s' % variant
    kit = '%s_%s' % (kitName, variant)
    if kitExists(kit):
        return kit
    else:
        return