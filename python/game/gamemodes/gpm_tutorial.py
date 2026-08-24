import cq
import game.realitygamemode as rgamemode


class Tutorial(cq.PRAAS):
    def getType(self):
        return "tutorial"

    def getBf2Type(self):
        return "gpm_tutorial"


def init():
    rgamemode.setCurrentGameMode(Tutorial())


def deinit():
    rgamemode.setCurrentGameMode()
