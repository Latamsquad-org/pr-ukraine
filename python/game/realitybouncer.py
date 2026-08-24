import bf2
import host
import realityadmin as radmin
import realityconfig_admin as ras
import realityconstants as rconstants
import realitycore as rcore
import realitydebug as rdebug
import realitymemory as rmemory
import realitytimer as rtimer

def init():
    ACSYS()


class ACSYS:
    """
    Asset Claim SYStem
    """
    KICK_ENTER_GRACE = 3.0
    KICK_SQUAD_GRACE = 10.0
    KICK_SQUAD_AIR_GRACE = 30.0
    EVENT_TYPE_SQUADSTATE = 64
    EVENT_IS_ASSET_SL = 256
    EVENT_IS_LOCKED = 512

    def __init__(self):
        if not ras.acsys_enable:
            rdebug.debugMessage('ACSYS is Disabled!', 'acsys')
            return
        rdebug.debugMessage('ACSYS is Enabled!', 'acsys')
        host.registerHandler('EnterVehicle', self.onEnterVehicle)
        host.registerHandler('EnterVehicle', self.onEnterVehicleCheckLowPop)
        host.registerHandler('SquadCreated', self.onSquadCreated)
        host.registerHandler('SquadRemoved', self.onSquadRemoved)
        host.registerHandler('PlayerChangedSquad', self.onPlayerChangedSquad)
        host.registerHandler('RemoteCommandACSYSToggle', self.onRemoteCommandACSYSToggle)
        host.registerHandler('ChangedSquadLeader', self.onChangedSquadLeader)
        host.registerHandler('ChatMessage', self.onChatDebug)
        host.registerGameStatusHandler(self.onGameStatusChanged)
        rdebug.debugMessage('ACSYS registered handlers', 'acsys')
        self.asset_squads = {1: {},
         2: {}}
        self.locked_squads = set()
        self.types = {}
        self.excludes = {}
        self.low_pop_types = set()
        self.low_pop_includes = set()

    def onChatDebug(self, playerID, msgText, channel, flags):
        if 'racsysprint' in msgText:
            for qa in rdebug.PRDEBUG_QAs_ONLINE:
                radmin.personalMessage('locked sq: ' + str(self.locked_squads), qa)
                radmin.personalMessage('asset types: %s' % str(self.types), qa)
                radmin.personalMessage('asset squads: %s' % str(self.asset_squads), qa)

    def onGameStatusChanged(self, status):
        if status == bf2.GameStatus.Loaded:
            self.asset_squads = {1: {},
             2: {}}
            self.locked_squads.clear()
            self.types.clear()
            self.low_pop_types.clear()
            self.excludes.clear()
            self.low_pop_includes.clear()
            for claimable in ras.acsys_assets:
                self.types[claimable] = ras.acsys_assets[claimable]['squad_controls']
                self.excludes[claimable] = [ templateName.lower() for templateName in ras.acsys_assets[claimable]['exclude'] ]

            rdebug.debugMessage('ACSYS asset types: %s' % str(self.types))
            self.low_pop_types.update([ t for t in ras.acsys_low_pop['vehicle_type'] ])
            self.low_pop_includes.update([ templateName.lower() for templateName in ras.acsys_low_pop['include'] ])

    def deinit(self):
        host.unregisterHandler(self.onEnterVehicle)
        host.unregisterHandler(self.onEnterVehicleCheckLowPop)
        host.unregisterHandler(self.onSquadCreated)
        host.unregisterHandler(self.onSquadRemoved)
        host.unregisterHandler(self.onPlayerChangedSquad)
        host.unregisterHandler(self.onRemoteCommandACSYSToggle)
        host.unregisterHandler(self.onChangedSquadLeader)
        host.unregisterGameStatusHandler(self.onGameStatusChanged)

    def onRemoteCommandACSYSToggle(self, player, cmd, args):
        rdebug.debugMessage('ACSYS toggle', 'acsys')
        if not player.isValid():
            return False
        team = player.getTeam()
        sq = player.getSquadId()
        player_sq = (team, sq)
        if self.isAssetSquadSL(player):
            if player_sq not in self.locked_squads:
                bf2.gameLogic.sendGameEvent(player, 10, self.EVENT_TYPE_SQUADSTATE | self.EVENT_IS_ASSET_SL | self.EVENT_IS_LOCKED)
                self.locked_squads.add(player_sq)
                rdebug.debugMessage('ACSYS assets locked', 'acsys')
            else:
                bf2.gameLogic.sendGameEvent(player, 10, self.EVENT_TYPE_SQUADSTATE | self.EVENT_IS_ASSET_SL)
                self.locked_squads.remove(player_sq)
                rdebug.debugMessage('ACSYS assets unlocked', 'acsys')

    def isAssetSquadSL(self, player):
        if not player.isValid():
            return False
        team = player.getTeam()
        player_sq = (team, player.getSquadId())
        if not player.isSquadLeader():
            return False
        return player_sq in self.asset_squads[team].values()

    def onSquadCreated(self, player, team, squad, name):
        if not self.isACSYSGameMode():
            return
        if not player.isValid():
            return
        assetFound = False
        for asset in ras.acsys_assets:
            for searchstr in ras.acsys_assets[asset]['squadname_contains']:
                if searchstr.lower() not in name.lower():
                    continue
                if assetFound:
                    radmin.personalMessage('Has sido resignado por utilizar un nombre de escuadra ambiguo.', player)
                    rtimer.fireNextTick(radmin.resignPlayer, data=player)
                    return
                if asset in self.asset_squads[team]:
                    rdebug.debugMessage('ACSYS existing asset squad found, denying player', 'acsys')
                    radmin.personalMessage('Has sido resigando por duplicar una escuadra.', player)
                    rtimer.fireNextTick(radmin.resignPlayer, data=player)
                    return
                rdebug.debugMessage('ACSYS claiming asset for squad', 'acsys')
                self.asset_squads[team][asset] = (team, squad)
                assetFound = True
                self.locked_squads.add((team, squad))
                player.asset_squad_team_creation = team
                rdebug.debugMessage('ACSYS claimed asset for squad OK', 'acsys')

        self.refreshSL(player)

    def refreshSL(self, SL):
        rdebug.debugMessage('ACSYS refreshing SL', 'acsys')
        event = self.EVENT_TYPE_SQUADSTATE
        if self.isAssetSquadSL(SL):
            event |= self.EVENT_IS_ASSET_SL
        if (SL.getTeam(), SL.getSquadId()) in self.locked_squads:
            event |= self.EVENT_IS_LOCKED
        bf2.gameLogic.sendGameEvent(SL, 10, event)
        rdebug.debugMessage('ACSYS refreshed SL OK', 'acsys')

    def onChangedSquadLeader(self, squadID, oldLeaderPlayerObject, newLeaderPlayerObject):
        """
        Refresh HUD state
        """
        rdebug.debugMessage('ACSYS SL change', 'acsys')
        event = self.EVENT_TYPE_SQUADSTATE
        if oldLeaderPlayerObject is not None and oldLeaderPlayerObject.isValid():
            bf2.gameLogic.sendGameEvent(oldLeaderPlayerObject, 10, event)
            rdebug.debugMessage('ACSYS cleared SL state', 'acsys')
        self.refreshSL(newLeaderPlayerObject)
        return

    def onSquadRemoved(self, team, squad):
        rdebug.debugMessage('ACSYS squad removed %i' % squad, 'acsys')
        for sq in self.asset_squads[team]:
            if (team, squad) == self.asset_squads[team][sq]:
                del self.asset_squads[team][sq]
                rdebug.debugMessage('ACSYS cleared squad %s from claim list' % str(sq), 'acsys')
                break

    def forceDriverExitLowPop(self, data):
        player, vehicle, count, grace = data
        secondsPerCheck = 2.0
        if not player.isValid():
            return
        if not self.isServerLowPop():
            return
        rcore.sendMessageToPlayer(player, 1220104, 1)
        if count * secondsPerCheck > grace:
            rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
            rtimer.fireOnce(self.forceDriverExit, secondsPerCheck, data=(player,
             vehicle,
             count + 1,
             grace))
        else:
            return

    def forceDriverExit(self, data):
        rdebug.debugMessage('ACSYS forcing driver exit', 'acsys')
        player, vehicle, count, grace = data
        secondsPerCheck = 2.0
        if not player.isValid():
            return
        else:
            vehicleOwner = self.getVehicleOwner(vehicle)
            if vehicleOwner is None or (player.getTeam(), player.getSquadId()) == vehicleOwner:
                rdebug.debugMessage('ACSYS player is allowed to use vehicle, owner: %s' % str(vehicleOwner), 'acsys')
                return
            if self.isPlayerDriver(player, vehicle):
                rdebug.debugMessage('ACSYS player with no claim is driving forcing exit, owner: %s' % str(vehicleOwner), 'acsys')
                if count * secondsPerCheck > grace:
                    rcore.sendMessageToPlayer(player, 1220104, 1)
                    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_USE)
                rtimer.fireOnce(self.forceDriverExit, secondsPerCheck, data=(player,
                 vehicle,
                 count + 1,
                 grace))
            else:
                rdebug.debugMessage('ACSYS player with no claim is not driving, owner: %s' % str(vehicleOwner), 'acsys')
                return
            return

    def getVehicleOwner(self, vehicle):
        rdebug.debugMessage('ACSYS checking vehicle ownership', 'acsys')
        if not vehicle.isValid():
            return
        else:
            veh_type = rconstants.getVehicleType(vehicle.templateName)
            rdebug.debugMessage('ACSYS vehicle type: %s' % str(veh_type), 'acsys')
            claimable = None
            for claim in self.types:
                if veh_type in self.types[claim]:
                    claimable = claim

            rdebug.debugMessage('ACSYS vehicle claimable? %s' % str(claimable), 'acsys')
            if claimable is None:
                return
            team = vehicle.getTeam()
            if any((excludeName in vehicle.templateName.lower() for excludeName in self.excludes[claimable])):
                rdebug.debugMessage('ACSYS vehicle excluded', 'acsys')
                return
            owner = None
            for asset in self.asset_squads[team]:
                if asset.lower() == claimable.lower():
                    owner = self.asset_squads[team][asset]

            rdebug.debugMessage('ACSYS owner: %s' % str(owner), 'acsys')
            return owner

    def isPlayerDriver(self, player, vehicle):
        if not player.isValid():
            return False
        root = bf2.objectManager.getRootParent(vehicle)
        return player.getVehicle() is root

    def isServerLowPop(self):
        if bf2.playerManager.getNumberOfPlayers() < ras.acsys_low_pop_limit:
            return True
        return False

    def isACSYSGameMode(self):
        valid_modes = ('cq', 'cnc', 'coop', 'insurgency')
        if rcore.getGameMode() in valid_modes:
            return True
        return False

    def onEnterVehicleCheckLowPop(self, player, vehicle, freeSoldier = False):
        if not ras.acsys_enable:
            return
        if not self.isACSYSGameMode():
            return
        if player.isAIPlayer():
            return
        if not self.isServerLowPop():
            return
        if not self.isPlayerDriver(player, vehicle):
            return
        vtype = rconstants.getVehicleType(vehicle.templateName)
        if vtype in self.low_pop_types or vehicle.templateName.lower() in self.low_pop_includes:
            radmin.personalMessage('Se necesitan mas jugadores para utilizar este vehiculo!', player)
            rmemory.HudVarWriteEventWstringWithTimedShowvar(player, 'PythonGameWarning', 'ADVERTENCIA:\nSe necesitan mas jugadores para utilizar este vehiculo!', 8)
            rcore.sendMessageToPlayer(player, 1220104, 1)
            rtimer.fireOnce(self.forceDriverExitLowPop, 2.0, data=(player,
             vehicle,
             0,
             self.KICK_ENTER_GRACE))

    def onEnterVehicle(self, player, vehicle, freeSoldier = False):
        if not ras.acsys_enable:
            return
        elif player.isAIPlayer():
            return
        elif not self.isPlayerDriver(player, vehicle):
            return
        else:
            owner = self.getVehicleOwner(vehicle)
            rdebug.debugMessage('ACSYS Vehicle Owner: (team,sq) %s' % str(owner), 'acsys')
            if owner is None:
                return
            elif (player.getTeam(), player.getSquadId()) == owner:
                return
            elif owner not in self.locked_squads:
                return
            radmin.personalMessage('No estas en la escuadra correcta para usar este vehiculo!', player)
            rcore.sendMessageToPlayer(player, 1220104, 1)
            rmemory.HudVarWriteEventWstringWithTimedShowvar(player, 'PythonGameWarning', 'ADVERTENCIA:\nNo estas en la escuadra correcta para usar este vehiculo!', 8)
            rtimer.fireOnce(self.forceDriverExit, 1.0, data=(player,
             vehicle,
             0,
             self.KICK_ENTER_GRACE))
            return

    def onPlayerChangedSquad(self, player, oldSquadID, newSquadID):
        if not player.isValid():
            return
        else:
            team = player.getTeam()
            vehicle = player.getVehicle()
            air = {rconstants.VEHICLE_TYPE_HELIATTACK,
             rconstants.VEHICLE_TYPE_HELI,
             rconstants.VEHICLE_TYPE_JET,
             rconstants.VEHICLE_TYPE_TURBOPROP}
            if vehicle is player.getDefaultVehicle():
                return
            owner = self.getVehicleOwner(vehicle)
            if owner is None:
                return
            if (team, newSquadID) == owner:
                return
            if not self.isPlayerDriver(player, vehicle):
                return
            radmin.personalMessage('No estas en la escuadra correcta para usar este vehiculo!', player)
            if rconstants.getVehicleType(vehicle.templateName) in air:
                grace = self.KICK_SQUAD_AIR_GRACE
            else:
                grace = self.KICK_SQUAD_GRACE
            rtimer.fireOnce(self.forceDriverExit, grace, data=(player,
             vehicle,
             0,
             grace))
            return