import os
import re
import bf2
import host
import realityconfig_common as rconfig_common
import realitydebug as rdebug
import realitymemory as rmemory
import realitycore as rcore
HOTFIX_LETTER = ''
SERVER_DEFAULT = 1
CONFIG = {}
CONFIG_BACKUP = {}
g_serverPassword = None
g_serverInternet = None
g_serverCoop = None
g_serverMaxPlayers = None
g_serverConfig = None
g_version = None
g_serverModded = False
g_serverModdedItems = []
roundStartDelay = -1
MAX_PLAYERS = 100

def copy(variable):
    return variable


def verifyMaxPlayers():
    maxPlayers = int(host.rcon_invoke('sv.maxPlayers').replace('\r\n', ''))
    if MAX_PLAYERS < maxPlayers:
        raise ValueError('sv.maxPlayers must be under {}'.format(MAX_PLAYERS))


def verifyServerSettings():
    verifyMaxPlayers()


def isModdedServer(modded = None, message = None):
    global g_serverModded
    global g_serverModdedItems
    if modded:
        g_serverModded = True
    if message and message not in g_serverModdedItems:
        g_serverModdedItems.append(message)
    return g_serverModded


def isPasswordedServer():
    global g_serverPassword
    if g_serverPassword is None:
        try:
            password = str(host.rcon_invoke('sv.password').replace('\n', ''))
        except:
            password = None

        if password:
            g_serverPassword = True
        else:
            g_serverPassword = False
    return g_serverPassword


def isInternetServer():
    global g_serverInternet
    if g_serverInternet is None:
        try:
            internet = int(host.rcon_invoke('sv.internet').replace('\n', ''))
        except:
            internet = None

        if internet:
            g_serverInternet = True
        else:
            g_serverInternet = False
    return g_serverInternet


def isCoopServer():
    global g_serverCoop
    if g_serverCoop is None:
        if host.sgl_getIsAIGame():
            g_serverCoop = True
        else:
            g_serverCoop = False
    return g_serverCoop


def isModdableServer():
    if isInternetServer() and not isPasswordedServer() and not isCoopServer():
        return False
    return True


def checkShutdownLock():
    if os.path.exists('shutdown.lock'):
        raise Exception('Server is in shutdown lock. Delete "shutdown.lock"  to start successfully')


def getPlayerName(player, lowercase = True, prefix = False):
    name = player.getName()
    sp = name.split(' ')
    if len(sp) == 2:
        if not prefix:
            name = sp[1]
    else:
        name = sp[0]
    if lowercase:
        return name.lower()
    return name


def backupConfig():
    global CONFIG
    global CONFIG_BACKUP
    for k, v in CONFIG.items():
        CONFIG_BACKUP[k] = v


def restoreConfig():
    for k, v in CONFIG_BACKUP.items():
        CONFIG[k] = v


def C(key, value = None):
    if value is not None:
        CONFIG[key] = value
    if key not in CONFIG:
        return
    else:
        return CONFIG[key]


def getServerConfig():
    global g_serverConfig
    return g_serverConfig


g_serverProperties = {}
g_serverPropertiesDefault = {'manDownTime': 300,
 'spawnTime': 300,
 'startDelay': 180,
 'timelimit': 14400,
 'numPlayersNeededToStart': 1,
 'ranked': 0,
 'allowFreeCam': 0,
 'allowNoseCam': 1,
 'allowExternalViews': 1,
 'hitIndicator': 0,
 'setScoreLimit': 1000,
 'soldierFriendlyFire': 100,
 'vehicleFriendlyFire': 100,
 'soldierSplashFriendlyFire': 100,
 'vehicleSplashFriendlyFire': 100,
 'friendlyFireWithMines': 1,
 'radioSpamInterval': 4,
 'radioMaxSpamFlagCount': 4,
 'radioBlockedDurationTime': 30,
 'roundsPerMap': 1,
 'noVehicles': 0}
g_serverPropertiesLoad = {'radioSpamInterval': 2,
 'radioMaxSpamFlagCount': 1,
 'radioBlockedDurationTime': 5}

def init():
    verifyServerSettings()
    checkShutdownLock()
    host.registerGameStatusHandler(onGameStatusChanged)
    host.registerHandler('RoundStart', onRoundStart)
    host.registerHandler('RemoteCommandModded', onRemoteModdedCommand)
    host.registerHandler('RemoteCommandShutdown', onRemoteShutdownCommand)
    host.registerHandler('RemoteCommandServer', onRemoteServerCommand)
    setServerName()
    setServerProperties()
    print 'realityserver.py initialized'


def getPlayerHash(p):
    if not isInternetServer():
        return True
    elif hasattr(p, 'hash') and p.hash is not None:
        return p.hash
    else:
        m = re.search('^Id:\\s*%s -.*\\s*CD-key hash: (?P<Hash>[0-9a-f]*)' % p.index, host.rcon_invoke('admin.listplayers'), re.MULTILINE)
        if m and len(m.group('Hash')) == 32:
            p.hash = m.group('Hash')
        else:
            p.hash = False
        return p.hash


def onGameStatusChanged(status):
    global g_serverProperties
    global g_serverPropertiesDefault
    global g_serverConfig
    global g_serverMaxPlayers
    global roundStartDelay
    global g_serverModdedItems
    if status == bf2.GameStatus.Loaded:
        if g_serverConfig:
            C('STARTDELAY', roundStartDelay)
        else:
            if isCoopServer():
                g_serverConfig = 'coop'
            elif isModdableServer():
                if isInternetServer():
                    g_serverConfig = 'private'
                else:
                    g_serverConfig = 'local'
            else:
                g_serverConfig = 'public'
            print '------------ Project Reality %s config' % g_serverConfig
            try:
                CFG = __import__('game.realityconfig_%s' % g_serverConfig, globals(), locals(), ['*'])
            except:
                rdebug.errorMessage()
                raise Exception('Error parsing config! Closing')

            try:
                if g_serverConfig == 'public' and CFG.CONFIG_DEFAULT:
                    pass
            except:
                print '-------------- PR MOD DETECTED - config is invalid'
                raise Exception('Invalid config')

            for k, v in CFG.C.items():
                C(k, v)

            backupConfig()
            CFG = None
            del CFG
            if C('STARTDELAY') != 0:
                roundStartDelay = C('STARTDELAY')
            else:
                roundStartDelay = int(rconfig_common.PRROUNDSTARTDELAY)
            if roundStartDelay < 120 and g_serverConfig == 'public':
                roundStartDelay = 120
            elif roundStartDelay < 5:
                roundStartDelay = 5
            if roundStartDelay > 360:
                roundStartDelay = 360
            if isCoopServer():
                roundStartDelay = 0
            #if str(rcore.getMapName()) == 'test_airfield' or str(rcore.getMapName()) == 'test_bootcamp':
            #    roundStartDelay = 0
            C('STARTDELAY', roundStartDelay)
            try:
                g_serverMaxPlayers = int(host.rcon_invoke('sv.maxPlayers').replace('\n', ''))
            except:
                g_serverMaxPlayers = 64

            if g_serverMaxPlayers <= 0:
                g_serverMaxPlayers = 64
            g_serverPropertiesDefault['manDownTime'] = C('WOUNDED_TIME')
            g_serverPropertiesDefault['spawnTime'] = C('WOUNDED_TIME')
            g_serverPropertiesDefault['startDelay'] = 1
            g_serverPropertiesDefault['maxPlayers'] = g_serverMaxPlayers
            g_serverPropertiesDefault['timelimit'] = int(rconfig_common.PRTIMELIMIT)
            if C('PRTIMELIMIT') is not None:
                g_serverPropertiesDefault['timelimit'] = int(C('PRTIMELIMIT'))
            else:
                C('PRTIMELIMIT', int(rconfig_common.PRTIMELIMIT))
            setServerProperties()
        setServerProperties(g_serverPropertiesLoad)
        if not rmemory.isWindowsListenServer:
            import _realitymemory
            for templateName in C('EXPLOSION_LAGCOMP_DISABLE'):
                _realitymemory.explosionLagCompOverrideTemplate(templateName)

    if status == bf2.GameStatus.EndGame and getServerConfig():
        restoreConfig()
    if status == bf2.GameStatus.Loaded and getServerConfig():
        g_serverModdedItems = []
        if isModdableServer():
            return
        setServerProperties()
        if int(host.rcon_invoke('sv.ranked').replace('\n', '')):
            print '-------------- PR MOD DETECTED - ranked server'
            isModdedServer(True)
        if int(host.rcon_invoke('sv.spawnTime').replace('\n', '')) < g_serverProperties['spawnTime']:
            print '-------------- PR MOD DETECTED - spawnTime too low'
            isModdedServer(True)
        if int(host.rcon_invoke('sv.manDownTime').replace('\n', '')) < g_serverProperties['manDownTime']:
            print '-------------- PR MOD DETECTED - manDownTime too low'
            isModdedServer(True)
        if isModdedServer():
            print '-------------- PR MOD DETECTED'
            host.rcon_invoke('game.unload')
    return


def updateServerName(servername):
    version = getVersion()
    prefix = '[PR v' + version + HOTFIX_LETTER + '] '
    servername = servername.replace(prefix, '')
    servername = '"' + prefix + servername + '"'
    g_serverProperties['serverName'] = servername
    host.rcon_invoke('sv.serverName %s' % servername)


def setServerName():
    try:
        servername = host.rcon_invoke('sv.serverName').replace('\n', '')
    except:
        servername = 'Project Reality Server'

    version = getVersion()
    prefix = '[PR v' + version + HOTFIX_LETTER + '] '
    servername = servername.replace(prefix, '')
    g_serverPropertiesDefault['serverName'] = '"' + prefix + servername + '"'


def getVersion():
    global g_version
    if g_version:
        return g_version
    FILE = file(bf2.gameLogic.getModDir() + '/mod.desc', 'r')
    rawDesc = FILE.read()
    FILE.close()
    pattern = re.compile('<version>(.*)</version>', re.MULTILINE)
    for p in pattern.findall(rawDesc):
        g_version = p.strip()

    return g_version


def setServerProperties(properties = None):
    if properties is not None:
        for key, val in properties.items():
            g_serverProperties[key] = val

    else:
        for key, val in g_serverPropertiesDefault.items():
            g_serverProperties[key] = val

    for key, val in g_serverProperties.items():
        if properties is not None and key not in properties:
            continue
        host.rcon_invoke('sv.%s %s' % (key, val))

    return


def onRoundStart():
    setServerProperties({'radioMaxSpamFlagCount': g_serverPropertiesDefault['radioMaxSpamFlagCount'],
     'radioBlockedDurationTime': g_serverPropertiesDefault['radioBlockedDurationTime']})


def onRemoteShutdownCommand(player, cmd, args):
    open('shutdown.lock', 'w').close()
    host.rcon_invoke('quit')


def onRemoteModdedCommand(player, cmd, args):
    if isModdedServer():
        res = 'true'
    else:
        res = 'false'


def onRemoteServerCommand(player, cmd, args):
    command = 'sv.' + ' '.join(args)
    host.rcon_invoke(command)