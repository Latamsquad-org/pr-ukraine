import realityconfig_local as cfg
import realitykits as rkits
from realitytutorial import *


# Entry point for the definitions. load() must be defined.
def load():
    antitank()
    sandboxes()
    basics()
    interface()


# EXAMPLE:
# A short tutorial that teaches the player to fire different types of anti tank weaponry on a BTR.
def antitank():
    # This creates a a new chapter, on index 0 of the main menu, and index 1 of the secondary menu.
    # The name on the button will be "ANTI TANK"
    # This function sets the current "active" chapter, like when creating objects in .con files.
    CreateChapter("ANTI TANK", 0, 1)

    # This creates the first task and sets it to active. The objective title will be this text.
    CreateTask("Light Anti-Tank - Hit the target: 50m")
    # Teleport the player to the relevant spot.
    TeleportAtStart(POS_FIRINGRANGE_100M)

    # These will play a sound file, activate subtitles (on the bottom), and add text to the objective list (on the left)
    VoiceOverAtStart(
        "voicefile.wav",
        1.0,
        "The main job of a Light Anti-Tank (LAT) is to defend the squad from enemy armour and destroy light vehicles.",
        20.0
    )
    TaskObjectives(
        "Objective - hit the enemy APC\nAlso note the HUD image on the side\n"
        "Press REARM in the tutorial menu if needed."
    )
    TaskImage("Ingame\Vehicles\Icons\Minimap\mini_SquadMedium_1.dds")

    # This will define a a spawner for a single object.
    # position / rotation / team can also be set. The default position is the player's.
    kitdefinition = ObjectSpawnerTemplate("us_riflemanat")
    # The kit will be spawned and picked up. The order of any task components do not matter.
    PickupKit(kitdefinition)
    SpawnObject(kitdefinition)
    SwitchWeapon(4)
    # Define a BTR spawner at a specific position
    btr = ObjectSpawnerTemplate("ru_apc_btr60", (-333.0, 26.5, 22.0))
    # Spawn it, but do not keep it alive if the current task ends.
    SpawnObject(btr, keep=False)
    # Our objective: Bring the btr to below 50% health.
    DamageTargetObjective(btr, 50)

    CreateTask("Light Anti-Tank - Hit the target: 300m")
    VoiceOverAtStart("voicefile.wav", 1.0, " ", 20.0)
    TaskObjectives(
        "The objectives changed.\n"
        "Hold your MAIN RADIO keybind (default Q) to adjust iron sights while aiming down range and hit the target "
        "again.\n"
        "Press REARM in the tutorial menu if needed."
    )

    TeleportAtStart(POS_FIRINGRANGE_300M)
    btr = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_300M)
    SpawnObject(btr, keep=False)
    DamageTargetObjective(btr, 50)
    # Rearm the player
    RearmPlayer()
    SwitchWeapon(4)

    CreateTask("Heavy Anti-Tank - Hit the moving target")
    # Subtitles and objectives can use localization strings, Note that only "prhelp.utxt" is loaded for these.
    VoiceOverAtStart("voicefile.wav", 1.0, "HUD_HELP_WEAPON_HANDHELD_SHOVEL_CONTROLS_BUILDING", 20.0)
    # TaskObjectives("HUD_HELP_COMMANDER_commanderApply")
    TaskObjectives(
        "\nSome handheld and deployable AT launchers require the user to hold the Left Mouse Button to launch the "
        "missile"
        "and then guide it until the target is destroyed.\n"
        "Hit the moving target!"
    )
    TeleportAtStart(POS_TOWER_500M)
    kitdefinition = ObjectSpawnerTemplate("usa_at")
    SpawnObject(kitdefinition)
    PickupKit(kitdefinition)
    SwitchWeapon(4)

    btr = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_400M)
    SpawnObject(btr, keep=False)
    # This tells the BTR to patrol between `points` at the speed `speed`.
    FollowPathAction(btr, points=[(0.0, 27.0, 425.0), POS_TARGET_400M], speed=4.0)
    # This time our objective is to destroy it, and not just damage it.
    DestroyTargetObjective(btr)

    CreateTask("Enter the gunner seat of the SPG technical")
    VoiceOverAtStart("voicefile.wav", 1.0, "", 20.0)
    TaskObjectives(
        "Press your ENTER/EXIT keybind (default E) to enter the vehicle\n"
        "While in a vehicle, press F2 to switch to the gunner position."
    )
    TeleportAtStart(POS_FIRINGRANGE_600M)
    spg = ObjectSpawnerTemplate("civ_atm_technical", POS_PLAYERFRONT, ROT_EAST)
    SpawnObject(spg)
    # Objective completes when the player enters a seat whose template contains this text
    GetInSeatObjective("spg")

    CreateTask("Hit the moving target (500m)")
    btr = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_500M)
    SpawnObject(btr, keep=False)
    FollowPathAction(btr, points=[(110.0, 27.0, 460.0), POS_TARGET_500M], speed=6.0)
    DestroyTargetObjective(btr)

    CreateTask("Shovel the anti-tank emplacement")
    VoiceOverAtStart("voicefile.wav", 1.0, "", 20.0)
    TaskObjectives(
        "1. Hold the LEFT MOUSE BUTTON to build the emplacement with the shovel until the progress bar disappears.\n"
        "2. Rearm the emplacement and destroy the target.\n"
    )
    LeaveVehicleButton()
    UnspawnObject(spg)
    tow = ObjectSpawnerTemplate("deployable_tow", POS_PLAYERFRONT, ROT_EAST)
    SpawnObject(tow)
    ammokit = ObjectSpawnerTemplate("usa_rifleman")
    SpawnObject(ammokit)
    PickupKit(ammokit)
    SwitchWeapon(2)
    BuildAssetObjective(tow, percent=0.99)

    CreateTask("Rearm the emplacement and enter the asset")
    VoiceOverAtStart("voicefile.wav", 1.0, "", 20.0)
    TaskObjectives(
        "Throw your ammo bag on the TOW and press your ENTER/EXIT keybind (default E)"
    )
    ammokit = ObjectSpawnerTemplate("usa_rifleman")
    SpawnObject(ammokit)
    PickupKit(ammokit)
    SwitchWeapon(4)
    GetInSeatObjective("tow")

    CreateTask("Hit the moving target")
    btr = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_700M)
    SpawnObject(btr, keep=False)
    FollowPathAction(btr, points=[(310.0, 27.0, 460.0), POS_TARGET_700M], speed=8.0)
    DestroyTargetObjective(btr)

    CreateTask("ATGM Vehicle - Enter the gunner seat")
    VoiceOverAtStart("voicefile.wav", 1.0, "", 20.0)
    TaskObjectives(
        "Press your ENTER/EXIT keybind (default E) to enter the vehicle\n"
        "While in a vehicle, press F2 to switch to the gunner position."
    )
    LeaveVehicleButton()
    UnspawnObject(tow)
    shturm = ObjectSpawnerTemplate("ru_atm_shturm", POS_PLAYERFRONT, ROT_EAST)
    SpawnObject(shturm)
    GetInSeatObjective("gunner")

    CreateTask("Hit the moving target")
    btr = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_700M)
    SpawnObject(btr, keep=False)
    FollowPathAction(btr, points=[(310.0, 27.0, 460.0), POS_TARGET_700M], speed=8.0)
    DestroyTargetObjective(btr)

    CreateTask("You have completed the Anti-tank course! Press CAPS LOCK to choose a new one")
    VoiceOverAtStart("voicefile.wav", 1.0, "", 20.0)
    TeleportAtStart(POS_FIRINGRANGE_100M)


# EXAMPLE (advanced):
# You can create your own components for tasks
class ExampleTaskComponent(TaskComponent):
    def __init__(self, examplearg):
        TaskComponent.__init__(self)
        self.examplearg = examplearg

    def start(self):
        rdebug.debugMessage("start: Set up timers/events here, or run your action directly")

    def stop(self):
        rdebug.debugMessage("stop: clean up")

    # This is called at 30hz between start and stop.
    # heavy things here will cause low fps.
    def think(self):
        pass


# EXAMPLE (advanced):
# You can create your own objectives for tasks.
# Objective inherits from TaskComponent and adds checkCompletion, which is called at 30hz and should return True when
# task is completed.
import time


class ExampleObjective(Objective):
    def __init__(self, time):
        Objective.__init__(self)
        self.time = time
        self.startTime = None

    def start(self):
        rdebug.debugMessage("start: Set up timers/events here")
        self.startTime = time.time()

    def stop(self):
        rdebug.debugMessage("stop: clean up")
        self.startTime = None

    def checkCompletion(self):
        return time.time() - self.startTime > self.time


def basics():
    SetMainMenuButtonText(0, "BASICS")

    CreateChapter("VOICE", 0, 0)
    CreateTask("About Mumble")
    TaskObjectives(
        "Mumble is an external application\nresponsible for voice chat.\r\nClick CONTINUE to launch "
        "Mumble.\r\n1\r\n2\r\n3\r\n4\r\n5"
    )
    ClickContinueObjective()
    CreateSquad()
    # SetMarker( (50, 50, 50), type="move" )

    CreateTask("Configure mumble")
    TaskObjectives("Mumble is launched in the background.\nConfigure your INPUT and OUTPUT devices.")
    OpenMumbleProcess()

    CreateChapter("TEST", 0, 5)
    CreateTask("test 0")
    SpawnInObjective()

    CreateTask("test 1")
    SoldierSprintObjective()

    CreateTask("test 2")
    SoldierStaminaLowObjective()

    CreateTask("test 3")


def addSandboxVehicles():
    tank500 = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_500M, team=TEAM_ENEMY)
    SpawnObject(tank500, respawn=True)
    FollowPathAction(tank500, points=[(100.0, 27.0, 400.0), POS_TARGET_500M], speed=8.0)

    tank400 = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_400M, team=TEAM_ENEMY)
    SpawnObject(tank400, respawn=True)
    FollowPathAction(tank400, points=[(0.0, 27.0, 400.0), POS_TARGET_400M], speed=8.0)

    tank300 = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_300M, team=TEAM_ENEMY)
    SpawnObject(tank300, respawn=True)
    FollowPathAction(tank300, points=[(-90.0, 27.0, 400.0), POS_TARGET_300M], speed=8.0)

    tank200 = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_200M, team=TEAM_ENEMY)
    SpawnObject(tank200, respawn=True)
    FollowPathAction(tank200, points=[(-190.0, 27.0, 400.0), POS_TARGET_200M], speed=8.0)

    tank100 = ObjectSpawnerTemplate("ru_apc_btr60", POS_TARGET_100M, team=TEAM_ENEMY)
    SpawnObject(tank100, respawn=True)
    FollowPathAction(tank100, points=[(-290.0, 27.0, 400.0), POS_TARGET_100M], speed=8.0)

    # target_test = ObjectSpawnerTemplate("target_pr_dynamic", (-290.0, 32.0, 17.0), team=TEAM_ENEMY)
    # SpawnObject(target_test, respawn=True)
    # FollowPathAction(target_test, points=[(-290.0, 32.0, 117.0), (-290.0, 32.0, 17.0)], speed=8.0)

    flyingtarget = ObjectSpawnerTemplate("us_the_uh1c", (0.0, 100.0, 270.0), team=TEAM_ENEMY)
    flyingbigtarget = ObjectSpawnerTemplate("us_the_chinook", (100.0, 100.0, 270.0), team=TEAM_ENEMY)
    SpawnObject(flyingtarget, respawn=True)
    SpawnObject(flyingbigtarget, respawn=True)
    FollowPathAction(flyingtarget, points=[(0.0, 100.0, -270.0), (0.0, 100.0, 670.0)], speed=25.0)
    FollowPathAction(flyingbigtarget, points=[(100.0, 100.0, -270.0), (100.0, 100.0, 670.0)], speed=30.0)

    flyingtarget = ObjectSpawnerTemplate("us_the_uh1c", (-100.0, 80.0, 270.0), team=TEAM_ENEMY)
    flyingbigtarget = ObjectSpawnerTemplate("us_the_chinook", (-200.0, 80.0, 270.0), team=TEAM_ENEMY)
    SpawnObject(flyingtarget, respawn=True)
    SpawnObject(flyingbigtarget, respawn=True)
    FollowPathAction(flyingtarget, points=[(-100.0, 80.0, -270.0), (-100.0, 80.0, 670.0)], speed=25.0)
    FollowPathAction(flyingbigtarget, points=[(-200.0, 80.0, -270.0), (-200.0, 80.0, 670.0)], speed=30.0)

    flyingtarget = ObjectSpawnerTemplate("us_the_uh1c", (-250.0, 60.0, 70.0), team=TEAM_ENEMY)
    flyingbigtarget = ObjectSpawnerTemplate("us_the_chinook", (-300.0, 60.0, 270.0), team=TEAM_ENEMY)
    SpawnObject(flyingtarget, respawn=True)
    SpawnObject(flyingbigtarget, respawn=True)
    FollowPathAction(flyingtarget, points=[(-250.0, 60.0, -270.0), (-250.0, 60.0, 670.0)], speed=25.0)
    FollowPathAction(flyingbigtarget, points=[(-300.0, 60.0, -270.0), (-300.0, 60.0, 670.0)], speed=30.0)


AllTeams = [
    'ch',
    'gb',
    'mec',
    'us',
    'usa',
    'fsa',
    'cf',
    'chinsurgent',
    'meinsurgent',
    'pl',
    'ru',
    'arf',
    'taliban',
    'idf',
    'hamas',
    'ger',
    'vnusa',
    'vnusmc',
    'vnnva',
    'gb82',
    'arg82',
    'fr',
    'nl',
    'ww2ger',
    'ww2ger41',
    'ww2usa',
    'ww2rus',
    'ww2rusearly'
]


def sandboxes():
    SetMainMenuButtonText(5, "SANDBOX")

    CreateChapter("ANTITANK", 5, 0)
    CreateTask()
    # Weapons
    TeleportAtStart((-400.0, 27.0, 131.0))
    SpawnObject(ObjectSpawnerTemplate("ru_at", (-400.0, 26.0, 136.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("ru_riflemanat", (-400.0, 26.0, 140.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("gb_at", (-400.0, 26.0, 144.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("gb_riflemanat", (-400.0, 26.0, 148.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("us_at", (-400.0, 26.0, 152.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("us_riflemanat", (-400.0, 26.0, 156.0)), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("us_riflemanat_alt", (-400.0, 26.0, 160.0)), respawn=True)

    SpawnObject(ObjectSpawnerTemplate("civ_atm_technical", (-400.0, 27.0, 165.0), rot=ROT_EAST), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("deployable_tow", (-400.0, 27.0, 170.0), rot=ROT_EAST), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("ru_atm_shturm", (-400.0, 27.0, 175.0), rot=ROT_EAST), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("ru_atm_spandrel", (-400.0, 27.0, 175.0), rot=ROT_EAST), respawn=True)
    SpawnObject(ObjectSpawnerTemplate("gb_aav_stormer", (-400.0, 27.0, 180.0), rot=ROT_EAST), respawn=True)
    addSandboxVehicles()

    CreateChapter("GRENADIER", 5, 1)
    CreateTask()
    # Weapons
    TeleportAtStart((-400.0, 27.0, 131.0))
    pos = (-400.0, 25.5, 136.0)
    i = 0
    for team in AllTeams:
        kitname = "%s_assault" % team
        if rkits.kitExists(kitname):
            SpawnObject(ObjectSpawnerTemplate(kitname, pos=(pos[0], pos[1], pos[2] + i * 3)), respawn=True)
            i += 1
    addSandboxVehicles()

    CreateChapter("AR", 5, 2)
    CreateTask()
    # Weapons
    TeleportAtStart((-400.0, 27.0, 131.0))
    pos = (-400.0, 25.5, 136.0)
    i = 0
    for team in AllTeams:
        kitname = "%s_support" % team
        if rkits.kitExists(kitname):
            SpawnObject(ObjectSpawnerTemplate(kitname, pos=(pos[0], pos[1], pos[2] + i * 3)), respawn=True)
            i += 1

        kitname = "%s_mg" % team
        if rkits.kitExists(kitname):
            SpawnObject(ObjectSpawnerTemplate(kitname, pos=(pos[0], pos[1], pos[2] + i * 3)), respawn=True)
            i += 1
    addSandboxVehicles()

    CreateChapter("DEPLOYABLES", 5, 3)
    CreateTask()
    addSandboxVehicles()
    TeleportAtStart((-400.0, 27.0, 131.0))
    pos = (-400.0, 25.5, 136.0)
    i = 0
    templates = {}
    for type in ["ANTIAIR_TEMPLATES", "HMG_TEMPLATES", "TOW_TEMPLATES", "MORTAR_TEMPLATES", "FOXHOLE_TEMPLATES", "RAZORWIRES_TEMPLATES", "SANDBAGS_TEMPLATES"]:
        templates[type] = set()
        templates[type].update(sum(cfg.C[type].values(), []))
    for type in templates:
        for deployableTemplate in templates[type]:
            template = ObjectSpawnerTemplate(deployableTemplate, pos=(pos[0], pos[1], pos[2] + i * 6), rot=ROT_EAST)
            SpawnObject(template)
            SetObjectHealth(template, 1.0)
            i += 1


# TODO untested old stuff
def assets():
    # assets
    CreateChapter("assets", 1, 2)

    CreateTask("Get in the logistics truck")
    CreateSquad()
    TeleportAtStart((221.0, 26.0, -253.0))
    SpawnObject(ObjectSpawnerTemplate("mec_trk_logistics", POS_PLAYERFRONT, ROT_NORTH))
    GetInSeatObjective("logistic")

    pos = (102.0, 26.0, -366.0)
    CreateTask("Drive the truck to the position marked on your map")
    SetMarker(pos, "move")
    MoveToPositionObjective(pos, 15)

    btr = ObjectSpawnerTemplate("ru_apc_btr60", (-272.0, 26.0, -361.0), team=TEAM_ENEMY)
    SpawnObject(btr)
    SetMarker((-272.0, 1000.0, -361.0), "attack")

    CreateTask("Drop one supply crate")
    BeAroundObjectObjective("pr_supply_crate_mec", 1)

    CreateTask("Get an officer kit from the crate")
    GetKitObjective("officer")

    CreateTask("Deploy a firebase")
    DeployAssetObjective("outpost")

    CreateTask("Get another kit and shovel the firebase")
    BuildAssetObjective("outpost")

    CreateTask("Drop another supply crate")
    BeAroundObjectObjective("pr_supply_crate_gb", 2)

    CreateTask("Deploy an anti tank so it can hit the vehicle to the west")

    DeployAssetObjective("tow")
    BuildAssetObjective("tow")

    CreateTask("Destroy the vehicle with the Anti Tank missile")
    DestroyTargetObjective(btr)
    # CreateChapter("Mortar sandbox", 5, 3)
    # CreateTask("Sandbox")
    # # Weapons
    # TeleportAtStart((-400.0, 27.0, 131.0))
    # pos = (-400.0, 25.5, 136.0)
    # i = 0
    # for team in AllTeams:
    #     if rkits.kitExists(kitname):
    #         SpawnObject(ObjectSpawnerTemplate(kitname, pos=(pos[0], pos[1], pos[2] + i * 3) ), respawn=True)
    #         i += 1
    #
    #     kitname = "%s_mg" % team
    #     if rkits.kitExists(kitname):
    #         SpawnObject(ObjectSpawnerTemplate(kitname, pos=(pos[0], pos[1], pos[2] + i * 3) ), respawn=True)
    #         i += 1
    # addSandboxesVehicles()

    # CreateChapter("grenadier", 1, 0)
    # truck100 = ObjectSpawnerTemplate("ru_trk_logistics", POS_TARGET_100M)
    # truck200 = ObjectSpawnerTemplate("ru_trk_logistics", POS_TARGET_200M)
    # CreateTask("Hit the target: 100m")
    #
    # TeleportAtStart(POS_FIRINGRANGE_100M)
    # kit = ObjectSpawnerTemplate("gb_assault")
    # SpawnObject(kit)
    # PickupKit(kit)
    #
    # SpawnObject(truck100, keep=False)
    # DamageTargetObjective(truck100, 100)
    #
    #
    # CreateTask("Hit the target: 200m")
    # TeleportAtStart(POS_FIRINGRANGE_200M)
    # SpawnObject(truck200, keep=False)
    # DamageTargetObjective(truck200, 100)
