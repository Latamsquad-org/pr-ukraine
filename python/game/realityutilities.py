# Embedded file name: realityutilities.py
import math
import random
import time
import _realitycore
import bf2
import host
import realityadmin as radmin
import realityconstants as rconstants
import realitycore as rcore
import realitydebug as rdebug
import realityevents as revents
import realitymemory as rmemory
import realityserver as rserver
import realityspawner as rspawner
import realitytimer as rtimer
import realityvehicles as rvehicles
import realityzones as rzones

def init():
    playerPreroundCameras.init()
    FPS.init()
    AntiGrief_FF.init()
    ProjectileHandler.init()
    Speedhack.init()
    StaminaHandler.init()
    DisableOutOfMapWarningForJets.init()
    DeviationOnSwitch.init()
    AutoMark_Mines()
    ReportSupplies.init()
    Teleporters()


class ReportSupplies:
    playersShowingSupplies = set()

    @classmethod
    def init(cls):
        if rmemory.isWindowsListenServer:
            return
        rtimer.repeatingTask(cls.refresh, 0.8)
        host.registerHandler('PlayerDisconnect', cls.playerDisconnect, 1)
        host.registerHandler('PlayerConnect', cls.playerConnect, 1)

    @classmethod
    def playerConnect(cls, player):
        cls.playersShowingSupplies.add(player)

    @classmethod
    def playerDisconnect(cls, player):
        cls.playersShowingSupplies.discard(player)

    @classmethod
    def refresh(cls, args = None):
        supplies = rcore.g_supply_objects.getObjects()
        cached = tuple(map(lambda s: (s, s.getPosition()), supplies))
        for player in bf2.playerManager.getPlayers():
            sol = player.getDefaultVehicle()
            veh = player.getVehicle()
            if sol is None or veh is not sol:
                cls.stop(player)
                continue
            pos = rcore.getPositionFromPlayer(player, 1.3)
            supply = None
            minimumSquared = 3.0
            for o in cached:
                posobj = o[1]
                if abs(posobj[0] - pos[0]) > 3:
                    continue
                currentdist = _realitycore.calcDistanceSquared(pos, posobj)
                if currentdist < minimumSquared:
                    minimumSquared = currentdist
                    supply = o[0]

            if supply is None:
                cls.stop(player)
            else:
                cls.send(player, rmemory.getSupplyCrateAmmo(supply))

        return

    @classmethod
    def send(cls, player, amount):
        cls.playersShowingSupplies.add(player)
        bf2.gameLogic.sendGameEvent(player, 10, 16 | (max(0, int(amount)) & 65535) << 16)

    @classmethod
    def stop(cls, player):
        if player not in cls.playersShowingSupplies:
            return
        cls.playersShowingSupplies.discard(player)
        bf2.gameLogic.sendGameEvent(player, 10, 16)


class DeviationOnSwitch:

    @classmethod
    def init(cls):
        if rmemory.isWindowsListenServer:
            return
        host.registerHandler('PlayerChangeWeapon', cls.playerChangeWeapon, 1)
        cls.switchMiscDevMod = 1.0
        cls.maxSwitchSpeedDevSettle = 0

    @classmethod
    def playerChangeWeapon(cls, player, oldWeapon, newWeapon):
        if newWeapon is None:
            return
        else:
            newDevComp = rmemory.getWeaponsDeviationComponent(newWeapon)
            if newDevComp is None:
                return
            newDevTemplate = newDevComp.template.contents
            if cls.switchMiscDevMod > 0:
                rdebug.debugMessage('misc before: %s' % newDevComp.deviationPenaltyMisc, 'deviation')
                newDevComp.deviationPenaltyMisc = cls.switchMiscDevMod * newDevTemplate.MiscDeviationMax
                rdebug.debugMessage('misc after: %s' % newDevComp.deviationPenaltyMisc, 'deviation')
            if oldWeapon is None:
                return
            if cls.maxSwitchSpeedDevSettle <= 0:
                return
            oldDevComp = rmemory.getWeaponsDeviationComponent(oldWeapon)
            relativeDev = 1.0
            if oldDevComp is not None:
                oldDevTemplate = oldDevComp.template.contents
                if oldDevTemplate is not None:
                    moveDeviation = oldDevComp.deviationPenaltySpeed
                    maxMoveSpeed = oldDevTemplate.SpeedDeviationMax
                    if maxMoveSpeed > 0:
                        relativeDev = moveDeviation / maxMoveSpeed
            rdebug.debugMessage('speed before: %s' % newDevComp.deviationPenaltySpeed, 'deviation')
            relativeDev = relativeDev * newDevTemplate.SpeedDeviationMax
            maxSettleDev = cls.maxSwitchSpeedDevSettle * newDevTemplate.SpeedDeviationSettle
            newDevComp.deviationPenaltySpeed = min(relativeDev, maxSettleDev)
            rdebug.debugMessage('speed after: %s' % newDevComp.deviationPenaltySpeed, 'deviation')
            return


class DisableOutOfMapWarningForJets:

    @classmethod
    def init(cls):
        rtimer.Timer(cls.refresh, 0.8, 1).setRecurring(0.8)
        radmin.addCommand('jetdod', cls.toggle, 777)

    @classmethod
    def toggle(cls, args, p):
        if hasattr(p, 'jetdod'):
            p.jetdod = not p.jetdod
        else:
            p.jetdod = True
        if p.jetdod:
            radmin.personalMessage('Enabled dod warning', p)
        else:
            radmin.personalMessage('Disabled dod warning', p)

    @classmethod
    def refresh(cls, arg = None):
        if rmemory.isWindowsListenServer:
            return
        for player in rvehicles.playersInJets:
            if hasattr(player, 'jetdod') and player.jetdod:
                continue
            rmemory.resetTimeOutsideWorld(player)


class ProjectileHandler:
    mines = set()

    @classmethod
    def init(cls):
        if rmemory.isWindowsListenServer:
            return
        import _realitymemory
        host.registerGameStatusHandler(cls.RoundStart)
        for projectileName in rconstants.mineTypeMap:
            _realitymemory.addProjectileCreatedTemplate(projectileName, cls.mineCreated)

        for projectileName in rconstants.rocketTypeMap:
            _realitymemory.addProjectileCreatedTemplate(projectileName, cls.rocketCreated)

        rtimer.repeatingTask(cls.deleteUnregisteredMines, 25.0)

    @classmethod
    def RoundStart(cls, status):
        if status != bf2.GameStatus.Playing:
            return
        cls.mines.clear()

    @classmethod
    def checkDeletion(cls, mine):
        if not mine.isValid() or mine.getPosition() == (0.0, 0.0, 0.0):
            cls.mines.remove(mine)
        elif hasattr(mine, 'pendingDeletion'):
            rdebug.debugMessage('Mine pending deletion deleted')
            rcore.deleteObject(mine)
            cls.mines.remove(mine)
        elif not hasattr(mine, 'player'):
            rdebug.debugMessage('Deleted an unknown mine')
            rcore.deleteObject(mine)
            cls.mines.remove(mine)
        elif not mine.player.isValid() or bf2.playerManager.getPlayerByIndex(mine.player.index) is not mine.player:
            rcore.deleteObject(mine)
            cls.mines.remove(mine)
            rdebug.debugMessage('Player %s disconnected - deleting his mines' % mine.player.index)

    @classmethod
    def deleteUnregisteredMines(cls, args = None):
        for mine in list(cls.mines):
            cls.checkDeletion(mine)

    @classmethod
    def rocketCreated(cls, weapon, proj):
        try:
            playerObject = rcore.getWeaponOwner(weapon)
            if playerObject is None:
                return
            proj.player = playerObject
            event = revents.getEvents('RocketCreated')
            revents.sendToHandlers(event, proj)
        except:
            rdebug.errorMessage()

        return

    @classmethod
    def mineCreated(cls, weapon, mine):
        try:
            playerObject = rcore.getWeaponOwner(weapon)
            if playerObject is None:
                return
            pos = mine.getPosition()
            distance = rzones.getDistanceFromMineDOD(pos)
            rdebug.debugMessage('Player %s placed mine %s, dod distance %s' % (playerObject.getName(), weapon.templateName, distance))
            mine.player = playerObject
            cls.mines.add(mine)
            if distance < -3:
                mine.pendingDeletion = True
                radmin.adminPM('El jugador %s puso una mina cerca del DOD, la mina ha sido borrada.' % playerObject.getName())
                radmin.personalMessage('Tu mina ha sido borrada. Estas muy cerca del DOD!', playerObject)
                rtimer.fireNextTick(cls.checkDeletion, mine)
            else:
                mine.player = playerObject
                event = revents.getEvents('MineCreated')
                revents.sendToHandlers(event, mine)
        except:
            rdebug.errorMessage()

        return


class AntiGrief_FF:
    isEarlyRound = True

    @classmethod
    def init(cls):
        if not rserver.isInternetServer():
            return
        host.registerGameStatusHandler(cls.RoundStart)
        host.registerHandler('PlayerTeamDamagePoint', cls.onDamage, 1)

    @classmethod
    def onDamage(cls, playerObject, victimObject):
        if cls.isEarlyRound:
            radmin.adminPM('%s in vehicle %s damaged friendly %s' % (playerObject.getName(), playerObject.getVehicle().templateName, victimObject.templateName))

    @classmethod
    def setFF(cls, amount):
        rdebug.debugMessage('Setting FF to %s' % amount)
        host.rcon_invoke('sv.soldierFriendlyFire %s' % amount)
        host.rcon_invoke('sv.vehicleFriendlyFire %s' % amount)
        host.rcon_invoke('sv.soldierSplashFriendlyFire %s' % amount)
        host.rcon_invoke('sv.vehicleSplashFriendlyFire %s' % amount)

    @classmethod
    def turnOnFF(cls, data = None):
        cls.setFF(100)
        host.rcon_invoke('scoreManager.setTeamDamageLimit 50')
        host.rcon_invoke('scoreManager.setTeamVehicleDamageLimit 25')
        cls.isEarlyRound = False

    @classmethod
    def RoundStart(cls, status):
        if status != bf2.GameStatus.Playing:
            return
        host.rcon_invoke('scoreManager.setTeamDamageLimit 2')
        host.rcon_invoke('scoreManager.setTeamVehicleDamageLimit 2')
        cls.setFF(100)
        cls.isEarlyRound = True
        rtimer.fireOnce(cls.turnOnFF, 80 + rserver.C('STARTDELAY'))


FPS_SAMPLESIZE = 220

class FPS:
    fps_counter = 0
    fps_starttime = 0
    fps_lasttime = 0
    times = []
    targetPlayers = set()
    reportSpikePlayers = set()
    isMeasuring = False

    @classmethod
    def init(cls):
        radmin.addCommand('fps', cls.startMeasure, 777)
        rtimer.perTickRegister(cls._tick)
        host.registerHandler('PlayerDisconnect', cls.playerDisconnect, 1)

    @classmethod
    def playerDisconnect(cls, player):
        cls.targetPlayers.discard(player)
        cls.reportSpikePlayers.discard(player)

    @classmethod
    def _tick(cls):
        currentTime = rdebug.clockFunc()
        thisTicksTime = (currentTime - cls.fps_lasttime) * 1000
        cls.fps_lasttime = currentTime
        if thisTicksTime > 70:
            for p in cls.reportSpikePlayers:
                radmin.personalMessage('Server lag: last tick was %sms ago' % round(thisTicksTime, 1), p, color=True)

        if not cls.isMeasuring:
            return
        cls.fps_counter += 1
        cls.times.append(thisTicksTime)
        if cls.fps_counter >= FPS_SAMPLESIZE:
            fps_current = FPS_SAMPLESIZE / (currentTime - cls.fps_starttime)
            cls.times.sort()
            sorted = map(lambda x: round(x, 1), cls.times[-8:])
            sorted.reverse()
            highframes = filter(lambda x: x > 70, sorted)
            outstring = 'SERVER STATUS - FPS: %s, Bad frames:' % fps_current
            outstring2 = str(highframes)
            for p in cls.targetPlayers:
                radmin.personalMessage(outstring, p, color=True)
                radmin.personalMessage(outstring2, p, color=True)

            cls.isMeasuring = False
            cls.targetPlayers = set()
            cls.fps_counter = 0

    @classmethod
    def startMeasure(cls, args, player):
        radmin.personalMessage('This is a measurement of the servers tick rate, not your client FPS.', player, color=True)
        if len(args) > 0 and args[0] == 'report':
            if player in cls.reportSpikePlayers:
                radmin.personalMessage('No longer reporting about frame spikes', player, color=True)
                cls.reportSpikePlayers.discard(player)
            else:
                radmin.personalMessage('now reporting about frame spikes', player, color=True)
                cls.reportSpikePlayers.add(player)
            return True
        cls.targetPlayers.add(player)
        if cls.isMeasuring:
            radmin.personalMessage('Measuring FPS...  (%s/%s)' % (cls.fps_counter, FPS_SAMPLESIZE), player)
            return True
        radmin.personalMessage('Starting measurement', player)
        cls.isMeasuring = True
        cls.times = []
        cls.fps_counter = 0
        cls.fps_starttime = rdebug.clockFunc()
        return True


class playerPreroundCameras:
    POS_NOWHERE = (0.0, 5000.0, 0.0)
    ROT_NOWHERE = (0.0, 0.0, 0.0)
    squadLockStatus = {}
    for team in (1, 2):
        squadLockStatus[team] = {}
        for squad in range(0, 10):
            squadLockStatus[team][squad] = False

    @classmethod
    def init(cls):
        if rmemory.isWindowsListenServer:
            return
        host.registerHandler('PlayerConnect', cls.onPlayerConnect, 1)
        host.registerHandler('RoundStart', cls.RoundStart, 1)

    @classmethod
    def movePlayers(cls, players, pos, rot = None):
        for player in players:
            cls.movePlayer(player, pos, rot)

    @classmethod
    def movePlayer(cls, player, pos, rot = None):
        veh = player.getVehicle()
        if veh is None:
            return
        elif veh.templateName.lower() != 'multiplayerfreecamera':
            return
        else:
            veh.setPosition(pos)
            if rot is not None:
                veh.setRotation(rot)
            return

    @classmethod
    def movePlayersSquad(cls, player, pos, rot = None):
        cls.movePlayers(rcore.getPlayersInSquad(player), pos, rot)

    @classmethod
    def onPlayerConnect(cls, player):
        if rcore.roundStarted():
            cls.movePlayer(player, cls.POS_NOWHERE)

    @classmethod
    def RoundStart(cls):
        rtimer.fireOnce(lambda x: cls.movePlayers(bf2.playerManager.getPlayers(), cls.POS_NOWHERE), 1)

    @classmethod
    def onRemoteCommandCamera(cls, player, cmd, args):
        if rcore.roundStarted():
            return
        if len(args) == 0:
            return
        cmd = args[0]
        args = args[1:]
        if cmd == 'move':
            cls.commandMoveRotate(player, cmd, args)
        elif cmd == 'rotate':
            cls.commandMoveRotate(player, cmd, args)
        elif cmd == 'squad':
            cls.commandSquad(player, cmd, args)
        elif cmd == 'flag':
            cls.commandFlag(player, cmd, args)

    MOVE = {'up': (0, 10, 0),
     'down': (0, -10, 0),
     'left': (-25, 0, 0),
     'right': (25, 0, 0),
     'forward': (0, 0, 25),
     'back': (0, 0, -25)}
    ROTATE = {'up': (0, -5, 0),
     'down': (0, 5, 0),
     'left': (-8, 0, 0),
     'right': (8, 0, 0)}

    @classmethod
    def commandMoveRotate(cls, player, cmd, args):
        isLocked = cls.squadLockStatus[player.getTeam()][player.getSquadId()]
        if isLocked and not player.isSquadLeader():
            return
        else:
            if len(args) == 1:
                direction, alt = args[0], ''
            elif len(args) == 2:
                direction, alt = args
            else:
                return
            isAlt = alt == 'alt'
            veh = player.getVehicle()
            if veh is None or veh.templateName.lower() != 'multiplayerfreecamera':
                return
            pos = veh.getPosition()
            rot = veh.getRotation()
            if cmd == 'move':
                if direction not in cls.MOVE:
                    return
                x, y, z = cls.MOVE[direction]
                if isAlt:
                    x, y, z = x * 7, y * 7, z * 7
                yaw = math.radians(rot[0])
                pos = (pos[0] + x * math.sin(yaw), pos[1] + y, pos[2] + z * math.cos(yaw))
            elif cmd == 'rotate':
                if direction not in cls.ROTATE:
                    return
                x, y, z = cls.ROTATE[direction]
                if isAlt:
                    x, y, z = x * 7, y * 7, z * 7
                rot = (rot[0] + x, rot[1] + y, rot[2] + z)
            else:
                return
            if isLocked:
                cls.movePlayersSquad(player, pos, rot)
            else:
                cls.movePlayer(player, pos, rot)
            return

    @classmethod
    def commandSquad(cls, player, cmd, args):
        if len(args) != 1:
            return
        if not player.isSquadLeader():
            return
        cls.squadLockStatus[player.getTeam()][player.getSquadId()] = args[0] == 'lock'

    @classmethod
    def commandFlag(cls, player, cmd, args):
        if len(args) != 1:
            return
        isLocked = cls.squadLockStatus[player.getTeam()][player.getSquadId()]
        if isLocked and not player.isSquadLeader():
            return
        isNext = args[0] == 'next'
        if not hasattr(player, 'preRoundCameraCurrentFlag'):
            player.preRoundCameraCurrentFlag = 0
        if isNext:
            player.preRoundCameraCurrentFlag += 1
        else:
            player.preRoundCameraCurrentFlag -= 1
        flags = rcore.getControlPoints()
        player.preRoundCameraCurrentFlag %= len(flags)
        pos = flags[player.preRoundCameraCurrentFlag].getPosition()
        pos = (pos[0], pos[1] + 80, pos[2])
        if isLocked:
            cls.movePlayersSquad(player, pos)
        else:
            cls.movePlayer(player, pos)

    @classmethod
    def SquadCreated(cls, player, team, squad, name):
        cls.squadLockStatus[team][squad] = False


class Speedhack:
    inputlog = None

    @classmethod
    def init(cls):
        rtimer.repeatingTask(cls.testInput, 0.6)

    @classmethod
    def getEngines(cls, obj, engines):
        for child in obj.getChildren():
            if rcore.getObjectType(child.templateName).lower() == 'engine':
                host.rcon_invoke('objectTemplate.active %s' % child.templateName)
                child.engineType = host.rcon_invoke('objectTemplate.engineType').strip().lower()
                if child.engineType == '194':
                    engines.append(child)
            cls.getEngines(child, engines)

        return engines

    @classmethod
    def testInput(cls, args = None):
        for v in rvehicles.getActiveVehicles():
            if not hasattr(v, 'tmp_engines'):
                v.tmp_engines = cls.getEngines(v, [])
            for engine in v.tmp_engines:
                if not engine.isValid():
                    return
                cengine = rmemory._getCObjectCasted(engine, rmemory.CEngine)
                x, y, z = cengine.inputx, cengine.inputy, cengine.inputz
                if abs(x) > 1.0 or abs(y) > 1.0 or abs(z) > 1.0:
                    player = None
                    for p in v.getOccupyingPlayers():
                        if p.getVehicle() == v:
                            player = p
                            break

                    if player is None:
                        continue
                    radmin.adminPM('Player %s was using bad inputs (Speedhack) and was kicked: %s,%s,%s' % (player.getName(),
                     x,
                     y,
                     z), display=True, history=False)
                    bf2.gameLogic.sendGameEvent(player, 11, 2)
                    rtimer.fireOnce(cls.delayedKick, 1.0, player)
                    fileName = host.sgl_getModDirectory() + '/badinputs.log'
                    inputlog = open(fileName, 'ab')
                    inputlog.write('[%s] %s,%s,%s, vehicle %s, player %s\n' % (time.strftime('%Y-%m-%d %H:%M'),
                     x,
                     y,
                     z,
                     v.templateName,
                     player.getName()))
                    inputlog.close()

        return

    @classmethod
    def delayedKick(cls, player):
        if player.isValid():
            radmin.kickPlayer(player)


class StaminaHandler:
    minDissipation = 0.1
    maxHP = 60
    minHP = 10
    minimumForStamina = 10
    exponent = 0.7
    defaultsCache = {}

    @classmethod
    def init(cls):
        host.registerHandler('PlayerRevived', cls.PlayerRevived, 1)
        host.registerHandler('PlayerSpawn', cls.PlayerSpawn, 1)
        rtimer.repeatingTask(cls.refresh, 2.5)

    @classmethod
    def PlayerSpawn(cls, player, soldier):
        soldier._lastDamage = 100.0

    @classmethod
    def PlayerRevived(cls, revivedPlayerObject, medicPlayerObject):
        soldier = revivedPlayerObject.getDefaultVehicle()
        if soldier is None:
            return
        else:
            rmemory.setSoldierStamina(soldier, 0.0)
            cls.refreshPlayer(revivedPlayerObject, forceRefresh=True)
            return

    @classmethod
    def refresh(cls, args = None):
        for player in bf2.playerManager.getPlayers():
            cls.refreshPlayer(player)

    @classmethod
    def refreshPlayer(cls, player, forceRefresh = False):
        soldier = player.getDefaultVehicle()
        if soldier is None:
            return
        else:
            damage = soldier.getDamage()
            if damage < cls.minimumForStamina:
                rmemory.setSoldierStamina(soldier, 0.0)
            if forceRefresh or abs(soldier._lastDamage - damage) > 5.0:
                soldier._lastDamage = damage
                defaults = cls.getDefaultSettings(soldier.templateName)
                if damage >= cls.maxHP:
                    x = 1.0
                elif damage <= cls.minHP:
                    x = 0.0
                else:
                    x = (damage - cls.minHP) / (cls.maxHP - cls.minHP)
                y = cls.minDissipation * (1 - x ** cls.exponent) + defaults['dissipation'] * x ** cls.exponent
                if rdebug.isDebugEnabled('gameplay'):
                    rdebug.debugMessage('Setting stamina for %s: %s' % (player.getName(), y))
                rmemory.setSoldierStaminaDissipation(soldier, y)
            return

    @classmethod
    def getDefaultSettings(cls, templateName):
        if templateName not in cls.defaultsCache:
            try:
                val = {'recovery': float(rcore.getTemplateProperty(templateName, 'SprintRecoverTime', 'soldier')),
                 'dissipation': float(rcore.getTemplateProperty(templateName, 'SprintDissipationTime', 'soldier')),
                 'limit': float(rcore.getTemplateProperty(templateName, 'SprintLimit', 'soldier'))}
            except:
                rdebug.debugMessage('could not get stamina times for %s' % templateName)
                val = {'recovery': 30,
                 'dissipation': 35,
                 'limit': 0.5}

            cls.defaultsCache[templateName] = val
        return cls.defaultsCache[templateName]


class BotGiveUpLogic:
    MEDIC_SEARCH_RADIUS_SQUARED = 1600
    woundedBots = set()

    @classmethod
    def init(cls):
        if not rserver.isCoopServer():
            return
        host.registerHandler('PlayerKilled', cls.onWounded, 1)
        host.registerHandler('PlayerDeath', cls.onNotWounded, 1)
        host.registerHandler('PlayerRevived', cls.onNotWounded, 1)
        host.registerGameStatusHandler(cls.roundStart)
        rtimer.repeatingTask(cls.botGiveUpThink, 7)

    @classmethod
    def roundStart(cls, status):
        cls.woundedBots.clear()

    @classmethod
    def onWounded(cls, player, a = None, b = None, c = None, d = None):
        if player.isAIPlayer():
            player._AILogic_deathtime = host.timer_getWallTime()
            cls.woundedBots.add(player)

    @classmethod
    def onNotWounded(cls, player, a = None, b = None, c = None, d = None):
        if player.isAIPlayer():
            cls.woundedBots.discard(player)

    @classmethod
    def collectPositions(cls, team):
        ret = []
        for p in bf2.playerManager.getPlayers():
            if p.getTeam() != team:
                continue
            kit = p.getKit()
            if kit is None:
                continue
            if 'medic' not in kit.templateName.lower():
                continue
            pos = cls.positionOrNone(p)
            if pos is None:
                continue
            ret.append(pos)

        return ret

    @classmethod
    def botGiveUpThink(cls, args = None):
        for team in [1, 2]:
            positions = cls.collectPositions(team)
            for bot in list(cls.woundedBots):
                if bot.getTeam() != team:
                    continue
                if not cls.arePositionsNearby(bot, positions):
                    rdebug.debugMessage('Bot %s giving up, no medics nearby' % bot.getName(), 'gameplay')
                    cls.giveUp(bot)

    @classmethod
    def arePositionsNearby(cls, player, teamMedicPositions):
        botpos = cls.positionOrNone(player)
        if botpos is None:
            return True
        else:
            for medicpos in teamMedicPositions:
                if rcore.getSquareVectorDistance(botpos, medicpos) < cls.MEDIC_SEARCH_RADIUS_SQUARED:
                    rdebug.debugMessage('Bot %s has medic nearby at %s' % (player.getName(), str(medicpos)), 'gameplay')
                    return True

            return False

    @staticmethod
    def positionOrNone(player):
        sol = player.getDefaultVehicle()
        if sol is None:
            return
        else:
            return sol.getPosition()

    @staticmethod
    def giveUp(player):
        soldier = player.getDefaultVehicle()
        if soldier:
            soldier.setDamage(0)
        player.setTimeToSpawn(0)


class AutoMark_Mines:
    """
    This class implements auto marking mines on the map for Project Reality.
    """

    def __init__(self):
        """
        Initialize AutoMark_Mines handlers and tasks
        """
        host.registerGameStatusHandler(self.onGameStatusChanged)
        if rmemory.isWindowsListenServer:
            rtimer.repeatingTask(self.listenServerPollMines, 3)
        else:
            host.registerHandler('MineCreated', self.playerPlacedMine)
        revents.registerObjectSpawnedCallback(self.getMinePCO)
        rtimer.repeatingTask(self.cleanOldMarkers, 5)
        self.mines = []
        self.dummy_pco_templates = set()
        self.automark_mine_types = [rconstants.PROJECTILE_TYPE_MINE_VICTIM_AP, rconstants.PROJECTILE_TYPE_MINE_VICTIM_AT]

    def onGameStatusChanged(self, status):
        """
        Handler to clear the list of mines and timers at game change
        """
        if status == bf2.GameStatus.Playing:
            self.mines = []

    def listenServerPollMines(self, args = None):
        for projectile in bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.GenericProjectile'):
            if hasattr(projectile, '_automark_checked'):
                continue
            if projectile.getPosition() == (0.0, 0.0, 0.0):
                continue
            projectile._automark_checked = True
            self.playerPlacedMine(projectile)

    def removeMinePCO(self, pco):
        """
        Clean up a mine marker from the map given the mine object
        """
        if pco.isValid():
            rcore.deleteObject(pco)

    def hideMinePCO(self, pco):
        if pco.isValid():
            pos = pco.getPosition()
            pco.setPosition((pos[0], 10000.0, pos[2]))

    def cleanOldMarkers(self, args = None):
        """
        Set a timer for mines that no longer exist to clean their markers up after a random interval
        """
        for mine in list(self.mines):
            pco = mine.dummy_pco
            if not mine.isValid() or pco is not None and not pco.isValid() or pco is not None and pco.getIsWreck():
                self.mines.remove(mine)
                if mine.isValid():
                    rcore.deleteObject(mine)
                if pco is None:
                    rdebug.debugMessage('Mine %s not valid and has no PCO assigned', 'markers')
                    return
                if not pco.isValid():
                    rdebug.debugMessage('Mine %s and its PCO not valid', 'markers')
                    return
                interval = random.randint(1200, 2400)
                rtimer.fireOnce(self.removeMinePCO, interval, data=pco)
                rtimer.fireOnce(self.hideMinePCO, 2.5, data=pco)
                rdebug.debugMessage('setting timer to delete marker in ' + str(interval) + ' seconds', 'markers')
            elif pco is not None:
                pco.setPosition(mine.getPosition())

        return

    def playerPlacedMine(self, mineObject):
        """
        MineCreated Handler to put a marker on the map when a player places a mine
        """
        if mineObject is None:
            return
        else:
            projectile_type = rconstants.getProjectileType(mineObject.templateName)
            if projectile_type not in self.automark_mine_types:
                return
            rtimer.fireOnce(self.spawnMinePCO, 1.25, mineObject)
            return

    def spawnMinePCO(self, mineObject):
        """
        Spawn a PCO for the newly created mine object
        @param mineObject:
        @return:
        """
        if not mineObject.isValid():
            rdebug.debugMessage('Mine %s not valid' % mineObject.templateName, 'markers')
            return
        else:
            mineObject.dummy_pco = None
            dummyTemplate = self.getDummyTemplate(mineObject.templateName)
            if rmemory.isWindowsListenServer:
                rtimer.fireOnce(self.listenServerGetPCO, 0.5, dummyTemplate)
                playerTeam = bf2.playerManager.getPlayerByIndex(255).getTeam()
            else:
                playerTeam = mineObject.player.getTeam()
            pos = mineObject.getPosition()
            rot = mineObject.getRotation()
            self.dummy_pco_templates.add(dummyTemplate)
            revents.registerObjectSpawnedTemplate(dummyTemplate)
            rspawner.createSpawner(dummyTemplate + '_spawner', {'team': str(playerTeam),
             'position': pos,
             'rotation': (rot[0], 0.0, 0.0)})
            rdebug.debugMessage('Spawning PCO for mine %s' % mineObject.templateName, 'markers')
            self.mines.append(mineObject)
            return

    def listenServerGetPCO(self, dummyTemplate):
        dummies = rcore.getObjectsOfTemplate(dummyTemplate, 'dice.hfe.world.ObjectTemplate.PlayerControlObject')
        dummies = filter(lambda dummy: not hasattr(dummy, 'mine'), dummies)
        for dummyPCO in dummies:
            self.getMinePCO(dummyPCO)

    def getMinePCO(self, dummy_pco):
        if dummy_pco.templateName not in self.dummy_pco_templates:
            return
        else:
            mines = filter(lambda mine: mine.dummy_pco is None, self.mines)
            mine = rcore.findClosestObj(dummy_pco.getPosition(), mines, minimumSquared=20)
            if mine is None:
                rdebug.debugMessage('Could not get a mine close enough to PCO %s' % dummy_pco.templateName, 'markers')
                return
            rdebug.debugMessage('Got PCO for mine %s' % dummy_pco.templateName, 'markers')
            rdebug.debugMessage('PCO at %s' % str(dummy_pco.getPosition()), 'markers')
            rdebug.debugMessage('Mine at %s' % str(mine.getPosition()), 'markers')
            mine.dummy_pco = dummy_pco
            dummy_pco.mine = mine
            return

    def getDummyTemplate(self, templateName):
        """
        Returns the dummy PCO template for the mine.
        @param templateName: template name of the mine the player placed
        @return:
        """
        templateName = templateName.lower()
        if 'at_mine_projectile' == templateName:
            return 'at_mine_projectile_dummy'
        elif 'argmin_fmk1_projectile' == templateName:
            return 'argmin_fmk1_projectile_dummy'
        elif 'argmin_fmk3_projectile' == templateName:
            return 'argmin_fmk3_projectile_dummy'
        elif 'at_mine_tm35_projectile' == templateName:
            return 'at_mine_tm35_projectile_dummy'
        elif 'insgr_hgr_trap_projectile' == templateName:
            return 'insgr_hgr_trap_projectile_dummy'
        elif 'insrg_watercontainer_ied_projectile' == templateName:
            return 'insrg_watercontainer_ied_projectile_dummy'
        elif 'rumin_pomz_projectile' == templateName:
            return 'rumin_pomz_projectile_dummy'
        elif 'rumin_tm35_projectile' == templateName:
            return 'rumin_tm35_projectile_dummy'
        elif 'tm62m_mine_projectile' == templateName:
            return 'tm62m_mine_projectile_dummy'
        elif 'tripflare_projectile' == templateName:
            return 'tripflare_projectile_dummy'
        elif 'usmin_m1a1_projectile' == templateName:
            return 'usmin_m1a1_projectile_dummy'
        elif 'usmin_m2a3_projectile' == templateName:
            return 'usmin_m2a3_projectile_dummy'
        elif 'vnhgr_betty_projectile' == templateName:
            return 'vnhgr_betty_projectile_dummy'
        else:
            return 'marker_mines'


import re

class Teleporters:
    teleports = {}
    task = None

    class Teleport:

        def __init__(self, pos, id):
            self.pos = pos
            self.id = id
            self.target = None
            return

    def __init__(self):
        host.registerGameStatusHandler(self.roundStart)

    def roundStart(self, status):
        if status == bf2.GameStatus.Playing:
            self.teleports.clear()
            pattern = re.compile('.*dummy_teleport_(\\d){1,2}_.*')
            if self.task is not None:
                self.task.destroy()
            for spawner in revents.getOnPlayingObjectSpawners():
                try:
                    match = pattern.match(spawner.templateName)
                except AttributeError:
                    rdebug.debugMessage('rutilities roundStart bad spawner type %s' % str(type(spawner)))
                    rdebug.errorMessage()

                if match:
                    teleportid, = match.groups()
                    tele = self.Teleport(spawner.getPosition(), teleportid)
                    if teleportid not in self.teleports:
                        self.teleports[teleportid] = []
                    self.teleports[teleportid].append(tele)

            shouldRunThisRound = False
            for id in self.teleports:
                length = len(self.teleports[id])
                if length <= 1:
                    continue
                for index, tele in enumerate(self.teleports[id]):
                    nextTele = self.teleports[id][(index + 1) % length]
                    tele.target = nextTele.pos
                    rdebug.debugMessage('Added tele from %s' % str(tele.pos), 'gameplay')
                    rdebug.debugMessage('to %s' % str(tele.target), 'gameplay')
                    shouldRunThisRound = True

            if shouldRunThisRound:
                self.task = rtimer.repeatingTask(self.refresh, 3.5)
        return

    def refresh(self, args = None):
        for player in bf2.playerManager.getPlayers():
            if not player.isAlive() or player.isManDown():
                continue
            sol = player.getDefaultVehicle()
            veh = player.getVehicle()
            if sol is not veh:
                continue
            playerpos = sol.getPosition()
            for id in self.teleports:
                for tele in self.teleports[id]:
                    dist = _realitycore.calcDistanceSquared(tele.pos, playerpos)
                    if dist < 4:
                        playerToTeleporterOffset = rcore.vectorSub(playerpos, tele.pos)
                        target = rcore.vectorAddition(playerToTeleporterOffset, tele.target)
                        target = rcore.vectorAddition(target, (0.0, 3.0, 0.0))

                        def tele(args):
                            sol, target = args
                            if rcore.getSquareVectorDistance(sol.getPosition(), target) > 70:
                                sol.setPosition(target)

                        tele((sol, target))
                        rtimer.fireOnce(tele, 0.2, (sol, target))
                        rtimer.fireOnce(tele, 0.6, (sol, target))
                        rtimer.fireOnce(tele, 1.0, (sol, target))