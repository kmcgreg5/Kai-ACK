# David Johnson
# Implementation into UI done by Kai McGregor
# v 1.1
'''
In case SSH and FTP is disabled once Kai-ACK tries to log in, the program
will need to attempt to enable them through using the API service (port 8728).

We use a library called 'librouteros' that allows us to communicate directly to
the MikroTik through the API using Python.

https://librouteros.readthedocs.io

************NOT COMPATIBLE WITH ROUTER_OS 6.43 AND UP**************************
'''

import librouteros  # library used to communciate with MikroTik API + Python
from librouteros import connect  # imported so we can rip code directly off doc
import json
import socket  # used to except connection errors
import time

def enableServices(ip, password):
    try:
        sshStatus = False  # these get disabled at the end if it works correctly
        ftpStatus = False  # these get disabled at the end if it works correctly

        # *******SERVICE ENABLING STARTS*********
        api = connect(username='admin', password=password, host=ip)
        serviceList = api(cmd='/ip/service/print')

        # services are checked & recorded
        for service in serviceList:
            if service['name'] == 'ssh':
                sshID = service['.id']
            if service['name'] == 'ftp':
                ftpID = service['.id']

        # **************SSH ENABLES***************
        sshBody = {
            '.id': sshID
        }
        sshResult = api(cmd='/ip/service/enable', **sshBody)

        # ************FTP ENABLES****************
        ftpBody = {
        '.id': ftpID
        }
        ftpResult = api(cmd='/ip/service/enable', **ftpBody)

        # ******VERIFY SERVICES GOT ENABLED******
        serviceList = api(cmd='/ip/service/print')
        for service in serviceList:
            if service['name'] == 'ssh' and service['disabled'] is False:
                sshStatus = True
            if service['name'] == 'ftp' and service['disabled'] is False:
                ftpStatus = True

        # happens if services don't enable at the end
        if (sshStatus or ftpStatus) is False:
            print('Service enable failed.')
            return False  # Kai-ACK will work around the issue
        else:
            api(cmd='/quit')
            return True  # Kai-ACK accepts our response and continues



    except (librouteros.exceptions.ConnectionError, socket.gaierror):
        print("Couldn't log into MikroTik.")
        print('Please manually check the following:\n\n  \
        Port 8728 must be enabled.\n  \
        MikroTik IP is either 192.168.88.1 or 192.168.87.1\n')

def disableSSH(ip, password):
    while True:
        try:
            api = connect(username='admin', password = password, host= ip)
            serviceList = api(cmd='/ip/service/print')

            for service in serviceList:
                if service['name'] == 'ssh' and service['disabled'] is False:
                    api(cmd='/ip/service/disable', **{'.id' : service['.id']})

            try:
                api(cmd='/quit')
            except librouteros.exceptions.FatalError:
                pass

            break
        except (librouteros.exceptions.ConnectionError, socket.gaierror):
            time.sleep(.5)

def testAuth(ip, password):
    try:
        api = connect(username='admin', password=password, host=ip)
        api(cmd='/ip/service/print')
        try:
            api(cmd='/quit')
        except librouteros.exceptions.FatalError:
            pass
    except (librouteros.exceptions.ConnectionError, socket.gaierror):
        pass
    
    # except librouteros.exceptions.FatalError:
    #     print('Password incorrect on MikroTik API login.')

