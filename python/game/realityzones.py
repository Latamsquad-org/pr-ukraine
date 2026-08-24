# Embedded file name: realityzones.py
import os
import sys
import zipfile
import _realitycore
import bf2
import host
import realityadmin as radmin
import realitycore as rcore
import realitydebug as rdebug
import realitymemory as rmemory
import realitytimer as rtimer
import realityserver as rserver
import realitydebug as rdebug
g_combat_areas = None

def getPlayerDODs(player):
    """
    Checks if the given player is in one of the round map's DODs.
    A player is considered in a "good zone" if he is in at least one Combat area (non-inverted CA) and in zero DODs (InvertedCA )
    
    Returns a list of inverted combat areas the player is in.
    
    """
    global g_combat_areas
    INDEX = player.index
    if not host.pmgr_isIndexValid(INDEX):
        return []
    elif not host.pmgr_p_get('alive', INDEX) or host.pmgr_p_get('mandown', INDEX):
        return []
    else:
        playerteam = host.pmgr_p_get('team', INDEX)
        kit = host.pmgr_p_get('kit', INDEX)
        if kit is None:
            return []
        if not hasattr(kit, 'dod_types'):
            _setKitType(kit)
        veh = host.pmgr_p_get('vehicle', INDEX)
        if veh is None:
            return []
        veh = bf2.objectManager.getRootParent(veh)
        point = veh.getPosition()
        if not hasattr(veh, 'dod_types'):
            if player.isInsideVehicle:
                _setVehicleType(veh)
            else:
                veh.dod_types = {LAND}
        DODs = []
        insideAnyCA = False
        for type in kit.dod_types | veh.dod_types | {ALL}:
            for dod in g_combat_areas.dods_by_type[type]:
                if not dod.usePython:
                    continue
                if dod.team != 0 and playerteam != dod.team:
                    continue
                if dod.minHeight is not None and point[1] < dod.minHeight:
                    continue
                if dod.maxHeight is not None and point[1] > dod.maxHeight:
                    continue
                if dod.ignoreInVehicle is True and player.isInsideVehicle:
                    continue
                inside = _realitycore.isPointInPolygon(point, dod.points)
                if inside:
                    if dod.inverted:
                        DODs.append(dod)
                    else:
                        insideAnyCA = True

        if not insideAnyCA:
            DODs.append(g_combat_areas.dummy_outsideCA)
        
        return DODs
        

def getPointDODs(point, team, dodTypes):
    DODs = []
    for type in dodTypes:
        for dod in g_combat_areas.dods_by_type[type]:
            if team != 0 and team != dod.team:
                continue
            inside = _realitycore.isPointInPolygon(point, dod.points)
            if dod.inverted is inside:
                DODs.append(dod)

    return DODs


def getDistanceFromDOD(point, types, team = 0, isDeployables = False):
    """
    Returns the distance of the point from the nearest DOD of given types as a float.
    If the given point is inside one of the DODs the value is returned as a negative number that represented the
    shortest distance to a line from inside.
    If team isn't given the function will assume that you want to check all DODs.
    @param point: the point in 3d
    @param types: list of dod type enum (see examples that call this)
    @param team: 0 for both teams, 1 to ignore dods of team 2, 2 to ignore dods of team 1
    @param isDeployables: skip dods that are marked as "allowDeployables"
    """
    min_distance_from_DOD = sys.float_info.max
    min_distance_from_CA = sys.float_info.max
    for dodTypes in types:
        for dod in g_combat_areas.dods_by_type[dodTypes]:
            if team != 0 and team != dod.team:
                continue
            if isDeployables and dod.allowDeployables:
                continue
            distance = _realitycore.calcDistanceToPolygon(point, dod.points)
            inside = _realitycore.isPointInPolygon(point, dod.points)
            if inside:
                distance = -distance
            if dod.inverted:
                min_distance_from_DOD = min(min_distance_from_DOD, distance)
                rdebug.debugMessage('Distance from DOD %s: %s' % (dod.name, distance), 'zones')
            else:
                min_distance_from_CA = min(min_distance_from_CA, distance)
                rdebug.debugMessage('Distance from CA %s: %s' % (dod.name, distance), 'zones')

    return min(min_distance_from_DOD, -min_distance_from_CA)


def getDistanceFromAssetDOD(point, team = 0):
    return getDistanceFromDOD(point, [DEPLOYABLES, ALL, LAND], team, isDeployables=True)


def getDistanceFromMineDOD(point, team = 0):
    return getDistanceFromDOD(point, [MINES,
     DEPLOYABLES,
     ALL,
     LAND], team)


def refresh(data = None):
    if not g_combat_areas.enablePython:
        return
    else:
        for player in bf2.playerManager.getPlayers():
            dods = getPlayerDODs(player)
            if len(dods) == 0:
                player.dod_enterTimes.clear()
            else:
                mintimeleft = 999.9
                for dod in player.dod_enterTimes.keys():
                    if dod not in dods:
                        del player.dod_enterTimes[dod]
                        continue
                    now = host.timer_getWallTime()
                    timeleftthisdod = dod.getTime() - (now - player.dod_enterTimes[dod])
                    mintimeleft = min(timeleftthisdod, mintimeleft)
                    mintimeleft = max(mintimeleft, 0)
                    if timeleftthisdod < 0:
                        if dod.damage is None:
                            damage = g_combat_areas.player_damage
                        else:
                            damage = dod.damage
                        damagePlayerRoot(player, damage, dod.damageUsePercentage)
                    warnPlayer(player, dods, mintimeleft)

                for dod in dods:
                    if dod in player.dod_enterTimes:
                        continue
                    player.dod_enterTimes[dod] = host.timer_getWallTime()
                    warnPlayer(player, dods, dod.getTime())

        return


def damagePlayerRoot(player, amount, isPercent = False):
    veh = player.getVehicle()
    if veh is None:
        return
    else:
        veh = bf2.objectManager.getRootParent(veh)
        now = host.timer_getWallTime()
        if not hasattr(veh, '_zones_lastdamagetick') or veh._zones_lastdamagetick != now:
            veh._zones_lastdamagetick = now
        else:
            return
        current = veh.getDamage()
        if current is None or current <= 0:
            return
        if isPercent:
            amount *= int(veh.getTemplateProperty('armor.maxHitPoints')) / 100.0
        targetHP = current - amount
        if targetHP <= 0:
            targetHP = 1e-06
        veh.setDamage(targetHP)
        rdebug.debugMessage('Vehiculo %s impactado por %s' % (veh.templateName, amount), 'zones')
        return


def warnPlayer(player, DODs, timeleft):
    rdebug.debugMessage('Player %s in DOD %s!' % (player.getName(), str(tuple((dod.name for dod in DODs)))), 'zones')
    rmemory.HudVarWriteEventWstringWithTimedShowvar(player, 'PythonGameWarningCA', 'Advertencia:\nEstas abandonando el area de combate. Tienes %s segundos para regresar!' % int(timeleft), 4)
    if rmemory.isWindowsListenServer:
        rcore.sendMessageToPlayer(player, 1220104, 1)
        radmin.personalMessage('Estas abandonando el area de combate. Tienes %s segundos para regresar!' % int(timeleft), player)


def onPlayerConnect(player):
    player.dod_enterTimes = {}


def init():
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    rtimer.repeatingTask(refresh, 2.5)


def onGameStatusChanged(status):
    """
    Called when the onGameStatusChanged event occurs.
    """
    {bf2.GameStatus.Loading: lambda : None,
     bf2.GameStatus.Loaded: onRoundLoaded,
     bf2.GameStatus.Playing: lambda : None,
     bf2.GameStatus.EndGame: lambda : None}[status]()


def onRoundLoaded():
    """
    Called when the server loads the map.
    """
    global g_combat_areas
    g_combat_areas = _combatAreaManager()
    g_combat_areas.parseLayout()
    if rdebug.isDebugEnabled('zones'):
        for dod in g_combat_areas.all_dods:
            dod.printCA()

    if g_combat_areas.enablePython:
        for dod in g_combat_areas.all_dods:
            if dod.usePython:
                dod.deleteFromEngine()

    else:
        rdebug.debugMessage('zones disabled, use combatareamanager.enablePython 1', 'zones')


def getAllDODs():
    return list(g_combat_areas.all_dods)


class _combatAreaManager():
    """
    Holds the current round's combat areas within combat area objects
    and serves as an interface to combat area related logic.
    """

    def __init__(self):
        self.active = None
        self.all_dods = []
        self.dods_by_type = []
        for i in range(0, 10):
            self.dods_by_type.append([])

        self.used = True
        self.player_damage = 15
        self.time_allowed_outside = 5
        self.enablePython = False
        self.dummy_outsideCA = self.combatArea('_CA_DUMMY')
        return

    class combatArea:
        """
        Holds individual capture areas
        """

        def __init__(self, name):
            self.name = name
            self.points = []
            self.team = 0
            self.vehicles = 4
            self.min = 0.0
            self.max = 0.0
            self.layer = 0
            self.inverted = False
            self.time = None
            self.damage = None
            self.damageUsePercentage = True
            self.minHeight = None
            self.maxHeight = None
            self.ignoreInVehicle = False
            self.usePython = False
            self.deleted = False
            self.allowDeployables = '_allowdeployable' in self.name.lower()
            return

        def __str__(self):
            return 'name %s; team %d; vehicles %d; layer %d; inverted %r;\n points %s; min %s; max %s;' % (self.name,
             self.team,
             self.vehicles,
             self.layer,
             self.inverted,
             str(self.points),
             str(self.min),
             str(self.max))

        def printCA(self):
            rdebug.debugMessage('------------------CA %s' % self.name)
            rdebug.debugMessage('team %s, vehicles %s, inverted %s, usePython %s' % (self.team,
             self.vehicles,
             self.inverted,
             self.usePython))
            if not self.inverted and self.damage is not None:
                rdebug.debugMessage('WARNNING: cannot override damage on non-inverted area, it will be ignored')
            rdebug.debugMessage('---Extensions:')
            rdebug.debugMessage('time %s, damage %s, UsePercentage %s' % (self.time, self.damage, self.damageUsePercentage))
            rdebug.debugMessage('minHeight %s, maxHeigh %s, ignoreInVehicle %s' % (self.minHeight, self.maxHeight, self.ignoreInVehicle))
            return

        def deleteFromEngine(self):
            if self.deleted:
                return
            rdebug.debugMessage('Deleting DOD %s' % self.name, 'zones')
            host.rcon_invoke('combatArea.active %s' % self.name).strip()
            host.rcon_invoke('combatArea.deleteActiveCombatArea')
            self.deleted = True

        def getTime(self):
            if self.time is None:
                return g_combat_areas.time_allowed_outside
            else:
                return self.time
                return

    def _verifyActive(self):
        if self.active is None:
            raise Exception('Active not set, GPO is not in protocol.')
        return

    def updateDODArrays(self, dod):
        for i in range(0, 10):
            if dod in self.dods_by_type[i]:
                self.dods_by_type[i].remove(dod)

        if len(dod.points) == 0:
            return
        type = dod.vehicles
        self.dods_by_type[type].append(dod)

    def __str__(self):
        output = 'used %r; active: %s; combat areas:\n' % (self.used, self.active.name)
        for capture_area in self.all_dods:
            output += str(capture_area) + '\n'

        return output

    def commitActive(self):
        if self.active is not None:
            self.updateDODArrays(self.active)
        return

    def create(self, area_name, isCombatAreaPython = False):
        self.commitActive()
        self.active = self.combatArea(area_name)
        self.active.isDeleted = True
        self.active.usePython = isCombatAreaPython
        self.all_dods.append(self.active)

    def setActive(self, name, isCombatAreaPython = False):
        self.commitActive()
        for ca in self.all_dods:
            if ca.name == name:
                self.active = ca
                return

        raise Exception('Called combatarea.active on an unlisted name %s' % name)

    def addPoint(self, coords, isCombatAreaPython = False):
        self._verifyActive()
        x, y = coords.split('/')
        self.active.points.append((float(x), float(y)))

    def setOption(self, name, type, value, isManagerSetting = False):
        if type is None:
            value = True
        elif type is bool:
            value = bool(int(value))
        elif type.__class__ == tuple:
            s = value.split('/')
            if len(s) != len(type):
                raise Exception('Value does not fit type size. Name %s, value %s, type %s' % (name, value, type))
            for i in range(len(s)):
                s[i] = type[i](s[i])

            value = tuple(s)
        else:
            value = type(value)
        if isManagerSetting:
            self.__dict__[name] = value
        else:
            self._verifyActive()
            self.active.__dict__[name] = value
        return

    def parseLayout(self):
        """
        Update the class' DODs list based on the current map being played.
        """
        try:
            specialHandlers = {'combatarea.create': self.create,
             'combatarea.addareapoint': self.addPoint,
             'combatarea.active': self.setActive}
            parsing_funcs = {'combatarea.layer': ('layer', int, False),
             'combatarea.team': ('team', int, False),
             'combatarea.vehicles': ('vehicles', int, False),
             'combatarea.inverted': ('inverted', bool, False),
             'combatarea.min': ('min', (float, float), False),
             'combatarea.max': ('max', (float, float), False),
             'combatareamanager.pythondamage': ('player_damage', float, True),
             'combatareamanager.timeallowedoutside': ('time_allowed_outside', float, True),
             'combatareamanager.use': ('used', bool, True),
             'combatareamanager.enablepython': ('enablePython', bool, True),
             'combatarea.usepython': ('usePython', bool, False),
             'combatarea.damageusepercentage': ('damageUsePercentage', bool, False),
             'combatarea.overridetimer': ('time', float, False),
             'combatarea.overridedamage': ('damage', float, False),
             'combatarea.minheight': ('minHeight', float, False),
             'combatarea.maxheight': ('maxHeight', float, False),
             'combatarea.ignoreinvehicle': ('ignoreInVehicle', bool, False),
             'combatarea.allowdeployables': ('allowDeployables', bool, False)}
            zipfilepath = os.path.join(host.sgl_getModDirectory(), 'levels', host.sgl_getMapName(), 'server.zip')
            gpopath = os.path.join('gamemodes', 'gpm_' + rcore.getGameMode(), str(rcore.getMapLayer()), 'gameplayobjects.con').replace('\\', '/')
            gpopathextra = os.path.join('gamemodes', 'gpm_' + rcore.getGameMode(), str(rcore.getMapLayer()), 'combatareaextras.con').replace('\\', '/')
            zip = zipfile.ZipFile(zipfilepath, 'r')
            lines = zip.read(gpopath)
            try:
                linesextra = zip.read(gpopathextra)
            except:
                linesextra = ''

            for line in (lines + linesextra).splitlines():
                line = line.lower()
                if not (line.startswith('combatarea') or line.startswith('combatareamanager.') or line.startswith('combatareapython.')):
                    continue
                if line.startswith('combatareapython.'):
                    line = line.replace('combatareapython.', 'combatarea.', 1)
                    isCombatAreaPython = True
                else:
                    isCombatAreaPython = False
                split = line.split(' ')
                key = split[0].lower()
                if len(split) == 1:
                    arg = ''
                else:
                    arg = split[1]
                try:
                    if key in specialHandlers:
                        specialHandlers[key](arg, isCombatAreaPython)
                    elif key in parsing_funcs:
                        name, typ, isManager = parsing_funcs[key]
                        self.setOption(name, typ, arg, isManager)
                except:
                    rdebug.debugMessage('Error parsing %s, check python_errors.log' % line)
                    rdebug.errorMessage()

            self.commitActive()
            zip.close()
        except:
            rdebug.debugMessage('fatal error parsing combat areas, check python_errors.log')
            rdebug.errorMessage()

    def deleteAllFromEngine(self):
        for dod in self.all_dods:
            dod.deleteFromEngine()


NUMBEROFTYPES = 10
LAND = 0
SEA = 1
PLANES = 2
CHOPPERS = 3
ALL = 4
AERIAL = 5
DEPLOYABLES = 6
ANTIAIR = 7
ANTITANK = 8
MINES = 9
vehicleTypeToDODType = {'apc': {LAND},
 'jep': {LAND},
 'aav': {LAND, ANTIAIR},
 'ifv': {LAND, ANTITANK},
 'trk': {LAND},
 'tnk': {LAND, ANTITANK},
 'atm': {LAND, ANTITANK},
 'bik': {LAND},
 'shp': {SEA},
 'jet': {PLANES, AERIAL},
 'the': {CHOPPERS, AERIAL},
 'ahe': {CHOPPERS, AERIAL}}
kitTypeToDODType = {'aa': {ANTIAIR},
 'at': {ANTITANK},
 'riflemanat': {ANTITANK}}

def _setVehicleType(vehicle):
    try:
        split = vehicle.templateName.split('_', 2)
        if split[0].lower() == 'deployable':
            vehicle.dod_types = {LAND}
            return
        type = split[1].lower()
        if type in vehicleTypeToDODType:
            vehicle.dod_types = vehicleTypeToDODType[type]
        elif vehicle.templateName.contains('boat'):
            vehicle.dod_types = {SEA}
    except:
        vehicle.dod_types = {LAND}


def _setKitType(kit):
    try:
        split = kit.templateName.split('_', 2)
        type = split[1].lower()
        kit.dod_types = kitTypeToDODType.get(type, set())
    except:
        kit.dod_types = set()