# Embedded file name: realitytracker.py
PROTOCOL_VERSION = 3
import datetime
import json
import os
import struct
import time
import zlib
import bf2
import host
import realityadmin
import realityassets
import realityconfig_admin as ras
import realityconfig_tracker
import realityconstants
import realitycore
import realitydebug
import realityevents
import realitylogger
import realitymemory
import realityserver
import realitytimer
import realityvehicles
import realityzones
realitylogger.createLogger('tracker', 'admin', 'trackerlog.log', True)
g_update = None
g_update_interval = 0.3
g_server_start_time = 0
g_server = None
g_server_port = 6669
g_flush_every_tick = False
NEUTRAL = 0
BLUFOR = 1
OPFOR = 2

def init():
    global g_flush_every_tick
    global g_server_start_time
    global g_update_interval
    realityadmin.addCommand('tracker', commandPrintInfo, 777)
    if not realityconfig_tracker.C['ENABLE']:
        return True
    if realityconfig_tracker.C.get('OUTPUT_FLUSH_EVERY_TICK', False):
        g_flush_every_tick = True
    if realityconfig_tracker.C['UPDATE_INTERVAL']:
        g_update_interval = realityconfig_tracker.C['UPDATE_INTERVAL']
    Output.init()
    for cls in EventInterfaceClasses:
        cls.init()

    g_server_start_time = time.time()
    host.registerGameStatusHandler(onGameStatusChanged)
    return True


def commandPrintInfo(args, p):
    if realityconfig_tracker.C['ENABLE']:
        chatAll = 'N'
        chatTeam = 'N'
        chatSquad = 'N'
        if realityconfig_tracker.C['CHAT_ENABLE']:
            chatAll = 'Y'
            if realityconfig_tracker.C['CHAT_TEAM']:
                chatTeam = 'Y'
            if realityconfig_tracker.C['CHAT_SQUAD']:
                chatSquad = 'Y'
        out = 'Tracker enabled. Chat recording: All:%s,Team:%s,Squad:%s' % (chatAll, chatTeam, chatSquad)
    else:
        out = 'Tracker disabled'
    realityadmin.personalMessage(out, p)


def onRoundLoaded():
    """
    Called when server loads the map.
    """
    logWithTime('Round Load')
    for cls in EventInterfaceClasses:
        cls.roundLoaded()

    logWithTime('Round Load events completed')


def onRoundStart():
    """
    Called when briefing time clock starts ticking.
    TODO: Tickets are not initialized when this is called. results in sending 0 for tickets on the first tick
          It happens because tickets are initialized by python code that reads some dummy objects parameters as tickets.
    
    """
    global g_lastTickTime
    global g_update
    logWithTime('Round Start')
    g_lastTickTime = host.timer_getWallTime()
    Output.openFile()
    for cls in EventInterfaceClasses:
        cls.roundStart()

    g_update = realitytimer.repeatingTask(onTrackerTick, g_update_interval)
    logWithTime('Round Start events completed')


def onRoundEnd():
    """
    Called on round end to clear the timer and all the variables that are used by the clients
    """
    global g_update
    logWithTime('Round end')
    for cls in EventInterfaceClasses:
        cls.roundEnd()

    if realityconfig_tracker.C['JSON_ENABLE']:
        JsonMaker.CreateJson()
    if g_update:
        g_update.destroy()
        g_update = None
    Output.writeToAll(Output.MESSAGETYPE_ROUNDEND, '')
    Output.closeFile()
    logWithTime('Round end events complete')
    return


def onGameStatusChanged(status):
    """
    Called when the onGameStatusChanged event occurs.
    """
    {bf2.GameStatus.Loading: lambda : None,
     bf2.GameStatus.Loaded: onRoundLoaded,
     bf2.GameStatus.Playing: onRoundStart,
     bf2.GameStatus.EndGame: onRoundEnd}[status]()


g_lastTickTime = 0

def onTrackerTick(data = None):
    global g_lastTickTime
    for cls in SendDiffClasses:
        cls.sendDiff()

    realtime = host.timer_getWallTime()
    delta = int((realtime - g_lastTickTime) / 0.04)
    if delta > 255:
        delta = 255
    g_lastTickTime += delta * 0.04
    Output.writeToAll(Output.MESSAGETYPE_TICK, struct.pack('<B', delta))
    if g_flush_every_tick:
        Output.flush()


def printMsg(msg):
    """
    Prints out console messages for debugging
    """
    realitydebug.errorMessage()
    strmsg = str(msg)
    logWithTime(strmsg)


def logWithTime(msg):
    realitylogger.RealityLogger['tracker'].logLine(str(time.time()) + ': %s' % msg)


def onClientAuth(client):
    """Send all up to date information to a client that just auth"""
    if realityevents.g_gameState == bf2.GameStatus.Playing or realityevents.g_gameState == bf2.GameStatus.Loaded:
        writeFullStateToClient(client)


def writeFullStateToClient(client):
    for cls in EventInterfaceClasses:
        cls.sendAll(client)


def onClientError(client, message):
    printMsg('client %s error: %s' % (client, message))


def onClientCommand(client, message):
    printMsg('client %s command: %s' % (client, message))


def clamp_int16(i):
    int16_max = 32766
    if i < -int16_max:
        return int(-int16_max + 1)
    if i > int16_max:
        return int(int16_max - 1)
    return int(i)


def positionToByteString(pos):
    return struct.pack('<hhh', clamp_int16(pos[0]), clamp_int16(pos[1]), clamp_int16(pos[2]))


class IEventInterface(object):

    @classmethod
    def init(cls):
        pass

    @classmethod
    def roundLoaded(cls):
        pass

    @classmethod
    def roundStart(cls):
        pass

    @classmethod
    def roundEnd(cls):
        pass

    @classmethod
    def sendAll(cls, client):
        pass

    @classmethod
    def sendDiff(cls):
        pass


class ServerDetails(IEventInterface):
    """
    Used to store server information.
    """
    ip = ''
    name = ''
    port = ''
    timezone = ''
    startTime = 0
    maxPlayers = 0
    roundWarmup = 0
    roundLength = 0
    currentMap = 'Unknown'
    gamemode = 'Unknown'
    mapLayer = 0
    mapSize = 0
    teamnameBlu = ''
    teamnameOp = ''
    roundStartTime = 0
    ticketsBlu = 0
    ticketsOp = 0
    serverStatus = None

    @classmethod
    def init(cls):
        host.registerHandler('TicketsChanged', cls.updateTickets)
        cls.name = cls.getServerProperty('sv.serverName')
        cls.ip = cls.getServerProperty('sv.serverIP')
        cls.port = cls.getServerProperty('sv.serverPort')
        cls.startTime = time.time()
        cls.maxPlayers = int(cls.getServerProperty('sv.maxPlayers'))

    @classmethod
    def roundLoaded(cls):
        cls.currentMap = host.sgl_getMapName()
        cls.gamemode = host.ss_getParam('gameMode')
        cls.mapLayer = realitycore.getMapLayer()
        cls.roundWarmup = realityserver.C('STARTDELAY')
        cls.teamnameBlu = bf2.gameLogic.getTeamName(BLUFOR)
        cls.teamnameOp = bf2.gameLogic.getTeamName(OPFOR)

    @classmethod
    def roundStart(cls):
        cls.roundStartTime = int(time.time())
        cls.roundLength = realityserver.C('PRTIMELIMIT')
        cls.sendAll(None)
        return

    @classmethod
    def getHeader(cls):
        """
        Receive all relevant class values
        """
        message = struct.pack('<if', PROTOCOL_VERSION, g_update_interval)
        message += cls.ip + ':' + cls.port + '\x00'
        message += cls.name + '\x00'
        message += struct.pack('<B', cls.maxPlayers)
        message += struct.pack('<H', cls.roundLength)
        message += struct.pack('<H', cls.roundWarmup)
        message += str(cls.currentMap) + '\x00'
        message += str(cls.gamemode) + '\x00'
        message += struct.pack('<B', cls.mapLayer)
        message += cls.teamnameBlu + '\x00' + cls.teamnameOp + '\x00'
        message += struct.pack('<I', cls.roundStartTime)
        message += struct.pack('<H', bf2.gameLogic.getTickets(BLUFOR))
        message += struct.pack('<H', bf2.gameLogic.getTickets(OPFOR))
        message += struct.pack('<f', bf2.gameLogic.getWorldSize()[0] / 1024.0)
        return message

    @classmethod
    def updateTickets(cls, team, tickets, remaining):
        """
        Updates the server's details for the tracker's clients
        """
        if team == 1:
            cls.ticketsOp = max(remaining, 0)
            Output.writeToAll(Output.MESSAGETYPE_TICKETS_TEAM1, struct.pack('<h', remaining))
        else:
            cls.ticketsBlu = max(remaining, 0)
            Output.writeToAll(Output.MESSAGETYPE_TICKETS_TEAM2, struct.pack('<h', remaining))

    @classmethod
    def sendAll(cls, client = None):
        """
        Send the server's details to a given client or write it to the tracker file
        """
        msg = cls.getHeader()
        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_SERVERDETAILS, msg)

    @staticmethod
    def getServerProperty(property, replace = ''):
        """
        Returns a string of the requested server property
        """
        try:
            return str(host.rcon_invoke(property).replace('\n', replace))
        except Exception as e:
            printMsg('GetServerDetails: ' + str(e))

        return ''


class DODList(IEventInterface):

    @classmethod
    def roundStart(cls):
        out = ''
        try:
            DODs = realityzones.getAllDODs()
            for DOD in DODs:
                out += struct.pack('<BBBB', DOD.team, not DOD.inverted, DOD.vehicles, len(DOD.points))
                for point in DOD.points:
                    out += struct.pack('<ff', point[0], point[1])

            if out:
                Output.writeToAll(Output.MESSAGETYPE_DODLIST, out)
        except:
            realitydebug.errorMessage()


HEALTH_WRECK = -1
HEALTH_ERROR = -128

class Player(IEventInterface):
    """
    Used to store players in the cachedPlayers dictionary
    """
    cached_players = {}
    cached_disconnected = {}
    PLAYERUPDATEFLAGS_TEAM = 1
    PLAYERUPDATEFLAGS_SQUAD = 2
    PLAYERUPDATEFLAGS_VEHICLE = 4
    PLAYERUPDATEFLAGS_HEALTH = 8
    PLAYERUPDATEFLAGS_SCORE = 16
    PLAYERUPDATEFLAGS_TEAMWORKSCORE = 32
    PLAYERUPDATEFLAGS_KILLS = 64
    PLAYERUPDATEFLAGS_DEATHS = 256
    PLAYERUPDATEFLAGS_PING = 512
    PLAYERUPDATEFLAGS_ISALIVE = 2048
    PLAYERUPDATEFLAGS_ISJOINING = 4096
    PLAYERUPDATEFLAGS_POSITION = 8192
    PLAYERUPDATEFLAGS_ROTATION = 16384
    PLAYERUPDATEFLAGS_KIT = 32768
    PLAYERUPDATEFLAGS_ALL = 65535

    @classmethod
    def init(cls):
        host.registerHandler('PlayerConnect', cls.onPlayerJoined, 1)
        host.registerHandler('PlayerSpawn', cls.onPlayerSpawn, 1)
        host.registerHandler('PlayerDisconnect', cls.onPlayerDisconnect, 1)
        host.registerHandler('PlayerKilled', cls.onPlayerKilled, 1)
        host.registerHandler('PlayerRevived', cls.onPlayerRevived, 1)

    @classmethod
    def roundLoaded(cls):
        cls.cached_players = {}
        cls.cached_disconnected = {}

    @classmethod
    def roundStart(cls):
        cls.sendAll(None)
        return

    def __init__(self, p):
        self.team = 0
        self.squad = 0
        self.isSquadLead = False
        self.kit = ''
        self.vehicleid = Vehicle.VEHICLEID_ERROR_NOTINITIALIZED
        self.vehicleseat = ''
        self.vehicleslot = 0
        self.score = 0
        self.scoreTW = 0
        self.kills = 0
        self.deaths = 0
        self.ping = 0
        self.health = 0
        self.position = (-1, -2, -3)
        self.rotation = 0
        self.xrotation = 0
        self.alive = False
        self.joining = True
        self.name = p.getName()
        self.index = p.index
        self.epochDisconnectTime = 0
        self.joinTime = 0
        self.vehiclechanged = True

    def getCurrentState(self, p):
        """
        Get all cached values without trying to update them
        """
        try:
            flags = Player.PLAYERUPDATEFLAGS_ALL
            output = ''
            output += struct.pack('<B', p.index)
            output += struct.pack('<B', self.team)
            output += struct.pack('<B', self.squad + 128 * int(self.isSquadLead))
            output += struct.pack('<h', self.vehicleid)
            if self.vehicleid >= 0:
                output += self.vehicleseat + '\x00' + struct.pack('<B', self.vehicleslot)
            output += struct.pack('<B', self.health % 256)
            output += struct.pack('<hhhhh', self.score, self.scoreTW, self.kills, self.deaths, self.ping)
            output += struct.pack('<B', int(self.alive))
            if hasattr(p, 'joining'):
                self.joining = p.joining
                output += struct.pack('<B', int(self.joining))
            else:
                output += struct.pack('<B', 1)
            output += positionToByteString(self.position)
            output += struct.pack('<h', int(self.xrotation))
            output += self.kit + '\x00'
            return struct.pack('<H', flags) + output
        except Exception as e:
            printMsg('PlayerUpdate->getCurrentState: ' + str(e))

    def getChangedValues(self, p):
        """
        Get values that differ from the cached values
        """
        try:
            flags = 0
            output = ''
            veh = p.getVehicle()
            output += struct.pack('<B', p.index)
            team = p.getTeam()
            if self.team != team:
                flags += Player.PLAYERUPDATEFLAGS_TEAM
                self.team = team
                output += struct.pack('<B', self.team)
            squadID = p.getSquadId()
            squadleader = p.isSquadLeader() or p.isCommander()
            if self.squad != squadID or self.isSquadLead != squadleader:
                self.squad = squadID
                self.isSquadLead = squadleader
                flags += Player.PLAYERUPDATEFLAGS_SQUAD
                output += struct.pack('<B', squadID + 128 * int(squadleader))
            if self.vehiclechanged:
                if self.vehicleid < 0:
                    vehicle = struct.pack('<h', self.vehicleid)
                else:
                    vehicle = struct.pack('<h', self.vehicleid) + self.vehicleseat + '\x00' + struct.pack('<B', self.vehicleslot)
                flags += Player.PLAYERUPDATEFLAGS_VEHICLE
                output += vehicle
                self.vehiclechanged = False
            soldier = p.getDefaultVehicle()
            if soldier is not None:
                health = soldier.getDamage()
                if health is not None:
                    if not 0 <= health <= 100:
                        health = -2
                else:
                    health = HEALTH_ERROR
            else:
                health = 0
            if self.health != health:
                flags += Player.PLAYERUPDATEFLAGS_HEALTH
                self.health = health
                output += struct.pack('<b', int(self.health))
            score = host.pmgr_getScore(self.index, 'score')
            if self.score != score:
                flags += Player.PLAYERUPDATEFLAGS_SCORE
                self.score = score
                output += struct.pack('<h', self.score)
            rplScore = host.pmgr_getScore(self.index, 'rplScore')
            if self.scoreTW != rplScore:
                flags += Player.PLAYERUPDATEFLAGS_TEAMWORKSCORE
                self.scoreTW = rplScore
                output += struct.pack('<h', self.scoreTW)
            kills = host.pmgr_getScore(self.index, 'kills')
            if self.kills != kills:
                flags += Player.PLAYERUPDATEFLAGS_KILLS
                self.kills = kills
                output += struct.pack('<h', self.kills)
            deaths = host.pmgr_getScore(self.index, 'deaths')
            if self.deaths != deaths:
                flags += Player.PLAYERUPDATEFLAGS_DEATHS
                self.deaths = deaths
                output += struct.pack('<h', self.deaths)
            if self.ping != p.getPing():
                flags += Player.PLAYERUPDATEFLAGS_PING
                self.ping = p.getPing()
                output += struct.pack('<h', self.ping)
            alive = p.isAlive() and not p.isManDown()
            if self.alive != alive:
                flags += Player.PLAYERUPDATEFLAGS_ISALIVE
                self.alive = alive
                output += struct.pack('<B', int(self.alive))
            if hasattr(p, 'joining'):
                if self.joining != p.joining:
                    flags += Player.PLAYERUPDATEFLAGS_ISJOINING
                    self.joining = p.joining
                    output += struct.pack('<B', int(self.joining))
            pos = veh.getPosition()
            if self.position[0] != pos[0] or self.position[2] != pos[2]:
                self.position = (pos[0], pos[1], pos[2])
                output += positionToByteString(pos)
                flags += Player.PLAYERUPDATEFLAGS_POSITION
            camera = realitycore.getVehicleCamera(veh)
            if camera is not None and camera.isValid():
                xrotation = realitycore.getCameraYaw(camera)
                if self.xrotation != xrotation:
                    self.xrotation = xrotation
                    output += struct.pack('<h', int(self.xrotation))
                    flags += Player.PLAYERUPDATEFLAGS_ROTATION
            kitObj = p.getKit()
            if kitObj is not None and self.kit != kitObj.templateName and self.alive:
                flags += Player.PLAYERUPDATEFLAGS_KIT
                self.kit = kitObj.templateName
                output += self.kit + '\x00'
            if flags == 0:
                return ''
            return struct.pack('<H', flags) + output
        except Exception as e:
            printMsg('PlayerUpdate->getChangedValues: ' + str(e))
            return ''

        return

    @classmethod
    def getPlayerHeader(cls, p, getAllPrivate):
        cachedplayer = cls.cached_players[p.getName()]
        out = struct.pack('<B', p.index) + p.getName() + '\x00'
        cachedplayer.hash = str(realityserver.getPlayerHash(p))
        if Output.write_private_data_hash or getAllPrivate:
            out += cachedplayer.hash
        out += '\x00'
        cachedplayer.IP = str(p.getAddress())
        if Output.write_private_data_IP or getAllPrivate:
            out += cachedplayer.IP
        out += '\x00'
        return out

    @classmethod
    def sendFullPlayerList(cls, client = None):
        """
        Send a list of all of the connected players to a given client
        Called at round start, or when client connects
        """
        try:
            messageStringPublic = ''
            messageStringPrivate = ''
            for p in bf2.playerManager.getPlayers():
                name = p.getName()
                if name not in cls.cached_players:
                    cls.cached_players[name] = Player(p)
                messageStringPublic += cls.getPlayerHeader(p, False)
                messageStringPrivate += cls.getPlayerHeader(p, True)

            if messageStringPublic:
                if not client:
                    Output.writeToFile(Output.MESSAGETYPE_PLAYER_ADD, messageStringPublic, writeprivate=False)
                    Output.writeToFile(Output.MESSAGETYPE_PLAYER_ADD, messageStringPrivate, writepublic=False)
                else:
                    Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_PLAYER_ADD, messageStringPrivate)
        except Exception as e:
            printMsg('GetPlayerList: ' + str(e))

    @classmethod
    def sendDiff(cls):
        """
        Sends only the information different from the stored state
        """
        msg = ''
        for p in bf2.playerManager.getPlayers():
            msg += cls.cached_players[p.getName()].getChangedValues(p)

        if msg:
            Output.writeToAll(Output.MESSAGETYPE_PLAYER_UPDATE, msg)

    @classmethod
    def sendAll(cls, client):
        cls.sendFullPlayerList(client)
        msg = ''
        for p in bf2.playerManager.getPlayers():
            msg += cls.cached_players[p.getName()].getCurrentState(p)

        if msg:
            Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_PLAYER_UPDATE, msg)

    @classmethod
    def onPlayerJoined(cls, p):
        """
        Called when a player joins.
        """
        name = p.getName()
        cls.cached_players[name] = Player(p)
        if name in cls.cached_disconnected:
            cls.cached_players[name].joinTime = cls.cached_disconnected[name].joinTime
            del cls.cached_disconnected[name]
        else:
            cls.cached_players[name].joinTime = int(time.time())
        outprivate = cls.getPlayerHeader(p, True)
        outpublic = cls.getPlayerHeader(p, False)
        Output.writeToFile(Output.MESSAGETYPE_PLAYER_ADD, outprivate, writepublic=False)
        Output.writeToClients(Output.MESSAGETYPE_PLAYER_ADD, outprivate)
        Output.writeToFile(Output.MESSAGETYPE_PLAYER_ADD, outpublic, writeprivate=False)

    @classmethod
    def onPlayerDisconnect(cls, p):
        """
        Called when a player disconnects to notify the tracker's clients that they should remove the
        player from their list
        """
        try:
            name = p.getName()
            if name in Player.cached_players:
                cls.cached_disconnected[name] = cls.cached_players[name]
                cls.cached_disconnected[name].epochDisconnectTime = int(time.time())
                del cls.cached_players[name]
            Output.writeToAll(Output.MESSAGETYPE_PLAYER_REMOVE, struct.pack('<B', p.index))
        except Exception as e:
            printMsg('PlayerLeft: ' + str(e))

    @classmethod
    def onPlayerSpawn(cls, p, vehicle):
        """
        Called when a player spawns to update that he's not "joining" anymore
        """
        p.joining = False

    @classmethod
    def onPlayerKilled(cls, victimPlayerObject, attackerPlayerObject, weaponObject, assists, victimSoldierObject):
        """
        Called when a player is killed to add his death string to the killbuffer
        """
        try:
            if not victimPlayerObject or not attackerPlayerObject:
                return
            if weaponObject:
                weapon = weaponObject.templateName
            else:
                weapon = '?'
            Output.writeToAll(Output.MESSAGETYPE_KILL, struct.pack('<BB', attackerPlayerObject.index, victimPlayerObject.index) + weapon + '\x00')
        except Exception as e:
            printMsg('onPlayerKilled: ' + str(e))

    @classmethod
    def onPlayerRevived(cls, revivedPlayerObject, medicPlayerObject):
        """
        Write revive event:
            medic ID, revived player ID
        """
        if revivedPlayerObject is None or medicPlayerObject is None:
            return
        else:
            Output.writeToAll(Output.MESSAGETYPE_REVIVE, struct.pack('<BB', medicPlayerObject.index, revivedPlayerObject.index))
            return


class Vehicle(IEventInterface):
    """
    Used to store vehicles in the vehicle cache dictionary
    """
    VEHICLEUPDATEFLAGS_TEAM = 1
    VEHICLEUPDATEFLAGS_POSITION = 2
    VEHICLEUPDATEFLAGS_ROTATION = 4
    VEHICLEUPDATEFLAGS_HEALTH = 8
    VEHICLEUPDATEFLAGS_ALL = 255
    VEHICLEID_NONE = -1
    VEHICLEID_ROPE = -2
    VEHICLEID_ERROR_IDFAILED = -1000
    VEHICLEID_ERROR_NOTINITIALIZED = -1001
    registeredVehicles = {}
    vehicleDestroyersList = {}
    vehicleIndex = 0
    objectidToTrackerVehicle = {}

    @classmethod
    def init(cls):
        host.registerHandler('VehicleDestroyed', cls.onVehicleDestroyed, 1)
        host.registerHandler('EnterVehicle', cls.onEnterVehicle)
        host.registerHandler('ExitVehicle', cls.onExitVehicle)
        host.registerHandler('AssetCreated', cls.assetCreated, 1)
        host.registerHandler('AssetRemoved', cls.assetRemoved, 1)

    @classmethod
    def roundLoaded(cls):
        cls.registeredVehicles = {}
        cls.vehicleDestroyersList = {}
        cls.vehicleIndex = 0

    def __init__(self, veh):
        self.veh = veh
        self.trackerindex = Vehicle.vehicleIndex
        Vehicle.vehicleIndex += 1
        self.health = 0
        self.position = (-1, -2, -3)
        self.rotation = 0
        self.team = 0
        self.name = veh.templateName.lower()
        self.healthMax = int(realityvehicles.getVehicleProperties(veh)['maxHitPoints'])
        if not 0 <= self.healthMax <= 65535:
            self.healthMax = 0

    def getAllValues(self):
        """
        Receive all possible values
        """
        output = '\xff' + struct.pack('<h', self.trackerindex) + struct.pack('<B', self.team) + positionToByteString(self.position) + struct.pack('<h', self.rotation) + struct.pack('<h', self.health)
        return output

    def getChangedValues(self):
        """
        Only gets values that differ from the cached values
        """
        try:
            flags = 0
            output = ''
            veh = self.veh
            team = self.veh.getTeam()
            if self.team != team:
                flags += Vehicle.VEHICLEUPDATEFLAGS_TEAM
                self.team = team
                output += struct.pack('<B', team)
            pos = veh.getPosition()
            posInt = (int(pos[0]), int(pos[1]), int(pos[2]))
            if self.position[0] != posInt[0] or self.position[2] != posInt[2]:
                flags += Vehicle.VEHICLEUPDATEFLAGS_POSITION
                self.position = posInt
                output += positionToByteString(pos)
            rot = int(veh.getRotation()[0])
            if self.rotation != rot:
                self.rotation = rot
                flags += Vehicle.VEHICLEUPDATEFLAGS_ROTATION
                output += struct.pack('<h', rot)
            health = veh.getDamage()
            if health is not None:
                if health > 32767:
                    health = 0
                elif health < 0:
                    health = HEALTH_WRECK
            else:
                health = HEALTH_ERROR
            if self.health != health:
                self.health = health
                flags += Vehicle.VEHICLEUPDATEFLAGS_HEALTH
                output += struct.pack('<h', int(self.health))
            if flags != 0:
                return struct.pack('<Bh', flags, self.trackerindex) + output
            return ''
        except Exception as e:
            printMsg('Vehicle->getChangedValues: ' + str(e))
            return ''

        return

    @classmethod
    def assetCreated(cls, type, team, PhysicslObject):
        if type not in ('tow', 'hmg', 'antiair', 'mortar'):
            return
        root = bf2.objectManager.getRootParent(PhysicslObject)
        root.tracker_isDeployable = True
        if root not in cls.registeredVehicles:
            cls.newVehicle(root)

    @classmethod
    def assetRemoved(cls, type, team, PhysicslObject):
        if type not in ('tow', 'hmg', 'antiair', 'mortar'):
            return
        Output.writeToAll(Output.MESSAGETYPE_VEHICLE_REMOVE, struct.pack('<hBB', cls.registeredVehicles[PhysicslObject].trackerindex, 0, 0))
        del cls.registeredVehicles[PhysicslObject]

    @classmethod
    def onVehicleDestroyed(cls, vehicle, attacker = None):
        """
        Called when a vehicle is destroyed to notify the tracker's clients that they should remove the
        vehicle from their lists
        """
        if hasattr(vehicle, 'tracker_isDeployable'):
            return
        attackerIsKnown = 0
        id = 0
        if vehicle in cls.registeredVehicles:
            if attacker:
                attackerIsKnown = 1
                id = attacker.index
                name = attacker.getName()
                if name not in cls.vehicleDestroyersList:
                    cls.vehicleDestroyersList[name] = {}
                if vehicle.templateName not in cls.vehicleDestroyersList[name]:
                    cls.vehicleDestroyersList[name][vehicle.templateName] = 0
                cls.vehicleDestroyersList[name][vehicle.templateName] += 1
            Output.writeToAll(Output.MESSAGETYPE_VEHICLE_REMOVE, struct.pack('<hBB', cls.registeredVehicles[vehicle].trackerindex, attackerIsKnown, id))
            del cls.registeredVehicles[vehicle]

    def getVehicleAddString(self):
        return struct.pack('<h', self.trackerindex) + self.name + '\x00' + struct.pack('<H', self.healthMax)

    @classmethod
    def newVehicle(cls, vehObject):
        pyobj = Vehicle(vehObject)
        cls.registeredVehicles[vehObject] = pyobj
        msg = pyobj.getVehicleAddString()
        Output.writeToAll(Output.MESSAGETYPE_VEHICLE_ADD, msg)

    @classmethod
    def onExitVehicle(cls, p, v):
        cached_player = Player.cached_players[p.getName()]
        cached_player.vehicleid = cls.VEHICLEID_NONE
        cached_player.vehiclechanged = True

    @classmethod
    def onEnterVehicle(cls, p, v, freeSoldier = False):
        """
        Called when a player enters a vehicle. Used to check if vehicle exists in our lists.
        "freeSoldier" is 1 if the player is a passenger of the vehicle and is able to use weapons/objects of his kit
        """
        if v.templateName.startswith('Multi'):
            return
        root = bf2.objectManager.getRootParent(v)
        if root not in cls.registeredVehicles:
            cls.newVehicle(root)
        cached_player = Player.cached_players[p.getName()]
        cached_player.vehicleid = cls.registeredVehicles[root].trackerindex
        cached_player.vehicleseat = v.templateName
        cached_player.vehicleslot = realityvehicles.getPositionInVehicle(v)
        cached_player.vehiclechanged = True

    @classmethod
    def sendDiff(cls):
        """
        Updates the vehicles list for the tracker's clients
        """
        messageString = ''
        try:
            for pythonveh in cls.registeredVehicles.values():
                if pythonveh.veh.isValid():
                    messageString += pythonveh.getChangedValues()
                else:
                    cls.onVehicleDestroyed(pythonveh.veh, None)

            if messageString:
                Output.writeToAll(Output.MESSAGETYPE_VEHICLE_UPDATE, messageString)
        except Exception as e:
            printMsg('vehicles sendDiff ' + str(e))

        return

    @classmethod
    def sendAll(cls, client):
        """
        Updates the vehicles list for the tracker's clients
        """
        msgAdd = ''
        msgUpdate = ''
        for veh in cls.registeredVehicles.values():
            msgAdd += veh.getVehicleAddString()
            msgUpdate += veh.getAllValues()

        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_VEHICLE_ADD, msgAdd)
        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_VEHICLE_UPDATE, msgUpdate)

    @classmethod
    def getJSONSummary(cls, name):
        return cls.vehicleDestroyersList.get(name, {})


class Flags(IEventInterface):
    flags = set()

    @classmethod
    def init(cls):
        host.registerHandler('ControlPointCaptured', cls.onFlagCapture, 1)
        host.registerHandler('ControlPointNeutralized', cls.onFlagCapture, 1)

    @classmethod
    def roundLoaded(cls):
        cls.flags.clear()
        for cp in realitycore.getControlPoints():
            if cp.isValid():
                cls.flags.add(cp)

    @classmethod
    def roundStart(cls):
        cls.sendAll(None)
        return

    @classmethod
    def sendAll(cls, client = None):
        """
        List all flags
        """
        msg = ''
        discardList = []
        for cp in cls.flags:
            if cp.isValid():
                cpPos = cp.getPosition()
                msg += struct.pack('<hB', int(cp.getTemplateProperty('ControlPointID')), cp.cp_getParam('team'))
                msg += positionToByteString(cpPos)
                msg += struct.pack('<H', int(cp.getTemplateProperty('radius')))
            else:
                discardList.append(cp)

        for cp in discardList:
            cls.flags.discard(cp)

        if msg:
            Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_FLAG_LIST, msg)

    @classmethod
    def onFlagCapture(cls, cp, team, players):
        """
        On flag capture/Neutralize
        2 bytes ID, 1 byte new team
        """
        cpString = struct.pack('<hB', int(cp.getTemplateProperty('ControlPointID')), cp.cp_getParam('team'))
        Output.writeToAll(Output.MESSAGETYPE_FLAG_UPDATE, cpString)

    @classmethod
    def getJSONSummary(cls):
        out = []
        for flag in cls.flags:
            out.append({'id': int(flag.getTemplateProperty('ControlPointID')),
             'team': flag.cp_getParam('team'),
             'position': flag.getPosition(),
             'radius': int(flag.getTemplateProperty('radius'))})

        return out


class Fobs(IEventInterface):

    @classmethod
    def init(cls):
        host.registerHandler('AssetCreated', cls.assetCreated, 1)
        host.registerHandler('AssetRemoved', cls.assetRemoved, 1)

    @classmethod
    def assetCreated(cls, type, team, PhysicslObject):
        if type != 'outpost':
            return
        out = cls.serializeFob(PhysicslObject)
        Output.writeToAll(Output.MESSAGETYPE_FOB_ADD, out)

    @classmethod
    def assetRemoved(cls, type, team, PhysicslObject):
        if type != 'outpost':
            return
        out = struct.pack('<i', realitycore.getObjectId(PhysicslObject))
        Output.writeToAll(Output.MESSAGETYPE_FOB_REMOVE, out)

    @classmethod
    def sendAll(cls, client):
        out = ''
        for fob in realityassets.getAssetsOfType('outpost'):
            out += cls.serializeFob(fob)

        if out:
            Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_FOB_ADD, out)

    @staticmethod
    def serializeFob(fob):
        pos = fob.getPosition()
        return struct.pack('<iB', realitycore.getObjectId(fob), int(fob.getTeam())) + positionToByteString(pos)


class Rallies(IEventInterface):
    rallies = [{}, {}]

    @classmethod
    def init(cls):
        host.registerHandler('RallyCreated', cls.addRally, 1)
        host.registerHandler('RallyDelete', cls.delRally, 1)

    @classmethod
    def roundLoaded(cls):
        cls.rallies = [{}, {}]

    @classmethod
    def addRally(cls, team, squad, pos):
        team0based = team - 1
        cls.rallies[team0based][squad] = pos
        Output.writeToAll(Output.MESSAGETYPE_RALLY_ADD, Rallies.serializeRally(team0based, squad, pos))

    @classmethod
    def delRally(cls, team, squad):
        team0based = team - 1
        if squad in cls.rallies[team0based]:
            del cls.rallies[team0based][squad]
        Output.writeToAll(Output.MESSAGETYPE_RALLY_REMOVE, struct.pack('<B', team0based * 128 + squad))

    @staticmethod
    def serializeRally(team0based, squad, pos):
        return struct.pack('<B', team0based * 128 + squad) + positionToByteString(pos)

    @classmethod
    def sendAll(cls, client):
        out = ''
        for team in [1, 2]:
            for squad in cls.rallies[team]:
                out += Rallies.serializeRally(team, squad, cls.rallies[team][squad])

        if out:
            Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_RALLY_ADD, out)


COMMAND_PREFIXES = tuple(list(ras.adm_commandAliases.keys()) + list(realityadmin.g_adminCommands.keys()))

class Chat(IEventInterface):
    CHATCHANNEL_ALL = 0
    CHATCHANNEL_TEAM1 = 16
    CHATCHANNEL_TEAM2 = 32
    CHATCHANNEL_SERVER = 48
    CHATCHANNEL_RESPONSE = 49
    CHATCHANNEL_ADMINALERT = 50
    CHATCHANNEL_SERVERMESSAGE = 51
    CHATCHANNEL_SERVERTEAM1MESSAGE = 52
    CHATCHANNEL_SERVERTEAM2MESSAGE = 53
    record_any = False
    record_team = False
    record_squad = False

    @classmethod
    def init(cls):
        if realityconfig_tracker.C['CHAT_ENABLE'] or realityconfig_tracker.C['TRACKER_FILE_PRIVATE']:
            cls.record_team = bool(realityconfig_tracker.C['CHAT_TEAM'])
            cls.record_squad = bool(realityconfig_tracker.C['CHAT_SQUAD'])
            cls.record_any = bool(realityconfig_tracker.C['CHAT_ENABLE'])
            host.registerHandler('ChatMessage', cls.onChatMessage, 1)

    @classmethod
    def onChatMessage(cls, playerId, text, channel, flags):
        """
        Called when the onChatMessage event occurs. The function adds global and team chat messages
        to the chat buffer.
        """
        player = realitycore.getPlayerByIndex(playerId)
        SerializedChannel = None
        try:
            type = int(channel)
            if type == 4:
                SerializedChannel = cls.CHATCHANNEL_SERVER
            elif type == 5:
                SerializedChannel = cls.CHATCHANNEL_RESPONSE
            elif type == 6:
                SerializedChannel = cls.CHATCHANNEL_ADMINALERT
        except:
            pass

        if channel == 'Global':
            SerializedChannel = cls.CHATCHANNEL_ALL
        elif channel == 'Team' or channel == 'Squad':
            SerializedChannel = player.getTeam() << 4
            if channel == 'Squad':
                SerializedChannel += player.getSquadId()
        if SerializedChannel is None:
            return
        else:
            if text.startswith('HUD'):
                text = text.replace('HUD_TEXT_CHAT_COMMANDER', '')
                text = text.replace('HUD_TEXT_CHAT_TEAM', '')
                text = text.replace('HUD_TEXT_CHAT_SQUAD', '')
                text = text.replace('HUD_CHAT_DEADPREFIX', '')
            out = struct.pack('<BB', SerializedChannel, playerId) + text + '\x00'
            Output.writeToClients(Output.MESSAGETYPE_CHAT, out)
            writepublic = True
            untrackable_commands = ('!r', '!report', '!rp', '!reportplayer', '!m', '!message', '!info', '!ec')
            if not cls.record_any:
                writepublic = False
            elif channel == 'Team' and not cls.record_team:
                writepublic = False
            elif channel == 'Squad' and not cls.record_squad and not (text.startswith(COMMAND_PREFIXES) and ras.track_commandchat and not text.lower().startswith(untrackable_commands)):
                writepublic = False
            Output.writeToFile(Output.MESSAGETYPE_CHAT, out, writepublic=writepublic)
            return


class KitAllocations(IEventInterface):
    kitAllocations = {}

    @classmethod
    def init(cls):
        host.registerHandler('KitAllocated', cls.onKitAllocated)

    @classmethod
    def roundLoaded(cls):
        cls.kitAllocations = {}

    @classmethod
    def onKitAllocated(cls, p, kitName):
        name = p.getName()
        if name not in cls.kitAllocations:
            cls.kitAllocations[name] = {}
        if kitName not in cls.kitAllocations[name]:
            cls.kitAllocations[name][kitName] = 0
        cls.kitAllocations[name][kitName] += 1
        Output.writeToAll(Output.MESSAGETYPE_KITALLOCATED, struct.pack('<B', p.index) + kitName + '\x00')

    @classmethod
    def getJSONSummary(cls, name):
        return cls.kitAllocations.get(name, {})


class SquadNames(IEventInterface):

    @classmethod
    def init(cls):
        host.registerHandler('SquadCreated', cls.newSquad)

    @classmethod
    def newSquad(cls, player, team, squad, name):
        teamsquad = (team - 1) * 128 + squad
        Output.writeToAll(Output.MESSAGETYPE_SQUADNAME, struct.pack('<B', teamsquad) + name + '\x00')

    @classmethod
    def sendAll(cls, client):
        msg = ''
        for team in [1, 2]:
            for squad in range(1, 10):
                name = realitycore.getSquadName(team, squad)
                if name is not None:
                    teamsquad = (team - 1) * 128 + squad
                    msg += struct.pack('<B', teamsquad) + name + '\x00'

        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_SQUADNAME + msg)
        return


class Caches(IEventInterface):
    allCaches = set()
    intel = 0

    @classmethod
    def init(cls):
        host.registerHandler('InsurgencyCacheAdded', cls.cacheAdd)
        host.registerHandler('InsurgencyCacheRevealed', cls.cacheReveal)
        host.registerHandler('InsurgencyCacheDestroyed', cls.cacheDestroyed)
        host.registerHandler('InsurgencyIntelChanged', cls.intelChange)

    @classmethod
    def roundLoaded(cls):
        cls.allCaches = set()
        cls.intel = 0

    @classmethod
    def roundStart(cls):
        cls.sendAll(None)
        return

    @classmethod
    def sendAll(cls, client):
        msgNew = ''
        msgReveal = ''
        for cache in cls.allCaches:
            msgNew += struct.pack('<B', cache.index) + positionToByteString(cache.pos)
            if cache.isRevealed():
                msgReveal += struct.pack('<B', cache.index)

        if msgNew:
            Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_CACHE_ADD, msgNew)
            if msgReveal:
                Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_CACHE_REVEAL, msgReveal)
        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_INTEL_CHANGE, struct.pack('<b', cls.intel))

    @classmethod
    def cacheAdd(cls, cache):
        cls.allCaches.add(cache)
        Output.writeToAll(Output.MESSAGETYPE_CACHE_ADD, struct.pack('<B', cache.index) + positionToByteString(cache.pos))

    @classmethod
    def cacheReveal(cls, cache):
        Output.writeToAll(Output.MESSAGETYPE_CACHE_REVEAL, struct.pack('<B', cache.index))

    @classmethod
    def cacheDestroyed(cls, cache):
        cls.allCaches.discard(cache)
        Output.writeToAll(Output.MESSAGETYPE_CACHE_REMOVE, struct.pack('<B', cache.index))

    @classmethod
    def intelChange(cls, newIntel):
        cls.intel = newIntel
        Output.writeToAll(Output.MESSAGETYPE_INTEL_CHANGE, struct.pack('<b', cls.intel))


class SLOrders(IEventInterface):
    orders = {}

    @classmethod
    def init(cls):
        cls.reset()

    @classmethod
    def roundLoaded(cls):
        cls.reset()

    @classmethod
    def reset(cls):
        for team in range(1, 3):
            cls.orders[team] = {}
            for squad in range(1, 10):
                cls.orders[team][squad] = None

        return

    @classmethod
    def serializeOrder(cls, squad, team, orderWithType):
        if orderWithType is None:
            orderWithType = (-1, (0, 0, 0))
        return struct.pack('<Bb', (team - 1) * 128 + squad, orderWithType[0]) + positionToByteString(orderWithType[1])

    @classmethod
    def sendAll(cls, client):
        out = ''
        for team in range(1, 3):
            for squad in range(1, 10):
                out += cls.serializeOrder(squad, team, realitymemory.getSLOrderWithType(team, squad))

        Output.writeToOneClientOrFile(client, Output.MESSAGETYPE_SLORDERS, out)

    @classmethod
    def sendDiff(cls):
        out = ''
        for team in range(1, 3):
            for squad in range(1, 10):
                pos = realitymemory.getSLOrder(team, squad)
                if pos != cls.orders[team][squad]:
                    out += cls.serializeOrder(squad, team, realitymemory.getSLOrderWithType(team, squad))
                    cls.orders[team][squad] = pos

        if out:
            Output.writeToAll(Output.MESSAGETYPE_SLORDERS, out)


class Markers(IEventInterface):
    activeMarkers = {}
    index = 0

    @classmethod
    def init(cls):
        pass

    @classmethod
    def roundLoaded(cls):
        cls.activeMarkers = {}
        cls.index = 0

    @classmethod
    def markAdd(cls, PRMarker):
        if not PRMarker.template.startswith('marker_spotted'):
            return
        out = struct.pack('<HB', cls.index, PRMarker.team) + positionToByteString(PRMarker.pos) + PRMarker.template[len('marker_spotted_'):] + '\x00'
        Output.writeToAll(Output.MESSAGETYPE_MARKER_ADD, out)
        cls.activeMarkers[cls.index] = PRMarker
        cls.index += 1

    @classmethod
    def markDel(cls, PRMarker):
        if PRMarker in cls.activeMarkers:
            index = cls.activeMarkers[PRMarker]
            del cls.activeMarkers[PRMarker]
            Output.writeToAll(Output.MESSAGETYPE_MARKER_REMOVE, struct.pack('H', index))


class Projectiles(IEventInterface):
    activeProjectiles = {}
    index = 0

    @classmethod
    def init(cls):
        host.registerHandler('MineCreated', cls.projCreated)
        host.registerHandler('RocketCreated', cls.projCreated)

    @classmethod
    def sendDiff(cls):
        out = ''
        for index, proj in cls.activeProjectiles.items():
            if not proj.isValid() or proj.getPosition()[1] == 0.0:
                del cls.activeProjectiles[index]
                Output.writeToAll(Output.MESSAGETYPE_PROJECTILE_REMOVE, struct.pack('<H', index))
            else:
                yaw = proj.getRotation()[0]
                pos = proj.getPosition()
                if pos != proj._tracker_lastpos or yaw != proj._tracker_lastyaw:
                    proj._tracker_lastpos = pos
                    proj._tracker_lastyaw = yaw
                    out += struct.pack('<Hh', index, yaw) + positionToByteString(pos)

        if out:
            Output.writeToAll(Output.MESSAGETYPE_PROJECTILE_UPDATE, out)

    @classmethod
    def projCreated(cls, proj):
        while cls.index in cls.activeProjectiles:
            cls.index = cls.index + 1 & 65535

        cls.activeProjectiles[cls.index] = proj
        type = realityconstants.getProjectileType(proj.templateName)
        yaw = proj.getRotation()[0]
        pos = proj.getPosition()
        proj._tracker_lastpos = pos
        proj._tracker_lastyaw = yaw
        Output.writeToAll(Output.MESSAGETYPE_PROJECTILE_ADD, struct.pack('<HBB', cls.index, proj.player.index, type) + proj.templateName + '\x00' + struct.pack('<h', yaw) + positionToByteString(pos))
        cls.index += 1

    @classmethod
    def roundLoaded(cls):
        cls.activeProjectiles.clear()
        cls.index = 0


class Output(object):
    FILEEXT_INCOMPLETE = '.PRdemo.incomplete'
    FILEEXT_DEMOFILE = '.PRdemo'
    FILEEXT_PRIVATE = '.p'
    MESSAGETYPE_SERVERDETAILS = '\x00'
    MESSAGETYPE_DODLIST = '\x01'
    MESSAGETYPE_PLAYER_UPDATE = '\x10'
    MESSAGETYPE_PLAYER_ADD = '\x11'
    MESSAGETYPE_PLAYER_REMOVE = '\x12'
    MESSAGETYPE_VEHICLE_UPDATE = ' '
    MESSAGETYPE_VEHICLE_ADD = '!'
    MESSAGETYPE_VEHICLE_REMOVE = '"'
    MESSAGETYPE_FOB_ADD = '0'
    MESSAGETYPE_FOB_REMOVE = '1'
    MESSAGETYPE_FLAG_UPDATE = '@'
    MESSAGETYPE_FLAG_LIST = 'A'
    MESSAGETYPE_KILL = 'P'
    MESSAGETYPE_CHAT = 'Q'
    MESSAGETYPE_TICKETS_TEAM1 = 'R'
    MESSAGETYPE_TICKETS_TEAM2 = 'S'
    MESSAGETYPE_RALLY_ADD = '`'
    MESSAGETYPE_RALLY_REMOVE = 'a'
    MESSAGETYPE_CACHE_ADD = 'p'
    MESSAGETYPE_CACHE_REMOVE = 'q'
    MESSAGETYPE_CACHE_REVEAL = 'r'
    MESSAGETYPE_INTEL_CHANGE = 's'
    MESSAGETYPE_MARKER_ADD = '\x80'
    MESSAGETYPE_MARKER_REMOVE = '\x81'
    MESSAGETYPE_PROJECTILE_UPDATE = '\x90'
    MESSAGETYPE_PROJECTILE_ADD = '\x91'
    MESSAGETYPE_PROJECTILE_REMOVE = '\x92'
    MESSAGETYPE_REVIVE = '\xa0'
    MESSAGETYPE_KITALLOCATED = '\xa1'
    MESSAGETYPE_SQUADNAME = '\xa2'
    MESSAGETYPE_SLORDERS = '\xa3'
    MESSAGETYPE_ROUNDEND = '\xf0'
    MESSAGETYPE_TICK = '\xf1'
    MESSAGETYPE_ADMINERROR = '\xfd'
    MESSAGETYPE_ADMINMESSAGE = '\xfe'
    filemode = False
    write_private_data_IP = False
    write_private_data_hash = False
    file = None
    filename = 'unassigned'
    private_filemode = False
    private_file = None

    @classmethod
    def init(cls):
        if not os.path.exists(realityconfig_tracker.C['TMP_FOLDER']):
            os.makedirs(realityconfig_tracker.C['TMP_FOLDER'])
        cls.zipOldFiles()
        if realityconfig_tracker.C['TRACKER_FILE_PUBLIC']:
            cls.filemode = True
            if not os.path.exists(realityconfig_tracker.C['PUBLIC_FOLDER']):
                os.makedirs(realityconfig_tracker.C['PUBLIC_FOLDER'])
            if realityconfig_tracker.C['FILE_PRIVATEDATA_IP']:
                cls.write_private_data_IP = True
            if realityconfig_tracker.C['FILE_PRIVATEDATA_HASH']:
                cls.write_private_data_hash = True
        if realityconfig_tracker.C['TRACKER_FILE_PRIVATE']:
            cls.private_filemode = True
            if not os.path.exists(realityconfig_tracker.C['PRIVATE_FOLDER']):
                os.makedirs(realityconfig_tracker.C['PRIVATE_FOLDER'])

    @classmethod
    def openFile(cls):
        map = str(host.sgl_getMapName())
        mode = str(host.ss_getParam('gameMode'))
        layer = str(realitycore.getMapLayer())
        cls.filename = realityconfig_tracker.C['FILE_NAME'].replace('/map', map).replace('/mode', mode).replace('/layer', layer)
        cls.filename = datetime.datetime.now().strftime(cls.filename)
        if cls.filemode:
            cls.file = open(os.path.join(realityconfig_tracker.C['TMP_FOLDER'], cls.filename) + cls.FILEEXT_INCOMPLETE, 'ab')
        if cls.private_filemode:
            cls.private_file = open(os.path.join(realityconfig_tracker.C['TMP_FOLDER'], cls.filename) + cls.FILEEXT_PRIVATE + cls.FILEEXT_INCOMPLETE, 'ab')

    @classmethod
    def closeFile(cls):
        if cls.filemode:
            if not cls.file:
                return
            cls.file.close()
            cls.file = None
            srcname = os.path.join(realityconfig_tracker.C['TMP_FOLDER'], cls.filename) + cls.FILEEXT_INCOMPLETE
            targetname = os.path.join(realityconfig_tracker.C['PUBLIC_FOLDER'], cls.filename) + cls.FILEEXT_DEMOFILE
            cls.zipFile(srcname, targetname)
        if cls.private_filemode:
            if not cls.private_file:
                return
            cls.private_file.close()
            cls.private_file = None
            srcname = os.path.join(realityconfig_tracker.C['TMP_FOLDER'], cls.filename) + cls.FILEEXT_PRIVATE + cls.FILEEXT_INCOMPLETE
            targetname = os.path.join(realityconfig_tracker.C['PRIVATE_FOLDER'], cls.filename) + cls.FILEEXT_PRIVATE + cls.FILEEXT_DEMOFILE
            cls.zipFile(srcname, targetname)
        return

    @classmethod
    def zipFile(cls, srcname = None, targetname = None):
        logWithTime('Zipping...')
        src = open(srcname, 'rb')
        target = open(targetname, 'wb')
        compressObj = zlib.compressobj()
        while True:
            buffer = src.read(1048576)
            if buffer == '':
                break
            compressedData = compressObj.compress(buffer)
            target.write(compressedData)

        target.write(compressObj.flush())
        src.close()
        target.close()
        os.remove(srcname)
        logWithTime('Zip done')

    @classmethod
    def zipOldFiles(cls):
        files = os.listdir(realityconfig_tracker.C['TMP_FOLDER'])
        files = filter(lambda filename: filename.endswith(cls.FILEEXT_INCOMPLETE), files)
        if len(files) > 0:
            logWithTime('Ziping old files...')
            for file in files:
                try:
                    srcname = os.path.join(realityconfig_tracker.C['TMP_FOLDER'], file)
                    if srcname.endswith(cls.FILEEXT_PRIVATE + cls.FILEEXT_INCOMPLETE):
                        targetFolder = realityconfig_tracker.C['PRIVATE_FOLDER']
                    else:
                        targetFolder = realityconfig_tracker.C['PUBLIC_FOLDER']
                    targetname = os.path.join(targetFolder, file[:-len(cls.FILEEXT_INCOMPLETE)]) + cls.FILEEXT_DEMOFILE
                    Output.zipFile(srcname=srcname, targetname=targetname)
                except:
                    pass

    @classmethod
    def writeToAll(cls, subject, message):
        """
        Writes a given message with the given subject to the enabled output modes
        """
        cls.writeToClients(subject, message)
        cls.writeToFile(subject, message)

    @classmethod
    def writeToClients(cls, subject, message):
        """
        Writes a given message with the given subject to all of the tracker's authenticated clients
        """
        global g_server
        if not g_server:
            return
        for client in g_server.auth_clients:
            cls.writeToOneClientOrFile(client, subject, message)

    @classmethod
    def writeToOneClientOrFile(cls, client, subject, message, closing = False):
        if client is not None:
            client.writeBack('%s%s' % (subject, message), closing)
        else:
            cls.writeToFile(subject, message)
        return

    @classmethod
    def writeToFile(cls, subject, message, writepublic = True, writeprivate = True):
        """
        Writes a given message to the tracker file
        """
        length = struct.pack('<H', len(message) + 1)
        out = '%s%s%s' % (length, subject, message)
        if writepublic:
            cls._writeToFile_public(out)
        if writeprivate:
            cls._writeToFile_private(out)

    @classmethod
    def flush(cls):
        if Output.filemode and Output.file and not Output.file.closed:
            Output.file.flush()
        if Output.private_filemode and Output.private_file and not Output.private_file.closed:
            Output.private_file.flush()

    @classmethod
    def _writeToFile_public(cls, out):
        if Output.filemode and Output.file and not Output.file.closed:
            Output.file.write(out)

    @classmethod
    def _writeToFile_private(cls, out):
        if Output.private_filemode and Output.private_file and not Output.private_file.closed:
            Output.private_file.write(out)


EventInterfaceClasses = [ServerDetails,
 Flags,
 Fobs,
 Rallies,
 Chat,
 Caches,
 Player,
 Vehicle,
 KitAllocations,
 SquadNames,
 DODList,
 SLOrders,
 Projectiles]
SendDiffClasses = [Player,
 Vehicle,
 SLOrders,
 Projectiles]

class JsonMaker(object):

    @classmethod
    def JsonOnePlayer(cls, p, disconnected):
        try:
            out = {'Name': p.name,
             'Team': p.team,
             'SquadLeader': bool(p.isSquadLead),
             'Squad': p.squad,
             'Score': p.score,
             'ScoreTW': p.scoreTW,
             'Kills': p.kills,
             'Deaths': p.deaths,
             'JoinTime': p.joinTime,
             'Disconnected': bool(disconnected),
             'DisconnectTime': p.epochDisconnectTime}
            if realityconfig_tracker.C['JSON_WRITE_HASH']:
                out['Hash'] = p.hash
            if realityconfig_tracker.C['JSON_WRITE_IP']:
                out['IP'] = p.IP
            out['KitAllocations'] = KitAllocations.getJSONSummary(p.name)
            out['VehiclesDestroyed'] = Vehicle.getJSONSummary(p.name)
            return out
        except Exception as e:
            printMsg('JsonOnePlayer: ' + str(e))
            return ''

    @classmethod
    def CreateJson(cls):
        try:
            cls.folder = realityconfig_tracker.C['JSON_FOLDER']
            if not os.path.exists(realityconfig_tracker.C['JSON_FOLDER']):
                os.makedirs(realityconfig_tracker.C['JSON_FOLDER'])
            out = {'ServerName': ServerDetails.name,
             'IPPort': ServerDetails.ip + ':' + ServerDetails.port,
             'StartTime': ServerDetails.roundStartTime,
             'EndTime': int(time.time()),
             'MapName': ServerDetails.currentMap,
             'MapMode': ServerDetails.gamemode,
             'MapLayer': ServerDetails.mapLayer,
             'Team1Name': ServerDetails.teamnameBlu,
             'Team2Name': ServerDetails.teamnameOp,
             'Team1Tickets': ServerDetails.ticketsBlu,
             'Team2Tickets': ServerDetails.ticketsOp}
            playerList = []
            out['Players'] = playerList
            for k in Player.cached_players:
                playerList.append(cls.JsonOnePlayer(Player.cached_players[k], False))

            for k in Player.cached_disconnected:
                playerList.append(cls.JsonOnePlayer(Player.cached_disconnected[k], True))

            out = json.dumps(out, indent=2)
            JSONfile = open(os.path.join(cls.folder, Output.filename) + '.json', 'ab')
            JSONfile.write(out)
            JSONfile.close()
        except Exception as e:
            printMsg('CreateJson: ' + str(e))


global g_server_port ## Warning: Unused global