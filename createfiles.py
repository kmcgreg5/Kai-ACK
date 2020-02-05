# Written by Kai McGregor for use in Kai-ACK

from pathlib import Path
import os

def createFiles(panel):
    mtAutoscript = open(panel.siteDir + '\\MTAutoscript.rsc','r')
    password = open(panel.siteDir + '\\Password.txt','r')
    wattBox = open(panel.siteDir + '\\WattBox.cfg','r')
    dynu = open('dynuscript.rsc', 'r')

    # Gets password from file
    panel.sitePassword = password.read().strip()
    password.close()

    # Creates Autoscript files for panels
    config = mtAutoscript.read()
    mtAutoscript.close()

    # Write ddnsHostname to autoscript
    index = config.index('ReplaceWithDynu')
    y = 0
    dir_path = os.path.dirname(os.path.realpath(__file__))
    filename = Path(dir_path + '/Autoscript/')
    filename.mkdir(parents=True, exist_ok=True)
    filename = Path(dir_path + '/Autoscript/' + panel.ssid + '.rsc')
    filename.touch(exist_ok=True)
    file = open(dir_path + '/Autoscript/' + panel.ssid + '.rsc', 'w')
    if panel.optionsList['Dynu'] is True: # Edits dynu if True
        file.write(config[0:index] + panel.ddnsHostname + config[index + 15:len(config)])
    else:
        file.write(config[0:index] + 'ReplaceWithDynu' + config[index + 15:len(config)])
    file.close()

    # Creates wattbox configs for panels
    config = wattBox.read()
    index = config.index('ReplaceWithSSID')
    index2 = config.index('ReplaceWithSSID',index + 1)
    index3 = config.index('ReplaceWithSSID',index2 + 1)
    wattBox.close()
    y = 0

    # Write ssid's to wattbox config
    filename = Path(dir_path + '/WattBox/')
    filename.mkdir(parents=True, exist_ok=True)
    filename = Path(dir_path + '/WattBox/' + panel.ssid + '.cfg')
    filename.touch(exist_ok=True)
    file = open(dir_path + '/WattBox/' + panel.ssid + '.cfg', 'w')
    file.write(config[0:index] + panel.ssid)
    file.write(config[index + (len('replacewithssid') - 1) + 1:index2] + panel.ssid)
    file.write(config[index2 + (len('replacewithssid') - 1) + 1:index3] + panel.ssid + config[index3 + 15:len(config)])
    file.close()

    # Creates dynu scripts for panels
    config = dynu.read()
    dynu.close()
    index = config.index('ReplaceWithDynu')

    filename = Path(dir_path + '/Dynu/')
    filename.mkdir(parents=True, exist_ok=True)
    filename = Path(dir_path + '/Dynu/' + panel.ssid + '.rsc')
    filename.touch(exist_ok=True)
    file = open(dir_path + '/Dynu/' + panel.ssid + '.rsc', 'w')
    file.write(config[0:index] + panel.ddnsHostname + config[index + 15:len(config)])
    file.close()
    
    return panel
