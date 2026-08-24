# aas
#
# $Id: gpm_objective.py 40171 2024-05-11 15:51:38Z prbot $

import host

import objective
import realitydebug


def init():
    try:
        objective.init()
    except:
        host.rcon_invoke('echo "Error"')
        realitydebug.errorMessage()


def deinit():
    try:
        objective.deinit()
    except:
        host.rcon_invoke('echo "Error"')
        realitydebug.errorMessage()
