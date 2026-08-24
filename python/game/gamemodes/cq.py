import random
import bf2
import game.realitycore as rcore
import game.realitydebug as rdebug
import game.realityflags as rflags
import game.realitygamemode as rgamemode
import game.realitymarkers as rmarkers
import game.realityserver as realityserver
import host
SGID_ALWAYS_CAPTUREABLE = 99

def init():
    rgamemode.setCurrentGameMode(PRAAS())
    print 'gpm_cq.py initialized'


def deinit():
    rgamemode.setCurrentGameMode()
    print 'gpm_cq.py uninitialized'


class PRAAS(rflags.PRFlags):

    def __init__(self):
        rflags.PRFlags.__init__(self)
        self.g_markers = []
        self.g_active_flags = {}
        self.g_active_groups = {}
        self.flagtriggers_ignoreFlyingVehicles = True
        self.flagtriggers_ignoreKits = ['civilian', 'pilot', 'unarmed']

    def registerHandlers(self):
        rflags.PRFlags.registerHandlers(self)
        host.registerHandler('ControlPointNeutralized', self.onCPNeutralized)
        host.registerHandler('ControlPointCaptured', self.onCPCaptured)

    def unregisterHandlers(self):
        rflags.PRFlags.unregisterHandlers(self)
        host.unregisterHandler(self.onCPNeutralized)
        host.unregisterHandler(self.onCPCaptured)

    def onGameStatusChanged(self, status):
        rflags.PRFlags.onGameStatusChanged(self, status)
        self.g_markers = []
        if status == bf2.GameStatus.Playing:
            host.sh_setEnableCommander(realityserver.C('AAS_COMMANDER'))
            for team in [1, 2]:
                bf2.gameLogic.setTickets(team, int(bf2.gameLogic.getTickets(team)))

            self.updateObjectives()
            if 'andromeda' == bf2.gameLogic.getMapName():
                realityserver.C('DEAD_TIME', realityserver.C('SKIRMISH_DEAD_TIME'))
                realityserver.C('MAX_PENALTY', realityserver.C('SKIRMISH_MAX_PENALTY'))
            elif 'test_airfield' == bf2.gameLogic.getMapName():
                realityserver.C('DEAD_TIME', 2)
                realityserver.C('MAX_PENALTY', 2)
            elif 'test_bootcamp' == bf2.gameLogic.getMapName():
                realityserver.C('DEAD_TIME', 2)
                realityserver.C('MAX_PENALTY', 2)

    def setupRoutes(self):
        allRoutes = {}
        groupSizes = {}
        self.g_active_groups = {}
        for cp in rcore.getControlPoints():
            if cp.sgid < 1:
                continue
            if not self.isCPCapturable(cp):
                continue
            if cp.route not in allRoutes:
                allRoutes[cp.route] = {}
                groupSizes[cp.route] = {}
                allRoutes[cp.route][cp.sgid] = [cp]
            elif cp.sgid not in allRoutes[cp.route]:
                allRoutes[cp.route][cp.sgid] = [cp]
            else:
                allRoutes[cp.route][cp.sgid].append(cp)
            groupSizes[cp.route][cp.sgid] = cp.random

        if 0 in allRoutes:
            self.g_active_groups = allRoutes[0]
            del allRoutes[0]
        route = 0
        routes = allRoutes.keys()
        if len(routes) > 0:
            route = random.choice(routes)
            self.g_active_groups.update(allRoutes[route])
        for group in self.g_active_groups:
            groupFlags = self.g_active_groups[group]
            if len(groupFlags) > 1:
                remove = len(groupFlags) - groupSizes[route][group]
                if 0 < remove < len(groupFlags):
                    random.shuffle(groupFlags)
                    del groupFlags[0:remove]
                    self.g_active_groups[group] = groupFlags

        return route

    def setupFlags(self):
        route = self.setupRoutes()
        deletion = []
        for cp in rcore.getControlPoints():
            if cp.route not in [0, route]:
                if self.isCPCapturable(cp):
                    deletion.append(cp)
            elif cp.sgid not in self.g_active_groups:
                if self.isCPCapturable(cp):
                    deletion.append(cp)
            elif cp not in self.g_active_groups[cp.sgid]:
                if self.isCPCapturable(cp):
                    deletion.append(cp)

        rcore.deleteControlPoints(deletion)

    def isCPCapturableByTeam(self, cp, team):
        if not rflags.PRFlags.isCPCapturableByTeam(self, cp, team):
            return False
        if team not in (1, 2) or cp not in self.g_active_flags[team]:
            return False
        return True

    def getMinNumPlayersToTakeControl(self):
        if bf2.playerManager.getNumberOfPlayers() / 2 < realityserver.C('AAS_MINNRTOTAKECONTROL'):
            return 1
        return realityserver.C('AAS_MINNRTOTAKECONTROL')

    def getMinNumPlayersToNeutral(self):
        if bf2.playerManager.getNumberOfPlayers() / 2 < realityserver.C('AAS_MINNRTONEUTRAL'):
            return 1
        return realityserver.C('AAS_MINNRTONEUTRAL')

    def onCPNeutralized(self, cp, team, players):
        self.updateObjectives()

    def onCPCaptured(self, cp, team, players):
        self.updateObjectives()

    def updateCaptureAll(self):
        for team in [1, 2]:
            for cp in self.g_active_flags[team]:
                self.updateCapture(cp)

    def updateObjectives(self):
        secured = {1: None,
         2: None}
        markers = []
        self.g_active_flags = {1: [],
         2: []}
        groups = self.g_active_groups.keys()
        if SGID_ALWAYS_CAPTUREABLE in groups:
            groups.remove(SGID_ALWAYS_CAPTUREABLE)
        groups.sort()
        for team in [1, 2]:
            ids = range(0, len(groups))
            if team == 2:
                ids.reverse()
            for i in ids:
                sgid = groups[i]
                notSecured = False
                for cp in self.g_active_groups[sgid]:
                    if cp.cp_getParam('team') != team:
                        notSecured = True
                        break

                if notSecured:
                    break
                else:
                    secured[team] = i

        if len(groups) == 0:
            return
        else:
            advance = {1: groups[0],
             2: groups[-1]}
            for team in [1, 2]:
                if secured[team] is None:
                    continue
                _next = secured[team]
                if team == 1:
                    _next += 1
                else:
                    _next -= 1
                if len(groups) > _next > -1:
                    advance[team] = groups[_next]
                else:
                    advance[team] = -1

            for sgid in self.g_active_groups:
                for cp in self.g_active_groups[sgid]:
                    team = cp.cp_getParam('team')
                    capture = self.getCPCapture(cp)
                    if capture == 0:
                        continue
                    for ateam in [1, 2]:
                        dteam = rcore.getOtherTeam(ateam)
                        if (sgid == SGID_ALWAYS_CAPTUREABLE or sgid == advance[ateam]) and (capture == 3 or capture == ateam) and team != ateam:
                            if self.isBleedFlag(cp, ateam):
                                markers.append(rmarkers.markerPointAttackRevealed(ateam, cp.getPosition(), cp.templateName))
                                if team == dteam:
                                    markers.append(rmarkers.markerPointDefendRevealed(dteam, cp.getPosition(), cp.templateName))
                            else:
                                markers.append(rmarkers.markerPointAttack(ateam, cp.getPosition(), cp.templateName))
                                if team == dteam:
                                    markers.append(rmarkers.markerPointDefend(dteam, cp.getPosition(), cp.templateName))
                            self.g_active_flags[ateam].append(cp)
                            rdebug.debugMessage('active flag %s for team %s' % (cp.templateName, ateam), 'gamemode')

            for index in self.g_markers:
                if index not in markers:
                    rmarkers.deleteMarker(index)

            self.g_markers = markers
            return

    def getType(self):
        return 'aas'

    def getBf2Type(self):
        return 'gpm_cq'