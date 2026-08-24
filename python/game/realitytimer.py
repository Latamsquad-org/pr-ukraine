import bf2
import host
import realitydebug as rdebug
import realityevents as revents
import realitylogger as rlogger

class Timer(object):

    def __init__(self, targetFunc, delta, alwaysTrigger, data = None):
        self.targetFunc = targetFunc
        self.data = data
        self.time = host.timer_getWallTime() + delta
        self.interval = 0.0
        self.alwaysTrigger = alwaysTrigger
        self.isDestroyed = False
        host.timer_created(self)

    def destroy(self):
        if not self.isDestroyed:
            self.isDestroyed = True
            host.timer_destroy(self)

    def getTime(self):
        return self.time

    def setTime(self, time):
        self.time = time

    def setRecurring(self, interval):
        self.interval = interval

    def onTrigger(self):
        if not self.isDestroyed:
            try:
                if rdebug.isDebugEnabled('profiler'):
                    start = rdebug.clockFunc()
                    self.targetFunc(self.data)
                    time = rdebug.clockFunc() - start
                    rlogger.RealityLogger['profiler'].logLine('%s.%s\t%s' % (self.targetFunc.__module__, self.targetFunc.__name__, '{0:.7f}'.format(time * 1000)))
                else:
                    self.targetFunc(self.data)
            except:
                rdebug.errorMessage()


class fireOnce(Timer):

    def __init__(self, targetFunc, delay, data = None):
        Timer.__init__(self, targetFunc, delay, 1, data)
        activeFireOnceTimers.add(self)

    def onTrigger(self):
        Timer.onTrigger(self)
        self.destroy()

    def destroy(self):
        Timer.destroy(self)
        activeFireOnceTimers.discard(self)

    def setRecurring(self, interval):
        raise Exception('Not supported')

    def setTime(self, time):
        raise Exception('Not supported')


class fireNextTick(fireOnce):

    def __init__(self, targetFunc, data = None):
        fireOnce.__init__(self, targetFunc, -1, data)


class coolDown:

    def __init__(self, targetFunc, args = None):
        self._targetFunc = targetFunc
        self._timer = None
        self._args = args
        return

    def __del__(self):
        self.reset()

    def _fireAndReset(self, args):
        self.reset()
        self._targetFunc(self._args)

    def reset(self):
        if self._timer:
            self._timer.destroy()
        self._timer = None
        return

    def start(self, time):
        self.reset()
        if time is None:
            self._timer = False
        else:
            self._timer = fireOnce(self._fireAndReset, time)
        return

    def isOnCoolDown(self):
        return self._timer is not None

    def isOnCoolDownForever(self):
        return self._timer is False

    def getTimeLeft(self):
        if self._timer is False:
            return -1.0
        elif self._timer is None:
            return 0.0
        else:
            return self._timer.time - host.timer_getWallTime()


activeFireOnceTimers = set()

def cleanupOnRoundEnd(status):
    if status == bf2.GameStatus.EndGame:
        for timer in list(activeFireOnceTimers):
            timer.destroy()


perTickList = set()

def perTickRefresh(args = None):
    now = host.timer_getWallTime()
    PerTick.frameTime = now - PerTick.lastFrameTime
    PerTick.lastFrameTime = now
    for fun in list(perTickList):
        try:
            fun()
        except:
            rdebug.errorMessage()


def perTickRegister(fun):
    perTickList.add(fun)


def perTickUnregister(fun):
    perTickList.discard(fun)


def perTickIsRegistered(fun):
    return fun in perTickList


class PerTick(object):
    lastFrameTime = host.timer_getWallTime()
    frameTime = 0.033

    def tick(self):
        pass

    def registerTimer(self):
        if self.tick in perTickList:
            raise Exception('Timer already registered')
        perTickList.add(self.tick)

    def unregisterTimer(self):
        if self.tick not in perTickList:
            raise Exception('Timer not registered')
        perTickList.remove(self.tick)


def init():
    host.registerGameStatusHandler(cleanupOnRoundEnd)
    Timer(perTickRefresh, 0.1, 1).setRecurring(1e-06)
    perTickRegister(_taskManager.refresh)


from heapq import *

class _taskManager:
    taskQueue = []

    @classmethod
    def refresh(cls, data = None):
        while True:
            if len(cls.taskQueue) == 0:
                return
            if cls.taskQueue[0].isDestroyed:
                heappop(cls.taskQueue)
            else:
                break

        startTime = rdebug.clockFunc()
        currentTime = startTime
        simulationTime = host.timer_getWallTime()
        while currentTime - startTime < 0.002:
            task = cls.taskQueue[0]
            if task.nextTime > simulationTime:
                return
            heappop(cls.taskQueue)
            task.onTrigger()
            if not task.isDestroyed:
                task.nextTime = simulationTime + task.interval
                heappush(cls.taskQueue, task)
            currentTime = rdebug.clockFunc()


class repeatingTask:

    def __init__(self, targetFunc, interval, data = None):
        self.interval = interval
        self.nextTime = host.timer_getWallTime() + interval
        self.targetFunc = targetFunc
        self.data = data
        self.isDestroyed = False
        heappush(_taskManager.taskQueue, self)

    def destroy(self):
        self.isDestroyed = True

    def onTrigger(self):
        if revents.g_gameState != bf2.GameStatus.Playing:
            return
        try:
            if rdebug.isDebugEnabled('profiler'):
                start = rdebug.clockFunc()
                self.targetFunc(self.data)
                time = rdebug.clockFunc() - start
                rlogger.RealityLogger['profiler'].logLine('%s.%s\t%s' % (self.targetFunc.__module__, self.targetFunc.__name__, '{0:.7f}'.format(time * 1000)))
            else:
                self.targetFunc(self.data)
        except:
            rdebug.errorMessage()

    def __cmp__(self, other):
        if self.nextTime > other.nextTime:
            return 1
        return -1


class task(repeatingTask):

    def onTrigger(self):
        repeatingTask.onTrigger(self)
        self.isDestroyed = True