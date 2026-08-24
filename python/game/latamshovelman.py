# rcon shovelman: instant shovel-build for deployables (debug toggle).
# Raises shovel abilityStrength to the same value used by super_shovel.
import bf2
import host
import realityadmin as radmin
import realitydebug as rdebug

# Normal shovels (abilityStrength 1 in tweak). super_shovel stays at 100.
SHOVEL_TEMPLATES = (
    'klappspaten',
    'klappspaten_sov',
    'klappspaten_ww2ger',
    'klappspaten_ww2us',
    'insrgshov_mpl50',
)
STRENGTH_NORMAL = 1
STRENGTH_INSTANT = 100

g_enabled = False


def init():
    host.registerHandler('RemoteCommandShovelman', onRemoteShovelman)
    host.registerGameStatusHandler(onGameStatusChanged)
    rdebug.debugMessage('latamshovelman initialized', 'gameplay')


def onGameStatusChanged(status):
    global g_enabled
    # Reset each round so the cheat does not leak into the next map.
    if status == bf2.GameStatus.EndGame or status == bf2.GameStatus.PreGame:
        if g_enabled:
            g_enabled = False
            _setShovelStrength(STRENGTH_NORMAL)


def onRemoteShovelman(player, cmd, args):
    global g_enabled
    g_enabled = not g_enabled
    if g_enabled:
        _setShovelStrength(STRENGTH_INSTANT)
        msg = 'shovelman enabled (instant build)...'
    else:
        _setShovelStrength(STRENGTH_NORMAL)
        msg = 'shovelman disabled...'
    radmin.personalMessage(msg, player)
    radmin.adminPM(msg)
    rdebug.debugMessage('%s by %s' % (msg, _playerName(player)), 'gameplay')


def _playerName(player):
    try:
        if player is not None and player.isValid():
            return player.getName()
    except:
        pass
    return '?'


def _setShovelStrength(strength):
    # Live-edit ObjectTemplate so already-equipped shovels pick up the new rate.
    for name in SHOVEL_TEMPLATES:
        try:
            host.rcon_invoke('ObjectTemplate.activeSafe GenericFireArm %s' % name)
            host.rcon_invoke('ObjectTemplate.ammo.abilityStrength %s' % int(strength))
        except:
            rdebug.errorMessage()
