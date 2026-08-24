import bf2
import host
import realityconstants as CONSTANTS
import realitycore as rcore
import realitydebug as rdebug
import realityevents as revents
import realityserver
import realityspawner as rspawner
import realitytimer as rtimer
g_currentGPM = None

def init():
    global g_currentGPM
    g_currentGPM = PRGameMode()
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('ConsoleSendCommand', onSetLayerMode, 1)


def onSetLayerMode(cmd, args):
    if cmd == 'setLayerMode':
        maplistArray = host.rcon_invoke('maplist.list').split('\n')
        currentlevel = int(host.rcon_invoke('admin.currentlevel').split('\n')[0])
        layer = int(maplistArray[currentlevel].split(' ')[3])
        host.rcon_invoke('v_layer = %s' % layer)
        host.rcon_invoke('v_mode = %s' % g_currentGPM.getBf2Type())


def getCurrentGameMode():
    return g_currentGPM


def getCurrentGameModeType():
    if g_currentGPM:
        return g_currentGPM.getType()
    else:
        return 'something went wrong'


def setCurrentGameMode(gpm = None):
    global g_currentGPM
    if gpm:
        g_currentGPM = gpm
    elif g_currentGPM:
        del g_currentGPM


def onGameStatusChanged(status):
    if status != bf2.GameStatus.Loading:
        if g_currentGPM:
            g_currentGPM.onGameStatusChanged(status)


class PRGameMode(object):

    def __init__(self):
        self.g_message = None
        self.g_end = None
        return

    def registerHandlers(self):
        host.registerHandler('TimeLimitReached', self.onTimeLimitReached)
        host.registerHandler('TicketLimitReached', self.onTicketLimitReached)
        host.registerHandler('PlayerDeath', self.onPlayerDeathTicket)
        host.registerHandler('PlayerKilled', self.onPlayerKilledTicket)
        host.registerHandler('VehicleDestroyed', self.onVehicleDestroyedTicket)

    def unregisterHandlers(self):
        host.unregisterHandler(self.onTimeLimitReached)
        host.unregisterHandler(self.onTicketLimitReached)
        host.unregisterHandler(self.onPlayerDeathTicket)
        host.unregisterHandler(self.onPlayerKilledTicket)
        host.unregisterHandler(self.onVehicleDestroyedTicket)

    def onGameStatusChanged(self, status):
        if status == bf2.GameStatus.Playing:
            self.registerHandlers()
            self.setupTickets()
            self.g_message = rtimer.Timer(rcore.sendMessageToAll, realityserver.C('STARTDELAY') + 3, 1, 'Comienza la batalla! Mapa: (%s) Modo de juego: (%s) Variante: (%s)' % ( rcore.getMapName(), rcore.getGameModeName(), rcore.getMapLayerName()))
        elif status == bf2.GameStatus.EndGame:
            self.unregisterHandlers()
            if self.g_message:
                self.g_message.destroy()
                self.g_message = None
            if self.g_end:
                self.g_end.destroy()
                self.g_end = None
        return

    def setupTickets(self):
        ticketsTeam1 = self.calcStartTickets(bf2.gameLogic.getDefaultTickets(1))
        ticketsTeam2 = self.calcStartTickets(bf2.gameLogic.getDefaultTickets(2))
        try:
            gpm = rspawner.getSpawnerProperties('gpm_tickets', ['minspawndelay', 'maxspawndelay'])
            if gpm:
                ticketsTeam1 = self.calcStartTickets(int(gpm['minspawndelay']))
                ticketsTeam2 = self.calcStartTickets(int(gpm['maxspawndelay']))
        except:
            pass

        bf2.gameLogic.setTickets(1, ticketsTeam1)
        bf2.gameLogic.setTickets(2, ticketsTeam2)
        bf2.gameLogic.setTicketState(1, 0)
        bf2.gameLogic.setTicketState(2, 0)
        bf2.gameLogic.setTicketChangePerSecond(1, 0)
        bf2.gameLogic.setTicketChangePerSecond(2, 0)
        bf2.gameLogic.setTicketLimit(1, 1, 0)
        bf2.gameLogic.setTicketLimit(2, 1, 0)
        bf2.gameLogic.setTicketLimit(1, 2, 50)
        bf2.gameLogic.setTicketLimit(2, 2, 50)
        bf2.gameLogic.setTicketLimit(1, 3, int(ticketsTeam1 * 0.1))
        bf2.gameLogic.setTicketLimit(2, 3, int(ticketsTeam2 * 0.1))
        bf2.gameLogic.setTicketLimit(1, 4, int(ticketsTeam1 * 0.2))
        bf2.gameLogic.setTicketLimit(2, 4, int(ticketsTeam1 * 0.2))

    def onTicketLimitReached(self, team, limitId):
        if limitId == -1:
            self.endGame(rcore.getOtherTeam(team), 3)
        else:
            self.updateTicketWarning(team, limitId)

    def onTimeLimitReached(self, value):
        team1tickets = bf2.gameLogic.getTickets(1)
        team2tickets = bf2.gameLogic.getTickets(2)
        winner = 0
        victoryType = 0
        if team1tickets > team2tickets:
            winner = 1
            victoryType = 3
        elif team2tickets > team1tickets:
            winner = 2
            victoryType = 3
        self.endGame(winner, victoryType)

    def updateTicketWarning(self, team, limitId):
        oldTicketState = bf2.gameLogic.getTicketState(team)
        newTicketState = 0
        if oldTicketState >= 10:
            newTicketState = 10
        if limitId == -2:
            newTicketState = 10
        elif limitId == 2:
            newTicketState = 0
        elif limitId == -3:
            newTicketState += 2
        elif limitId == -4:
            newTicketState += 1
        if oldTicketState != newTicketState:
            bf2.gameLogic.setTicketState(team, newTicketState)

    def calcTicketLossForTeam(self, team, otherTeamAreaValue, otherTeamAreaOverweight):
        if otherTeamAreaValue >= 100 and otherTeamAreaOverweight > 0:
            if realityserver.isCoopServer():
                if otherTeamAreaValue == 100:
                    ticketLossPerSecond = bf2.gameLogic.getDefaultTicketLossPerMin(team) * 10
                    return ticketLossPerSecond
                if otherTeamAreaValue > 100:
                    ticketLossPerSecond = bf2.gameLogic.getDefaultTicketLossPerMin(team) / 60.0 * (otherTeamAreaOverweight / 100.0)
                    return ticketLossPerSecond
            else:
                ticketLossPerSecond = bf2.gameLogic.getDefaultTicketLossPerMin(team) / 60.0 * (otherTeamAreaOverweight / 100.0)
                return ticketLossPerSecond
        else:
            return 0

    def calcStartTickets(self, mapDefaultTickets):
        return int(mapDefaultTickets * (bf2.serverSettings.getTicketRatio() / 100.0))

    def endGame(self, winner, victory):
        if not self.g_end:
            rcore.sendMessageToAll('La batalla ha terminado...')
            self.g_end = rtimer.Timer(self.reallyEndGame, 5, 1, (winner, victory))

    def reallyEndGame(self, data):
        try:
            if self.g_end:
                self.g_end.destroy()
                self.g_end = None
        except:
            pass

        rcore.silentlyEndGame(data[0], data[1])
        return

    def onPlayerDeathTicket(self, victim, vehicle):
        if not victim:
            return
        if CONSTANTS.VEHICLE_TYPE_SOLDIER not in realityserver.C('TICKETS'):
            return
        self.addTickets(victim.getTeam(), realityserver.C('TICKETS')[CONSTANTS.VEHICLE_TYPE_SOLDIER], 'player death - %s' % victim.getName())

    def onPlayerKilledTicket(self, victim, attacker, weapon, assists, soldier):
        if not victim:
            return
        if CONSTANTS.VEHICLE_TYPE_SOLDIER not in realityserver.C('TICKETS'):
            return
        self.addTickets(victim.getTeam(), realityserver.C('TICKETS')[CONSTANTS.VEHICLE_TYPE_SOLDIER], 'player kill - %s' % victim.getName())

    def onVehicleDestroyedTicket(self, vehicle, attacker):
        if not vehicle or rcore.isSoldier(vehicle) or vehicle.getIsWreck():
            return
        try:
            vehicleTeam = vehicle.getTeam()
            if vehicleTeam not in (1, 2):
                return
        except:
            return

        rootVehicle = bf2.objectManager.getRootParent(vehicle)
        vehicleTemplate = rootVehicle.templateName.lower()
        vehicleType = CONSTANTS.getVehicleType(vehicleTemplate)
        if vehicleType not in realityserver.C('TICKETS'):
            return
        self.addTickets(vehicleTeam, realityserver.C('TICKETS')[vehicleType], 'vehicle destroyed - %s' % vehicleTemplate)

    def addTickets(self, team, tickets, debug = ''):
        tickets = int(tickets)
        if team not in (1, 2) or tickets == 0 or self.g_end:
            return
        remaining = bf2.gameLogic.getTickets(team) + tickets
        event = revents.getEvents('TicketsChanged')
        revents.sendToHandlers(event, team, tickets, remaining)
        bf2.gameLogic.setTickets(team, remaining)
        if debug and rdebug.isDebugEnabled('tickets'):
            rdebug.debugMessage(str(tickets) + ' tickets to team ' + str(team) + ' - ' + debug, 'tickets')

    def checkAssetPlacementRestrictions(self, asset, position, player):
        return True

    def checkKitRequestRestrictions(self, kit, player):
        return True

    def overrideModifySpawn(self, player):
        return False

    def getType(self):
        return 'uknown'