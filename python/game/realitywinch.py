# Embedded file name: realitywinch.py
import _realitymemory as _rmemory
import bf2
import host
import realitycore as rcore
import realitydebug as rdebug
import realityropes as rropes
import realitytimer as rtimer
import realityvehicles as rvehicles
TruckAttachmentTemplate = rropes.AttachmentTemplate(objectMass=1.0, inertiaMod=10.0)
TargetAttachmentTemplate = rropes.AttachmentTemplate(objectMass=0.8, inertiaMod=2.5, unFlipAssist=5.0)
DefaultRopeTemplate = rropes.RopeTemplate(stiffness=0.2, minimumLength=10.0)

def applysettings(arg = None):
    host.rcon_invoke('ObjectTemplate.activeSafe GenericFireArm c4_smallexplosives')
    host.rcon_invoke('ObjectTemplate.velocity 25')
    host.rcon_invoke('ObjectTemplate.fire.fireLaunchDelay 0.0')
    host.rcon_invoke('ObjectTemplate.activeSafe GenericProjectile c4_smallexplosives_TIMED_Projectile')
    host.rcon_invoke('ObjectTemplate.detonation.explosionDamage 0')
    host.rcon_invoke('ObjectTemplate.detonation.explosionForce 0')
    host.rcon_invoke('ObjectTemplate.armor.explosionDamage 0')


def onchat(playerId, text, channel, flags):
    try:
        key = text.split(' ')[1]
        val = float(text.split(' ')[2])
    except:
        return

    def setAndPrint(obj):
        obj.__dict__[key] = val
        for k, v in obj.__dict__.items():
            rdebug.debugMessage('%s: %s' % (k, v))

    if 'setrope' in text:
        setAndPrint(DefaultRopeTemplate)
    if 'settruck' in text:
        setAndPrint(TruckAttachmentTemplate)
    if 'settarget' in text:
        setAndPrint(TargetAttachmentTemplate)


def init():
    _rmemory.addProjectileCreatedTemplate('c4_smallexplosives_TIMED_Projectile'.lower(), stickSpawn)
    host.registerGameStatusHandler(applysettings)
    host.registerHandler('ChatMessage', onchat, 1)


def stickSpawn(weapon, obj):
    rtimer.fireOnce(WinchFactory, 0.5, (weapon, obj))


def WinchFactory(args):
    weapon, projectile = args
    applysettings()
    if not weapon.isValid():
        rdebug.debugMessage('Weapon invalid')
        return
    elif not projectile.isValid():
        rdebug.debugMessage('projectile invalid')
        return
    else:
        projectileRoot = bf2.objectManager.getRootParent(projectile)
        if projectileRoot is projectile:
            rdebug.debugMessage('Sticky did not stick!')
            return
        rdebug.debugMessage('Stuck to %s' % projectileRoot.templateName)
        if not hasattr(projectileRoot, 'getOccupyingPlayers'):
            rdebug.debugMessage('stuck target not PCO')
            return
        root = bf2.objectManager.getRootParent(weapon)
        if not hasattr(root, 'getOccupyingPlayers'):
            rdebug.debugMessage('root not PCO')
            return
        players = root.getOccupyingPlayers()
        if len(players) == 0:
            rdebug.debugMessage('No players on weapon')
            return
        player = players[0]
        team = player.getTeam()
        projectilePos = projectile.getPosition()
        logi = None
        for v in rvehicles.getKnownVehicles():
            if v.getTeam() != team:
                continue
            if 'logistic' not in v.templateName:
                continue
            pos = v.getPosition()
            if rcore.getSquareVectorDistance(projectilePos, pos) > 900:
                continue
            if v is projectileRoot:
                continue
            logi = v
            break

        if logi is None:
            rdebug.debugMessage('No logi found')
            return
        logiAttachment = rropes.Attachment(obj=logi, offset=(0.0, 0.2, -2.8), template=TruckAttachmentTemplate)
        vehicleOffset = rcore.vectorSub(projectile.getPosition(), projectileRoot.getPosition())
        vehicleOffsetUnrotated = rcore.quaternionRotateVector3d(projectileRoot.getRotation(), vehicleOffset, invert=True)
        targetAttachment = rropes.Attachment(obj=projectileRoot, offset=vehicleOffsetUnrotated, template=TargetAttachmentTemplate)
        rdebug.debugMessage('Initializing rope with %s and %s, target offset %s' % (logi.templateName, projectileRoot.templateName, str(vehicleOffsetUnrotated)))
        rope = rropes.Rope(attachment1=logiAttachment, attachment2=targetAttachment, length=None, template=DefaultRopeTemplate, visuals=True)
        Winch(logi, rope)
        return


class Winch(rtimer.PerTick):

    def __init__(self, logi, rope):
        self.registerTimer()
        self.logi = logi
        self.rope = rope
        self.time = 0

    def tick(self):
        self.time += 1
        if self.time > 1000:
            self.delete()
        self.rope.setPull(distance=0.06, strength=100000)

    def delete(self):
        self.unregisterTimer()
        self.rope.delete()