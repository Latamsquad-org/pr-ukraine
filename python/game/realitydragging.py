import host
import realitycore as rcore
import realitydebug as rdebug
import realitymemory as rmemory
import realitytimer as rtimer

def init():
    if rmemory.isDebuggerListenServer:
        return
    host.registerHandler('PlayerChangeWeapon', onChangeWeapon, 1)
    host.registerHandler('ExitVehicle', onExitVehicle)


DRAG_STIFFNESS = 0.5
DRAG_DISTANCE_EXPONENT = 0.8
DETACH_RANGE = 0.9
STAMINA_COST = 0.0015
dragging = {}

class Dragging(rtimer.PerTick):

    class Target:

        @classmethod
        def fromParticleTuple(cls, particleTuple):
            target = cls()
            target.getPosition = lambda : rmemory.getRagdollParticlePosition(particleTuple)
            target.push = lambda deltav: rmemory.pushRagdollParticle(particleTuple, deltav)
            return target

        @classmethod
        def fromObject(cls, obj, grabPosition):
            target = cls()
            _grabOffset = rcore.quaternionRotateVector3d(obj.getRotation(), rcore.vectorSub(grabPosition, obj.getPosition()), invert=True)
            _inverseInertiaMod = 0.45
            _forceMultiplier = 2.4
            target.getPosition = lambda : cls._objectPosition(obj, _grabOffset)
            target.push = lambda deltaV: cls._pushObject(obj, _grabOffset, deltaV, _forceMultiplier, _inverseInertiaMod)
            return target

        @staticmethod
        def _objectPosition(obj, grabOffset):
            if not obj.isValid():
                return None
            else:
                return rcore.vectorAddition(obj.getPosition(), rcore.quaternionRotateVector3d(obj.getRotation(), grabOffset))

        @staticmethod
        def _pushObject(obj, grabOffset, deltaV, _forceMultiplier, _inverseInertiaMod):
            deltaV = rcore.vectorScaling(deltaV, _forceMultiplier)
            rmemory.setVelocity(obj, rcore.vectorAddition(rmemory.getVelocity(obj), deltaV))
            f = rcore.vectorScaling(deltaV, _inverseInertiaMod)
            r = rcore.quaternionRotateVector3d(obj.getRotation(), grabOffset)
            deltaAngularVelocity = rcore.vectorCross(r, f)
            rmemory.setAngularVelocity(obj, rcore.vectorAddition(rmemory.getAngularVelocity(obj), deltaAngularVelocity))

    @classmethod
    def factory(cls, player):
        if player in dragging:
            dragging[player].delete()
        soldier = player.getVehicle()
        if not rcore.isSoldier(soldier):
            return
        else:
            pose = rmemory.getSoliderPose(soldier)
            if pose != 1:
                rcore.sendMessageToPlayer(player, 3190318)
                rdebug.debugMessage('Player not crouching', 'dragging')
                forceSwitchWeapon(player)
                return
            camera = rcore.getVehicleCamera(soldier)
            rot = rcore.getCameraRotation(camera)
            pos = rcore.getPositionFromPositionAndRotationWithPitch(camera.getPosition(), rot, 0.4)
            particleTuple = rmemory.getNearestRagdollParticle(pos, player.getTeam(), 1.6)
            if particleTuple is not None:
                rdebug.debugMessage('player %d is now dragging' % player.index, 'dragging')
                drag = Dragging(player, Dragging.Target.fromParticleTuple(particleTuple))
                dragging[player] = drag
                return
            rcore.sendMessageToPlayer(player, 1190601, 3)
            rdebug.debugMessage('cannot find who to drag', 'dragging')
            forceSwitchWeapon(player)
            return

    def __init__(self, player, target):
        self.player = player
        self.target = target
        self.registerTimer()

    def tick(self):
        if not self.player.isValid():
            rdebug.debugMessage('dragger disconnected', 'dragging')
            return self.delete(switchWeapon=False)
        elif not self.player.isAlive() or self.player.isManDown():
            rdebug.debugMessage('dragger died', 'dragging')
            return self.delete(switchWeapon=False)
        else:
            grabPos = self.target.getPosition()
            if grabPos is None:
                rcore.sendMessageToPlayer(self.player, 1190601, 3)
                rdebug.debugMessage('target position returned None', 'dragging')
                return self.delete(switchWeapon=True)
            soldier = self.player.getVehicle()
            if not rcore.isSoldier(soldier):
                rdebug.debugMessage('dragging player is in PCO', 'dragging')
                return self.delete(switchWeapon=False)
            pose = rmemory.getSoliderPose(soldier)
            if pose != 1:
                rcore.sendMessageToPlayer(self.player, 3190318)
                rdebug.debugMessage('Player stopped crouching', 'dragging')
                return self.delete(switchWeapon=True)
            camera = rcore.getVehicleCamera(soldier)
            rot = rcore.getCameraYaw(camera)
            lookPos = rcore.getPositionFromPositionAndRotation(camera.getPosition(), (rot, 0.0, 0.0), 0.1)
            particlePosToLookPos = (lookPos[0] - grabPos[0], lookPos[1] - grabPos[1] - 0.4, lookPos[2] - grabPos[2])
            distance = rcore.magnitudeVector(particlePosToLookPos)
            if distance > DETACH_RANGE:
                rcore.sendMessageToPlayer(self.player, 1190601, 3)
                rdebug.debugMessage('particle too far away, detaching', 'dragging')
                return self.delete(switchWeapon=True)
            solV = rmemory.getVelocity(soldier)
            if solV[1] < 0:
                yspeedmod = 0
            else:
                yspeedmod = 20
            solVabsolute = rcore.magnitudeVector((solV[0], solV[1] * yspeedmod, solV[2]))
            stamina = rmemory.getSoldierStamina(soldier)
            staminadebt = solVabsolute * STAMINA_COST
            if stamina < staminadebt:
                rcore.sendMessageToPlayer(self.player, 1220803, 1)
                rdebug.debugMessage('dragging player out of stamina', 'dragging')
                return self.delete(switchWeapon=True)
            rmemory.setSoldierStamina(soldier, stamina - staminadebt)
            force = distance ** DRAG_DISTANCE_EXPONENT * DRAG_STIFFNESS
            particleDeltaV = (particlePosToLookPos[0] / distance * force, particlePosToLookPos[1] / distance * force, particlePosToLookPos[2] / distance * force)
            self.target.push(particleDeltaV)
            return

    def delete(self, switchWeapon = True):
        rdebug.debugMessage('player %d no longer dragging' % self.player.index, 'dragging')
        del dragging[self.player]
        self.unregisterTimer()
        if switchWeapon:
            forceSwitchWeapon(self.player)


def forceSwitchWeapon(player):
    rtimer.fireOnce(forceSwitchWeaponDelayed, 0.3, player)


def forceSwitchWeaponDelayed(player):
    if not player.isValid():
        return
    if not isDraggingWeapon(player.getPrimaryWeapon()):
        return
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_WEAPONSELECT1 + 1, 0.25, 0.0)
    rmemory.sendPlayerButtonClickEvent(player, rmemory.PI_WEAPONSELECT1 + 2)


def startDragging(player):
    soldier = player.getVehicle()
    if not rcore.isSoldier(soldier):
        return


def onExitVehicle(player, vehicle):
    if not isDraggingWeapon(player.getPrimaryWeapon()):
        return
    forceSwitchWeapon(player)


def onChangeWeapon(player, oldWeaponObject, newWeaponObject):
    if isDraggingWeapon(newWeaponObject):
        Dragging.factory(player)
    elif player in dragging:
        dragging[player].delete(switchWeapon=False)


def isDraggingWeapon(weapon):
    return weapon is not None and (weapon.templateName == 'Resuscitate' or weapon.templateName.endswith('bodydrag'))