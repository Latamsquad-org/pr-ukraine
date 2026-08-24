import ctypes
import json
import math
import random
import sys

# noinspection PyUnresolvedReferences
import _realitycore

import bf2
import cq
import game.realitycore as rcore
import game.realitydebug as rdebug
import game.realitygamemode as rgamemode
import game.realitykits as rkits
import game.realitymemory as rmemory
import game.realityserver as rserver
import game.realitytimer as rtimer
import host
from bf2.PlayerManager import Player

# noinspection PyUnreachableCode
if False:
    # This import is needed so that pychram understands the `# type:` comments when doing static analysis.
    # The typing module is not actually present in the BF2 python, so importing it at runtime would result in a crash.
    from typing import Any, Dict, Set, List, Optional, Tuple  # noinspection PyUnusedImport


# DEBUG
# rdebug.PRDEBUG = []
# rdebug.PRDEBUG_ALWAYSPRINTCONSOLE = True


def init():
    rgamemode.setCurrentGameMode(PRGunGame())


def deinit():
    rgamemode.setCurrentGameMode(None)


ITEM_EQUIP_PRIORITIES = [
    3,  # Primary
    2,  # Sidearm
    6,  # Explosives
    7,  # Explosives
    5,  # Explosives, UGL smoke
    4,  # UGL or Ammo
    1,  # Knife
]

HEAL_PER_LEVEL = 50
ARMOR_INVULNERABLE_TIME = 3.0

DEFAULT_KILLS_TO_PROMOTE = 2
DEFAULT_ASSISTS_COUNT_AS_KILL = 3
DEFAULT_TEAMKILLS_TO_DEMOTE = 1

SOUND_ID_PROMOTE = 1
SOUND_ID_DEMOTE = 2


def templateExists(templateName):
    # type: (str) -> bool
    host.rcon_invoke("ObjectTemplate.active %s" % templateName)
    return "no object template" not in host.rcon_invoke("ObjectTemplate.type").lower()


def kit_name_tempalte(team, group):
    # type: (str, str) -> str
    return "_".join(["gungame", team, group, "%s"])


def query_kit_group(template_name_template, max_length=200):
    # type: (str, int) -> (List[str])
    """
    Returns a mapping of index -> kit tempalate name, given a weapon group template
    """
    kit_names = []  # type: List[str]

    for i in xrange(max_length):
        kit_name = template_name_template % i
        if templateExists(kit_name):
            kit_names.append(kit_name)
        else:
            break
    if len(kit_names) == 0:
        rdebug.debugMessage("No kits found matching template '%s'" % template_name_template)
    return kit_names


def query_kit_items(kit_name):
    # type: (str) -> Dict[int, str]
    host.rcon_invoke("ObjectTemplate.active %s" % kit_name)
    template_list_lines = host.rcon_invoke("ObjectTemplate.listTemplates").strip().split('\n')
    item_names = [line.split()[-1] for line in template_list_lines]

    # A mapping of item_index -> item_name
    items = {}  # type: Dict[int, str]
    for item in item_names:
        host.rcon_invoke("ObjectTemplate.active %s" % item)
        try:
            item_index = int(host.rcon_invoke("ObjectTemplate.itemIndex").strip())
        except ValueError:
            continue

        items[item_index] = item
    return items


class KitInfo(object):
    def __init__(self, name, items=None, primary_item=3):
        # type: (str, Optional[Dict[int, str]], int) -> None
        self.name = name
        self.items = items if items is not None else {}  # type: Dict[int, str]
        self.primary_item = primary_item

    def __repr__(self):
        return json.dumps(self, indent=4, default=vars)

    @staticmethod
    def from_template(template_name):
        # type: (str) -> KitInfo
        items = query_kit_items(template_name)
        # find the fist existing item index in the kit, in the order specified by ITEM_EQUIP_PRIORITIES
        primary_item_index = next((item for item in ITEM_EQUIP_PRIORITIES if item in items.keys()), 1)
        return KitInfo(template_name, items, primary_item_index)


class KitGroup(object):
    def __init__(self, name):
        self.name = name  # type: str
        self.kit_names_per_team = {
            1: query_kit_group(kit_name_tempalte("red", self.name)),
            2: query_kit_group(kit_name_tempalte("blue", self.name)),
        }  # type: Dict[int, List[str]]

    def pick_kits(self):
        #  type: () -> Optional[Dict[int, KitInfo]]
        """
        Consumes a random pair of kits from the group and returns it.
        If no more kits are availalbe in the group, kits are repeated.
        """
        selected_kit_names_per_team = {}
        for team, kit_names in self.kit_names_per_team.iteritems():
            if len(kit_names) != 0:
                random.shuffle(kit_names)
                selected_kit_names_per_team[team] = kit_names.pop()
            else:
                team_str = "red" if team == 1 else "blue"
                raise ValueError("Kit group '%s' ran out of kits for %sfor" % (self.name, team_str))

        kit_info_per_team = {
            team: KitInfo.from_template(kit_name)
            for team, kit_name in selected_kit_names_per_team.iteritems()
        }
        return kit_info_per_team


class Level(object):
    def __init__(
        self,
        kit_groups,
        kills_to_promote=None,
        assists_count_as_kill=None,
        teamkills_to_demote=None,
    ):
        # type: (List[KitGroup], int, int, int) -> None
        self.kit_group_options = kit_groups[:]
        try:
            while True:
                random.shuffle(kit_groups)
                self.kit_group = kit_groups.pop()
                try:
                    self.kits_per_team = self.kit_group.pick_kits()  # type: Dict[int, KitInfo]
                except ValueError:
                    continue
                break
        except IndexError:
            rdebug.debugMessage(
                "Valid groups left for level in [%s]", ", ".join([opt.name for opt in self.kit_group_options])
            )
            self.kit_group = KitGroup("fallback")
            self.kits_per_team = self.kit_group.pick_kits()

        self.kills_to_promote = kills_to_promote or DEFAULT_KILLS_TO_PROMOTE  # type: int
        self.assists_count_as_kill = assists_count_as_kill or DEFAULT_ASSISTS_COUNT_AS_KILL  # type: int
        self.teamkills_to_demote = teamkills_to_demote or DEFAULT_TEAMKILLS_TO_DEMOTE  # type: int

    def __getitem__(self, team):
        # type: (int) -> KitInfo
        return self.kits_per_team.__getitem__(team)


class Progression(object):
    def __init__(self, levels):
        self.levels = levels  # type: List[Level]

    def __getitem__(self, level):
        # type: (int) -> Level
        """
        Returns the Level with the given index.

        Usage:
        `progression[l][t]`
        returns a KitInfo object for level `l` and team `t`.
        """
        return self.levels.__getitem__(level)

    def __len__(self):
        return len(self.levels)


def build_progression():
    # type: () -> Progression
    """
    Generates a new unique progression.
    This is a function instead of a constant, because we want to ensure
    a new progression on every map load.
    """

    # Groups defined in gungame*_kits.tweak files
    group_rif_iron = KitGroup("rif_iron")
    group_rif_scope = KitGroup("rif_scope")
    group_rif_semi = KitGroup("rif_semi")
    group_rif_old = KitGroup("rif_old_semi")
    group_rif_bolt = KitGroup("rif_old_bolt")
    group_dmr = KitGroup("dmr")
    group_sniper = KitGroup("sniper")
    group_ar_iron = KitGroup("ar_iron")
    group_ar_scope = KitGroup("ar_scope")
    group_mg_iron = KitGroup("mg_iron")
    group_mg_scope = KitGroup("mg_scope")
    group_smg = KitGroup("smg")
    group_shotgun = KitGroup("shotgun")
    group_shotgun_auto = KitGroup("shotgun_auto")
    group_pistol = KitGroup("pistol")
    group_at = KitGroup("at")
    group_gl = KitGroup("gl")
    group_grenade = KitGroup("grenade")
    group_grenade_impact = KitGroup("grenade_impact")
    # Specials
    group_m79 = KitGroup("m79")
    group_makarov = KitGroup("makarov")
    group_scorpion = KitGroup("scorpion")
    group_claymore = KitGroup("claymore")
    group_knife = KitGroup("knife")

    progression = Progression(
        [
            # level:  1, kills: 00 -> 02
            Level([group_rif_scope]),
            # level:  2, kills: 02 -> 04
            Level([group_ar_scope]),
            # level:  3, kills: 04 -> 06
            Level([group_mg_scope]),
            # level:  4, kills: 06 -> 08
            Level([group_dmr]),
            # level:  5, kills: 08 -> 10
            Level([group_rif_iron]),
            # level:  6, kills: 10 -> 12
            Level([group_ar_iron]),
            # level:  7, kills: 12 -> 14
            Level([group_mg_iron]),
            # level:  8, kills: 14 -> 16
            Level([group_rif_semi]),
            # level:  9, kills: 16 -> 18
            Level([group_smg]),
            # level: 10, kills: 18 -> 20
            Level([group_shotgun_auto]),
            # level: 11, kills: 20 -> 22
            Level([group_shotgun]),
            # level: 12, kills: 22 -> 24
            Level([group_rif_old]),
            # level: 13, kills: 24 -> 26
            Level([group_rif_bolt]),
            # level: 14, kills: 26 -> 28
            Level([group_sniper]),
            # level: 15, kills: 28 -> 30
            Level(
                [
                    group_pistol,
                    group_pistol,  # sic, double the probability
                    group_m79,
                ],
                assists_count_as_kill=1
            ),
            # level: 16, kills: 30 -> 31
            Level(
                [group_grenade_impact],
                kills_to_promote=1
            ),
            # level: 17, kills: 31 -> 32
            Level(
                [
                    group_grenade,
                    group_gl,
                    group_at,
                    group_claymore,
                ],
                kills_to_promote=1
            ),
            # level: 18, kills: 32 -> 33
            Level(
                [
                    group_makarov,
                    group_scorpion,
                ],
                kills_to_promote=1,
            ),
            # level: 19, kills: 33 -> 34
            Level(
                [group_knife],
                kills_to_promote=1,
                assists_count_as_kill=999,
            ),
        ]
    )

    return progression


# Kit utilities


def delete_kit(kit):
    if (
        kit is None
        or not kit.isValid()
        or kit.getParent() is not None
    ):
        return
    rcore.deleteObject(kit)


# Kill utilities


def is_bleedout_kill(weapon):
    # type: (Optional[Any]) -> bool
    return weapon is None


def is_teamkill(victim, attacker, weapon):
    # type: (Player, Optional[Player], Optional[Any]) -> bool
    victim = ensure_valid(victim)
    attacker = ensure_valid(attacker)
    return (
        attacker is not None
        and victim.getTeam() == attacker.getTeam()
        and not is_bleedout_kill(weapon)
    )


def is_suicide(victim, attacker):
    victim = ensure_valid(victim)
    attacker = ensure_valid(attacker)
    return attacker is None or victim == attacker


def assisting_players(assists):
    # type: (Tuple[Tuple[Player, int]]) -> Set[Player]
    return {assist_info[0] for assist_info in assists}


# Player utilities


def force_give_up(victim):
    # type: (Player) -> None
    if victim is not None and victim.isValid():
        rcore.onPlayerGiveUp(victim, "", [])


def ensure_valid(player):
    # type: (Optional[Player]) -> Optional[Player]
    return player if player is not None and player.isValid() else None


def heal_player(player, amount):
    if player.isAlive() and not player.isManDown():
        soldier = player.getDefaultVehicle()
        soldier.setDamage(soldier.getDamage() + amount)


def refresh_stamina(_args=None):
    for player in bf2.playerManager.getPlayers():
        sol = player.getDefaultVehicle()
        if sol:
            rmemory.setSoldierStaminaRecovery(sol, 0.1)


def switch_weapon(data):
    # type: (Tuple[Player, int]) -> None
    player, weapon_idx = data
    if not player.isValid():
        return
    # Using clickPlayerSelectWeaponButton or sendPlayerButtonClickEvent without time=0.1 is inconsistent
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_WEAPONSELECT1 + weapon_idx - 1, time=0.1)


def player_level(player):
    # type: (GunGamePlayerState) -> int
    return player.level


def format_name(name):
    # type: (str) -> str
    return "\xc2\xa7C1001" + name.strip() + "\xc2\xa7C1001"


def format_names(names):
    # type: (List[str]) -> str
    return (
        "\xc2\xa7C1001" +
        ", ".join(names[:-1]) +
        "\xc2\xa7C1001" +
        " y "
        "\xc2\xa7C1001" +
        names[-1] +
        "\xc2\xa7C1001"
    )


def lead_message(players, remaining_levels=None):
    # type: (Set[str], Optional[int]) -> str
    if len(players) == 0:
        return ""

    if remaining_levels and remaining_levels <= 3:
        plural = "es" if remaining_levels != 1 else ""
        plural2 = "s" if remaining_levels != 1 else ""
        level_str = " (%d nivel%s restante%s.)" % (remaining_levels, plural, plural2)
    else:
        level_str = ""

    if len(players) == 1:
        names_str = ("%s lidera la partida!" % format_name(next(iter(players)))) + level_str
    else:
        player_names_ordered = list(sorted(iter(players)))
        names_str = format_names(player_names_ordered) + " pelean por el liderazgo!"
    return names_str + level_str


class GunGamePlayerState(object):
    def __init__(self):
        self.level = 0
        self.kills_pending = 0
        self.assists_pending = 0
        self.teamkills_pending = 0


class PRGunGame(cq.PRAAS):
    def __init__(self):
        # Per player Gungame game state
        self.player_states = {}  # type: Dict[Player, GunGamePlayerState]
        self.old_player_states = {}  # type: Dict[str, GunGamePlayerState]
        self.players_requiring_update = set()  # type: Set[Player]

        # General gungame state
        self.progression = None  # type: Optional[Progression]
        self.is_game_over = False
        self.max_level = 0  # type: int
        self.top_level = 0  # type: int
        self.top_player_names = set()  # type: Set[str]

        self.smart_spawn = SmartSpawn()

        # Timers
        self.refresh_stamina_timer = None
        self.state_update_timer = None

        if not rmemory.isWindowsListenServer:
            if "linux" in sys.platform:
                self.invurnabilityTime = ctypes.POINTER(ctypes.c_float).from_address(0x108FD00)
            else:
                self.invurnabilityTime = ctypes.POINTER(ctypes.c_float).from_address(0x00892D00)

            self.defaultInvurnabilityTime = self.invurnabilityTime.contents.value
        else:
            rdebug.debugMessage("Gungame in listen server: Not supported")

        cq.PRAAS.__init__(self)

    def get_level_for_player(self, player):
        # type: (Player) -> Level
        return self.progression[self.player_states[player].level]

    def get_kit_for_player(self, player):
        level = self.get_level_for_player(player)

        try:
            return level[player.getTeam()]
        except KeyError:
            return KitInfo("global_unarmed")

    def enforce_kit(self, player, kit=None):
        # type: (Player, KitInfo) -> None
        if kit is None:
            kit = self.get_kit_for_player(player)

        current_kit = player.getKit()

        if current_kit is None or current_kit.templateName.lower() == kit.name.lower():
            return

        soldier = player.getDefaultVehicle()
        if soldier is None:
            return

        rkits.spawnerKit(player, soldier.getPosition(), kit.name, player.getTeam(), sound=False)
        rtimer.fireNextTick(switch_weapon, data=(player, kit.primary_item))

        rdebug.debugMessage("Forzando kit %s (default_idx %s) para el jugador %s" % (kit.name, kit.primary_item, player.getName()))

    def promote_player(self, player, player_state):
        # type: (Player, GunGamePlayerState) -> None
        player_state.teamkills_pending = 0
        player_state.kills_pending = 0

        new_level = player_state.level + 1
        player_state.level = new_level

        if new_level >= self.max_level:
            self.player_won(player)
        else:
            self.enforce_kit(player)

        rcore.playSoundForPlayer(player, SOUND_ID_PROMOTE)
        heal_player(player, HEAL_PER_LEVEL)
        player.score.score = new_level + 1

    def demote_player(self, player, player_state):
        # type: (Player, GunGamePlayerState) -> None
        player_state.teamkills_pending = 0
        player_state.kills_pending = 0

        new_level = max(player_state.level - 1, 0)
        player_state.level = new_level

        self.enforce_kit(player)
        rcore.playSoundForPlayer(player, SOUND_ID_DEMOTE)
        player.score.score = new_level + 1

    @property
    def state_update_pending(self):
        return self.state_update_timer is not None

    def mark_player_for_update(self, player):
        # type: (bf2.playerManager.Player) -> None
        self.players_requiring_update.add(player)
        if not self.state_update_pending:
            self.state_update_timer = rtimer.fireNextTick(self.update_state)

    def update_state(self, _data=None):
        for player in self.players_requiring_update:
            if (
                not player.isValid()
                # This is needed in order to handle disconnected players
                or player not in self.player_states.keys()
            ):
                continue

            player_state = self.player_states[player]
            level = self.get_level_for_player(player)
            if player_state.teamkills_pending >= level.teamkills_to_demote:
                self.demote_player(player, player_state)
            else:
                if player_state.kills_pending >= level.kills_to_promote:
                    self.promote_player(player, player_state)

            # Teamwork score shows how many kills you need to level up
            if player_state.level < self.max_level:
                new_level = self.get_level_for_player(player)
                player.score.rplScore = new_level.kills_to_promote - player_state.kills_pending
            else:
                player.score.rplScore = 0

        self.players_requiring_update.clear()
        self.state_update_timer = None

        self.update_scores()

    def update_scores(self):
        # type: () -> (Set[Player], int)
        if len(self.player_states) == 0:
            self.top_level = 0
            self.top_player_names = set()
            return

        # Ticket counter
        team1_levels = {0}  # type: Set[int]
        team2_levels = {0}  # type: Set[int]
        for player, state in self.player_states.iteritems():
            team1_levels.add(state.level) if player.getTeam() == 1 else team2_levels.add(state.level)
        top_level_team1 = max(team1_levels)
        top_level_team2 = max(team2_levels)
        bf2.gameLogic.setTickets(1, top_level_team1 + 1)
        bf2.gameLogic.setTickets(2, top_level_team2 + 1)

        if self.is_game_over:
            return

        # Lead message
        new_top_level = max(top_level_team1, top_level_team2)
        new_top_player_names = set()  # type: Set[str]
        for player, state in self.player_states.iteritems():
            if state.level == new_top_level:
                new_top_player_names.add(player.getName())

        old_top_level = self.top_level
        old_top_player_names = self.top_player_names

        self.top_level = new_top_level
        self.top_player_names = new_top_player_names

        # Lead with first level is meaningless.
        if new_top_level == 0:
            return
        # If the set of leading players doesn't change, no message is shown;
        # unless we're going from level 0 to level 1, in which case we
        # did not announce players yet due to the ealry return above.
        if old_top_player_names == new_top_player_names and not (old_top_level == 0 and new_top_level == 1):
            return

        # To avoid spammy and long messages, messages are only shown if
        # the number of players at the top is relatively low.
        top_player_count = len(new_top_player_names)
        if top_player_count == 0 or top_player_count > 3:
            return

        rcore.sendMessageToAll(lead_message(new_top_player_names, self.max_level - new_top_level))

    def player_won(self, player):
        if self.is_game_over:
            # Someone else won already
            return

        self.is_game_over = True
        rcore.sendMessageToAll("La batalla ha terminado! %s es el ganador!" % format_name(player.getName()))
        rtimer.fireOnce(lambda args: rcore.silentlyEndGame(args[0], args[1]), 5.0, (player.getTeam(), True))

    # Event handlers

    def gg_onPlayerChangeTeams(self, _player, _human_has_spawned):
        rtimer.fireNextTick(lambda _: self.update_scores())

    def gg_onPlayerKilled(self, victim, attacker, weapon, assists, _soldier):
        # type: (Player, Optional[Player], Optional[Any], Tuple[Tuple[Player, int]], Any) -> None
        victim = ensure_valid(victim)
        attacker = ensure_valid(attacker)

        if attacker is not None:
            attacker_state = self.player_states.get(attacker, GunGamePlayerState())

            if is_teamkill(victim, attacker, weapon):
                attacker_state.teamkills_pending += 1
            elif not is_suicide(victim, attacker):
                attacker_state.kills_pending += 1

            self.mark_player_for_update(attacker)

        if assists is not None:
            for assistee in assisting_players(assists):
                assistee = ensure_valid(assistee)
                if assistee is None or is_suicide(victim, assistee):
                    continue

                assistee_state = self.player_states[assistee]
                assistee_state.assists_pending += 1

                assistee_level = self.get_level_for_player(assistee)

                if assistee_state.assists_pending >= assistee_level.assists_count_as_kill:
                    assistee_state.kills_pending += (
                        math.floor(assistee_state.assists_pending / assistee_level.assists_count_as_kill)
                    )
                    assistee_state.assists_pending %= assistee_level.assists_count_as_kill
                    self.mark_player_for_update(assistee)

        if victim is not None:
            rtimer.fireNextTick(force_give_up, victim)

    def gg_onPlayerConnect(self, player):
        self.player_states[player] = self.old_player_states.get(
            player.getName(),
            GunGamePlayerState()
        )
        self.mark_player_for_update(player)
        player.score.score = max(player.score.score, 1)

    def gg_onPlayerDisconnect(self, player):
        # type: (Optional[Player]) -> None
        if player is None:
            return
        old_player_state = self.player_states.pop(player)
        self.old_player_states[player.getName()] = old_player_state
        self.mark_player_for_update(player)

    # noinspection PyMethodMayBeStatic
    def gg_onSpawn(self, _player, soldier):
        rmemory.setSoldierStaminaRecovery(soldier, 0.5)

    def gg_onPickupKit(self, player, _kit):
        player = ensure_valid(player)
        if player is None:
            return
        self.enforce_kit(player)

    # noinspection PyMethodMayBeStatic
    def gg_onDropKit(self, _player, kit):
        rtimer.fireNextTick(delete_kit, kit)

    def gg_onChatMessage(self, player_id, text, _channel, _flags):
        if player_id is not None and player_id >= 0:
            player = bf2.playerManager.getPlayerByIndex(player_id)  # type: Player
        else:
            return
        try:
            param = int(text.strip().split()[-1])
        except ValueError:
            param = None

        if "selectweapon" in text:
            player = bf2.playerManager.getPlayerByIndex(player_id)
            rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_WEAPONSELECT1 + param - 1)

        if "kill" in text:
            player = bf2.playerManager.getPlayerByIndex(player_id)  # type: Player
            self.player_states[player].kills_pending += param if param is not None else 1
            self.mark_player_for_update(player)

        if "team" in text:
            player = bf2.playerManager.getPlayerByIndex(player_id)  # type: Player
            self.player_states[player].teamkills_pending += param if param is not None else 1
            self.mark_player_for_update(player)

        if "resetlevel" in text:
            self.player_states[player].level = 0
            self.enforce_kit(player)

    def gg_registerHandlers(self):
        host.registerHandler('PlayerConnect', self.gg_onPlayerConnect, 1)
        host.registerHandler('PlayerDisconnect', self.gg_onPlayerDisconnect, 1)
        host.registerHandler('PlayerKilled', self.gg_onPlayerKilled, 1)
        host.registerHandler('PickupKit', self.gg_onPickupKit, 1)
        host.registerHandler('DropKit', self.gg_onDropKit, 1)
        host.registerHandler("PlayerSpawn", self.gg_onSpawn, 1)
        host.registerHandler("PlayerChangeTeams", self.gg_onPlayerChangeTeams, 1)

        self.refresh_stamina_timer = rtimer.Timer(refresh_stamina, 1.0, 1)
        self.refresh_stamina_timer.setRecurring(7)

        # DEBUG
        # host.registerHandler('ChatMessage', self.gg_onChatMessage, 1)

    def gg_unregisterHandlers(self):
        self.refresh_stamina_timer.destroy()

        host.unregisterHandler(self.gg_onPlayerConnect)
        host.unregisterHandler(self.gg_onPlayerDisconnect)
        host.unregisterHandler(self.gg_onPlayerKilled)
        host.unregisterHandler(self.gg_onPickupKit)
        host.unregisterHandler(self.gg_onDropKit)
        host.unregisterHandler(self.gg_onSpawn)
        host.unregisterHandler(self.gg_onPlayerChangeTeams)

        # DEBUG
        # host.unregisterHandler(self.gg_onChatMessage)

    # Overrides

    def onTicketLimitReached(self, team, limitId):
        pass

    def calcStartTickets(self, mapDefaultTickets):
        return 1

    def calcTicketLossForTeam(self, team, otherTeamAreaValue, otherTeamAreaOverweight):
        return 0

    def addTickets(self, team, tickets, debug=''):
        return

    def onGameStatusChanged(self, status):
        cq.PRAAS.onGameStatusChanged(self, status)

        if status == bf2.GameStatus.Loaded:
            self.smart_spawn.onLoaded()
            self.smart_spawn.registerHandlers()
            self.progression = build_progression()
            self.max_level = len(self.progression)
            self.invurnabilityTime.contents.value = ARMOR_INVULNERABLE_TIME
            self.gg_registerHandlers()

        if status == bf2.GameStatus.Playing:
            for player in rcore.getPlayers():
                self.gg_onPlayerConnect(player)

            # Sets _config values. These are reset reloaded from file at every map load so its fine to overwrite them
            rserver.C('KIT_LIMITS', {})
            rserver.C('RALLY_TEAMS', [])
            rserver.C('ASSET_TEAMS', [])
            rserver.C('WOUNDED_TIME', 1)
            rserver.C('DEAD_TIME', 3)
            rserver.C('MAX_PENALTY', 2)
            rserver.C('KIT_FACTION_LOCKED', 0)
            rserver.C('SCORING_GENERAL', 0)
            rserver.C('SCORING_TEAMWORK', 0)

        elif status == bf2.GameStatus.EndGame:
            self.invurnabilityTime.contents.value = self.defaultInvurnabilityTime
            self.gg_unregisterHandlers()
            self.smart_spawn.unregisterHandlers()

    def getType(self):
        return "gungame"

    def getBf2Type(self):
        return "gpm_gungame"

    def checkKitRequestRestrictions(self, kit, player):
        return False

    def overrideModifySpawn(self, player):
        for kitIndex in range(7):
            team = player.getTeam()
            kit = self.get_kit_for_player(player)
            soldier = rkits.g_kits_slots[team][kitIndex].Soldier
            host.rcon_invoke("gameLogic.setKit %s %s %s %s" % (team, kitIndex, kit, soldier))
        return True


SPAWNPOINT_SAFESPACE_RADIUS_SQUARED = 28 * 28


class SmartSpawn:
    def __init__(self):
        self.spawnpoints = {1: [], 2: []}
        self.disabledSpawnPoints = {1: set(), 2: set()}
        self.taskTeam1 = None
        self.taskTeam2 = None

    def onLoaded(self):
        for spawnpoint in bf2.objectManager.getObjectsOfType('dice.bf.SpawnPoint'):
            # TODO no way to get spawnpoint team, would likely need some reverse engineering
            spawnpoint.pos = spawnpoint.getPosition()
            if "blufor" in spawnpoint.templateName.lower():
                self.spawnpoints[2].append(spawnpoint)
                spawnpoint.team = 2
            else:
                self.spawnpoints[1].append(spawnpoint)
                spawnpoint.team = 1

    def registerHandlers(self):
        host.registerHandler("PlayerSpawn", self.onSpawn)
        self.taskTeam1 = rtimer.repeatingTask(self.refresh, 4.0, 1)
        self.taskTeam2 = rtimer.repeatingTask(self.refresh, 4.0, 2)

    def unregisterHandlers(self):
        host.unregisterHandler(self.onSpawn)
        self.taskTeam1.destroy()
        self.taskTeam2.destroy()

    def onSpawn(self, _player, sol):
        enemyteam = 3 - sol.getTeam()
        self.refreshSoldier(sol, enemyteam)

    def refresh(self, team):
        otherteam = 3 - team

        # Set of all points of that are disabled
        disabledPoints = set(self.disabledSpawnPoints[otherteam])

        for player in bf2.playerManager.getPlayers():
            if player.getTeam() != team:
                continue
            if player.isManDown():
                continue
            sol = player.getDefaultVehicle()
            if sol is None:
                continue
            self.refreshSoldier(sol, otherteam, disabledPoints)

        for sp in disabledPoints:
            self._enableSpawnPoint(sp)

    def refreshSoldier(self, soldier, team, disabledPoints=None):
        pos = soldier.getPosition()

        for sp in self.spawnpoints[team]:
            if _realitycore.calcHorizDistanceSquared(pos, sp.pos) < SPAWNPOINT_SAFESPACE_RADIUS_SQUARED:
                # SP is already disabled, mark it to not clear
                if sp in self.disabledSpawnPoints[sp.team]:
                    if disabledPoints is not None:
                        disabledPoints.discard(sp)

                # SP isn't disabled, disable it
                else:
                    self._disableSpawnPoint(sp)

    def _disableSpawnPoint(self, sp):
        # rdebug.debugMessage("Disabling spawnpoint %s" % sp.templateName)
        self.disabledSpawnPoints[sp.team].add(sp)

        host.rcon_invoke('ObjectTemplate.activeSafe SpawnPoint ' + sp.templateName)
        # If this doesn't work well:
        # There's SpawnPoint::setActive which is read dynamically from SpawnGroup::GetSpawnPoint.
        # bool at 0x23C in linux
        # bool at 0x18 in windows (at interface ISpawnPoint at 0x144) = 0x15C?
        host.rcon_invoke("ObjectTemplate.setOnlyForAI 1")

    def _enableSpawnPoint(self, sp):
        # rdebug.debugMessage("Enabling spawnpoint %s" % sp.templateName)
        self.disabledSpawnPoints[sp.team].remove(sp)

        host.rcon_invoke('ObjectTemplate.activeSafe SpawnPoint ' + sp.templateName)
        host.rcon_invoke("ObjectTemplate.setOnlyForAI 0")
