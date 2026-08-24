import sys, time, bf2, host, realityadmin, realityevents, realitylogger, realitymemory, realityserver, realitytimer, realityvehicles
PRDEBUG = None
PRDEBUG_AVAILABLE = [
 2,
 3,
 4,
 5,
 6,
 7,
 8,
 9,
 10,
 11,
 12,
 13,
 14,
 15,
 16,
 17,
 18,
 19,
 20,
 21,
 22,
 23,
 24,
 25,
 10,
 26,
 27,
 28,
 29]
PRDEBUG_DEVS = {'[r-dev]mats391': '1d9d25ce42dc45a9b46209b129389a15',
    'Chaziz': '792eb21803b84249a43c27752f9bd0e7',
    'pawina': '8a59e8005de34f0da5c9ad0d117efe87'}                
PRDEBUG_ONLINE = []
PRDEBUG_ALWAYSPRINTCONSOLE = False
PRDEBUG_QAs = {'alon': '2490fb4169a6469d9cb6134cf259df1f',
   'max': 'e3ffa59119d54ca0b976d60722f7c471',
   'outlawz': '410d7dd46acf49f588301ad7a485dcb6',
   'shrapgnoll': '77ff5fecc0e648249bd6b01fdba02242',
   'suchar': 'd3592817d1ef466db01c7a56769e2b45'}
PRDEBUG_QAs_ONLINE = []
DEBUG = '\xc2\xa7C1001*LATAM_DBG*\xc2\xa7C1001'
DEBUG_CONSOLE = 'DBG '

def errorMessage():
    try:
        try:
            errType = str(sys.exc_type)
            errPart1 = 'EXCEPTION: ' + errType[errType.find('.') + 1:]
            errPart2 = str(sys.exc_value)
        except:
            return

        trace = '\n\tTrace:'
        lastTrace = ''
        while sys.exc_traceback is not None:
            if sys.exc_traceback.tb_lineno == 0:
                sys.exc_traceback = sys.exc_traceback.tb_next
                continue
            lastTrace = str(sys.exc_traceback.tb_frame.f_code.co_filename) + ' on line ' + str(sys.exc_traceback.tb_lineno)
            trace += '\n\t\t' + lastTrace
            sys.exc_traceback = sys.exc_traceback.tb_next

        try:
            players = set()
            players.update(PRDEBUG_ONLINE)
            players.update(PRDEBUG_QAs_ONLINE)
            players.update(realityadmin.g_admins.keys())
            players.update(realityadmin.g_lite_admins.keys())
            for player in players:
                realityadmin.personalMessage(errPart1 + ', ' + errPart2, player)
                realityadmin.personalMessage(lastTrace, player)

        except:
            pass

        if not realityserver.isInternetServer() or PRDEBUG_ALWAYSPRINTCONSOLE:
            host.rcon_invoke('echo "' + errPart1 + ', ' + errPart2 + '"')
            host.rcon_invoke('echo "' + lastTrace + '"')
        try:
            fileName = host.sgl_getModDirectory() + '/settings/python_errors_v' + realityserver.getVersion() + '.log'
            d = time.strftime('[%d-%m--%Y %H:%M:%S]')
            errorFile = open(fileName, 'a')
            try:
                errorFile.write('%s GameStatus: %s\n\t%s\n\t%s%s\n' % (d, realityevents.g_gameState, errPart1, errPart2, trace))
            except:
                pass

            errorFile.close()
        except:
            pass

        if isDebugEnabled():
            debugMessage(errPart1 + ', ' + errPart2)
            debugMessage(lastTrace)
    except:
        pass

    return


def debugMessage(message, typ=None):
    prefix = ''
    if typ:
        prefix = typ + ': '
    message = prefix + str(message)
    if bf2.g_debug:
        print (message)
        return
    if isDebugEnabled(typ):
        realityadmin.adminPM(DEBUG + message)
        if not realityserver.isInternetServer() or PRDEBUG_ALWAYSPRINTCONSOLE:
            host.rcon_invoke('echo "' + DEBUG_CONSOLE + message + '"')


def isDebugEnabled(typ=None):
    global PRDEBUG
    if PRDEBUG is None:
        return False
    else:
        if not typ:
            return True
        if typ in PRDEBUG:
            return True
        return False


def init():
    host.registerHandler('RemoteCommandPosition', onRemotePosition)
    host.registerHandler('RemoteCommandDebug', onRemoteDebugCommand)
    host.registerHandler('RemoteCommandIDKFA', onRemoteIDKFA)
    host.registerHandler('RemoteCommandRef', onRemoteRef)
    host.registerHandler('RemoteCommandStamina', onRemoteStamina)
    host.registerHandler('RemoteCommandDestroyables', onRemoteDestroyablesCommand)
    host.registerHandler('RemoteCommandPhysics', onRemoteCommandPhysics)
    host.registerHandler('PlayerDisconnect', onPlayerDisconnect, 1)
    host.registerHandler('PlayerConnect', onPlayerConnect, 1)
    realitylogger.createLogger('profiler', './', 'profiler.txt', 1)
    print ('realitydebug.py initialized')
    try:
        from hashlib import sha1
    except:
        errorMessage()
        host.rcon_invoke('echo "%s"' % 'Warning: failed importing hashlib!')
        host.rcon_invoke('echo "%s"' % 'Please try installing python2.7 on your system as some Python modules wrongly depend on libpython2.7')
        host.rcon_invoke('echo "%s"' % 'Contact us on the forums for more info')


def onPlayerConnect(player):
    if realityserver.isInternetServer():
        if realityserver.getPlayerHash(player) in PRDEBUG_DEVS.values():
            PRDEBUG_ONLINE.append(player)
            debugMessage('Global debug DEV joined')
        if realityserver.getPlayerHash(player) in PRDEBUG_QAs.values():
            PRDEBUG_QAs_ONLINE.append(player)
    elif realityserver.getPlayerName(player).lower() in PRDEBUG_DEVS:
        PRDEBUG_ONLINE.append(player)
        debugMessage('Global debug DEV joined')


def onPlayerDisconnect(player):
    if player in PRDEBUG_ONLINE:
        PRDEBUG_ONLINE.remove(player)
        debugMessage('Global debug DEV left')
    if player in PRDEBUG_QAs_ONLINE:
        PRDEBUG_QAs_ONLINE.remove(player)


def onRemoteRef(player, cmd, args):
    debugMessage('%x' % realitymemory._getObjectPtr(player.getVehicle()))


def onRemoteIDKFA(player, cmd, args):
    if 'linux' in sys.platform:
        debugMessage('Linux not supported')
        return
    realitymemory.rearmPlayer(player)


def onRemoteStamina(player, cmd, args):
    soldier = player.getDefaultVehicle()
    if soldier:
        realitymemory.setSoldierStamina(soldier, 1.0)


physicsTarget = None
physicsTimer = None
physicsSpeed = None
physicsRotationalVelocity = None
physicsPrint = False

def onRemoteCommandPhysics(player, cmd, args):
    global physicsPrint
    global physicsRotationalVelocity
    global physicsSpeed
    global physicsTarget
    global physicsTimer

    def refresh(args=None):
        if physicsTarget is None or not physicsTarget.isValid() or physicsTarget.getPosition() == (0.0,
                                                                                                   0.0,
                                                                                                   0.0):
            return
        physics = realitymemory._getObjectPhysics(physicsTarget)
        if hasattr(physics, 'vx'):
            v = (
             round(physics.vx, 2), round(physics.vy, 2), round(physics.vz, 2))
        else:
            v = None
        if hasattr(physics, 'rx'):
            rv = (
             round(physics.rx, 2), round(physics.ry, 2), round(physics.rz, 2))
        else:
            rv = None
        sleepiness = getattr(physics, 'sleepiness', None)
        sleepinessMax = getattr(physics, 'sleepinessMax', None)
        if physicsPrint:
            debugMessage('v: %s, rv: %s, S: %s/%s' % (
             str(v), str(rv), sleepiness, sleepinessMax))
        if realitymemory.getObjectHasDynamicPhysics(physicsTarget):
            if physicsSpeed:
                realitymemory.setVelocity(physicsTarget, physicsSpeed)
            if physicsRotationalVelocity:
                realitymemory.setAngularVelocity(physicsTarget, physicsRotationalVelocity)
        return

    if physicsTimer is None:
        physicsTimer = realitytimer.Timer(refresh, 0.001, 1)
        physicsTimer.setRecurring(1e-05)
    try:
        if args[0] == 'select':
            physicsTarget = realityvehicles.getRoot(player.getVehicle())
            debugMessage('selected %s' % physicsTarget.templateName)
        elif args[0] == 'stop':
            physicsTarget = None
            debugMessage('unselected')
        elif args[0] == 'speed':
            physicsSpeed = (
             float(args[1]), float(args[2]), float(args[3]))
            debugMessage('speed: %s' % physicsPrint)
        elif args[0] == 'rot':
            physicsRotationalVelocity = (
             float(args[1]), float(args[2]), float(args[3]))
            debugMessage('rot: %s' % physicsPrint)
        elif args[0] == 'print':
            physicsPrint = not physicsPrint
            debugMessage('print: %s' % physicsPrint)
        elif args[0] == 'sleepmax':
            maxSleep = int(args[1])
            realitymemory._getObjectPhysics(physicsTarget).sleepinessMax = maxSleep
            debugMessage('physicsmax: %s' % maxSleep)
    except:
        pass

    return


POSITIONS_DEBUG = {}

def onRemotePosition(player, cmd, args):
    veh = player.getVehicle()
    try:
        if args[0] == 'save':
            name = (' ').join(args[1:])
            POSITIONS_DEBUG[name] = veh.getPosition()
            debugMessage('Posicion guardada como %s' % name)
            return
    except:
        pass

    try:
        if args[0] == 'go':
            name = (' ').join(args[1:])
            veh.setPosition(POSITIONS_DEBUG[name])
            return
    except:
        pass

    try:
        posSplit = ('').join(args).split(',')
        veh.setPosition(tuple(float(p) for p in posSplit))
    except:
        debugMessage('Tu posicion: %s,%s,%s' % veh.getPosition())


def onRemoteDebugCommand(player, cmd, args):
    global PRDEBUG
    global PRDEBUG_AVAILABLE
    import realityadmin
    if len(args) == 0:
        if PRDEBUG is not None:
            realityadmin.adminPM('game.sayAll "' + DEBUG + 'desactivado..."')
            realityadmin.sendToPrism('debugOff', [None])
            PRDEBUG = None
        else:
            realityadmin.adminPM('game.sayAll "' + DEBUG + 'activado..."')
            realityadmin.sendToPrism('debugOn', [None])
            PRDEBUG = []
    else:
        for arg in args:
            if arg == 'all':
                PRDEBUG = []
                for d in PRDEBUG_AVAILABLE:
                    PRDEBUG.append(d)

                realityadmin.adminPM('game.sayAll "' + DEBUG + 'all debugs enabled..."')
            elif arg in PRDEBUG_AVAILABLE:
                if PRDEBUG is not None and arg in PRDEBUG:
                    realityadmin.adminPM('game.sayAll "' + DEBUG + arg + ' debug disabled..."')
                    PRDEBUG.remove(arg)
                else:
                    realityadmin.adminPM('game.sayAll "' + DEBUG + arg + ' debug enabled..."')
                    if PRDEBUG is None:
                        PRDEBUG = []
                    PRDEBUG.append(arg)

    return


def onRemoteDestroyablesCommand(player, cmd, args):
    templates = {}
    for o in bf2.objectManager.getObjectsOfType('dice.hfe.world.ObjectTemplate.DestroyableObject'):
        if not o.isValid():
            continue
        if o.templateName not in templates:
            templates[o.templateName] = 0
        templates[o.templateName] += 1

    for tmp, num in templates.items():
        debugMessage('destroyables: ' + tmp + ' = ' + str(num))


def addDebugger(playerId):
    if playerId not in PRDEBUG_ONLINE:
        PRDEBUG_ONLINE.append(playerId)


def removeDebugger(playerId):
    if playerId in PRDEBUG_ONLINE:
        PRDEBUG_ONLINE.remove(playerId)


def canExecute(player, debug=True, dev=False):
    debugAll = realityserver.isModdableServer() and realityserver.C('PRDEBUG_ALL') == 1
    if dev:
        return debugAll or player in PRDEBUG_ONLINE
    else:
        if debug:
            return (debugAll or player in PRDEBUG_ONLINE) and isDebugEnabled()
        return True


if 'linux' in sys.platform:
    clockFunc = time.time
elif 'win' in sys.platform:
    clockFunc = time.clock
