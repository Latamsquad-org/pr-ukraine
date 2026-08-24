# FPV launch from a fully built sandbag bunker (command_bunker mesh).
# Press E inside the emplacement to spawn fpv_drone 10 m above, then enter it.
# Exit the drone to teleport back inside the bunker.
import bf2
import host
import realityadmin as radmin
import realitycore as rcore
import realitydebug as rdebug
import realityevents as revents
import realitymemory as rmemory
import realityspawner as rspawner
import realitytimer as rtimer

BUNKER_TEMPLATES = ('deployable_sandbags_5m', 'deployable_sandbags_5m_sp')
DRONE_TEMPLATE = 'fpv_drone'
PCO_TYPE = 'dice.hfe.world.ObjectTemplate.PlayerControlObject'
# Interior offset in bunker local space (meters).
INTERIOR_OFFSET = (0.0, -1.0, 0.0)
# Spawn the drone this many meters above the bunker origin (world up).
SPAWN_HEIGHT = 10.0
# Consider the emplacement built when HP is at least this ratio of maxHitPoints.
BUILT_HP_RATIO = 0.85
# Ignore a new E on the bunker right after returning from the drone.
REENTER_COOLDOWN = 2.0
# 20 m radius: spawn is 10 m up, claim must still find the drone.
DRONE_MATCH_DIST_SQ = 400.0
# Stand a bit above the wreck origin so the soldier is not buried in debris.
WRECK_STAND_Y = 1.0

g_pending = {}
g_flying = {}
g_cooldown = {}
g_spawn_id = 0


def init():
    host.registerGameStatusHandler(_onGameStatusChanged)
    host.registerHandler('EnterVehicle', _onEnterVehicle, 1)
    host.registerHandler('ExitVehicle', _onExitVehicle, 1)
    host.registerHandler('VehicleDestroyed', _onVehicleDestroyed, 1)
    host.registerHandler('AssetRemoved', _onAssetRemoved, 1)
    host.registerHandler('PlayerDeath', _onPlayerDeath, 1)
    host.registerHandler('PlayerDisconnect', _onPlayerDisconnect, 1)
    rtimer.repeatingTask(_watchBunkers, 0.5)
    if not rmemory.isWindowsListenServer:
        revents.registerObjectSpawnedTemplate(DRONE_TEMPLATE)
        revents.registerObjectSpawnedCallback(_onObjectSpawned)
    rdebug.debugMessage('latambunkerfpv initialized', 'gameplay')


def _onGameStatusChanged(status):
    if status == bf2.GameStatus.EndGame:
        g_pending.clear()
        g_flying.clear()
        g_cooldown.clear()


def _root(obj):
    if obj is None:
        return None
    try:
        return bf2.objectManager.getRootParent(obj)
    except:
        return obj


def _templateName(obj):
    if obj is None:
        return ''
    try:
        return obj.templateName.lower()
    except:
        return ''


def _isBunker(obj):
    return _templateName(_root(obj)) in BUNKER_TEMPLATES


def _isDrone(obj):
    return _templateName(_root(obj)) == DRONE_TEMPLATE


def _worldOffset(obj, offset):
    pos = obj.getPosition()
    rot = obj.getRotation()
    world = rcore.quaternionRotateVector3d(rot, offset)
    return rcore.vectorAddition(pos, world)


def _airSpawnPos(bunker):
    # World-up, not bunker-local: keeps the drone in the air even if the mesh is rotated.
    pos = bunker.getPosition()
    return (pos[0], pos[1] + SPAWN_HEIGHT, pos[2])


def _sameObj(a, b):
    if a is None or b is None:
        return False
    if a is b:
        return True
    try:
        return rcore.getObjectId(a) == rcore.getObjectId(b)
    except:
        return False


def _isBunkerDead(bunker):
    if bunker is None:
        return True
    try:
        if not bunker.isValid():
            return True
    except:
        return True
    try:
        if bunker.getIsWreck():
            return True
    except:
        pass
    hp = None
    try:
        hp = bunker.getDamage()
    except:
        hp = None
    if hp is not None and hp <= 0:
        return True
    return False


def _wreckStandPos(data):
    bunker = data.get('bunker')
    try:
        if bunker is not None and bunker.isValid():
            pos = bunker.getPosition()
            return (pos[0], pos[1] + WRECK_STAND_Y, pos[2])
    except:
        pass
    origin = data.get('origin')
    if origin is not None:
        return (origin[0], origin[1] + WRECK_STAND_Y, origin[2])
    interior = data.get('interior')
    if interior is not None:
        return (interior[0], interior[1] + 2.0, interior[2])
    return None


def _isBuilt(bunker):
    if bunker is None or not bunker.isValid():
        return False
    hp = bunker.getDamage()
    if hp is None or hp < 0:
        return False
    try:
        maxhp = float(bunker.getTemplateProperty('armor.maxHitPoints'))
    except:
        maxhp = 600.0
    if maxhp <= 0:
        return False
    return hp >= (maxhp * BUILT_HP_RATIO)


def _playerKey(player):
    return player.index


def _clearPlayer(player):
    key = _playerKey(player)
    g_pending.pop(key, None)
    g_flying.pop(key, None)


def _onEnterVehicle(player, vehicle, freeSoldier=False):
    if player is None or not player.isValid() or player.isAIPlayer():
        return
    if not player.isAlive() or player.isManDown():
        return
    root = _root(vehicle)
    # Boarding the drone during launch: lock flying state and never send another E.
    if _isDrone(root):
        key = _playerKey(player)
        pending = g_pending.get(key)
        if pending is not None:
            pending['use_sent'] = 1
            _markFlying(key, pending, root)
        return
    if not _isBunker(root):
        return
    bunker = root
    now = host.timer_getWallTime()
    last = g_cooldown.get(_playerKey(player), 0)
    if now < last:
        _eject(player)
        return
    if not _isBuilt(bunker):
        radmin.personalMessage('Termina de palear el emplazamiento primero.', player)
        _eject(player)
        return
    if bunker.getTeam() and player.getTeam() != bunker.getTeam():
        _eject(player)
        return
    _startLaunch(player, bunker)


def _startLaunch(player, bunker):
    key = _playerKey(player)
    interior = _worldOffset(bunker, INTERIOR_OFFSET)
    roof = _airSpawnPos(bunker)
    rot = bunker.getRotation()
    origin = bunker.getPosition()
    g_pending[key] = {
        'player': player,
        'bunker': bunker,
        'origin': origin,
        'interior': interior,
        'roof': roof,
        'rotation': (rot[0], 0.0, 0.0),
        'started': host.timer_getWallTime(),
        'bunker_ejected': 1,
        'use_sent': 0,
    }
    # Leave the bunker seat immediately so the interior camera is only a blink.
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
    _spawnDrone(player, bunker, roof, rot)
    rtimer.fireOnce(_tryEnterDrone, 0.2, key)
    rtimer.fireOnce(_tryEnterDrone, 0.5, key)
    rtimer.fireOnce(_tryEnterDrone, 0.9, key)
    rtimer.fireOnce(_tryEnterDrone, 1.4, key)
    rtimer.fireOnce(_tryEnterDrone, 2.0, key)
    rtimer.fireOnce(_expireLaunch, 4.0, key)


def _spawnDrone(player, bunker, roof, rot):
    global g_spawn_id
    g_spawn_id += 1
    name = 'fpv_drone_bunker_%s_%s' % (g_spawn_id, player.index)
    props = {
        'team': str(player.getTeam()),
        'template': DRONE_TEMPLATE,
        'position': roof,
        'rotation': (rot[0], 0.0, 0.0),
        'timeToLive': '0',
        'distance': '0',
    }
    if rmemory.isWindowsListenServer:
        rtimer.fireOnce(_findListenDrone, 0.5, _playerKey(player))
    else:
        revents.registerObjectSpawnedTemplate(DRONE_TEMPLATE)
    rspawner.createSpawner(name, props)
    rdebug.debugMessage('Spawned bunker FPV spawner %s' % name, 'gameplay')


def _onObjectSpawned(obj):
    root = _root(obj)
    if not _isDrone(root):
        return
    if getattr(root, 'latam_bunker_fpv', None):
        return
    _claimDrone(root)


def _findListenDrone(key):
    pending = g_pending.get(key)
    if pending is None:
        return
    drones = rcore.getObjectsOfTemplate(DRONE_TEMPLATE, PCO_TYPE)
    roof = pending['roof']
    for drone in drones:
        root = _root(drone)
        if getattr(root, 'latam_bunker_fpv', None):
            continue
        if rcore.getSquareVectorDistance(root.getPosition(), roof) <= DRONE_MATCH_DIST_SQ:
            _assignDrone(pending['player'], root, pending)
            return


def _claimDrone(drone):
    best = None
    bestDist = None
    pos = drone.getPosition()
    for pending in g_pending.values():
        dist = rcore.getSquareVectorDistance(pos, pending['roof'])
        if dist > DRONE_MATCH_DIST_SQ:
            continue
        if bestDist is None or dist < bestDist:
            best = pending
            bestDist = dist
    if best is None:
        return
    _assignDrone(best['player'], drone, best)


def _markFlying(key, pending, drone):
    g_flying[key] = {
        'player': pending['player'],
        'bunker': pending['bunker'],
        'origin': pending.get('origin'),
        'interior': pending['interior'],
        'drone': drone,
    }
    g_pending.pop(key, None)


def _assignDrone(player, drone, pending):
    if player is None or not player.isValid():
        return
    drone.latam_bunker_fpv = 1
    pending['drone'] = drone
    # Team is set by the spawner ('team' in props). Vehicle objects have
    # getTeam but not setTeam; calling setTeam logs AttributeError.
    try:
        drone.setPosition(pending['roof'])
        drone.setRotation(pending['rotation'])
    except:
        rdebug.errorMessage()
    _tryEnterDrone(_playerKey(player))


def _tryEnterDrone(key):
    pending = g_pending.get(key)
    if pending is None:
        return
    player = pending['player']
    drone = pending.get('drone')
    if player is None or not player.isValid() or not player.isAlive() or player.isManDown():
        _clearPlayer(player)
        return
    if drone is None or not drone.isValid():
        return
    current = _root(player.getVehicle())
    air = pending['roof']
    if _isDrone(current):
        # Already in. Do not setPosition: moving an occupied vehicle kicks the player out.
        _markFlying(key, pending, drone)
        return
    # Leave the bunker seat first. setPosition on a seated soldier does not move the camera.
    if _isBunker(current):
        now = host.timer_getWallTime()
        retry = (now - pending.get('started', now)) > 0.7 and not pending.get('bunker_eject_retry')
        if not pending.get('bunker_ejected') or retry:
            if retry:
                pending['bunker_eject_retry'] = 1
            pending['bunker_ejected'] = 1
            rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
        return
    soldier = player.getDefaultVehicle()
    if soldier is None or not soldier.isValid():
        return
    if soldier is not player.getVehicle():
        if not pending.get('bunker_ejected'):
            pending['bunker_ejected'] = 1
            rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
        return
    try:
        drone.setPosition(air)
        drone.setRotation(pending['rotation'])
        soldier.setPosition(air)
    except:
        rdebug.errorMessage()
        return
    if pending.get('use_sent'):
        return
    pending['use_sent'] = 1
    rtimer.fireOnce(_pressUseEnterDrone, 0.05, player)


def _pressUseEnterDrone(player):
    # E toggles enter/exit. Never send it if the player is already in the drone.
    if player is None or not player.isValid():
        return
    current = _root(player.getVehicle())
    if _isDrone(current):
        return
    if _playerKey(player) in g_flying:
        return
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)


def _pressUse(player):
    if player is None or not player.isValid():
        return
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)


def _expireLaunch(key):
    pending = g_pending.pop(key, None)
    if pending is None:
        return
    player = pending.get('player')
    if player is not None and player.isValid() and player.isAlive():
        current = _root(player.getVehicle())
        if _isBunker(current):
            _eject(player)
        elif not _isDrone(current):
            _teleportInside(player, pending.get('interior'))
    _cleanupDrone(pending.get('drone'))


def _eject(player):
    rtimer.fireOnce(_pressUse, 0.05, player)


def _onExitVehicle(player, vehicle):
    if player is None or not player.isValid():
        return
    key = _playerKey(player)
    root = _root(vehicle)
    if key in g_pending and _isBunker(root):
        # Leaving the bunker seat while launching the drone.
        return
    if not _isDrone(root):
        return
    # Kicked out of the drone before flying state was locked: do not leave them in the sky.
    pending = g_pending.pop(key, None)
    if pending is not None:
        g_cooldown[key] = host.timer_getWallTime() + REENTER_COOLDOWN
        _teleportInside(player, pending.get('interior'))
        _cleanupDrone(pending.get('drone'))
        return
    flying = g_flying.pop(key, None)
    if flying is None:
        return
    g_cooldown[key] = host.timer_getWallTime() + REENTER_COOLDOWN
    interior = flying.get('interior')
    bunker = flying.get('bunker')
    if flying.get('recalling'):
        interior = _wreckStandPos(flying)
    elif bunker is not None and bunker.isValid() and not _isBunkerDead(bunker):
        interior = _worldOffset(bunker, INTERIOR_OFFSET)
    elif bunker is None or _isBunkerDead(bunker):
        interior = _wreckStandPos(flying)
    _teleportInside(player, interior)
    _cleanupDrone(flying.get('drone'))


def _teleportInside(player, interior):
    if interior is None:
        return
    if player is None or not player.isValid() or not player.isAlive() or player.isManDown():
        return

    def _move(args):
        p, target = args
        if p is None or not p.isValid() or not p.isAlive() or p.isManDown():
            return
        soldier = p.getDefaultVehicle()
        if soldier is None or not soldier.isValid():
            return
        if soldier is not p.getVehicle():
            return
        try:
            soldier.setPosition(target)
        except:
            rdebug.errorMessage()

    _move((player, interior))
    rtimer.fireOnce(_move, 0.05, (player, interior))
    rtimer.fireOnce(_move, 0.2, (player, interior))
    rtimer.fireOnce(_move, 0.6, (player, interior))
    rtimer.fireOnce(_move, 1.0, (player, interior))


def _cleanupDrone(drone):
    if drone is None or not drone.isValid():
        return
    if not getattr(drone, 'latam_bunker_fpv', None):
        return
    try:
        # Move far away. Never kill it: death detonates C4 and turns the bunker into dummy/wreck.
        drone.setPosition((0.0, -500.0, 0.0))
    except:
        rdebug.errorMessage()


def _onAssetRemoved(typ, team, obj):
    if typ != 'sandbags':
        return
    _onBunkerGone(_root(obj))


def _watchBunkers(args=None):
    for key, flying in list(g_flying.items()):
        if flying.get('recalling'):
            continue
        if _isBunkerDead(flying.get('bunker')):
            _onBunkerGone(flying.get('bunker'), flying)
    for key, pending in list(g_pending.items()):
        if _isBunkerDead(pending.get('bunker')):
            _onBunkerGone(pending.get('bunker'))


def _onBunkerGone(bunker, flyingHint=None):
    for key, flying in list(g_flying.items()):
        if flying.get('recalling'):
            continue
        if flyingHint is flying:
            _recallFromDestroyedBunker(key, flying)
            continue
        if bunker is not None and _sameObj(flying.get('bunker'), bunker):
            _recallFromDestroyedBunker(key, flying)
    for key, pending in list(g_pending.items()):
        if bunker is not None and _sameObj(pending.get('bunker'), bunker):
            _cancelPendingToWreck(key, pending)
            continue
        if flyingHint is None and _isBunkerDead(pending.get('bunker')):
            _cancelPendingToWreck(key, pending)


def _recallFromDestroyedBunker(key, flying):
    flying['recalling'] = 1
    wreck = _wreckStandPos(flying)
    flying['interior'] = wreck
    player = flying.get('player')
    g_cooldown[key] = host.timer_getWallTime() + REENTER_COOLDOWN
    if player is None or not player.isValid() or not player.isAlive() or player.isManDown():
        g_flying.pop(key, None)
        _cleanupDrone(flying.get('drone'))
        return
    rdebug.debugMessage('Bunker destroyed, recalling FPV player', 'gameplay')
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
    rtimer.fireOnce(_pressUse, 0.1, player)
    rtimer.fireOnce(_pressUse, 0.3, player)
    rtimer.fireOnce(_finishRecall, 0.5, (key, player, wreck, flying.get('drone')))


def _finishRecall(args):
    key, player, wreck, drone = args
    g_flying.pop(key, None)
    if player is not None and player.isValid() and player.isAlive() and not player.isManDown():
        current = _root(player.getVehicle())
        if _isDrone(current) and wreck is not None:
            try:
                current.setPosition(wreck)
            except:
                rdebug.errorMessage()
            rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
        _teleportInside(player, wreck)
    _cleanupDrone(drone)


def _cancelPendingToWreck(key, pending):
    g_pending.pop(key, None)
    player = pending.get('player')
    wreck = _wreckStandPos(pending)
    if player is not None and player.isValid() and player.isAlive() and not player.isManDown():
        _eject(player)
        rtimer.fireOnce(_teleportAfterEject, 0.3, (player, wreck))
    _cleanupDrone(pending.get('drone'))


def _teleportAfterEject(args):
    player, wreck = args
    _teleportInside(player, wreck)


def _onVehicleDestroyed(vehicle, attacker):
    root = _root(vehicle)
    if _isBunker(root):
        _onBunkerGone(root)
        return
    if not _isDrone(root):
        return
    if not getattr(root, 'latam_bunker_fpv', None):
        return
    for key, flying in list(g_flying.items()):
        if flying.get('drone') is root:
            player = flying.get('player')
            g_flying.pop(key, None)
            g_cooldown[key] = host.timer_getWallTime() + REENTER_COOLDOWN
            if player is not None and player.isValid() and player.isAlive() and not player.isManDown():
                interior = flying.get('interior')
                bunker = flying.get('bunker')
                if bunker is not None and bunker.isValid() and not _isBunkerDead(bunker):
                    interior = _worldOffset(bunker, INTERIOR_OFFSET)
                else:
                    interior = _wreckStandPos(flying)
                _teleportInside(player, interior)


def _onPlayerDeath(victim, vehicle):
    if victim is None:
        return
    _clearPlayer(victim)


def _onPlayerDisconnect(player):
    if player is None:
        return
    _clearPlayer(player)
    g_cooldown.pop(_playerKey(player), None)
