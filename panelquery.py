# Written by Kai McGregor for use in Kai-ACK

import subprocess
import re

# Get arp table for panel interfaces
def getPanelList(): #BETTER USE THIS SETUP
    CREATE_NO_WINDOW = 0x08000000
    arpTables = []
    ipMACList = []
    interfaceIP = None

    # Get ip of interface from cmd return
    cmdCommand = subprocess.Popen(['ipconfig'], stdout = subprocess.PIPE, creationflags = CREATE_NO_WINDOW)
    arpReturn = cmdCommand.communicate()
    arpReturn = str(arpReturn[0])
    if '192.168.88.1' in arpReturn:
        gatewayIndex = arpReturn.index('192.168.88.1')
        while gatewayIndex >= 0:
            if arpReturn[gatewayIndex:gatewayIndex+12] == 'IPv4 Address':
                break
            gatewayIndex -= 1
            
        while gatewayIndex < len(arpReturn):
            if arpReturn[gatewayIndex] == ':':
                interfaceIP = arpReturn[gatewayIndex+2:gatewayIndex+16]
                break
            gatewayIndex += 1

    if '192.168.87.1' in arpReturn:
        gatewayIndex = arpReturn.index('192.168.87.1')
        while gatewayIndex >= 0:
            if arpReturn[gatewayIndex:gatewayIndex+12] == 'IPv4 Address':
                break
            gatewayIndex -= 1
            
        while gatewayIndex < len(arpReturn):
            if arpReturn[gatewayIndex] == ':':
                interfaceIP = arpReturn[gatewayIndex+2:gatewayIndex+16]
                break
            gatewayIndex += 1

    # Return empty array if no interface ip is found
    if interfaceIP is None:
        return []

    # Get arp Table from ip
    cmdCommand = subprocess.Popen(['arp','/a', '/n', interfaceIP], stdout = subprocess.PIPE, creationflags = CREATE_NO_WINDOW)
    arpReturn = cmdCommand.communicate()
    arpTables.append([False, interfaceIP, str(arpReturn[0])])

    for tables in arpTables:
        index = 0
        while tables[0] is False:
            try:
                if tables[1][0:len(tables[1])-4] == '192.168.88':
                    ipIndex = tables[2].index('192.168.88', index)
                    index = ipIndex + 5
                    ip = tables[2][ipIndex:ipIndex + 14]
                    ip = ip.strip()
                    if ip == tables[1] or ip == '192.168.88.255':
                        continue
                    if re.match('192\.168\.88\.\d{1,2}', ip) is not None:
                        ipMACList.append([ip, tables[2][ipIndex + 13 + 9:ipIndex + 13 + 9 + 17]])
                        
                    
                elif tables[1][0:len(tables[1])-4] == '192.168.87':
                    ipIndex = tables[2].index('192.168.87', index)
                    index = ipIndex + 5
                    ip = tables[2][ipIndex:ipIndex + 14]
                    ip = ip.strip()
                    if ip == tables[1] or ip == '192.168.87.255':
                        continue
                    if re.match('192\.168\.87\.\d{1,2}', ip) is not None:
                        ipMACList.append([ip, tables[2][ipIndex + 13 + 9:ipIndex + 13 + 9 + 17]])
                        
            except ValueError:
                tables[0] = True

    # Replace hyphens with colons
    x = 0
    while x < len(ipMACList):
        ipMACList[x][1] = ipMACList[x][1].replace('-',':')
        x += 1
     
    return ipMACList

# Increment a hex number by one
def getHexNum(int3MAC):
    int3MAC = int3MAC.replace(':', '')
    int3MAC = hex(int('0x' + int3MAC, 16) + 1)[2:]
    int3MAC = ':'.join(a+b for a,b in zip(int3MAC[::2], int3MAC[1::2]))

    return int3MAC

if __name__ == '__main__':
    print(getPanelList())
