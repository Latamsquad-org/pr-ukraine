import datetime
import hashlib
import json
import random
import re
import sqlite3
import struct
import time
import urllib2
import bf2
import host
import realityassets as rassets
import realityconfig_admin as ras
import realitycore as rcore
import realitydatabase as rdb
import realitydebug as rdebug
import realitylogger as rlogger
import realitymaplist as rmaplist
import realitymemory as rmemory
import realityplayerdata as rplayerdata
import realityprism as rprism
import realityserver
import realitytimer as rtimer
import realityvehicles as rvehicles
import realityzones as rzones
import realitykits as rkits
import realitylocalization
from realitymaplist import MAPLISTALL
if False:
    from typing import Dict, Optional
g_roundStartTime = 0
g_squadlessTimer = None
g_admins = {}
g_lite_admins = {}
g_switch_next = {}
g_scramble_next = False
g_swap_teams_next = False
g_adminCommands = {}
g_last_setnext = None
g_sponsorText = ''
g_mapList = {}
g_lastPlayedMaps = []
g_voteRunning = False
g_vote_Timer = None
g_voteMsgTimer = None
g_voteList = {}
g_vote_map = []
g_vote_res_msg = ''
g_vote_res_time = 0
g_vote_performed_on = ''
g_vote_tleft_msg = ras.adm_mvoteDuration
g_voteAdmin = ''
g_prism_admins = []
g_lastBan = ()
g_announcerTimers = {}
g_sponsorTimer = None
g_preGameBalanceTimer = None
g_knownGrapplingHooks = {}
g_disconnected_player_teams = {}
g_banSystem = None
g_allchat_enabled = True
GRAPPLE_WEAPONS = ['nsrif_grapplinghook', 'nsrif_grapplinghook_idx5', 'nsrif_grapplinghook_idx8']
LAYER_NUMBERS = {'Inf': 16,
 'Alt': 32,
 'Std': 64,
 'Lrg': 128}

class BanSystem():
    """
    This class implements a sqlite3 database to store logs and current bans for Project Reality
    It replaces the old server console admin.listBannedKeys etc commands and bf2 ban list and instead
    kicks a player a tick after they join, when their PlayerID is in the bans table.
    """
    APPLICATION_ID = 1452608661
    VALID_ID_CHARS = list('abcdef0123456789')
    USER_VERSION = 2

    def __init__(self):
        self.db_path = '%s/settings/bans.sqlite3' % host.sgl_getModDirectory()
        if hasattr(ras, 'bans_sqlite3'):
            self.db_path = ras.bans_sqlite3
        self.banned_ids_path = '%s/settings/banned_ids.txt' % host.sgl_getModDirectory()
        self.con = sqlite3.connect(self.db_path)
        self.cur = self.con.cursor()
        self._setup_tables()
        self.round_start = time.time()
        self.migrated = False
        host.registerGameStatusHandler(self.onGameStatusChanged)
        host.registerHandler('PlayerConnect', self.onPlayerConnect, 1)

    def onGameStatusChanged(self, status):
        if status == bf2.GameStatus.Loaded:
            self.round_start = time.time()
            self.remove_roundbans()
            self.remove_tempbans()
            self._migrateOldBans()
            self.write_banned_ids_txt()

    def _kickOnNextTick(self, player):
        try:
            reason = self.getBanReason(realityserver.getPlayerHash(player))
            kickPlayer(player, reason, announce=False, bansystem=True)
        except LookupError:
            rdebug.errorMessage()
            kickPlayer(player, 'None', announce=False, bansystem=True)

    def onPlayerConnect(self, player):
        """
        When a player connects this event checks if they are banned, if they are it removes tempbans and checks again.
        If the player is still banned it creates a fireNextTick timer to kick them on next tick.
        """
        if self.isPlayerBanned(player):
            adminPM("==Jugador " + getPlayerTag(player) + " " + getPlayerName(player) + " con BAN registrado==")
            rtimer.fireNextTick(self._kickOnNextTick, player)

    def _setup_tables(self):
        logs_table_v2 = 'CREATE TABLE IF NOT EXISTS logs ( ' + 'log_id INTEGER PRIMARY KEY AUTOINCREMENT, ' + 'name TEXT, ' + 'clantag TEXT, ' + 'date REAL, ' + 'player_id TEXT, ' + 'ip TEXT, ' + 'reason TEXT, ' + 'type TEXT, ' + 'length REAL, ' + 'admin TEXT, ' + 'round_start REAL, ' + 'UNIQUE (name, date, player_id, reason))'
        bans_table_v2 = 'CREATE TABLE IF NOT EXISTS bans ( ' + 'ban_id INTEGER PRIMARY KEY NOT NULL, ' + 'player_id TEXT, ' + 'log_id INTEGER NOT NULL, ' + 'UNIQUE (player_id), ' + 'FOREIGN KEY(log_id) REFERENCES logs(log_id))'
        self.cur.execute('PRAGMA application_id')
        appid = self.cur.fetchone()
        if appid[0] == 0:
            application_id = 'PRAGMA application_id = 1452608661'
            self.cur.execute(application_id)
        elif appid[0] != int(self.APPLICATION_ID):
            raise Exception('Attempted to use a database that is not a Project Reality sqlite3 ban database.')
        self.cur.execute('PRAGMA user_version')
        userversion = self.cur.fetchone()
        if userversion[0] == 0:
            self.cur.execute('PRAGMA user_version = 2')
        elif userversion[0] == 1:
            self.cur.execute('ALTER TABLE logs RENAME TO logs_migration')
            self.cur.execute('ALTER TABLE bans RENAME TO bans_migration')
            self.cur.execute(logs_table_v2)
            self.cur.execute(bans_table_v2)
            self.cur.execute('INSERT INTO logs SELECT * FROM logs_migration')
            self.cur.execute('INSERT INTO bans SELECT * FROM bans_migration')
            self.cur.execute('DROP TABLE logs_migration')
            self.cur.execute('DROP TABLE bans_migration')
            self.cur.execute('PRAGMA user_version = 2')
        elif userversion[0] != self.USER_VERSION:
            raise Exception('Attempted to use a Project Reality sqlite3 ban database with a wrong version number.')
        self.cur.execute(logs_table_v2)
        self.cur.execute(bans_table_v2)
        self.con.commit()

    def remove_roundbans(self):
        """
        Delete active round bans from the database if the round has changed.
        """
        query = 'DELETE FROM bans WHERE log_id IN (' + 'SELECT log_id FROM logs WHERE type == "round" AND round_start < ?)'
        try:
            self.cur.execute(query, (self.round_start,))
            self.con.commit()
            return True
        except sqlite3.Error:
            rdebug.errorMessage()
            return False

    def remove_tempbans(self):
        """
        Delete timebans that have expired from the database
        """
        query = 'DELETE FROM bans WHERE log_id IN (' + 'SELECT log_id FROM logs WHERE type == "timeban" AND date + length <= ?)'
        try:
            self.cur.execute(query, (time.time(),))
            self.con.commit()
            return True
        except sqlite3.Error:
            rdebug.errorMessage()
            return False

    def remove_ban(self, playerId):
        """
        Remove an active ban from the bans table by player_id
        """
        query = 'DELETE FROM bans WHERE player_id == ?'
        try:
            self.cur.execute(query, (playerId,))
            self.con.commit()
            return True
        except sqlite3.Error:
            rdebug.errorMessage()
            return False

    def validatePlayerId(self, playerId):
        """
        This only checks length and all characters are in hex charset
        """
        if len(playerId) != 32:
            return False
        for char in playerId:
            if char not in self.VALID_ID_CHARS:
                return False

        return True

    def _enter_log(self, name, clantag, date, playerid, ip, reason, logtype, length, admin, round_start):
        log = 'INSERT INTO logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        ban = 'INSERT INTO bans VALUES (?, ?, ?)'
        logvalues = (None, name, clantag, date, playerid, ip, reason, logtype, length, admin, round_start)
        assert self.validatePlayerId(playerid)
        try:
            self.cur.execute(log, logvalues)
            if logtype in ('perm', 'timeban', 'round'):
                banvalues = (
                 None, playerid, self.cur.lastrowid)
                self.cur.execute(ban, banvalues)
            self.con.commit()
            return True
        except sqlite3.IntegrityError:
            raise
        except sqlite3.Error:
            rdebug.errorMessage()
            return False

    def write_banned_ids_txt(self):
        """
        This generates settings/banned_ids.txt
        """
        banned_ids = self.getCurrentBansInfo()
        if banned_ids is None:
            return False
        else:
            with open(self.banned_ids_path, 'w+') as banstxt:
                banstxt.truncate(0)
                banstxt.writelines([ ' '.join(ban) + '\n' for ban in banned_ids ])
            return True

    def log_action(self, player, admin, logtype, reason, length = None):
        """
        This is the primary function to enter logs for bans, kicks, warns etc
        _enter_log() will determine if the log should be entered into the bans table
        """
        if logtype not in ('perm', 'timeban', 'round', 'kick', 'warn', 'kill'):
            rdebug.debugMessage('log type invalid')
            return
        else:
            if not player:
                playername = None
                clantag = None
            else:
                playername = getPlayerName(player)
                clantag = getPlayerTag(player)
            if not admin:
                adminname = 'NO ADMIN FOUND'
            else:
                adminname = admin.getName()
            date = time.time()
            if realityserver.isInternetServer():
                playerId = realityserver.getPlayerHash(player)
            else:
                playerId = '0' * 32
            ip = str(player.getAddress())
            if logtype in ('timeban',):
                length = float(length)
            else:
                length = None
            return self._enter_log(playername, clantag, date, playerId, ip, reason, logtype, length, adminname, self.round_start)

    def ban_id(self, cmd, banningAdmin):
        """
        Enters a ban into the database based on player_id and reason
        :param cmd: [player_id, reasonword1, reasonword2]
        :param banningAdmin: None or player object
        :return: True for success False otherwise
        # TODO merge this with log_action
        """
        name = 'MANUALLY BANNED ID'
        if banningAdmin is None:
            admin = None
        else:
            admin = banningAdmin.getName()
        clantag = ''
        if not admin:
            admin = 'NO ADMIN FOUND'
        date = time.time()
        playerId = cmd[0]
        ip = ''
        reason = ' '.join(cmd[1:])
        length = None
        bantype = 'perm'
        try:
            return self._enter_log(name, clantag, date, playerId, ip, reason, bantype, length, admin, self.round_start)
        except sqlite3.IntegrityError:
            adminPM('El jugador ya se encuentra en la banlist.', banningAdmin)
            return

        return

    def isPlayerIdBanned(self, playerId):
        """
        :return: True if a player_id is banned False otherwise
        """
        select = 'SELECT player_id FROM bans WHERE player_id == ?'
        self.cur.execute(select, (playerId,))
        if self.cur.fetchone():
            self.remove_tempbans()
        else:
            return False
        self.cur.execute(select, (playerId,))
        if self.cur.fetchone():
            return True
        return False

    def isPlayerBanned(self, player):
        """
        :return: True if a player object is banned False otherwise
        """
        playerId = realityserver.getPlayerHash(player)
        if not playerId:
            return None
        else:
            return self.isPlayerIdBanned(playerId)

    def getBanReason(self, playerId):
        """
        :return: Ban reason from the log associated with a ban or "Ban reason not found."
        """
        query = 'SELECT reason FROM logs WHERE log_id == (SELECT log_id FROM bans ' + 'WHERE player_id == ?)'
        self.cur.execute(query, (playerId,))
        banreason = self.cur.fetchone()
        if banreason and len(banreason) > 0:
            return banreason[0].encode()
        else:
            return 'Razon de baneo no encontrada.'

    def getBanRemainingTime(self, playerId):
        """
        :return: "perm", "round" or int(n) seconds
        """
        query = 'SELECT date, type, length FROM logs WHERE log_id == (SELECT log_id FROM bans ' + 'WHERE player_id == ?)'
        try:
            self.cur.execute(query, (playerId,))
            row = self.cur.fetchone()
            if row and len(row) == 3:
                date, bantype, length = row
            else:
                date, bantype, length = (None, 'perm', None)
        except sqlite3.Error:
            rdebug.errorMessage()
            return 'perm'
        except ValueError:
            rdebug.errorMessage()
            return 'perm'

        if bantype == 'timeban':
            if date is None or length is None:
                rdebug.debugMessage('timeban db values are None')
                return 'perm'
            return int(date + length - time.time())
        else:
            return bantype
            return

    def getCurrentBanIds(self):
        """
        :return: a list of banned player_ids
        """
        query = 'SELECT player_id FROM bans'
        self.cur.execute(query)
        return self.cur.fetchall()

    def getCurrentPermBanIds(self):
        """
        :return: a list of perm banned player_ids
        """
        query = 'SELECT player_id FROM logs WHERE log_id IN (SELECT log_id FROM bans) AND (type == "perm")'
        self.cur.execute(query)
        return self.cur.fetchall()

    def getCurrentBansInfo(self):
        """
        :return: a list of player_ids (player_id, type, name)
        """
        query = 'SELECT player_id, type, name, reason FROM logs WHERE log_id IN (SELECT log_id FROM bans)'
        self.cur.execute(query)
        return self.cur.fetchall()

    def getBannedIdByName(self, name):
        """
        Get a banned player_id based on their name from the associated log
        :param name: exact player name from logs table
        :return: (player_id,) or None
        """
        query = 'SELECT player_id FROM bans WHERE log_id IN (SELECT log_id FROM logs WHERE name LIKE ?)'
        self.cur.execute(query, (name,))
        result = self.cur.fetchone()
        if result:
            return result[0]

    def getLogStatsById(self, playerid):
        """
        Return counts of players perms, tempbans, kicks and warns. Based on a players id.
        """
        query = 'SELECT ' + 'SUM(type LIKE "perm") AS permcount, ' + 'SUM(type LIKE "timeban") + SUM(type LIKE "round") AS tempcount, ' + 'SUM(type LIKE "kick") AS kickcount, ' + 'SUM(type LIKE "warn") AS warncount ' + 'FROM logs WHERE player_id == ?'
        self.cur.execute(query, (playerid,))
        results = self.cur.fetchone()
        return [ (0 if count is None else count) for count in results ]

    def getLastActionsById(self, playerid):
        query = 'SELECT date, type, reason FROM logs WHERE player_id == ? ORDER BY date DESC LIMIT 3'
        self.cur.execute(query, (playerid,))
        results = self.cur.fetchall()
        return [ str('Fecha: %s Tipo: %s Razon: %s' % (datetime.datetime.fromtimestamp(result[0]), result[1], result[2])) for result in results ]

    def _migrateOldBans(self):
        """
        This migrates bans from banlist.con and enters them into the database, removing the entries from
        banlist.con as it goes. It happens once per server boot. admin.listBannedKeys and banlist.con will be
        empty after a successful migration.
        """
        if self.migrated:
            return
        else:
            bannedKeys = host.rcon_invoke('admin.listBannedKeys').lower()
            bannedKeys = bannedKeys.split('\n')
            for key in bannedKeys:
                try:
                    if 'perm' in key:
                        player_id = key[5:][:-5]
                        self.ban_id((player_id, 'Migrated ban from admin.listBannedKeys'), None)
                        host.rcon_invoke('admin.removeKeyFromBanList %s' % player_id)
                    if 'time left:' in key:
                        player_id = key[5:37]
                        remaining_time = float(key[49:])
                        self._enter_log('MANUALLY BANNED ID', None, time.time(), player_id, '', 'MIGRATED TEMPBAN', 'timeban', remaining_time, 'NO ADMIN FOUND', self.round_start)
                        host.rcon_invoke('admin.removeKeyFromBanList %s' % player_id)
                except:
                    rdebug.errorMessage()

            self.migrated = True
            return


def isRcon(*args):
    return False


def init():
    global g_sponsorText
    global g_banSystem
    rdebug.debugMessage('Initializing RealityAdmin', 'admin')
    IPTester.init()
    AFKDetection.init()
    DevReservedSlot.init()
    MumbleOTP.init()
    g_banSystem = BanSystem()
    KeepTeamOnReconnect()
    if rmemory.isWindowsListenServer and realityserver.isCoopServer():
        rtimer.Timer(printCoopUnstable, 60, 1, None).setRecurring(600)
    if not ras.RAEnabled:
        rdebug.debugMessage('RA Disabled', 'admin')
        return
    else:
        bf2.PlayerManager.Player.isRcon = isRcon
        if not realityserver.isInternetServer():
            ras.log_chat = False
            ras.log_teamkills = False
            ras.log_kills = False
            ras.log_admins = False
            ras.log_connects = False
            ras.log_bans = False
            ras.log_tickets = False
            ras.log_coincident_IPs = False
        else:
            modDir = host.sgl_getModDirectory()
            if ras.log_coincident_IPs:
                rlogger.createLogger('IPlog', ras.log_IP_coincidence_path.replace('[MOD]', modDir), ras.log_IP_coincidence_file, True)
            if ras.log_chat or ras.log_teamkills or ras.log_kills:
                rlogger.createLogger('ChatLog', ras.log_chat_path.replace('[MOD]', modDir), ras.log_chat_file, False)
            if ras.log_admins:
                rlogger.createLogger('AdminLog', ras.log_admins_path.replace('[MOD]', modDir), ras.log_admins_file, True)
            if ras.log_bans:
                rlogger.createLogger('BanLog', ras.log_bans_path.replace('[MOD]', modDir), ras.log_bans_file, True)
            if ras.log_tickets:
                rlogger.createLogger('TicketLog', ras.log_tickets_path.replace('[MOD]', modDir), ras.log_tickets_file, True)
        rdebug.debugMessage('Initializing RA Admin', 'admin')
        host.registerGameStatusHandler(onGameStatusChanged)
        host.registerHandler('PlayerKilled', onPlayerKilled)
        host.registerHandler('ChatMessage', onChatMessage)
        host.registerHandler('ChatMessage', onChatMessageCheckUnprintableChars)
        host.registerHandler('ChatMessage', onChatMessageVote)
        host.registerHandler('PlayerChangeWeapon', onPlayerChangeWeaponRopeCheck)
        host.registerHandler('PlayerChangedSquad', onPlayerChangedSquadEarly)
        host.registerHandler('PlayerChangedSquad', onPlayerChangedSquadMark)
        host.registerHandler('PlayerConnect', onPlayerConnect, 1)
        host.registerHandler('PlayerDisconnect', onPlayerDisconnect, 1)
        host.registerHandler('LocalConsoleCommand', onConsoleCommand, 1)
        host.registerHandler('PlayerChangeTeams', onPlayerChangeTeamsUnmarkTeamswitch)
        fillCommandDict()
        rdebug.debugMessage('Initializing RA Announcer', 'admin')
        if ras.ann_enabled:
            if ras.ann_joinMessageEnabled:
                host.registerHandler('PlayerSpawn', onAnnouncerPlayerSpawn)
            if ras.ann_disconnectMessageEnabled:
                host.registerHandler('PlayerDisconnect', onAnnouncerPlayerDisconnect)
        host.registerGameStatusHandler(onLoggerGameStatusChanged)
        host.registerHandler('ChatMessage', onLoggerChatMessage, 1)
        host.registerHandler('PlayerKilled', onLoggerPlayerKilled)
        host.registerHandler('PlayerConnect', onBalancePlayerConnect, 1)
        host.registerHandler('PlayerDeath', onBalancePlayerDeath)
        host.registerHandler('PlayerChangeTeams', onBalancePlayerChangeTeams)
        host.registerHandler('RoundStart', onBalanceRoundStart)
        host.registerHandler('PlayerVerified', onPlayerVerified)
        host.registerGameStatusHandler(onBalanceGameStatusChanged)
        host.registerGameStatusHandler(delayedAdminMapHistoryPM)
        constructMaplist()
        if not g_sponsorText:
            g_sponsorText = host.rcon_invoke('sv.sponsorText').replace('\n', '').strip()
        if not g_sponsorText:
            g_sponsorText = 'Next map:pr_maplist'
        host.registerHandler('RemoteCommandVote', onVoteHUDEvent)
        host.registerHandler('RemoteCommandTransferSL', onTransferSquadLeader)
        host.registerHandler('RemoteCommandCheckChat', onAllChatEnableRequest)
        host.registerHandler('RemoteCommandPlayerActive', onPlayerDeclaredActive)
        return


def sendAdminsMapHistory(data = None):
    global g_lastPlayedMaps
    if len(g_lastPlayedMaps) == 0:
        adminPM('Mapas previamente jugados: Ninguno')
        return
    history = list(g_lastPlayedMaps)
    history_str = 'Mapas previamente jugados: %s' % ', '.join(history)
    adminPM(history_str)


def delayedAdminMapHistoryPM(status):
    delay = 1200
    if status == bf2.GameStatus.Playing:
        rtimer.fireOnce(sendAdminsMapHistory, delay)


def printCoopUnstable(args = None):
    globalMessage('NOTE: Local coop servers are unstable. Set up a server to prevent crashes')
    globalMessage('Use mods\\pr\\settings\\maplist.con to select maps. Make sure you select only coop maps')
    globalMessage('Use server.bat to start the server and then join it with your client through join local')
    globalMessage('In the server, type rcon debug in chat to be able to change map using !setnext and !runnext')


def findPlayer(name, admin):
    if name.startswith(ras.adm_idPrefix):
        name = name.lstrip(ras.adm_idPrefix)
        if re.match('^\\d{1,3}$', name):
            _id = int(name)
            player = bf2.playerManager.getPlayerByIndex(_id)
            if not player:
                personalMessage('No se encontraron jugadores con el ID %i' % _id, admin)
                return []
            return [player]
        else:
            personalMessage('ID invalido %s - solo los valores entre 0-255 son validos.' % name, admin)
            return []
    elif name.startswith(ras.adm_squadPrefix):
        name = name.lstrip(ras.adm_squadPrefix)
        match = re.match('^([1-9])(us|them)$', name)
        if match:
            squad = int(match.group(1))
            adminTeam = admin.getTeam()
            if match.group(2) == 'them':
                team = rcore.getOtherTeam(adminTeam)
            else:
                team = adminTeam
            players = list(rcore.getPlayersOfSquad(team, squad))
            if len(players) == 0:
                personalMessage('No se encontraron jugadores en la escuadra %i del equipo %i' % (squad, team), admin)
            return players
        else:
            personalMessage('Escuadra invalida %s - especifica el ID y us|them.' % name, admin)
            return []
    else:
        name = name.lower()
        playerlist = []
        for p in bf2.playerManager.getPlayers():
            if p.isAIPlayer():
                continue
            if getPlayerName(p).lower().find(name) != -1:
                playerlist.append(p)

        if len(playerlist) == 0:
            personalMessage('No se encontraron jugadores con el nombre %s' % name, admin)
        elif len(playerlist) > 1:
            personalMessage('Multiples jugadores encontrados con el nombre %s:' % name, admin)
            linesamount = min(4, len(playerlist))
            for i in range(0, linesamount):
                personalMessage('%s%s: %s ' % (ras.adm_idPrefix, playerlist[i].index, playerlist[i].getName()), admin)

            return []
        return playerlist


def findReason(reason):
    if reason.lower().strip() in ras.adm_reasons:
        reason = ras.adm_reasons[reason.lower().strip()]
    return reason


def updateSponsorMapList():
    global g_mapList
    mapId = int(host.rcon_invoke('admin.nextLevel'))
    map_name = rcore.getMapName(g_mapList[mapId][0], True)
    map_gamemode = rcore.getGameModeName(g_mapList[mapId][1])
    map_layer = g_mapList[mapId][2]
    sponsorMapListText = g_sponsorText.replace('pr_maplist', '%s %s %s' % (map_name, map_gamemode, map_layer))
    if len(sponsorMapListText) > 254:
        sponsorMapListText = sponsorMapListText[0:253]
    host.rcon_invoke('sv.sponsorText "%s"' % sponsorMapListText)


def constructMaplist():
    global g_mapList
    g_mapList = {}
    map_list = host.rcon_invoke('maplist.list').strip().split('\n')
    for _map in map_list:
        _map = _map.replace('"', '')
        map_splitted = _map.split(': ')
        map_id = int(map_splitted[0])
        map_splitted = map_splitted[1].split(' ')
        map_name = map_splitted[0].lower()
        map_gamemode = map_splitted[1].lower()
        map_layer = rcore.getMapLayerNameAbbr(int(map_splitted[2]))
        g_mapList[map_id] = (map_name, map_gamemode, map_layer)


def setNextMap(mapId, mapName, gamemode, layer, p):
    global g_last_setnext
    mapName = rcore.getMapName(mapName, True)
    if realityserver.isInternetServer() and not realityserver.isPasswordedServer():
        if mapName.startswith('test_'):
            adminPM('No se pueden jugar mapas "test" en un server publico', p, display=True)
            return
    layer = layer.title()
    gamemode = rcore.getGameModeName(gamemode)
    globalMessage('El siguiente mapa es: %s (%s, %s)' % (mapName, gamemode, layer))
    host.rcon_invoke('admin.nextLevel %i' % mapId)
    g_last_setnext = p.getName()
    logAdmin('!setnext', p.getName(), '', '%s (%s, %s)' % (mapName, gamemode, layer))
    updateSponsorMapList()
    players = list(rcore.getPlayers())
    for player in players:
        sendRhooksAdminWarnEventWrapper(player, 'El siguiente mapa es: %s (%s, %s) por: %s' % (mapName,
         gamemode,
         layer,
         p.getName()), display=False)


def addToMapList(mapName, gamemode, layer, p):
    result = host.rcon_invoke('maplist.append %s %s %s' % (mapName, gamemode, LAYER_NUMBERS[layer]))
    if not result.startswith('1'):
        personalMessage('No se encontraron mapas con: %s %s %s' % (mapName, gamemode, layer), p)
        return -1
    mapId = len(g_mapList)
    g_mapList[mapId] = (mapName, gamemode, layer)
    mapName = rcore.getMapName(mapName, True)
    layer = layer.title()
    gamemode = rcore.getGameModeName(gamemode)
    adminPM('El siguiente mapa ha sido anadido a la rotacion: ' + mapName + ' (' + gamemode + ', ' + layer + ')', p)
    return mapId


def playerInit(p):
    p.teamswitch = False
    p.killreason = ''
    p.failedSquads = 0
    if not hasattr(p, 'hash'):
        p.hash = None
    return


canAlwaysExecute = ['admins', 'fps']

def canExecute(command, player):
    global g_lite_admins
    global g_admins
    if command in canAlwaysExecute:
        return True
    if rdebug.canExecute(player) or not realityserver.isInternetServer():
        return True
    if command not in ras.adm_adminPowerLevels:
        return False
    reqPower = ras.adm_adminPowerLevels[command]
    if reqPower == 777:
        return True
    if player in g_admins:
        return g_admins[player] <= reqPower
    if len(g_admins) == 0 and player in g_lite_admins:
        return g_lite_admins[player] <= reqPower
    return False


def getPlayerName(p):
    return p.getName().split(' ')[-1]


def getPlayerTag(p):
    return p.getName().split(' ')[0]


def teamSwitchPlayer(p):
    if hasattr(p, 'teamswitch') and p.teamswitch:
        p.teamswitch = False
    if p.getTeam() == 1:
        p.setTeam(2)
    else:
        p.setTeam(1)


def swapTeams():
    globalMessage('Intercambiando a todos los jugadores...')
    for player in bf2.playerManager.getPlayers():
        if player.isAIPlayer():
            continue
        player.setTeam(rcore.getOtherTeam(player.getTeam()))


def onPlayerChangedSquadMark(player, oldId, newId):
    if newId > 0:
        player.lastValidSquad = newId


def scrambleTeams():
    teams = [1, 2]
    random.shuffle(teams)
    players = list(rcore.getPlayers())
    squads = {}
    for player in players:
        if not hasattr(player, 'lastValidSquad'):
            player.lastValidSquad = 0
        player_sq = (player.getTeam(), player.lastValidSquad)
        if player_sq in squads:
            squads[player_sq].append(player)
        else:
            squads[player_sq] = [player]

    full_squads = []
    tiny_squads = []
    for squad, squadMembers in squads.items():
        k = 0
        d = 0
        for sqm in squadMembers:
            k += sqm.score.kills
            d += sqm.score.deaths

        if d == 0:
            d = 1
        kd = k / d
        if len(squadMembers) >= 6:
            full_squads.append((squad, kd))
        if len(squadMembers) < 6:
            tiny_squads.append((squad, kd))

    full_squads = sorted(full_squads, key=lambda s: s[1])
    tiny_squads = sorted(tiny_squads, key=lambda s: s[1])

    def setTeamOne(p):
        p.setTeam(teams[0])

    def setTeamTwo(p):
        p.setTeam(teams[1])

    if ras.testscramble and len(full_squads) >= 4:
        globalMessage('Balanceando escuadras...')
        team = random.choice([1, 2])
        for sq in full_squads:
            if team == 1:
                map(setTeamOne, [ e[0] for e in sq ])
                team = 2
            else:
                map(setTeamTwo, [ e[0] for e in sq ])
                team = 1

        for sq in tiny_squads:
            if team == 1:
                map(setTeamOne, [ e[0] for e in sq ])
                team = 2
            else:
                map(setTeamTwo, [ e[0] for e in sq ])
                team = 1

    elif len(full_squads) >= 4:
        globalMessage('Mezclando escuadras...')
        random.shuffle(full_squads)
        random.shuffle(tiny_squads)
        for sq in full_squads[:len(full_squads) / 2]:
            map(setTeamOne, [ e[0] for e in sq ])

        for sq in full_squads[len(full_squads) / 2:]:
            map(setTeamTwo, [ e[0] for e in sq ])

        for sq in full_squads[:len(tiny_squads) / 2]:
            map(setTeamOne, [ e[0] for e in sq ])

        for sq in full_squads[len(tiny_squads) / 2:]:
            map(setTeamTwo, [ e[0] for e in sq ])

    else:
        globalMessage('Mezclando equipos...')
        random.shuffle(players)
        for player in players[:len(players) / 2]:
            player.setTeam(teams[0])

        for player in players[len(players) / 2:]:
            player.setTeam(teams[1])


def resignPlayer(p):
    if p.isAIPlayer():
        return
    if p.getTeam() == 1:
        p.setTeam(2)
        p.setTeam(1)
    else:
        p.setTeam(1)
        p.setTeam(2)


def kickPlayer(p, reason = '', announce = False, admin = None, bansystem = False, related_key = ''):
    if bansystem:
        length = g_banSystem.getBanRemainingTime(realityserver.getPlayerHash(p))
        annocMessage, pbmsg, bantype = getPBBanString(length, reason)
        if admin and ras.display_kickAdmin:
            pbmsg = pbmsg + ' Admin: %s' % admin.getName()
    else:
        annocMessage, pbmsg, bantype = getPBBanString('kick', reason)
        if admin and ras.display_kickAdmin:
            pbmsg = pbmsg + ' Admin: %s' % admin.getName()
        if related_key:
            g_banSystem.log_action(p, admin, 'kick', 'Cuenta relacionada con un ID baneado: %s' % related_key)
        else:
            g_banSystem.log_action(p, admin, 'kick', reason)
    if reason and announce:
        if admin:
            globalMessage('Kickeando al jugador %s, %s - %s' % (p.getName(), reason, admin.getName()))
        else:
            globalMessage('Kickeando al jugador %s, %s' % (p.getName(), reason))
    rmemory.setPBKickstring(pbmsg)
    host.rcon_invoke('admin.kickPlayer %d' % p.index)


def warnPlayer(admin, p, reason, silent = False, pid = 1220104, level = 1):
    if silent:
        personalMessage('Advertencia al jugador %s, %s' % (p.getName(), reason), p)
    else:
        globalMessage('Advertencia al jugador %s, %s - %s' % (p.getName(), reason, admin.getName()))
        g_banSystem.log_action(p, admin, 'warn', reason)
    sendRhooksAdminWarnEventWrapper(p, 'Has sido advertido por un administrador ' + admin.getName() + ': \r\n' + reason, longDisplay=True)


def getPBBanString(length, reason):
    if str(length) == 'kick':
        annocMessage = 'KICK'
        pbmsg = 'Has sido Kickeado.'
        bantype = 'kick'
    elif str(length) == 'perm':
        annocMessage = ''
        pbmsg = 'Has sido Baneado.'
        bantype = 'perm'
    elif str(length) == 'round':
        annocMessage = 'TEMP'
        pbmsg = 'Baneado hasta finalizar la partida.'
        bantype = 'round'
    else:
        annocMessage = 'TEMP'
        length_hours = length / 3600.0
        length_days = length_hours / 24.0
        pbmsg = 'Baneado: %.2f horas.' % length_hours
        if length_days > 1:
            pbmsg = 'Baneado: %.1f dias.' % length_days
        bantype = 'timeban'
    if reason == '':
        reason = 'Fallo al verificar la cuenta. Seguro que no estas evadiendo?'
    return (annocMessage, '%s\n\nRAZON: %s' % (pbmsg, reason), bantype)


def banPlayer(cmd, banee, banningAdmin, length, reasonArgs):
    global g_lastBan
    foundPlayers = findPlayer(banee, banningAdmin)
    if len(foundPlayers) == 0:
        return False
    else:
        reason = findReason(' '.join(reasonArgs))
        annocMessage, pbmsg, bantype = getPBBanString(length, reason)
        if banningAdmin and ras.display_kickAdmin:
            pbmsg = pbmsg + ' Admin: %s' % banningAdmin.getName()
        rmemory.setPBKickstring(pbmsg)
        for player in foundPlayers:
            if banningAdmin == player:
                adminPM('No puedes kickearte a ti mismo!', banningAdmin)
                continue
            playerHash = realityserver.getPlayerHash(player)
            if playerHash is not True and playerHash != '':
                host.rcon_invoke('admin.kickPlayer %d' % player.index)
                if length == 'round':
                    g_banSystem.log_action(player, banningAdmin, 'round', reason, length)
                elif length != 'perm':
                    g_banSystem.log_action(player, banningAdmin, 'timeban', reason, length)
                else:
                    g_banSystem.log_action(player, banningAdmin, 'perm', reason, None)
            else:
                host.rcon_invoke('admin.kickPlayer %d' % player.index)
                adminPM('El jugador baneado tiene un ID invalido.', banningAdmin)
            globalMessage('%s HA SIDO %s BANEADO, %s - %s' % (player.getName(),
             annocMessage,
             reason,
             banningAdmin.getName()))
            g_lastBan = (getPlayerName(player), realityserver.getPlayerHash(player))
            logAdmin(cmd, banningAdmin.getName(), player.getName(), reason)

        if ras.log_bans:
            for player in foundPlayers:
                logBan(player, reason, length, banningAdmin)

        return True


def flyPlayer(player, height):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        pos = player.getVehicle().getPosition()
        player.getVehicle().setPosition((pos[0], pos[1] + height, pos[2]))
        return True
    
def pushPlayer(player, distance, cardinal):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        vehicle = player.getVehicle()
        pos = player.getVehicle().getPosition()
        if cardinal == "n":
            player.getVehicle().setPosition((pos[0] , pos[1] , pos[2] + distance))
        elif cardinal == "s":
            player.getVehicle().setPosition((pos[0] , pos[1] , pos[2] - distance))
        elif cardinal == "e":
            player.getVehicle().setPosition((pos[0] + distance, pos[1] , pos[2]))
        elif cardinal == "w":
            player.getVehicle().setPosition((pos[0] - distance, pos[1] , pos[2]))
        return True

def flipPlayer(player):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        vehicle = player.getVehicle()
        rot1, rot2, rot3 = vehicle.getRotation()
        player.getVehicle().setRotation((rot1 , rot2, float(0)))
        return True
    
def teleportPlayer(player,newX,newY,newZ):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        pos = (newX, newY, newZ)
        player.getVehicle().setPosition((float(newX),float(newY),float(newZ)))
        return True
    
def healPlayer(player):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        vehicle = player.getVehicle()
        rcore.setPlayerDamage(player, 100)
        vehicle.setDamage(2000)
        return True

def rearmPlayer(player):
    if not player.isAlive() or player.isManDown():
        return False
    else:
        vehicle = player.getVehicle()
        rmemory.rearmPlayer(player)
        return True

lastTimeValid = {1: 0, 2: 0}
def checkSquadlessPlayers(data = ''):
    teamInvalid = {1: rcore.getAreAllSquadsLockedOrFull(1),
     2: rcore.getAreAllSquadsLockedOrFull(2)}
    kick_time = int(ras.sqd_kickSquadLessAFKTime)
    for team in [1, 2]:
        if not teamInvalid[team]:
            lastTimeValid[team] = rcore.now()

    timenow = rcore.now()
    for player in rcore.getPlayers():
        if player.isAIPlayer():
            continue
        if teamInvalid[player.getTeam()]:
            continue
        player_squad = player.getSquadId()
        if player_squad and not ras.sqd_kickSquadedAFK:
            continue
        if player_squad:
            kick_time = int(ras.sqd_kickSquadedAFKTime)
        if player.isCommander():
            continue
        maxPlayers = int(host.rcon_invoke('sv.maxPlayers').replace('\r\n', ''))
        reservedSlots = int(host.rcon_invoke('sv.numReservedSlots').replace('\r\n', ''))
        maxPlayers = maxPlayers - reservedSlots
        nPlayers = float(bf2.playerManager.getNumberOfPlayers())
        if nPlayers / maxPlayers < ras.sqd_kickAFKPercent:
            pass
        elif ras.sqd_kickSquadLessAFK and AFKDetection.estimateAFKNess(player) >= kick_time:
            rmemory.sendHudVarWriteEventBool(player, 'PythonAfkCheckShowvar', 0)
            kickPlayer(player, 'Has sido kickeado automaticamente luego de %i minutos de inactividad.' % int(kick_time / 60), True)
            if player_squad:
                ktype = 'Assigned'
            else:
                ktype = 'Unassigned'
            logAdmin('!kick', 'SERVER', player.getName(), '%s AFK' % ktype)
            continue
        elif ras.sqd_kickSquadLessAFK and AFKDetection.estimateAFKNess(player) >= kick_time - 60:
            rmemory.sendHudVarWriteEventBool(player, 'PythonAfkCheckShowvar', 1)
            continue
        if not ras.sqd_kickSquadLess:
            continue
        if player_squad:
            continue
        if not hasattr(player, 'lastSpawn') or player.lastSpawn is None:
            player.lastSpawn = None
            continue
        if player.leftSquad is not None:
            lastSquadChange = player.leftSquad
        else:
            lastSquadChange = 0
        timelastchange = max(player.lastSpawn, lastSquadChange)
        rdebug.debugMessage('squadlesskick: ' + player.getName() + str(timelastchange))
        if timenow - timelastchange > ras.sqd_kickSquadLessTime:
            kickPlayer(player, realitylocalization.t('squadless'), True, None)
            logAdmin('!kick', 'SERVER', player.getName(), 'No squad')
        else:
            warnPlayer(DummyAdminUser('SERVER'), player, realitylocalization.t('squadless'), True, 3240301, 0)

    return


def destroySquadlessTimer():
    global g_squadlessTimer
    if g_squadlessTimer:
        g_squadlessTimer.destroy()
        g_squadlessTimer = None
    return


sent = False

def onGameStatusChanged(status):
    global g_sponsorTimer
    global g_voteRunning
    global g_announcerTimers
    global g_squadlessTimer
    global g_roundStartTime
    global g_lastPlayedMaps
    global sent
    destroySponsorTimer()
    destroyAnnounceTimers()
    destroyVoteMsgTimer()
    destroyVoteTimer()
    destroyPreGameBalanceTimer()
    destroySquadlessTimer()
    g_disconnected_player_teams.clear()
    if status == bf2.GameStatus.Loaded:
        updateSponsorMapList()
        if not sent:
            sendToPrism('serverSettings', [realityserver.C('STARTDELAY'), realityserver.C('PRTIMELIMIT')])
            sent = True
    elif status == bf2.GameStatus.Playing:
        g_roundStartTime = rcore.now()
        sendToPrism('roundStart', [rcore.getMapLayer()])
        if ras.sqd_kickSquadLess or ras.sqd_kickSquadLessAFK:
            g_squadlessTimer = rtimer.Timer(checkSquadlessPlayers, realityserver.C('STARTDELAY') + 4, 1, '')
            g_squadlessTimer.setRecurring(30)
        if ras.sponsorMessageEnabled:
            g_sponsorTimer = rtimer.Timer(announceMessage, ras.sponsorMessageInterval, 1, ras.sponsorMessage)
            g_sponsorTimer.setRecurring(ras.sponsorMessageInterval)
        if ras.ann_enabled and ras.ann_timedMessagesEnabled:
            for _time in ras.ann_timedMessages:
                g_announcerTimers[_time] = rtimer.Timer(announceMessage, _time, 1, ras.ann_timedMessages[_time])
                g_announcerTimers[_time].setRecurring(_time)

        for player in rcore.getPlayers():
            playerInit(player)

    elif status == bf2.GameStatus.EndGame:
        playedMap = rcore.getMapName(None, True)
        playedMode = rcore.getGameModeName(rcore.getGameMode())
        playedLayer = rcore.getMapLayerNameAbbr()
        logTickets()
        if playedLayer is None:
            playedLayer = 'Unknown'
        g_lastPlayedMaps.insert(0, '%s %s %s' % (playedMap, playedMode, playedLayer))
        g_lastPlayedMaps = g_lastPlayedMaps[:5]
        if g_voteRunning:
            endVote(True, 'La batalla ha terminado...')
    g_knownGrapplingHooks.clear()
    return


VALID_TAG_CHARS = list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!#$%&'()*+,-./:;<=>?@[\\]^_~{|}~")

def onPlayerConnect(p):
    p.isAdmin = False
    if p.isAIPlayer():
        return
    playerInit(p)
    if ras.log_connects:
        logConnect(p, True)
    pHash = realityserver.getPlayerHash(p)
    if not pHash:
        kickPlayer(p)
        logAdmin('!kick', 'SERVER', p.getName(), 'No hash!')
        return
    fullName = p.getName().split(' ')
    if len(fullName) != 2:
        kickPlayer(p)
        logAdmin('!kick', 'SERVER', p.getName(), 'Bad tag!')
        return
    tag = fullName[0]
    name = fullName[1]
    if len(name) < 3:
        kickPlayer(p)
        logAdmin('!kick', 'SERVER', p.getName(), 'Bad name!')
        return
    for c in tag:
        if c not in VALID_TAG_CHARS:
            kickPlayer(p)
            logAdmin('!kick', 'SERVER', p.getName(), 'Bad tag!')
            return

    if name.startswith('@') or name.startswith('+') or name.startswith('#') or name.find(',') != -1 or name.find('\\') != -1:
        kickPlayer(p)
        logAdmin('!kick', 'SERVER', p.getName(), 'Bad name!')
        return
    for c in name:
        if ord(c) < 33 or ord(c) > 126:
            kickPlayer(p)
            logAdmin('!kick', 'SERVER', p.getName(), 'Bad name!')
            return

    if not ras.disable_allchat and updateAllChatStatus(bf2.playerManager.getNumberOfPlayers()):
        rtimer.fireOnce(broadcastAllChatStatus, 30)
    else:
        rtimer.fireOnce(sendAllChatStatus, 30, p)


def onPlayerVerified(p):
    adminsOnline = len(g_admins)
    pHash = realityserver.getPlayerHash(p)
    if pHash in ras.adm_adminHashes:
        if adminsOnline == 0 and g_lite_admins:
            adminPM('Real admin is joining, Liteadmins lost their power', p, display=True)
        g_admins[p] = ras.adm_adminHashes[pHash]
        p.isAdmin = True
    elif pHash in ras.adm_liteAdminHashes:
        g_lite_admins[p] = ras.adm_liteAdminHashes[pHash]
        p.isAdmin = True
    if p.isAdmin and ras.adm_autoAdmin:
        if str(host.rcon_invoke('sv.tkPunishEnabled')).strip() == '1':
            host.rcon_invoke('sv.tkPunishEnabled 0')
            adminPM('Autoadmin Desactivado!', p)
    if not rplayerdata.isPlayerWhitelisted(p):
        keys = rplayerdata.getPlayerRelatedKeys(p)
        bannedKeys = g_banSystem.getCurrentBanIds()
        for key in keys:
            if key in ras.whitelisted_player_ids:
                logAdmin('allowedid', 'SERVER', p.getName(), 'PERMITIDO Cuenta relacionada con un ID baneado: %s' % key)
                return
            if (key.lower(),) in bannedKeys:
                logAdmin('!kick', 'SERVER', p.getName(), 'DENEGADO Cuenta relacionada con un ID baneado: %s' % key)
                kickPlayer(p, related_key=key)
                return


def onPlayerDisconnect(player):
    try:
        playerName = player.getName().split(' ')[1]
        g_disconnected_player_teams[playerName] = player.getTeam()
    except:
        rdebug.errorMessage()

    if ras.log_connects:
        logConnect(player, False)
    if not ras.disable_allchat and updateAllChatStatus(bf2.playerManager.getNumberOfPlayers() - 1):
        rtimer.fireOnce(broadcastAllChatStatus, 30)
    adminsOnline = len(g_admins) + len(g_lite_admins)
    if player in g_admins:
        del g_admins[player]
        if len(g_admins) == 0 and g_lite_admins:
            adminPM('Last admin left, Liteadmins are now in charge!', player, display=True)
    elif player in g_lite_admins:
        del g_lite_admins[player]
    if adminsOnline and len(g_admins) == 0 and len(g_lite_admins) == 0:
        if ras.adm_autoAdmin:
            host.rcon_invoke('sv.tkPunishEnabled 1')
            globalMessage('Autoadmin activated!')


def onConsoleCommand(args):
    if len(args) == 0:
        return
    else:
        cmd = args[0]

        def printUsage():
            host.rcon_invoke('echo "Syntax:"')
            host.rcon_invoke('echo "%s"' % 'banadd hash [reason]')
            host.rcon_invoke('echo "%s"' % 'banremove hash')

        if cmd == 'ban':
            return printUsage()
        if cmd == 'banremove':
            if len(args) < 2:
                return printUsage()
            g_banSystem.remove_ban(args[1])
            host.rcon_invoke('echo "%s"' % 'Remove ban command executed')
        elif cmd == 'banadd':
            if len(args) < 2:
                return printUsage()
            g_banSystem.ban_id(args[1:], None)
            host.rcon_invoke('echo "%s"' % 'Add ban command executed')
            h = args[1]
            players = filter(lambda p: realityserver.getPlayerHash(p).lower() == h.lower(), rcore.getPlayers())
            if len(players) == 1:
                kickPlayer(players[0], reason=' '.join(args[2:]), announce=True)
        return


def onResignTimer(player):
    if player.isValid():
        resignPlayer(player)


def onPlayerChangedSquadEarly(player, oldID, newID):
    if newID == 0:
        return
    else:
        timeExpired = rcore.now() - g_roundStartTime
        if player.isAIPlayer():
            return
        noSquadsBefore = round(ras.sqd_noSquadsBefore, -1)
        noSquadsBefore = noSquadsBefore - 1
        if timeExpired <= noSquadsBefore and not rcore.roundStarted():
            if ras.sqd_resignEarly:
                rtimer.fireNextTick(onResignTimer, player)
                sendRhooksAdminWarnEventWrapper(player, 'Has creado una escuadra muy temprano!\r\nVuelve a intentarlo en %d segundos, cuando el tiempo de despliegue llegue a los %s minutos.' % (ras.sqd_noSquadsBefore - timeExpired, str('2:00')), display=True, history=False, longDisplay=True)
                if ras.sqd_kickLimit > 0:
                    if hasattr(player, 'failedSquads'):
                        player.failedSquads += 1
                    else:
                        player.failedSquads = 1
                    if player.failedSquads >= ras.sqd_kickLimit:
                        kickPlayer(player, 'Has creado una escuadra muy temprano!', True, None)
                        logAdmin('!kick', 'SERVER', player.getName(), 'Ha creado una escuadra muy temprano!')
        return


def onPlayerKilled(p, attacker, weapon, assists, obj):
    p.die = 0
    p.killreason = ''
    if hasattr(p, 'teamswitch') and p.teamswitch:
        teamSwitchPlayer(p)
        p.teamswitch = False


def onPlayerChangeWeaponRopeCheck(player, oldWeapon, newWeapon):
    if oldWeapon is None:
        return
    else:
        if oldWeapon.templateName in GRAPPLE_WEAPONS:
            grappleItems = rcore.getObjectsOfTemplate('GrapplingHookRope')
            for rope in rcore.cleanListOfObjects(grappleItems):
                if rcore.getObjectId(rope) not in g_knownGrapplingHooks:
                    g_knownGrapplingHooks[rope.index] = [rope, player.getProfileId()]
                    break

            ropeCount = 0
            for ropeIndex in g_knownGrapplingHooks.keys():
                if g_knownGrapplingHooks[ropeIndex][0] is None or not g_knownGrapplingHooks[ropeIndex][0].isValid():
                    try:
                        del g_knownGrapplingHooks[ropeIndex]
                    except:
                        pass

                    continue
                if g_knownGrapplingHooks[ropeIndex][1] == player.getProfileId():
                    ropeCount += 1

            if ropeCount > ras.adm_maxRopes:
                commandKick([player.getName().split(' ')[1], ' Demasiadas cuerdas'], DummyAdminUser('Autoadmin'))
        return


def personalMessage(msg, p, big = False, color = True):
    if p is None or not p.isValid() or p.isAIPlayer():
        return
    else:
        msg = str(msg)
        prefix = ''
        if big:
            prefix += '\xc2\xa73'
        if color:
            prefix += '\xc2\xa7C1001'
        try:
            if p.isRcon():
                sendToPrism('msg', [5, str(msg), ''])
                return
        except:
            pass

        if int(host.rcon_invoke('sv.internet').strip()) == 1:
            prefixedMsg = prefix + msg
            if len(prefixedMsg) > 240:
                prefixedMsg = prefixedMsg[0:239]
            host.sgl_sendTextMessage(p.index, 14, 1, prefixedMsg, 0)
        else:
            globalMessage(msg, big, color)
        return


def globalMessage(msg, big = False, color = True):
    prefix = ''
    if big:
        prefix += '\xc2\xa73'
    if color:
        prefix += '\xc2\xa7C1001'
    prefixedMsg = prefix + msg
    if len(prefixedMsg) > 240:
        prefixedMsg = prefixedMsg[0:239]
    host.rcon_invoke('game.sayall "%s"' % prefixedMsg)


def teamMessage(team, msg, big = False, color = True):
    prefix = ''
    if big:
        prefix += '\xc2\xa73'
    if color:
        prefix += '\xc2\xa7C1001'
    prefixedMsg = '%sTeam: %s' % (prefix, msg)
    if len(prefixedMsg) > 240:
        prefixedMsg = prefixedMsg[0:239]
    host.rcon_invoke('game.sayTeam %i "%s"' % (team, prefixedMsg))


def adminPM(msg, p = None, target = None, big = False, color = True, display = False, history = True, longDisplay = False, toPrism = True):
    if p:
        msg += ' [' + '%s (%s, %s)' % (p.getName(), rcore.getTeamName(p.getTeam()), p.getSquadId()) + ']'
    if realityserver.isInternetServer():
        if len(g_admins) > 0:
            for admin in g_admins:
                if not display:
                    personalMessage(msg, admin, big, color)
                if display or history:
                    sendRhooksAdminWarnEventWrapper(admin, msg, display, history, longDisplay)

        else:
            for admin in g_lite_admins:
                if not display:
                    personalMessage(msg, admin, big, color)
                if display or history:
                    sendRhooksAdminWarnEventWrapper(admin, msg, display, history, longDisplay)

    else:
        globalMessage(msg, big, color)
    if target is None and p is not None:
        target = p.getName()
    if target is None:
        target = ''
    if toPrism:
        sendToPrism('msg', [6, str(msg), str(target)])
    return

SOUND_ID_PROMOTE = 1

def adminPMBig(msg, p = None, target = None, big = True, color = True, display = False, history = True, longDisplay = False, toPrism = True):
    if p:
        msg += ' [' + '%s (%s, %s)' % (p.getName(), rcore.getTeamName(p.getTeam()), p.getSquadId()) + ']'
    if realityserver.isInternetServer():
        if len(g_admins) > 0:
            for admin in g_admins:
                if not display:
                    personalMessage(msg, admin, big, color)
                if display or history:
                    sendRhooksAdminWarnEventWrapper(admin, msg, display, history, longDisplay)
                    rcore.playSoundForPlayer(admin, SOUND_ID_PROMOTE)

        else:
            for admin in g_lite_admins:
                if not display:
                    personalMessage(msg, admin, big, color)
                if display or history:
                    sendRhooksAdminWarnEventWrapper(admin, msg, display, history, longDisplay)

    else:
        globalMessage(msg, big, color)
    if target is None and p is not None:
        target = p.getName()
    if target is None:
        target = ''
    if toPrism:
        sendToPrism('msg', [6, str(msg), str(target)])
    return


def onVoteHUDEvent(player, cmd, args):
    return

def updatePlayerVote(p, playerID, vote):
    global g_voteList
    global g_vote_map
    if playerID in g_voteList:
        if g_voteList[playerID] != vote:
            g_voteList[playerID] = vote
            sendRhooksAdminWarnEventWrapper(p, 'Voto aceptado y cambiado! Votaste por:\r\n%s' % g_vote_map[vote - 1], history=False)
        else:
            sendRhooksAdminWarnEventWrapper(p, 'Ya has votado por:\r\n%s' % g_vote_map[int(vote) - 1], history=False)
    else:
        g_voteList[playerID] = vote
        sendRhooksAdminWarnEventWrapper(p, 'Voto aceptado! Votaste por:\r\n%s' % g_vote_map[int(vote) - 1], history=False)


def onChatMessageVote(playerID, msgText, channel, flags):
    if g_voteRunning is True:
        if playerID != -1:
            p = bf2.playerManager.getPlayerByIndex(playerID)
            msgText = msgText.lstrip('HUD_TEXT_CHAT_TEAM')
            msgText = msgText.lstrip('HUD_TEXT_CHAT_SQUAD')
            msgText = msgText.lstrip('HUD_TEXT_CHAT_DEADPREFIX')
            msgText = msgText.lstrip('HUD_CHAT_DEADPREFIX')
            msgText = msgText.lstrip('* ')
            msgText = msgText.strip()
            mapsInVote = len(g_vote_map)
            m = re.match('^([1-%i])$' % mapsInVote, msgText)
            if not m:
                return
            vote = int(m.group(1))
            if channel != 'Squad' and p.isCommander() == 0:
                sendRhooksAdminWarnEventWrapper(p, 'Solo los votos en el chat de escuadra (verde) son aceptados!', history=False)
                return
            updatePlayerVote(p, playerID, vote)


def initializeVote(maps, player):
    global g_voteAdmin
    global g_voteRunning
    global g_vote_tleft_msg
    global g_vote_map
    global g_vote_Timer
    global g_voteMsgTimer
    g_voteRunning = True
    destroyVoteMsgTimer()
    destroyVoteTimer()
    g_voteList.clear()
    i = 0
    for _map in maps:
        maps[i] = findMapName(_map)
        i += 1

    g_vote_map = maps
    if len(g_vote_map) == 2:
        message = 'Votacion :    1: %s    2: %s   | Presiona L, escribe el numero que quieres votar y luego ENTER' % (g_vote_map[0], g_vote_map[1])
    if len(g_vote_map) == 3:   
        message = 'Votacion :    1: %s    2: %s    3: %s   | Presiona L, escribe el numero que quieres votar y luego ENTER' % (g_vote_map[0], g_vote_map[1], g_vote_map[2])
    if len(g_vote_map) == 4:
        message = 'Votacion :    1: %s    2: %s    3: %s    4: %s  | Presiona L, escribe el numero que quieres votar y luego ENTER' % (g_vote_map[0], g_vote_map[1], g_vote_map[2], g_vote_map[3])
    logAdmin('!mapvote', player.getName(), '', message)
    adminPM('Se ha iniciado la votacion...', player, history=False)
    g_voteAdmin = getPlayerName(player)
    players = list(rcore.getPlayers())
    for p in players:
        sendRhooksAdminWarnEventWrapper(p, 'Se ha iniciado la votacion\r\nPresiona L, escribe el numero que quieres votar y luego ENTER', history=False)
        rcore.playSoundForPlayer(p, SOUND_ID_PROMOTE)

    g_vote_tleft_msg = ras.adm_mvoteDuration
    g_voteMsgTimer = rtimer.Timer(onVoteMsgTimer, 0, 1, message)
    g_voteMsgTimer.setRecurring(ras.adm_mvoteRecurrence)
    g_vote_Timer = rtimer.Timer(onVote, ras.adm_mvoteDuration, 1, player.getName())


def endVote(terminated, player):
    global g_vote_performed_on
    global g_vote_res_time
    global g_voteRunning
    global g_vote_res_msg
    g_voteRunning = False
    destroyVoteTimer()
    destroyVoteMsgTimer()
    vote_result = g_voteList.values()
    if len(g_vote_map) == 2:
        message = 'Resultado votacion: %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2))
        if rdb.db:
            rdb.db.enter_votehistory(g_voteAdmin, g_vote_map[0], vote_result.count(1), g_vote_map[1], vote_result.count(2), None, None)
    if len(g_vote_map) == 3: 
        message = 'Resultado votacion: %s: %i | %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2),
         g_vote_map[2],
         vote_result.count(3))
        if rdb.db:
            rdb.db.enter_votehistory(g_voteAdmin, g_vote_map[0], vote_result.count(1), g_vote_map[1], vote_result.count(2), None, None)   
    if len(g_vote_map) == 4:
        message = 'Resultado votacion: %s: %i | %s: %i | %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2),
         g_vote_map[2],
         vote_result.count(3),
         g_vote_map[3],
         vote_result.count(4))
        if rdb.db:
            rdb.db.enter_votehistory(g_voteAdmin, g_vote_map[0], vote_result.count(1), g_vote_map[1], vote_result.count(2), g_vote_map[2], vote_result.count(3), g_vote_map[3], vote_result.count(4))
    globalMessage(message, True, True)
    if terminated:
        g_vote_res_msg = message + ', cancelada por %s hace' % player
    else:
        g_vote_res_msg = message + ', iniciada por %s hace' % player
    g_vote_res_time = int(time.time())
    g_vote_performed_on = rcore.getMapName(None, True)
    logAdmin('mapvoteresult', player, None, message)
    players = list(rcore.getPlayers())
    for player in players:
        sendRhooksAdminWarnEventWrapper(player, message, display=False)

    return


def destroyVoteTimer():
    global g_vote_Timer
    if g_vote_Timer:
        g_vote_Timer.destroy()
        g_vote_Timer = None
    return


def onVote(player):
    endVote(False, player)


def destroyVoteMsgTimer():
    global g_voteMsgTimer
    if g_voteMsgTimer:
        g_voteMsgTimer.destroy()
        g_voteMsgTimer = None
        
    return


def onVoteMsgTimer(data):
    global g_vote_tleft_msg
    message = data
    globalMessage(message, True, False)
    timerMessage = 'La votacion ha iniciado! Quedan ' + str(g_vote_tleft_msg) + ' segundos! Vota ahora!'
    globalMessage(timerMessage)
    players = list(rcore.getPlayers())
    vote_result = g_voteList.values()
    msg = ''
    if len(g_vote_map) == 2:
        msg = 'Conteo actual: %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2))

    if len(g_vote_map) == 3:
        msg = 'Conteo actual: %s: %i | %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2),
         g_vote_map[2],
         vote_result.count(3))
            
    if len(g_vote_map) == 4:
        msg = 'Conteo actual: %s: %i | %s: %i | %s: %i | %s: %i' % (g_vote_map[0],
         vote_result.count(1),
         g_vote_map[1],
         vote_result.count(2),
         g_vote_map[2],
         vote_result.count(3),
         g_vote_map[3],
         vote_result.count(4))  

    globalMessage(msg)
    g_vote_tleft_msg -= ras.adm_mvoteRecurrence
    
    return


def findMapName(mapNamePart):
    mapName = mapNamePart
    for mapId, _map in g_mapList.items():
        if _map[0].find(mapNamePart) == -1:
            continue
        mapName = _map[0]
        break

    return rcore.getMapName(mapName, True)


def onAnnouncerPlayerSpawn(p, vehicle):
    if ras.ann_enabled is True and ras.ann_joinMessageEnabled is True and hasattr(p, 'welcomeMsg') and p.welcomeMsg is False:
        msg = ras.ann_joinMessage.replace('[playername]', p.getName())
        sendRhooksAdminWarnEventWrapper(p, msg, display=False)
        p.welcomeMsg = True


def onAnnouncerPlayerDisconnect(p):
    if ras.ann_enabled is True and ras.ann_disconnectMessageEnabled is True:
        msg = ras.ann_disconnectMessage.replace('[playername]', p.getName())
        adminPM(msg)


def announceMessage(data = ''):
    for s in data.split('\n'):
        if len(s) > 0:
            host.rcon_invoke('game.sayall "%s"' % s)


def destroyAnnounceTimers():
    for _time in g_announcerTimers:
        if g_announcerTimers[_time]:
            g_announcerTimers[_time].destroy()
            g_announcerTimers[_time] = None

    g_announcerTimers.clear()
    
    return


def destroySponsorTimer():
    global g_sponsorTimer
    if g_sponsorTimer:
        g_sponsorTimer.destroy()
        g_sponsorTimer = None
        
    return


def logRoundStart():
    d = time.strftime(ras.log_date_format)
    rlogger.RealityLogger['ChatLog'].setActive(True)
    rlogger.RealityLogger['ChatLog'].logLines(['Map          : %s' % rcore.getMapName(),
     'Gamemode     : %s' % rcore.getGameMode(),
     'Layer        : %s' % rcore.getMapLayer(),
     'Team 1       : %s' % rcore.getTeamName(1),
     'Team 2       : %s' % rcore.getTeamName(2),
     'ROUND STARTED: %s' % d,
     ''])
    rlogger.RealityLogger['ChatLog'].writeBuffer()


def logChat(channel, message, player):
    d = time.strftime(ras.log_time_format)
    rlogger.RealityLogger['ChatLog'].logLine('[%s%s] %s: %s' % (d,
     channel.upper(),
     player.getName(),
     message))


def logTeamkill(attacker, victim, weapon):
    d = time.strftime(ras.log_time_format)
    rlogger.RealityLogger['ChatLog'].logLine('[%s   TEAMKILL] %s [%s] %s' % (d,
     attacker.getName(),
     weapon,
     victim.getName()))


def logKill(attacker, victim, weapon):
    d = time.strftime(ras.log_time_format)
    rlogger.RealityLogger['ChatLog'].logLine('[%s       KILL] %s [%s] %s' % (d,
     attacker.getName(),
     weapon,
     victim.getName()))


def logConnect(player, connect):
    d = time.strftime(ras.log_time_format)
    if connect:
        rlogger.RealityLogger['ChatLog'].logLine("[%s    CONNECT] '%s' connected with IP: %s" % (d, player.getName(), player.getAddress()))
    else:
        rlogger.RealityLogger['ChatLog'].logLine("[%s DISCONNECT] '%s' disconnected with IP: %s" % (d, player.getName(), player.getAddress()))


def logTeamChange(player, team):
    d = time.strftime(ras.log_time_format)
    rlogger.RealityLogger['ChatLog'].logLine("[%s CHANGETEAM] '%s' change to team %s" % (d, player.getName(), team))


def logBan(player, reason, length, banningAdmin):
    d = time.strftime(ras.log_date_format)
    rlogger.RealityLogger['BanLog'].logLine('[%s] %s %s %s %s banned by %s (%s)' % (d,
     realityserver.getPlayerHash(player),
     player.getName(),
     player.getAddress(),
     reason,
     banningAdmin.getName(),
     length))


def logAdmin(cmd, an, pn, text):
    if ras.log_admins:
        d = time.strftime(ras.log_date_format)
        cmd = cmd.ljust(15)
        if not pn:
            rlogger.RealityLogger['AdminLog'].logLine("[%s] %s performed by '%s': %s" % (d,
             cmd.upper(),
             an,
             text))
        else:
            rlogger.RealityLogger['AdminLog'].logLine("[%s] %s performed by '%s' on '%s': %s" % (d,
             cmd.upper(),
             an,
             pn,
             text))


def logTickets():
    if not ras.log_tickets:
        return
    d = time.strftime(ras.log_date_format)
    rlogger.RealityLogger['TicketLog'].logLine('[%s] Team 1: %s, Team 2: %s, Map: %s (%s, %s)' % (d,
     bf2.gameLogic.getTickets(1),
     bf2.gameLogic.getTickets(2),
     rcore.getMapName(),
     rcore.getGameMode(),
     rcore.getMapLayer()))


def onLoggerGameStatusChanged(status):
    if not (ras.log_chat or ras.log_connects or ras.log_teamkills or ras.log_kills):
        return
    if status == bf2.GameStatus.Loading:
        rlogger.RealityLogger['ChatLog'].setActive(False)
    if status == bf2.GameStatus.Loaded:
        logRoundStart()


def onLoggerChatMessage(playerID, msgText, channel, flags):
    channel = channel.lower()
    if len(msgText) > 0 and channel not in ('servermessage', 'serverteammessage', 'player') and ras.log_chat:
        msgText = msgText.lstrip('HUD_TEXT_CHAT_TEAM')
        msgText = msgText.lstrip('HUD_TEXT_CHAT_SQUAD')
        msgText = msgText.lstrip('HUD_TEXT_CHAT_DEADPREFIX')
        msgText = msgText.lstrip('HUD_CHAT_DEADPREFIX')
        msgText = msgText.lstrip('* ')
        p = bf2.playerManager.getPlayerByIndex(playerID)
        if p is None:
            p = DummyAdminUser('SERVER')
        if channel == 'team':
            channel = '     team %s' % p.getTeam()
        elif channel == 'squad':
            channel = ' t%s squad %s' % (p.getTeam(), p.getSquadId())
        elif channel == 'global':
            channel = '     global'
        logChat(channel, msgText, p)
    return


def onLoggerPlayerKilled(victim, attacker, weapon, assists, obj):
    if not victim or not attacker:
        return
    else:
        if not weapon:
            weapon = 'killed'
        else:
            weapon = weapon.templateName
        if victim.getTeam() == attacker.getTeam():
            if ras.log_teamkills:
                logTeamkill(attacker, victim, weapon)
            if ras.adm_sendTeamKillMessage:
                if attacker == victim:
                    return
                if attacker.getVehicle() and victim.getVehicle():
                    distance = int(rcore.getVectorDistance(attacker.getVehicle().getPosition(), victim.getVehicle().getPosition()))
                    adminPM('%s [%s : %s m] %s' % (attacker.getName(),
                     weapon,
                     distance,
                     victim.getName()), None, history=False, toPrism=False)
        elif ras.log_kills:
            logKill(attacker, victim, weapon)
        return


def onBalancePlayerChangeTeams(p, humanHasSpawned):
    switchCheck = not (p.isSquadLeader() or p.isCommander())
    didBalance = smartBalance(p, switchCheck, sendAdminPMonIPConflict=True)
    if not didBalance:
        rdebug.debugMessage('%s cambio de equipo por su cuenta' % p.getName(), 'admin')
        team = 'REDFOR' if p.getTeam() == 1 else 'BLUFOR'
        if ras.log_changeTeam:
            logTeamChange(p, team)
        if ras.adm_notifyChangeTeam:
            adminPM('%s cambio al equipo %s' % (p.getName(), team), None, p.getName(), history=False)
    return


def onBalancePlayerConnect(player):
    if player.isAIPlayer():
        return
    try:
        playerName = player.getName().split(' ')[1]
        if playerName in g_disconnected_player_teams:
            player.setTeam(g_disconnected_player_teams[playerName])
            return
        if ras.smb_randomiseJoinTeam:
            if random.uniform(0, 1) <= 0.5:
                player.setTeam(rcore.getOtherTeam(player.getTeam()))
        smartBalance(player, True)
    except:
        rdebug.errorMessage()


def onBalancePlayerDeath(p, vehicle):
    if ras.smb_balanceOnDeath:
        smartBalance(p, not (rcore.isSoldier(vehicle) is False or p.isSquadLeader() or p.isCommander()))


def onBalanceRoundStart():
    destroyPreGameBalanceTimer()


def sendABMessage(p):
    sendRhooksAdminWarnEventWrapper(p, 'Has sido AUTOBALANCEADO por el SERVIDOR.', history=True)


def getOtherPlayer(p):
    sameIPList = IPTester.getPlayersWithSameIPAsPlayer(p)
    otherp = None
    if len(sameIPList) > 1:
        if p == sameIPList[0]:
            otherp = sameIPList[1]
        else:
            otherp = sameIPList[0]
    return otherp


def smartBalance(p, switchCheck, isPreRoundBalance = False, sendAdminPMonIPConflict = False):
    """
    This function checks if a player should be switched or not.
    
    returns:
        0 (int): 0 if did not balance player
        1 (int): 1 antiGhost prevents switch
        2 (int): 2 smartBalance exclude list
    """
    if not ras.smb_enabled:
        return 0
    elif p.isAIPlayer():
        return 0
    elif rcore.isInsideVehicle(p):
        return 0
    tag = getPlayerTag(p)
    name = getPlayerName(p)
    if tag in ras.smb_excludeList:
        return 0
    for ct in ras.smb_excludeList:
        if ct.startswith('*') and name.endswith(ct.lstrip('*')):
            return 0
        if ct.endswith('*') and name.startswith(ct.rstrip('*')):
            return 0

    if ras.smb_antiGhost:
        sameIPList = IPTester.getPlayersWithSameIPAsPlayer(p)
        hasIpConflict = len(sameIPList) > 1
        if hasIpConflict:
            otherp = sameIPList[1] if p == sameIPList[0] else sameIPList[0]
            if otherp.getTeam() != p.getTeam():
                p.setTeam(otherp.getTeam())
                rdebug.debugMessage('%s IP conflict with %s' % (p.getName(), otherp.getName()), 'admin')
                if sendAdminPMonIPConflict:
                    rmemory.HudVarWriteEventWstringWithTimedShowvar(p, 'PythonGameWarning', 'Advertencia:\nHas sido cambiado de equipo debido a un conflicto de IP con otro jugador\nPide a los administradores un !switch para omitir esta verificacion automatica', 15)
                    adminPM('Se le denego el switch a%s, conflicto de IP con%s' % (p.getName(), otherp.getName()), history=False)
                return 1
            else:
                return 0
    team = p.getTeam()
    hisTeam = bf2.playerManager.getNumberOfPlayersInTeam(team)
    theirTeam = bf2.playerManager.getNumberOfPlayersInTeam(rcore.getOtherTeam(team))
    if hisTeam <= theirTeam + ras.smb_difference:
        return 0
    elif switchCheck:
        if isPreRoundBalance:
            rtimer.fireOnce(sendABMessage, 1.0, p)
        p.setTeam(rcore.getOtherTeam(p.getTeam()))
        return 2
    else:
        return 0


def onBalanceGameStatusChanged(status):
    global g_swap_teams_next
    global g_scramble_next
    global g_last_setnext
    global g_switch_next
    global g_preGameBalanceTimer
    if status == bf2.GameStatus.Playing:
        rdebug.debugMessage('Timer is destroyed in onGameStatusChanged!', 'admin')
        destroyPreGameBalanceTimer()
        rdebug.debugMessage('Timer started...', 'admin')
        g_preGameBalanceTimer = rtimer.Timer(preGameSmartBalance, 3, 1)
        g_preGameBalanceTimer.setRecurring(3)
        for player in bf2.playerManager.getPlayers():
            resignPlayer(player)
            playerId = player.getProfileId()
            if playerId in g_switch_next:
                player.setTeam(g_switch_next[playerId])

        if ras.smb_scrambleTeamsOnStart or g_scramble_next:
            try:
                swapTeams()
                scrambleTeams()
            except:
                rdebug.errorMessage()

        elif g_swap_teams_next:
            if not (ras.smb_enabled and ras.smb_swapTeamsOnStart):
                swapTeams()
        elif ras.smb_enabled and ras.smb_swapTeamsOnStart:
            swapTeams()
        g_scramble_next = False
        g_swap_teams_next = False
        g_switch_next.clear()
        g_last_setnext = None
    return


def destroyPreGameBalanceTimer():
    global g_preGameBalanceTimer
    if g_preGameBalanceTimer:
        g_preGameBalanceTimer.destroy()
        g_preGameBalanceTimer = None
    return


def preGameSmartBalance(data):
    rdebug.debugMessage('Entered PreGameSmartBalance()', 'admin')
    if ras.smb_enabled is True:
        team1 = bf2.playerManager.getNumberOfPlayersInTeam(1)
        team2 = bf2.playerManager.getNumberOfPlayersInTeam(2)
        rdebug.debugMessage('Team1: %s. Team 2: %s.' % (str(team1), str(team2)), 'admin')
        if team1 > team2 + ras.smb_difference:
            rdebug.debugMessage('Team 1 has more players than team 2', 'admin')
            teamToCheck = 1
        elif team2 > team1 + ras.smb_difference:
            rdebug.debugMessage('Team 2 has more players than team 1', 'admin')
            teamToCheck = 2
        else:
            return
        playersToCheck = [ p for p in rcore.getPlayers(teamToCheck) if not (p.getSquadId() or p.isSquadLeader() or p.isCommander() or p.isAIPlayer()) ]
        if playersToCheck:
            random.shuffle(playersToCheck)
            smartBalance(playersToCheck[0], True, isPreRoundBalance=True)


def sendToPrism(subject, args):
    if not args or args == '':
        args = [None]
    rprism.onAdminModuleCommand(subject, args)
    return


def onPrismAdminCommand(subject, adminname, message):
    global g_adminCommands
    adminUser = DummyAdminUser(adminname)
    response = True
    if '\n' in message[0]:
        for name in message[0].split('\n'):
            args = message[1:]
            args.insert(0, name)
            response = g_adminCommands[subject](args, adminUser) and response

    else:
        if len(message) == 1 and message[0] == '':
            message = []
        response = g_adminCommands[subject](message, adminUser)
    if response is None:
        response = False
    sendToPrism('adminResponse', [subject, response, adminUser.getName()])
    return


def prismAdminConnected(adminName):
    global g_prism_admins
    if adminName not in g_prism_admins:
        g_prism_admins.append(adminName)


def prismAdminDisconnected(adminName):
    if adminName in g_prism_admins:
        g_prism_admins.remove(adminName)


def fillCommandDict():
    g_adminCommands.update({'aa': commandAutoadmin,
     'ab': commandAutoBalance,
     'admins': commandAdmins,
     'ban': commandBan,
     'banid': commandBanId,
     'timebanid': commandTimeBanId,
     'br': commandBattleRecorder,
     'flip': commandFlip,
     'tp': commandTeleport,
     'tpto': commandTeleportTo,
     'heal': commandHeal,
     'rearm': commandRearm,
     'fly': commandFly,
     'push': commandPush,
     'pilot': commandPilot,
     'givelead': commandGiveLead,
     'hash': commandHash,
     'help': commandHelp,
     'history': commandHistory,
     'init': commandInit,
     'kick': commandKick,
     'kill': commandKill,
     'mapvote': commandMapVote,
     'message': commandMessage,
     'reload': commandReload,
     'report': commandReport,
     'reportplayer': commandReportPlayer,
     'resign': commandResign,
     'resignall': commandResignall,
     'rules': commandRules,
     'runnext': commandRunNext,
     'say': commandSay,
     'sayteam': commandSayTeam,
     'setnext': commandSetNext,
     'shownext': commandShowNext,
     'stopserver': commandStopServer,
     'scramble': commandScramble,
     'swapteams': commandSwapTeam,
     'switch': commandSwitch,
     'tempban': commandTempBan,
     'tickets': commandTickets,
     'timeban': commandTimeBan,
     'unban': commandUnban,
     'unbanid': commandUnbanId,
     'unbanname': commandUnbanName,
     'warn': commandWarn,
     'website': commandWebsite,
     'ungrief': commandUngrief,
     'resetsquads': commandResetsquads,
     'ec': commandEntranceControl,
     'info': commandPlayerInfo,
     'showafk': commandShowAfk,
     'roundban': commandRoundBan,
     'assignlead': commandAssignLead})


def onChatMessageCheckUnprintableChars(playerID, msgText, channel, flags):
    if playerID == -1:
        return
    if channel.lower() not in ('team', 'squad', 'global'):
        return
    for c in msgText:
        if ord(c) > 127 or ord(c) < 32:
            if rdebug.isDebugEnabled():
                rdebug.debugMessage('Detected bad char in chat message: %s' % c)
                continue
            p = bf2.playerManager.getPlayerByIndex(playerID)
            globalMessage('%s HA SIDO KICKEADO, %s - %s' % (p.getName(), 'Chat hack', '[Autoadmin]'))
            logAdmin('!k', '[Autoadmin]', p.getName(), 'Chat hack')
            host.rcon_invoke('admin.kickPlayer %d' % p.index)
            return


def onChatMessage(playerID, msgText, channel, flags):
    if len(msgText) > 1 and playerID != -1:
        msgText = msgText.lstrip('HUD_TEXT_CHAT_TEAM')
        msgText = msgText.lstrip('HUD_TEXT_CHAT_SQUAD')
        msgText = msgText.lstrip('HUD_TEXT_CHAT_DEADPREFIX')
        msgText = msgText.lstrip('HUD_CHAT_DEADPREFIX')
        msgText = msgText.lstrip('* ')
        if msgText.startswith(ras.adm_commandSymbol):
            msgText = msgText.lstrip(ras.adm_commandSymbol)
            words = msgText.split(' ')
            command = words[0].lower()
            if command in ras.adm_commandAliases:
                command = ras.adm_commandAliases[command]
            args = filter(None, words[1:])
            if command not in g_adminCommands:
                return
            p = bf2.playerManager.getPlayerByIndex(playerID)
            if canExecute(command, p):
                g_adminCommands[command](args, p)
    return


def commandAutoadmin(args, p):
    if len(args) > 0 and args[0].lower() != 'on' and args[0].lower() != 'off':
        personalMessage('Por favor especifica un parametro correcto (on/off)', p)
        return False
    else:
        if len(args) == 0:
            v = str(host.rcon_invoke('sv.tkPunishEnabled').strip())
            if v == '1':
                v = 'enabled'
            else:
                v = 'disabled'
            personalMessage('Autoadmin is ' + v, p)
        else:
            if args[0].lower() == 'on':
                host.rcon_invoke('sv.tkPunishEnabled 1')
                adminPM('Autoadmin ha sido activado', p)
            else:
                host.rcon_invoke('sv.tkPunishEnabled 0')
                adminPM('Autoadmin ha sido desactivado', p)
            logAdmin('!aa', p.getName(), '', args[0].lower())
        return True


def commandAutoBalance(args, player):

    def turnOnAB(p):
        ras.smb_enabled = True
        adminPM('El SmartBalance ha sido activado, es desbalance permitido es de %i' % ras.smb_difference, p)
        return True

    def turnOffAB(p):
        ras.smb_enabled = False
        adminPM('El SmartBalance ha sido desactivado, es desbalance permitido es de %i' % ras.smb_difference, p)
        return True

    argc = len(args)
    if argc == 1:
        if args[0].lower() == 'on':
            return turnOnAB(player)
        if args[0].lower() == 'off':
            return turnOffAB(player)
        if args[0].lower() == 'ip':
            status = 'enabled' if ras.smb_antiGhost else 'disabled'
            adminPM('Anti ghost is %s' % status, player)
            return True
        if args[0].lower() == 'deathbalance':
            status = 'enabled' if ras.smb_balanceOnDeath else 'disabled'
            adminPM('El balance al morir es %s' % status, player)
            return True
    elif argc == 2:
        if args[0].lower() in ('on', 'off'):
            if not re.match('^\\d+$', args[1]):
                personalMessage('Por favor especifica una diferencia de jugador valida.', player)
                return False
            else:
                ras.smb_difference = int(args[1])
                if args[0].lower() == 'on':
                    return turnOnAB(player)
                return turnOffAB(player)
        if args[0].lower() == 'ip':
            ras.smb_antiGhost = True if args[1].lower() == 'on' else False
            status = 'enabled' if ras.smb_antiGhost else 'disabled'
            adminPM('El anti-ghost esta %s' % status, player)
            return True
        if args[0].lower() == 'deathbalance':
            ras.smb_balanceOnDeath = True if args[1].lower() == 'on' else False
            status = 'enabled' if ras.smb_balanceOnDeath else 'disabled'
            adminPM('El balance al morir es %s' % status, player)
            return True
    status = 'enabled' if ras.smb_enabled else 'disabled'
    personalMessage('El SmartBalance es %s, con una diferencia de balance de %i. Sintaxis:' % (status, ras.smb_difference), player)
    personalMessage('!ab on/off [amount]', player)
    personalMessage('!ab ip [on/off]', player)
    personalMessage('!ab deathbalance [on/off]', player)
    return False


def commandAdmins(args, p):
    all_admins = []
    admin_teams = [ a.getTeam() for a in g_admins ]
    team1_count = admin_teams.count(p.getTeam())
    team2_count = admin_teams.count(rcore.getOtherTeam(p.getTeam()))
    prism_count = len(g_prism_admins)
    for a in g_admins:
        all_admins.append(a.getName())

    for a in g_lite_admins:
        all_admins.append(a.getName() + ' (Lite)')

    for a in g_prism_admins:
        all_admins.append(a + ' (PRISM)')

    if not all_admins:
        sendRhooksAdminWarnEventWrapper(p, 'No hay admins online (Aun asi te vigilamos 0_0)')
        return True
    sendstr = 'Admins: ' + ', '.join(all_admins)
    admincount = 'Admins disponibles: (%i en tu equipo, %i en el otro equipo, %i en PRISM)' % (team1_count, team2_count, prism_count)
    personalMessage(sendstr, p)
    sendRhooksAdminWarnEventWrapper(p, admincount, history=False)
    return True


def commandBan(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica un jugador a banear y la razon.', p)
        return False
    else:
        return banPlayer('!ban', args[0], p, 'perm', args[1:])


def commandBanId(args, p):
    if len(args) < 2:
        personalMessage('Uso: !banid 546039719a2755def5802f282d03b649 razon', p)
        return False
    if not g_banSystem.validatePlayerId(args[0]):
        personalMessage('PlayerID invalido (hash).', p)
        return False
    if g_banSystem.ban_id(args, p):
        logAdmin('!banid', p.getName(), 'id %s exitosamente baneado' % args[0], '')
        personalMessage('PlayerID %s exitosamente baneado' % args[0], p)
        for player in rcore.getPlayers():
            if realityserver.getPlayerHash(player) == args[0]:
                kickPlayer(player, findReason(' '.join(args[1:])), announce=True, admin=p, bansystem=True)
                break

        return True
    personalMessage('Fallo al banear el id %s' % args[0], p)
    return False


def commandTimeBanId(args, p):
    if len(args) < 3:
        personalMessage('Uso: !timebanid 546039719a2755def5802f282d03b649 tiempo razon', p)
        return False
    elif not g_banSystem.validatePlayerId(args[0]):
        personalMessage('ID de jugador invalido.', p)
        return False
    else:
        try:
            length = getTimeToBan(args[1])
        except TimeBanEpochException:
            personalMessage('Por favor especifica el tiempo a futuro.', p)
            return False
        except TimeBanSyntaxException:
            personalMessage("Por favor especifica una duracion valida. ('round', ':epoch' o '<number><m/h/d/w/M/y>')", p)
            return False

        reason = findReason(' '.join(args[2:]))
        try:
            if g_banSystem._enter_log('MANUALLY BANNED ID', None, time.time(), args[0], '', reason, 'timeban', length, p.getName(), g_banSystem.round_start):
                logAdmin('!timebanid', p.getName(), 'id %s sucessfully banned' % args[0], '')
                personalMessage('PlayerID %s exitosamente timebaneado.' % args[0], p)
                for player in rcore.getPlayers():
                    if realityserver.getPlayerHash(player) == args[0]:
                        kickPlayer(player, reason, announce=True, admin=p, bansystem=True)
                        break

                return True
        except sqlite3.IntegrityError:
            personalMessage('ID de jugador %s ya se encuentra baneado.' % args[0], p)
            return False

        personalMessage('Fallo al banear el ID %s' % args[0], p)
        return False


def commandBattleRecorder(args, p):
    v = str(host.rcon_invoke('sv.autoRecord').strip())
    if v == '1':
        u = str(host.rcon_invoke('sv.demoQuality').strip())
        personalMessage('Battlerecorder esta activado con calidad ' + u, p)
    else:
        personalMessage('Battlerecorder esta desactivado', p)
    return True

def commandFly(args, p):
    if len(args) != 2:
        personalMessage('Por favor especifica un jugador y una altura para hacer volar (maximo: %i)' % ras.adm_maxAltitude, p)
        return False
    if not re.match('^\\d+$', args[1]) or int(args[1]) > ras.adm_maxAltitude:
        personalMessage('Por favor especifica una altura correcta para hacer volar (maximo: %i)' % ras.adm_maxAltitude, p)
        return False
    foundPlayers = findPlayer(args[0], p)
    flungPlayers = 0
    height = int(args[1])
    for player in foundPlayers:
        if flyPlayer(player, height):
            globalMessage('HACIENDO VOLAR AL JUGADOR %s - %s' % (player.getName(), p.getName()))
            sendRhooksAdminWarnEventWrapper(player, 'Un administrador te hizo volar.')
            flungPlayers += 1
        else:
            personalMessage('%s esta muerto o herido.' % player.getName(), p)
        logAdmin('!fly', p.getName(), player.getName(), args[1])

    return flungPlayers > 0

def commandPush(args, p):
    if len(args) != 3:
        personalMessage('Por favor especifica un jugador, una distancia para empujar (maximo: %i) y un punto cardinal.' % ras.adm_maxPush, p)
        return False
    if args[2] == "n" or args[2] == "s" or args[2] == "e" or args[2] == "w":
        if not re.match('^\\d+$', args[1]) or int(args[1]) > ras.adm_maxPush:
            personalMessage('Por favor especifica una distancia valida para empujar (maximo: %i)' % ras.adm_maxPush, p)
            return False
        foundPlayers = findPlayer(args[0], p)
        pushedPlayers = 0
        distance = int(args[1])
        cardinal = str(args[2])
        for player in foundPlayers:
            if pushPlayer(player, distance, cardinal):
                globalMessage('EMPUJANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))
                if cardinal == "n":
                    tCardinal = "Norte"
                    sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha empujado en direccion ' + tCardinal + ".")
                    pushedPlayers += 1
                if cardinal == "s":
                    tCardinal = "Sur"
                    sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha empujado en direccion ' + tCardinal + ".")
                    pushedPlayers += 1
                if cardinal == "e":
                    tCardinal = "Este"
                    sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha empujado en direccion ' + tCardinal + ".")
                    pushedPlayers += 1
                if cardinal == "w":
                    tCardinal = "Oeste"
                    sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha empujado en direccion ' + tCardinal + ".")
                    pushedPlayers += 1    
            else:
                personalMessage('%s esta muerto o herido.' % player.getName(), p)
            logAdmin('!push', p.getName(), player.getName(), args[1])
    else:
        personalMessage('Por favor especifica un punto cardinal valido (n,s,e,w)', p)
        return False
    return pushedPlayers > 0

def commandPilot(args, p):
    team = p.getTeam()
    if rkits.pilotKit(p,team) == True:   
        personalMessage('Se te ha dado el kit de piloto :)', p)
    elif not p.isAlive() or p.isManDown():
        personalMessage('No puedes solicitar kit estando muerto o herido.', p)
    else:
        personalMessage('No se puede usar libremente el kit de piloto fuera de Test Airfield.', p)
    return True

def commandFlip(args, p):
    if len(args) != 1:
        personalMessage('Por favor especifica un jugador para voltear.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    flipedPlayers = 0
    for player in foundPlayers:
        if flipPlayer(player):
            globalMessage('VOLTEANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))
            sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha volteado %s' % p.getName())
            flipedPlayers += 1
        else:
            personalMessage('%s esta muerto o herido.' % player.getName(), p)
        logAdmin('!flip', p.getName(), player.getName(), 0)

    return flipedPlayers > 0

def commandTeleport(args, p):
    if len(args) != 4:
        personalMessage('Por favor especifica un jugador y sus coordenadas para teletransportar.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    playerX = args[1]
    playerY = args[2]
    playerZ = args[3]
    teleportedPlayers = 0
    for player in foundPlayers:
        if teleportPlayer(player,playerX,playerY,playerZ):
            '''globalMessage('TELETRANSPORTANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))'''
            sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha teletransportado.')
            teleportedPlayers += 1
        else:
            personalMessage('%s esta muerto o herido.' % player.getName(), p)
        logAdmin('!teleport', p.getName(), player.getName(), 0)

    return teleportedPlayers > 0

def commandTeleportTo(args, p):
    if len(args) == 0:
        personalMessage('Por favor especifica un jugador o keypad al que quieres teletransportarte.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    teleportedPlayers = 0
    if len(args) == 2:
        personalMessage('El input es:'+ str(args[0]) + str(args[1]), p)
        
        mapX = rcore.getCoordinates(args[0],args[1])
        
        personalMessage('Las coordenadas son:' + mapX)
        
        teleportPlayer(p,mapX,0,mapZ)
    if len(args) == 1: 
        for player in foundPlayers:
            pos = player.getVehicle().getPosition()
            playerX = pos[0] 
            playerY = pos[1] + 2
            playerZ = pos[2]
            if teleportPlayer(p,playerX,playerY,playerZ):
                '''globalMessage('TELETRANSPORTANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))'''
                sendRhooksAdminWarnEventWrapper(p, 'Te has teletransportado a%s' % player.getName())
                teleportedPlayers += 1

            else:
                personalMessage('%s esta muerto o herido.' % player.getName(), p)
            logAdmin('!teleport', p.getName(), player.getName(), 0)

        return teleportedPlayers > 0

def commandHeal(args, p):
    if len(args) != 1:
        personalMessage('Por favor especifica un jugador para curar.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    healPlayers = 0
    for player in foundPlayers:
        if healPlayer(player):
            globalMessage('CURANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))
            sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha curado.')
            healPlayers += 1
        else:
            personalMessage('%s esta muerto o herido.' % player.getName(), p)
        logAdmin('!heal', p.getName(), player.getName(), 0)

    return healPlayers > 0

def commandRearm(args, p):
    if len(args) != 1:
        personalMessage('Por favor especifica un jugador para rearmar.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    rearmPlayers = 0
    for player in foundPlayers:
        if rearmPlayer(player):
            globalMessage('REARMANDO AL JUGADOR %s - %s' % (player.getName(), p.getName()))
            sendRhooksAdminWarnEventWrapper(player, 'Un administrador te ha recargado.')
            rearmPlayers += 1
        else:
            personalMessage('%s esta muerto o herido.' % player.getName(), p)
        logAdmin('!rearm', p.getName(), player.getName(), 0)

    return rearmPlayers > 0


def updateTransferSquadLeaderHud(p, once = False):
    rmemory.sendHudVarWriteEventBool(p, 'PythonGiveLeadUpdateButtonShow', 1)


def rejoinSquadAfterTransferSquadLeader(data):
    p, localSquadId = data
    rmemory.sendHudVarWriteEventBool(p, 'PythonGiveLeadReturnToSquad%dShow' % localSquadId, 1)


def onTransferSquadLeader(player, cmd, args):
    if player.getSquadId() == 0 or not player.isSquadLeader():
        return False
    localPlayerId = -1
    localSquadId = player.getSquadId()
    if len(args) == 0:
        rtimer.fireOnce(updateTransferSquadLeaderHud, 1, player)
        for playerInSquad in rcore.getPlayersOfSquad(player.getTeam(), player.getSquadId(), player):
            localPlayerId += 1
            rmemory.sendHudVarWriteEventWstring(player, 'PythonGiveLeadPlayerNameString%d' % localPlayerId, '%s' % playerInSquad.getName())
            rmemory.sendHudVarWriteEventBool(player, 'PythonGiveLeadPlayer%dExistsShow' % localPlayerId, 1)

        if len(rcore.getPlayersOfSquad(player.getTeam(), player.getSquadId(), player)) == localPlayerId + 1:
            for x in range(localPlayerId + 1, 6):
                rmemory.sendHudVarWriteEventBool(player, 'PythonGiveLeadPlayer%dExistsShow' % x, 0)
                rmemory.sendHudVarWriteEventWstring(player, 'PythonGiveLeadPlayerNameString%d' % x, 'PythonGiveLeadPlayerNameString%d' % x)

    elif len(args) == 1:
        for playerInSquad in rcore.getPlayersOfSquad(player.getTeam(), player.getSquadId(), player):
            localPlayerId += 1
            if args[0] == str(localPlayerId):
                commandGiveLead([playerInSquad.getName().split(' ')[1]], player)

    return True


def commandGiveLead(args, p):
    """
    Give squadlead to somebody else
    """
    if not ras.adm_coopGiveLead and realityserver.isCoopServer():
        return False
    if p.getSquadId() == 0 or not p.isSquadLeader():
        return False
    if len(args) != 1:
        personalMessage('Por favor especifica un jugador para darle el liderazgo.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    if len(foundPlayers) != 1:
        return False
    target = foundPlayers[0]
    if target == p:
        return False
    if p.getSquadId() != target.getSquadId():
        personalMessage('El jugador %s no se encuentra en tu escuadra!' % target.getName(), p)
        return False
    for playerInSquad in rcore.getPlayersOfSquad(p.getTeam(), p.getSquadId(), p):
        if playerInSquad.index < target.index:
            resignPlayer(playerInSquad)
            rtimer.fireNextTick(rejoinSquadAfterTransferSquadLeader, data=(playerInSquad, target.getSquadId()))
            sendRhooksAdminWarnEventWrapper(playerInSquad, 'Has sido resignado: Tu lider de escuadra le ha transferido el liderazgo a alguien mas.\r\nIntentando auto-unirse a la escuadra...', longDisplay=True, history=False)

    resignPlayer(p)
    rtimer.fireNextTick(rejoinSquadAfterTransferSquadLeader, data=(p, target.getSquadId()))
    sendRhooksAdminWarnEventWrapper(p, 'Has sido resignado: Acabas de ceder tu puesto de Squad Leader.\r\nIntentando reincorporarte al Squad...', longDisplay=True, history=False)
    sendRhooksAdminWarnEventWrapper(target, 'Tu lider de escuadra te ha transferido el liderazgo.', history=False)
    return True


def commandHash(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica un jugador para saber el hash.', p)
        return False
    foundPlayers = findPlayer(args[0], p)
    if len(foundPlayers) == 0:
        return False
    for player in foundPlayers:
        personalMessage('El hash de %s es: %s' % (player.getName(), realityserver.getPlayerHash(player)), p)
        logAdmin('!hash', p.getName(), player.getName(), '')

    return True


def commandHelp(args, p):
    personalMessage('Comandos disponibles:', p)
    i = 0
    commands = ''
    for command in g_adminCommands:
        if canExecute(command, p):
            i += 1
            if commands != '':
                commands += ', '
            commands += ras.adm_commandSymbol + command
        if i == 8:
            personalMessage(commands, p)
            commands = ''
            i = 0

    if i > 0:
        personalMessage(commands, p)
    return True


def commandHistory(args, p):
    msgstr = ''
    if len(g_lastPlayedMaps) == 0:
        sendRhooksAdminWarnEventWrapper(p, 'No hay mapas en el historial rey.', history=False)
        return True
    for i in range(0, len(g_lastPlayedMaps)):
        index = len(g_lastPlayedMaps) - i
        if index == 1:
            prefix = '1er '
        elif index % 10 == 1:
            prefix = str(index) + 'er '
        elif index % 10 == 2:
            prefix = str(index) + 'do '
        elif index % 10 == 3:
            prefix = str(index) + 'er '
        else:
            prefix = str(index) + 'to '
        msg = prefix + 'mapa: ' + g_lastPlayedMaps[index - 1]
        sendRhooksAdminWarnEventWrapper(p, msg, force_topleft=True, history=False)

    return True


def commandInit(args, p):
    import realityconfig_admin as rasreload
    reload(rasreload)
    ras.adm_adminHashes = rasreload.adm_adminHashes
    ras.adm_liteAdminHashes = rasreload.adm_liteAdminHashes
    ras.adm_adminPowerLevels.update(rasreload.adm_adminPowerLevels)
    if not realityserver.isInternetServer():
        ras.log_chat = False
        ras.log_teamkills = False
        ras.log_kills = False
        ras.log_admins = False
        ras.log_connects = False
        ras.log_bans = False
        ras.log_tickets = False
        ras.log_coincident_IPs = False
    g_admins.clear()
    g_lite_admins.clear()
    for player in bf2.playerManager.getPlayers():
        _hash = realityserver.getPlayerHash(player)
        if _hash in ras.adm_adminHashes:
            g_admins[player] = ras.adm_adminHashes[_hash]
        elif _hash in ras.adm_liteAdminHashes:
            g_lite_admins[player] = ras.adm_liteAdminHashes[_hash]

    sendToPrism('reload', [None])
    adminPM('Adminhashes y powerlevels han sido recargados', p)
    logAdmin('!init', p.getName(), '', '')
    return True


def commandKick(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica  un jugador para kickear y el motivo.', p)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        if len(foundPlayers) == 0:
            return False
        reason = ' '.join(args[1:])
        reason = findReason(reason)
        for player in foundPlayers:
            if p == player:
                adminPM('No puedes kickearte a ti mismo!', p)
                continue
            adminPM('%s ha sido kickeado, %s' % (player.getName(), reason), p)
            kickPlayer(player, reason, True, p)
            logAdmin('!kick', p.getName(), player.getName(), reason)

        return True


def commandKill(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica un jugador para matar y el motivo.', p)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        if len(foundPlayers) == 0:
            return False
        reason = ' '.join(args[1:])
        reason = findReason(reason)
        for player in foundPlayers:
            globalMessage('%s ha sido asesinado, %s - %s' % (player.getName(), reason, p.getName()))
            rcore.killPlayer(player, False)
            sendRhooksAdminWarnEventWrapper(player, 'Te ha asesinado un administrador.' + p.getName() + ': \r\n' + reason, longDisplay=True)
            g_banSystem.log_action(player, p, 'kill', reason)
            logAdmin('!kill', p.getName(), player.getName(), reason)

        return True


def commandMapVote(args, p):
    pHash = realityserver.getPlayerHash(p)
    if pHash in ras.adm_adminHashes or p.isRcon():
        if g_voteRunning:
            if len(args) == 1 and args[0] == 'cancel':
                endVote(True, p.getName())
                globalMessage('La votacion ha sido cancelada. - %s' % p.getName())
                return True
            if len(args) == 0:
                if g_vote_res_msg != '':
                    sendRhooksAdminWarnEventWrapper(p, 'Ultima votacion: ' + g_vote_res_msg + ' %s minutos, en %s' % ((int(time.time()) - g_vote_res_time) / 60, g_vote_performed_on), history=False)
                    return True
                else:
                    sendRhooksAdminWarnEventWrapper(p, "Aun no ha habido una votacion en esta ronda! Escribe '!mvote cancel' para cancelar la votacion actual.", history=False)
                    return False
            else:
                sendRhooksAdminWarnEventWrapper(p, "Votacion en progreso, escribe '!mvote cancel' para cancelarla", history=False)
                return False
        elif len(args) == 0:
            if g_vote_res_msg != '':
                sendRhooksAdminWarnEventWrapper(p, 'Ultima votacion: ' + g_vote_res_msg + ' %s minutos, en %s' % ((int(time.time()) - g_vote_res_time) / 60, g_vote_performed_on), history=False)
                return True
            else:
                sendRhooksAdminWarnEventWrapper(p, 'Aun no ha habido una votacion en esta ronda! Por favor agrega 2 a 4 argumentos para votar!', history=False)
                return False
        else:
            if len(args) < 2 or len(args) > 4:
                sendRhooksAdminWarnEventWrapper(p, 'Por favor agrega 2 a 4 argumentos para votar!', history=False)
                return False
            initializeVote(args, p)
            return True
    else:
        if g_vote_res_msg != '':
            sendRhooksAdminWarnEventWrapper(p, 'Ultima votacion: ' + g_vote_res_msg + ' %s minutos, en %s' % ((int(time.time()) - g_vote_res_time) / 60, g_vote_performed_on), history=False)
            return True
        else:
            sendRhooksAdminWarnEventWrapper(p, 'Aun no ha habido una votacion en esta ronda!', history=False)
            return False


def commandMessage(args, p):
    if len(args) < 2:
        sendRhooksAdminWarnEventWrapper(p, 'Por favor especifica un jugador y el mensaje', history=False)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        if len(foundPlayers) == 0:
            sendRhooksAdminWarnEventWrapper(p, 'Jugador no encontrado', history=False)
            return False
        reason = ' '.join(args[1:])
        reason = findReason(reason)
        for player in foundPlayers:
            sendRhooksAdminWarnEventWrapper(player, 'Tienes un mensaje de ' + p.getName() + ':\r\n' + reason, longDisplay=True)
            sendRhooksAdminWarnEventWrapper(p, 'Mensaje enviado a ' + player.getName(), history=False)
            reason += ' - ' + p.getName()
            logAdmin('!message', p.getName(), player.getName(), reason)

        return True


def commandReload(args, p):
    currentMapID = host.rcon_invoke('admin.currentLevel').strip()
    host.rcon_invoke('admin.nextLevel %s' % str(currentMapID))
    globalMessage('Reloading map. - %s' % p.getName())
    host.rcon_invoke('admin.runNextLevel')
    logAdmin('!reload', p.getName(), '', '')
    return True


def sendPythonAdminNewReportDelayed(player):
    rmemory.sendHudVarWriteEventBool(player, 'PythonAdminNewReport', 0)


def commandReport(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica un mensaje para enviar a los administradores.', p)
        return False
    else:
        reason = ' '.join(args[0:])
        adminPM(reason, p, None, True)
        logAdmin('!report', p.getName(), '', reason)
        sendRhooksAdminWarnEventWrapper(p, 'Tu reporte ha sido enviado a todos los administradores disponibles.', history=False)
        if len(g_admins) > 0:
            for admin in g_admins:
                rmemory.sendHudVarWriteEventBool(admin, 'PythonAdminNewReport', 1)
                rtimer.fireOnce(sendPythonAdminNewReportDelayed, 2, admin)

        else:
            for admin in g_lite_admins:
                rmemory.sendHudVarWriteEventBool(admin, 'PythonAdminNewReport', 1)
                rtimer.fireOnce(sendPythonAdminNewReportDelayed, 2, admin)

        return True


def commandReportPlayer(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica un nombre para reportar y el motivo.', p)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        playername = None
        if len(foundPlayers) == 1:
            player = foundPlayers[0]
            playername = player.getName()
            playerNameAndTeam = '%s (%s, %s)' % (playername, rcore.getTeamName(player.getTeam()), player.getSquadId())
            reason = ' '.join(args[1:])
            adminPM('%s is reported, %s' % (playerNameAndTeam, reason), p, playername, True)
            logAdmin('!reportp', p.getName(), player.getName(), reason)
        else:
            reason = ' '.join(args[0:])
            adminPM(reason, p, None, True)
            logAdmin('!reportp', p.getName(), '', reason)
        if not playername:
            sendRhooksAdminWarnEventWrapper(p, "Tu reporte ha sido enviado a todos los administradores disponibles. Pero no se ha encontrado al jugador reportado", history=False)
        else:
            sendRhooksAdminWarnEventWrapper(p, 'Tu reporte sobre el jugador %s ha sido enviado a todos los administradores disponibles.' % playername, history=False)
        if len(g_admins) > 0:
            for admin in g_admins:
                rmemory.sendHudVarWriteEventBool(admin, 'PythonAdminNewReport', 1)
                rtimer.fireOnce(sendPythonAdminNewReportDelayed, 2, admin)

        else:
            for admin in g_lite_admins:
                rmemory.sendHudVarWriteEventBool(admin, 'PythonAdminNewReport', 1)
                rtimer.fireOnce(sendPythonAdminNewReportDelayed, 2, admin)

        return True


def commandResign(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica un jugador para resignar y la razon.', p)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        if len(foundPlayers) == 0:
            return False
        reason = ' '.join(args[1:])
        reason = findReason(reason)
        for player in foundPlayers:
            globalMessage('Resignando al jugador %s, %s - %s' % (player.getName(), reason, p.getName()))
            resignPlayer(player)
            sendRhooksAdminWarnEventWrapper(player, 'Has sido resignado del squad por el administrador ' + p.getName() + ': \r\n' + reason, longDisplay=True)
            logAdmin('!resign', p.getName(), player.getName(), reason)

        return True


def commandResignall(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica una razon.', p)
        return False
    elif len(args) == 2 and args[0] not in ('us', 'them'):
        personalMessage('Por favor especifica un equipo [us|them] y una razon.', p)
        return False
    else:
        team = None
        if args[0] in ('us', 'them'):
            if args[0] == 'us':
                team = p.getTeam()
            elif args[0] == 'them':
                team = rcore.getOtherTeam(p.getTeam())
            reason = ' '.join(args[1:])
        else:
            reason = ' '.join(args[0:])
        reason = findReason(reason)
        players = list(rcore.getPlayers())
        globalMessage('Resignando a todos, %s - %s' % (reason, p.getName()))
        if team == 1 or team == 2:
            for player in players:
                if player.getTeam() == team:
                    resignPlayer(player)
                    sendRhooksAdminWarnEventWrapper(player, 'Todos en el equipo han sido resignados por el administrador ' + p.getName() + ': \r\n' + reason, history=False)

            logAdmin('!resignall', p.getName(), '', args[0] + ' ' + reason)
        else:
            for player in players:
                resignPlayer(player)
                sendRhooksAdminWarnEventWrapper(player, 'Todos han sido resignados por el administrador ' + p.getName() + ': \r\n' + reason, history=False)

            logAdmin('!resignall', p.getName(), '', reason)
        adminPM('Todos los jugadores han sido resignados, %s' % reason, p)
        return True


def commandRules(args, p):
    if ras.adm_rulesEnabled:
        for r in ras.adm_rules:
            personalMessage(r, p)

        return True
    return False


def commandRunNext(args, p):
    globalMessage('Cambiando al siguiente mapa - %s' % p.getName())
    host.rcon_invoke('admin.runNextLevel')
    logAdmin('!runnext', p.getName(), '', '')
    return True


def commandSay(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica un mensaje.', p)
        return False
    else:
        message = ' '.join(args)
        message = findReason(message)
        message += ' - ' + p.getName()
        globalMessage(message, True, False)
        logAdmin('!say', p.getName(), '', message)
        return True


def commandSayTeam(args, p):
    if len(args) < 2 or args[0].lower() not in ('us', 'them', '1', '2'):
        personalMessage('Por favor especifica un equipo [us/them/1/2] y un mensaje.', p)
        return False
    else:
        if args[0].lower() in ('1', '2'):
            team = int(args[0])
        elif args[0].lower() == 'us':
            team = p.getTeam()
        else:
            team = rcore.getOtherTeam(p.getTeam())
        message = ' '.join(args[1:])
        message = findReason(message)
        message += ' - ' + p.getName()
        teamMessage(team, message, True, False)
        logAdmin('!sayteam', p.getName(), 'team ' + str(team), message)
        return True


def commandSetNext(args, p):
    if len(args) < 1:
        personalMessage('Por favor especifica el nombre de un mapa.', p)
        return False
    args = [ x.lower() for x in args ]
    if re.match('^\\d+$', args[0]):
        try:
            mapId = int(args[0])
        except:
            return False

        if mapId in g_mapList:
            _map = g_mapList[mapId]
            setNextMap(mapId, _map[0], _map[1], _map[2], p)
            return True
        else:
            personalMessage('No se encontro el mapa con el ID: %s' % mapId, p)
            return False
    else:
        if len(args) < 3:
            personalMessage('Por favor especifica un mapa, gamemode y layer.', p)
            return False
        mapName = args[0]
        gamemode = args[1]
        layer = args[2].title()
        for mapId, _map in g_mapList.items():
            if _map[0].find(mapName) == -1:
                continue
            if _map[1].find(gamemode) == -1:
                continue
            if _map[2] != layer:
                continue
            setNextMap(mapId, _map[0], _map[1], _map[2], p)
            return True

        for _map in MAPLISTALL:
            if _map[0].find(mapName) == -1:
                continue
            if _map[1].find(gamemode) == -1:
                continue
            if _map[2] != layer:
                continue
            mapId = addToMapList(_map[0], _map[1], _map[2], p)
            if mapId != -1:
                setNextMap(mapId, _map[0], _map[1], _map[2], p)
                return True
            return False

        for _map in ras.adm_mapListCustom:
            _map = _map.split('|')
            if _map[0].find(mapName) == -1:
                continue
            if _map[1].find(gamemode) == -1:
                continue
            if _map[2] != layer:
                continue
            mapId = addToMapList(_map[0], _map[1], _map[2], p)
            if mapId != -1:
                setNextMap(mapId, _map[0], _map[1], _map[2], p)
                return True
            return False

        personalMessage('No se encontro el mapa con los argumentos: %s %s %s' % (args[0], args[1], args[2]), p)
        return False


def commandShowNext(args, p):
    nextMapID = int(host.rcon_invoke('admin.nextLevel').strip())
    if nextMapID in g_mapList:
        _map = g_mapList[nextMapID]
        mapName = rcore.getMapName(_map[0], True)
        gamemode = rcore.getGameModeName(_map[1])
        layer = _map[2].title()
        if (canExecute('setnext', p) or p.isRcon()) and g_last_setnext:
            sendRhooksAdminWarnEventWrapper(p, 'El siguiente mapa es: %s (%s, %s), seteado por: %s' % (mapName,
             gamemode,
             layer,
             g_last_setnext))
        else:
            sendRhooksAdminWarnEventWrapper(p, 'El siguiente mapa en la rotacion es: %s (%s, %s)' % (mapName, gamemode, layer))
        return True
    return False


def commandStopServer(args, p):
    if len(args) == 0:
        personalMessage('Por favor especifica una razon para apagar el server.', p)
        return False
    reason = ' '.join(args[0:])
    reason = findReason(reason)
    logAdmin('!stopserver', p.getName(), '', reason)
    globalMessage('SE APAGARA EL SERVIDOR - POR FAVOR RECONECTE - %s' % p.getName())
    players = list(rcore.getPlayers())
    for player in players:
        sendRhooksAdminWarnEventWrapper(player, 'SE APAGARA EL SERVIDOR - POR FAVOR RECONECTE - %s')

    host.rcon_invoke('quit')
    return True


def commandScramble(args, p):
    global g_scramble_next
    if len(args) > 1 or len(args) == 1 and args[0] not in ('cancel',):
        personalMessage("El modo de uso es '!scramble [cancel], utilizando cancel anula el !scramble.", p)
        return False
    else:
        if len(args) == 0:
            if not g_scramble_next:
                g_scramble_next = True
                adminPM('Los equipos se mezclaran en la siguiente ronda.', p)
                logAdmin('!scramble', p.getName(), None, 'Next')
                return True
            else:
                personalMessage("La mezcla de equipos ya fue programada. Usa '!scramble cancel' para cancelar.", p)
                return False
        elif args[0] == 'cancel':
            if g_scramble_next:
                g_scramble_next = False
                adminPM('La mezcla de equipos en la siguiente ronda ha sido cancelada.', p)
                logAdmin('!scramble', p.getName(), None, 'Cancel')
                return True
            else:
                personalMessage('No existe mezcla de equipos para cancelar.', p)
                return False
        return


def commandSwapTeam(args, p):
    global g_swap_teams_next
    if len(args) > 1 or len(args) == 1 and args[0] not in ('next', 'cancel'):
        personalMessage("El modo de uso es '!swapteams [next|cancel]', o no incluyas argumentos.", p)
        return False
    else:
        if len(args) == 1:
            if args[0] == 'next':
                if not g_swap_teams_next:
                    g_swap_teams_next = True
                    adminPM('Los equipos seran intercambiados en la siguiente ronda.', p)
                    logAdmin('!swapteams', p.getName(), None, 'Next Round')
                    return True
                else:
                    personalMessage("El intercambio de equipos ya ha sido seteado para la siguiente ronda. Usa '!swapteams cancel' para cancelar.", p)
                    return False
            elif args[0] == 'cancel':
                if g_swap_teams_next:
                    g_swap_teams_next = False
                    adminPM('El intercambio de equipos para la siguiente ronda ha sido cancelado.', p)
                    logAdmin('!swapteams', p.getName(), None, 'Cancel')
                    return True
                else:
                    personalMessage('No existe intercambio de equipos para cancelar.', p)
                    return False
        else:
            if not bf2.GameStatus.Loaded and not bf2.GameStatus.Playing:
                if not g_swap_teams_next:
                    g_swap_teams_next = True
                    adminPM('Los equipos seran intercambiados en la siguiente ronda.', p)
                    logAdmin('!swapteams', p.getName(), None, 'Next Round')
                    return True
                else:
                    personalMessage("El intercambio de equipos ya ha sido seteado para la siguiente ronda. Usa '!swapteams cancel' para cancelar.", p)
                    return False
            if rcore.roundStarted():
                personalMessage('Solo se puede intercambiar a los equipos durante el tiempo de despliegue.', p)
                return False
            globalMessage('Intercambiando a todos - %s' % p.getName())
            logAdmin('!swapteams', p.getName(), None, 'Now')
            swapTeams()
            return True
        return


def onPlayerChangeTeamsUnmarkTeamswitch(player, humanHasSpawned):
    """
    remove teamswitch mark when a player changes team # TODO does this break on resign? not important
    """
    if player.teamswitch:
        rdebug.debugMessage('Removing teamswitch mark from %s' % player.getName())
    player.teamswitch = False


def commandSwitch(args, admin):
    pHash = realityserver.getPlayerHash(admin)
    if pHash in ras.adm_adminHashes or admin.isRcon(): 
        if len(args) < 1 or len(args) > 2 or len(args) == 2 and args[1].lower() not in ('now', 'next', 'cancel'):
            personalMessage('Por favor especifica un jugador para switchear, y opcionalmente [now|next|cancel]', admin)
            return
        switch_type = 'now'
        if len(args) == 2:
            switch_type = args[1].lower()
        foundPlayers = findPlayer(args[0], admin)
        if not foundPlayers:
            return False
        for player in foundPlayers:
            if switch_type == 'cancel':
                logAdmin('!switch', admin.getName(), player.getName(), 'cancel')
                if not hasattr(player, 'teamswitch') or not player.teamswitch:
                    globalMessage('El jugador %s no ha sido marcado para cambiar de equipo (en la siguiente muerte) - %s' % (player.getName(), admin.getName()))
                else:
                    player.teamswitch = False
                    globalMessage('El jugador %s no sera cambiado de equipo (luego de morir) - %s' % (player.getName(), admin.getName()))
                    sendRhooksAdminWarnEventWrapper(player, 'Tu solicitud para cambiar de equipo luego de morir, ha sido cancelada por el administrador ' + admin.getName())
                try:
                    del g_switch_next[player.getProfileId()]
                    globalMessage('El jugador %s no sera cambiado de equipo (en la siguiente ronda) - %s' % (player.getName(), admin.getName()))
                    sendRhooksAdminWarnEventWrapper(player, 'Tu solicitud para cambiar de equipo en la siguiente ronda, ha sido cancelada por el administrador ' + admin.getName())
                except KeyError:
                    globalMessage('El jugador %s no ha sido marcado para cambiar de equipo (en la siguiente ronda) - %s' % (player.getName(), admin.getName()))

                return True
            if switch_type == 'now':
                if ras.smb_disableSwitchNow and not player.isAdmin:
                    notice = 'Server notice: mid-round switch requests are now disabled.' + ' Try switching on your own when team player count is closer to even,' + ' or request a switch for next round.'
                    globalMessage(notice, False, False)
                    sendRhooksAdminWarnEventWrapper(player, 'Server notice: mid-round switch requests are now disabled. Try switching on your own\r\n' + 'when team player count is closer to even, or request a switch for next round')
                    return True
                player.teamswitch = True
                if not player.isAlive():
                    logAdmin('!switch', admin.getName(), player.getName(), 'Instantly')
                    globalMessage('Cambiando de equipo al jugador %s - %s' % (player.getName(), admin.getName()))
                    sendRhooksAdminWarnEventWrapper(player, 'Has sido cambiado de equipo por el administrador ' + admin.getName())
                    teamSwitchPlayer(player)
                    return True
                if rcore.isInsideVehicle(player):
                    globalMessage('El jugador %s esta dentro de un vehiculo, por lo que ha sido marcado para cambiar de equipo cuando muera - %s' % (player.getName(), admin.getName()))
                    sendRhooksAdminWarnEventWrapper(player, 'Has sido marcado para cambiar de equipo cuando mueras ' + admin.getName())
                    logAdmin('!switch', admin.getName(), player.getName(), 'On next death')
                    return True
                rcore.killPlayer(player, False)
                logAdmin('!switch', admin.getName(), player.getName(), 'Instantly')
            elif switch_type == 'next':
                if ras.smb_swapTeamsOnStart:
                    g_switch_next[player.getProfileId()] = rcore.getOtherTeam(player.getTeam())
                else:
                    g_switch_next[player.getProfileId()] = player.getTeam()
                globalMessage('El jugador %s ha sido marcado para cambiar de equipo en la siguiente ronda. - %s' % (player.getName(), admin.getName()))
                sendRhooksAdminWarnEventWrapper(player, 'Has sido marcado para cambiar de equipo en la siguiente ronda, por el administrador ' + admin.getName())
    else:
        if len(args) == 0:
            if rcore.roundStarted() == True:            
                sendRhooksAdminWarnEventWrapper(admin, 'Tu solicitud de SWITCH fue enviada a los administradores.')
                adminPM ('El jugador ' + admin.getName() + ' ha solicitado SWITCH.')
            else:
                logAdmin('!switch', admin.getName(), admin.getName(), 'Instantly')
                globalMessage(admin.getName() + ' cambio de equipo por su cuenta.')
                teamSwitchPlayer(admin)
    return True


def commandTempBan(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica un jugador para banear temporalmente y el motivo.', p)
        return False
    else:
        try:
            timeToBan = int(ras.adm_banTime) * 60
        except:
            timeToBan = 'round'

        return banPlayer('!tempban', args[0], p, timeToBan, args[1:])


def commandTickets(args, p):
    tickets = [str(bf2.gameLogic.getTickets(1)), str(bf2.gameLogic.getTickets(2))]
    name1 = rcore.g_mapTeams[1]
    name2 = rcore.g_mapTeams[2]
    line1 = name1 + ' : ' + tickets[0]
    line2 = name2 + ' : ' + tickets[1]
    personalMessage(line1, p)
    personalMessage(line2, p)
    globalMessage('%s uso el comando !tickets.' % p.getName())
    logAdmin('!tickets', p.getName(), '', '')
    return True


class TimeBanEpochException(Exception):
    """
    Please specify a time in the future
    """
    pass


class TimeBanSyntaxException(Exception):
    """
    Please specify a player to ban, length and a reason
    """
    pass


def getTimeToBan(timeToBan):
    if timeToBan == 'round':
        return timeToBan
    elif timeToBan[0] == ':':
        epoch = int(timeToBan[1:])
        if epoch - int(time.time()) <= 0:
            raise TimeBanEpochException
        return int(epoch - time.time())
    else:
        try:
            rematches = re.match('^([\\d\\.]+)([smMhdwy])$', timeToBan)
            if rematches:
                number = rematches.group(1)
                timemultiplier = {'s': 1,
                 'm': 60,
                 'h': 3600,
                 'd': 86400,
                 'w': 604800,
                 'M': 2419200,
                 'y': 29030400}[rematches.group(2)]
                timeToBan = float(number) * timemultiplier
            timeToBan = int(timeToBan)
        except ValueError:
            raise TimeBanSyntaxException

        return timeToBan


def commandRoundBan(args, p):
    if len(args) != 2:
        personalMessage('Modo de uso: !roundban playername reason', p)
    return commandTimeBan((args[0], 'round', ' '.join(args[1:])), p)


def commandTimeBan(args, p):
    try:
        if len(args) < 3:
            raise TimeBanSyntaxException
        timeToBan = getTimeToBan(args[1])
    except TimeBanEpochException:
        personalMessage('Por favor especifica un tiempo en el futuro', p)
        return False
    except TimeBanSyntaxException:
        personalMessage('Modo de uso: !timeban playername <length> <reason>', p)
        personalMessage("Tiempos validos: ('round', ':epoch' o '<number><m/h/d/w/M/y>' )", p)
        return False

    return banPlayer('!timeban', args[0], p, timeToBan, args[2:])


def commandUnban(args, p):
    global g_lastBan
    if not g_lastBan:
        adminPM('No player last banned', p)
        return True
    if not args or len(args) > 2:
        personalMessage('Modo de uso: !unban playername', p)
        personalMessage('Ultimo jugador baneado %s' % g_lastBan[0], p)
        return True
    if ' '.join(args[:2]) != g_lastBan[0]:
        personalMessage('Modo de uso: !unban playername', p)
        personalMessage('Ultimo jugador baneado %s' % g_lastBan[0], p)
        return True
    if g_banSystem.remove_ban(g_lastBan[1]):
        adminPM('El jugador %s ha sido desbaneado' % g_lastBan[0], p)
        logAdmin('!unban', p.getName(), 'hash ID ' + g_lastBan[1] + ' banned player', '')
        g_lastBan = ()
    else:
        personalMessage('Fallo al intentar desbanear.', p)
    return True


def commandUnbanId(args, p):
    if len(args) != 1:
        personalMessage('Modo de uso: !unbanid 546039719a2755def5802f282d03b649', p)
        return False
    else:
        playerId = args[0].lower()
        if g_banSystem.isPlayerIdBanned(playerId):
            g_banSystem.remove_ban(playerId)
            logAdmin('!unbanid', p.getName(), 'El ID de jugador %s ha sido desbaneado' % playerId, '')
            personalMessage('El ID de jugador %s ha sido desbaneado' % playerId, p)
            return True
        personalMessage('El ID de jugador %s no se encontro en la banlist' % playerId, p)
        return False


def commandUnbanName(args, p):
    if len(args) != 1:
        personalMessage('Debes usar el nombre exacto, por ejemplo: !unbanname exampleplayer123', p)
        return False
    else:
        playerId = g_banSystem.getBannedIdByName(args[0])
        if playerId:
            g_banSystem.remove_ban(playerId)
            logAdmin('!unbanname', p.getName(), 'Player named %s has been unbanned' % args[0], '')
            personalMessage('Player named %s has been unbanned' % args[0], p)
            return True
        personalMessage('Jugador de nombre %s no se encuentra en la banlist' % args[0], p)
        return False


def commandWarn(args, p):
    if len(args) < 2:
        personalMessage('Por favor especifica un jugador para advertir y un motivo', p)
        return False
    else:
        foundPlayers = findPlayer(args[0], p)
        if len(foundPlayers) == 0:
            return False
        reason = ' '.join(args[1:])
        reason = findReason(reason)
        for player in foundPlayers:
            warnPlayer(p, player, reason)
            logAdmin('!warn', p.getName(), player.getName(), reason)

        return True


def commandPlayerInfo(args, p):
    if len(args) == 1 or len(args) == 2 and args[1] == 'last':
        for player in findPlayer(args[0], p):
            s = '%s:' % player.getName()
            if not rplayerdata.isPlayerVerified(player):
                s += 'ADVERTENCIA - HASH Y NOMBRE NO VERIFICADO'
                countstr = 'Baneos y advertencias totales: NO DISPONIBLE'
            else:
                s += ' Nivel: %s' % rplayerdata.getPlayerTrustLevel(player)
                s += ' Creada: %s' % rplayerdata.getPlayerAccountCreationDate(player)
                if rplayerdata.getPlayerProfileIsLegacy(player):
                    s += ' (legacy)'
                if rplayerdata.isPlayerWhitelisted(player):
                    s += ' (WHITELISTED)'
                if rplayerdata.isVacBanned(player):
                    s += ' (VAC BANNED)'
                logcounts = g_banSystem.getLogStatsById(realityserver.getPlayerHash(player))
                if len(logcounts) == 4 and None not in logcounts:
                    countstr = 'Baneos y advertencias totales: perma: %d temps: %d kicks: %d advert: %d' % tuple(logcounts)
                else:
                    countstr = 'Baneos y advertencias totales: NO DISPONIBLE'
            personalMessage(s, p)
            s = '----->%s, %s' % (player.getAddress(), realityserver.getPlayerHash(player))
            personalMessage(s, p)
            personalMessage(countstr, p)
            if len(args) == 2:
                reasons = g_banSystem.getLastActionsById(realityserver.getPlayerHash(player))
                for r in reasons:
                    personalMessage(r, p)

    else:
        personalMessage('!info player o !info player last', p)
    return True


def commandEntranceControl(args, player):
    if rplayerdata.gPlayerDataManager is None:
        personalMessage('Entrance control not enabled', player)
        return False
    else:

        def printUsage(p):
            personalMessage('!ec recent: print recently denied joins', p)
            personalMessage('!ec whitelist <INDEX>: Add index from recent to whitelist (permanent)', p)
            personalMessage('!ec minimum 0|1|2: Set minimum trust level', p)
            personalMessage('!ec info player: Print player info', p)
            personalMessage('current minimum level: %s' % rplayerdata.gPlayerDataManager.getMinimumToJoin(), p)

        if len(args) == 0:
            printUsage(player)
            return True
        if len(args) == 1:
            if args[0] == 'recent':
                rplayerdata.gPlayerDataManager.sendJoinDeniedListToPlayer(player)
                return True
        elif len(args) == 2:
            if args[0] == 'whitelist':
                rplayerdata.gPlayerDataManager.addIndexToWhitelist(args[1], player)
                return True
            if args[0] == 'minimum':
                rplayerdata.gPlayerDataManager.setMinimumToJoin(args[1], player)
                return True
        printUsage(player)
        return True


def commandWebsite(args, player):
    personalMessage(ras.adm_website, player)
    return True


def commandUngrief(args, player):

    def printSyntax(p):
        personalMessage('La sintaxis es:', p)
        personalMessage('!ungrief deployable list', p)
        personalMessage('!ungrief deployable rebuild <index>', p)
        personalMessage('!ungrief dodvehicle list', p)
        personalMessage('!ungrief dodvehicle destroy <index>', p)
        personalMessage('!ungrief dodvehicle teleport <index>', p)

    try:
        if len(args) >= 2 and (args[0].lower() == 'deployable' or args[0].lower() == 'dep'):
            if args[1].lower() == 'list':
                return rassets.assetRemovalHistory.list(player)
            if len(args) == 3 and args[1].lower() == 'rebuild':
                history = rassets.assetRemovalHistory.get(int(args[2]))
                if history is None:
                    return personalMessage('index %s not found' % args[2], player)
                timestamp, playerName, template, team, position, rotation = history
                if len(filter(lambda x: x.getName() == playerName, rcore.getPlayers())) != 0:
                    return personalMessage('%s aun se encuentra en el servidor. Debes kickearlo para reconstruir el asset que destruyo.' % playerName, player)
                rassets.assetRemovalHistory.rebuild(int(args[2]))
                personalMessage('rebuilt index %s' % args[2], player)
                globalMessage('Un %s ha sido recontruido por el admin %s luego de ser removido por %s' % (template, player.getName(), playerName), True)
                logAdmin('!ungrief ', player.getName(), None, 'rebuild ' + template)
                return
        if len(args) >= 2 and (args[0].lower() == 'dodvehicle' or args[0].lower() == 'dv'):
            if args[1].lower() == 'list':
                return rvehicles.vehicleDODBleed.list(player)
            if len(args) == 3 and args[1].lower() == 'destroy':
                v = rvehicles.vehicleDODBleed.destroy(player, int(args[2]))
                if v:
                    globalMessage('Un %s fuera del mapa ha sido borrado por un admin - %s' % (v.templateName, player.getName()), True)
                    logAdmin('!ungrief', player.getName(), None, 'destroy ' + v.templateName)
                return
            if len(args) == 3 and args[1].lower() == 'teleport':
                v = rvehicles.vehicleDODBleed.teleport(player, int(args[2]))
                if v:
                    globalMessage('Un %s fuera del mapa ha sido teletransportado de regreso a la main por el admin - %s' % (v.templateName, player.getName()), True)
                    logAdmin('!ungrief', player.getName(), None, 'teleport ' + v.templateName)
                return
    except:
        rdebug.errorMessage()

    printSyntax(player)
    return


class Autovote():
    LAYER_WEIGHTS = {'Std': 4,
     'Alt': 3,
     'Lrg': 2,
     'Inf': 1}

    @classmethod
    def autovote_genmaps(cls, requested_mode = None):
        maplist = []
        map_selection = []
        last_maps = []
        history = list(g_lastPlayedMaps)
        if requested_mode is None:
            requested_mode = 'aas'
        for prmap in history:
            hmode, hlayer = prmap.split(' ')[-2:]
            hname = '_'.join(prmap.split(' ')[:-2]).lower()
            if hmode.startswith('gpm_'):
                hmode = hmode[4:]
            map_tuple = (hname, 'gpm_' + rcore.modeNameToMode(hmode), hlayer)
            last_maps.append(map_tuple)

        layer = rcore.getMapLayer()
        if layer == 128:
            layer_name = 'Lrg'
        elif layer == 64:
            layer_name = 'Std'
        elif layer == 32:
            layer_name = 'Alt'
        elif layer == 16:
            layer_name = 'Inf'
        else:
            layer_name = 'Std'
        current = (rcore.getMapName(), 'gpm_' + rcore.getGameMode(), layer_name)
        last_maps.append(current)
        env_weights = {'city': 8,
         'forest': 8,
         'desert': 8,
         'island': 8,
         'winter': 8}
        size_weights = {1000: 8,
         2000: 8,
         4000: 8,
         8000: 1}
        for last in last_maps:
            tags = rmaplist.MAPLISTALL[last]
            for tag in tags['environment']:
                env_weights[tag] -= 1

            size_weights[tags['size']] -= 1

        player_cnt = bf2.playerManager.getNumberOfPlayers()
        for each in rmaplist.MAPLISTALL:
            weight = 0
            tags = rmaplist.MAPLISTALL[each]
            weight += env_weights[tags['environment'][0]]
            weight += size_weights[tags['size']]
            if each[1][4:] != requested_mode:
                continue
            if each[0] in maplist:
                continue
            if each[0] in [ last[0] for last in last_maps ]:
                continue
            if player_cnt < 64 and tags['size'] > 2048:
                continue
            if weight < 0:
                continue
            maplist.extend([each[0]] * weight)

        for n in xrange(3):
            choice = random.choice(maplist)
            while choice in map_selection:
                choice = random.choice(maplist)

            map_selection.append(choice)

        return map_selection

    @classmethod
    def commandAutoVote(cls, args, p):
        valid_modes = ['cq',
         'insurgency',
         'cnc',
         'coop',
         'vehicles',
         'gungame']
        if len(args) != 1 or args[0] not in valid_modes:
            personalMessage('!autovote %s' % str(valid_modes), p)
            return False
        initializeVote(cls.autovote_genmaps(args[0]), p)
        for each in [ cls.autovote_genmaps(args[0]) for m in xrange(10) ]:
            rdebug.debugMessage(str(each))

        return True


def onPlayerDeclaredActive(player, cmd, args):
    player.afk_lastActionTime = int(time.time())
    sendRhooksAdminWarnEventWrapper(player, 'Kickeo cancelado!\nHas sido reconocido como un jugador activo.', longDisplay=True, history=False)


class AFKDetection():

    @classmethod
    def init(cls):
        host.registerHandler('PlayerConnect', cls._onPlayerConnect, 1)
        host.registerHandler('PlayerSpawn', cls._onPlayerSpawn, 1)
        host.registerHandler('PlayerChangedSquad', cls._onPlayerChangedSquad, 1)
        host.registerGameStatusHandler(cls._onGameStatusChanged)
        rtimer.repeatingTask(cls._refresh, 15.0)

    @classmethod
    def _onPlayerChangedSquad(cls, player, oldsquad, newsquad):
        player.afk_isConnecting = False
        player.afk_lastActionTime = int(time.time())

    @classmethod
    def _onGameStatusChanged(cls, status):
        for player in bf2.playerManager.getPlayers():
            player.afk_isConnecting = True

    @classmethod
    def _onPlayerConnect(cls, player):
        player.afk_isConnecting = True
        player.afk_lastActionTime = int(time.time())
        player._afk_lastYaw = 0

    @classmethod
    def _onPlayerSpawn(cls, player, soldier):
        player.afk_isConnecting = False
        player.afk_lastActionTime = int(time.time())

    @classmethod
    def _playerPing(cls, player):
        if player.getPing() != 0:
            player.afk_isConnecting = False

    @classmethod
    def _refresh(cls, args = None):
        for player in bf2.playerManager.getPlayers():
            cls._refreshPlayer(player)
            if player.afk_isConnecting:
                cls._playerPing(player)

    @classmethod
    def _refreshPlayer(cls, player):
        if player.isManDown() or not player.isAlive():
            return
        else:
            camera = rcore.getVehicleCamera(player.getVehicle())
            yaw = 0
            if camera is not None and camera.isValid():
                yaw = rcore.getCameraYaw(camera)
            if yaw != player._afk_lastYaw:
                player.afk_lastActionTime = int(time.time())
                player._afk_lastYaw = yaw
            return

    @classmethod
    def isConnecting(cls, player):
        """
        Returns if the player has spawned yet this round
        :param player:
        :return:
        """
        return player.afk_isConnecting

    @classmethod
    def estimateAFKNess(cls, player):
        """
        Estimates how long ago did the player last rotated his view
        ~~Dead players are considered not AFK~~
        :param player:
        :return:
        """
        cls._refreshPlayer(player)
        if not hasattr(player, 'afk_lastActionTime'):
            return 0
        return int(time.time() - player.afk_lastActionTime)


def commandShowAfk(args, admin):
    """
    Shows the top 5 idle players, sorted first by idle time
    """
    if rmemory.isWindowsListenServer:
        return
    sorted_list = filter(lambda p: not p.isAIPlayer(), bf2.playerManager.getPlayers())
    sorted_list = sorted(sorted_list, key=lambda p: p.afk_lastActionTime, reverse=True)
    i = 0
    for player in sorted_list:
        if i > 5:
            break
        if AFKDetection.isConnecting(player):
            continue
        idle_time = int(AFKDetection.estimateAFKNess(player) / 60)
        if idle_time < 6:
            continue
        i += 1
        if player.getSquadId() == 0:
            nosquad = 'Yes'
        else:
            nosquad = 'No'
        msg = 'El jugador %s ha estado AFK por %s minutos. No asignado: %s' % (player.getName(), idle_time, nosquad)
        personalMessage(msg, admin)

    if i == 0:
        personalMessage('No hay jugadores AFK', admin)
    return True


def checkSuicideAndLeaveSquad(p):
    if p.getSquadId() == 0 and p.suicided and p.changedSquad is not None and rcore.now() - p.changedSquad < 60:
        adminPM('El jugador %s se suicido y abandono la escuadra' % p.getName(), history=False)
    return


def commandResetsquads(args, p):
    if rmemory.isWindowsListenServer:
        return
    if realityserver.isCoopServer():
        return
    globalMessage('Reiniciando escuadras...', big=True)
    import _realitymemory as _rmemory
    swapTeams()
    swapTeams()
    _rmemory.resetSquads()
    globalMessage('Escuadras reiniciadas.', big=True)


LOCKEDCOMMANDS = {'admins', 'fps'}

def addCommand(name, handler, permissions, allowOverride = False):
    if name in LOCKEDCOMMANDS:
        rdebug.debugMessage('Cannot override %s' % name)
    if name in g_adminCommands and not allowOverride:
        rdebug.debugMessage('%s command already exists' % name, 'admin')
        return False
    g_adminCommands[name] = handler
    ras.adm_adminPowerLevels[name] = permissions
    rdebug.debugMessage('Command %s mapped to %s, permissions: %s' % (name, str(handler), permissions), 'admin')
    return True


class DummyAdminUser(object):
    adminName = ''
    index = -1

    def __init__(self, adminName):
        self.adminName = adminName

    def getName(self):
        return self.adminName

    def isValid(self):
        return True

    def isRcon(self):
        return True

    def isAIPlayer(self):
        return False

    def getTeam(self):
        return 2

    def getSquadId(self):
        return 0


class IPTester():
    _IPEntries = {}

    @classmethod
    def getPlayersWithSameIPAsPlayer(cls, Player):
        if Player.isAIPlayer():
            return [Player]
        IP = Player.getAddress()
        return cls._IPEntries[IP].players

    @classmethod
    def getAllConflicts(cls):
        ret = []
        for entry in cls._IPEntries:
            if entry.hasMultiple():
                ret.append(entry.players)

    @classmethod
    def getAllConflictsDifferentTeams(cls):
        ret = []
        for entry in cls._IPEntries:
            if entry.hasMultiple():
                expectedteam = entry.players[0].getTeam()
                for p in entry.players:
                    if expectedteam != p.getTeam():
                        ret.append(entry.players)
                        break

    @classmethod
    def init(cls):
        host.registerHandler('PlayerConnect', cls._playerJoin, 1)
        host.registerHandler('PlayerDisconnect', cls._playerLeave, 1)

    @classmethod
    def _playerJoin(cls, Player):
        if Player.isAIPlayer():
            return
        IP = Player.getAddress()
        if IP not in cls._IPEntries:
            cls._IPEntries[IP] = cls._IPEntry(IP)
        cls._IPEntries[IP].add(Player)

    @classmethod
    def _playerLeave(cls, Player):
        if Player.isAIPlayer():
            return
        IP = Player.getAddress()
        cls._IPEntries[IP].remove(Player)
        if cls._IPEntries[IP].isEmpty():
            del cls._IPEntries[IP]

    class _IPEntry:

        def __init__(self, IP):
            self.players = []
            self.IP = IP

        def add(self, Player):
            self.players.append(Player)
            if self.hasMultiple():
                if ras.adm_notifySameIP:
                    adminPM('El jugador %s tiene conflico de IP con: ' % Player.getName(), history=False)
                    for player in self.players:
                        if player != Player:
                            adminPM('%s' % player.getName(), history=False)

                if ras.log_coincident_IPs:
                    names = map(lambda p: p.getName(), self.players)
                    out = self.IP + ':' + '\t'.join(names)
                    rlogger.RealityLogger['IPlog'].logLine(out)

        def remove(self, Player):
            self.players.remove(Player)

        def isEmpty(self):
            return len(self.players) == 0

        def hasMultiple(self):
            return len(self.players) > 1


class DevReservedSlot():

    @classmethod
    def init(cls):
        try:
            data = json.loads(urllib2.urlopen('http://8a474bc0ea96657cb5f5-39162a6e09ffdab7394e3243fa2342c1.r17.cf2.rackcdn.com/reservedslots.json', timeout=1.5).read())
            for typ in ras.adm_devReservedSlots:
                for name in data.get(typ, []):
                    cls.addName(name.encode('utf-8'))

        except:
            rdebug.errorMessage()

    @classmethod
    def addName(cls, name):
        host.rcon_invoke('reservedSlots.addNick %s' % name)


class MumbleOTP():
    secret = ''

    @classmethod
    def init(cls):
        if not realityserver.isInternetServer():
            return
        if hasattr(ras, 'mum_mumbleSecret'):
            cls.secret = ras.mum_mumbleSecret
            if cls.secret != '':
                rtimer.repeatingTask(cls.refresh, 30)

    @classmethod
    def refresh(cls, data = None):
        secret = cls.secret
        minutesSinceEpoch = str(int(time.time() / 60.0))
        for player in rcore.getPlayers():
            if player.isAIPlayer():
                continue
            playerHash = realityserver.getPlayerHash(player)
            p = struct.unpack('<i', hashlib.sha1(minutesSinceEpoch + playerHash.lower() + secret).digest()[0:4])[0] & 8388607
            bf2.gameLogic.sendGameEvent(player, 10, p << 8 | 32)


class KeepTeamOnReconnect(object):
    """
    force a player on to the same team that they left on rejoin
    """

    def __init__(self):
        if realityserver.isCoopServer():
            return
        if not realityserver.isInternetServer():
            return
        host.registerHandler('PlayerConnect', self.onPlayerConnect)
        host.registerHandler('PlayerChangeTeam', self.onPlayerChangeTeam)
        self.teams = {1: set(),
         2: set()}
        host.registerGameStatusHandler(self.onGameStatusChanged)

    def onPlayerConnect(self, player):
        player_id = realityserver.getPlayerHash(player)
        if not ras.smb_forceRejoinTeamswitch:
            return
        for team in self.teams:
            if player_id in self.teams[team] and player.isValid():
                player.setTeam(team)
                return

        rtimer.fireNextTick(self.onPlayerChangeTeam, player)

    def onPlayerChangeTeam(self, player):
        if player.isValid():
            team = player.getTeam()
            otherteam = 3 - team
            player_id = realityserver.getPlayerHash(player)
            self.teams[team].add(player_id)
            self.teams[otherteam].discard(player_id)

    def onGameStatusChanged(self, status):
        if status == bf2.GameStatus.EndGame:
            self.teams[1].clear()
            self.teams[2].clear()
            for p in rcore.getPlayers():
                self.onPlayerChangeTeam(p)


def sendMsgToPRISM(msg):
    """
    send a standard user message to PRISM
    """
    sendToPrism('msg', [5, str(msg), ''])
    return True


def sendAdminMsgToPRISM(msg, target_name = ''):
    """
    send an admin message to PRISM
    """
    sendToPrism('msg', [6, str(msg), str(target_name)])
    return True


def stripColor(s):
    """
    Strip BF2 color codes out of messages
    """
    colorcodes = {u'\xc2\xa73', u'\xc2\xa7C1001'}
    for s in colorcodes:
        try:
            s = s.replace(s, '')
        except UnicodeDecodeError:
            s = s.replace(s.encode('utf-8'), '')

    return s


def addColor(s):
    colorcode = '\xc2\xa7C1001'
    return colorcode + s


alphabet = list(VALID_TAG_CHARS)
alphabet.append(' ')
alphabet.append('\r')
alphabet.append('\n')

def stripNonASCII(s):
    return ''.join([ char for char in s if char in alphabet ])


def sendRhooksAdminWarnEventWrapper(player, messageContent, display = True, history = True, longDisplay = False, force_topleft = False):
    if not hasattr(player, 'isRcon'):

        def isRcon():
            return False

        player.isRcon = isRcon
    if player.isRcon():
        sendMsgToPRISM(messageContent)
    elif len(messageContent) < 235 and not force_topleft:
        rmemory.sendRhooksAdminWarnEvent(player, stripNonASCII(messageContent), display, history, longDisplay)
    else:
        personalMessage(messageContent, player)
    return True


def commandAssignLead(args, p):
    helptxt = 'Uso: !assignlead jugador'
    if len(args) != 1:
        personalMessage(helptxt, p)
        return False
    foundPlayers = findPlayer(args[0], p)
    if not foundPlayers:
        return False
    if len(foundPlayers) > 1:
        playerlist = [ '@%i %s' % (user.index, user.getName()) for user in foundPlayers ]
        personalMessage('Multiples jugadores encontrados: %s' % str(playerlist), p)
        return False
    target = foundPlayers[0]
    squad = target.getSquadId()
    if squad == 0 or target.isCommander() or target.isSquadLeader():
        personalMessage('Jugador no disponible para hacerlo squad leader.', p)
        return False
    existing_sl = rcore.getSquadLeader(target.getTeam(), squad)
    for playerInSquad in rcore.getPlayersOfSquad(existing_sl.getTeam(), squad, existing_sl):
        if playerInSquad.index < target.index or playerInSquad.index < existing_sl.index:
            if playerInSquad.index == target.index or playerInSquad.index == existing_sl.index:
                continue
            resignPlayer(playerInSquad)
            sendRhooksAdminWarnEventWrapper(playerInSquad, 'Has sido resignado: Tu lider de escuadra le ha asignado el liderazgo a alguien mas\r\nReunete a la escuadra!', history=False)

    resignPlayer(existing_sl)
    sendRhooksAdminWarnEventWrapper(existing_sl, 'Has sido resignado:\r\nUn admin ha asignado a otro lider de escuadra.', history=False)
    sendRhooksAdminWarnEventWrapper(target, 'Has sido asignado como lider de escuadra por un administrador.', history=False)
    return True


def getAllChatStatus():
    global g_allchat_enabled
    return g_allchat_enabled


def updateAllChatStatus(count):
    global g_allchat_enabled
    if g_allchat_enabled and count >= ras.allchat_disable_threshold:
        g_allchat_enabled = False
        globalMessage('Chat global desactivado.')
        return True
    if not g_allchat_enabled and count < ras.allchat_enable_threshold:
        g_allchat_enabled = True
        globalMessage('Chat global activado.')
        return True
    return False


def onAllChatEnableRequest(player, cmd, args):
    sendAllChatStatus(player)


def broadcastAllChatStatus(data = None):
    for p in bf2.playerManager.getPlayers():
        if p.isAIPlayer():
            continue
        sendAllChatStatus(p)


def sendAllChatStatus(player):
    status = getAllChatStatus()
    if not status or ras.disable_allchat:
        rmemory.sendHudVarWriteEventBool(player, 'PythonAllChatEnabled', 0)
        return
    rmemory.sendHudVarWriteEventBool(player, 'PythonAllChatEnabled', 1)