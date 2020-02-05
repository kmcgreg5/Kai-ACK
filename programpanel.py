# Written by Kai McGregor for use in Kai-ACK

import sshftpconnection
import time
import os
import datetime
import createfiles
from pubsub import pub as Publisher
import ftplib
import wx

def progPanel1(panel): #gets tik mac, tik sn, and downgrades and runs autoscript
    dir_path = os.path.dirname(os.path.realpath(__file__))
    while True:
        try:
            panel = createfiles.createFiles(panel) #create unit-specific files
            break
        except ValueError:
            dlg = wx.MessageDialog(None, 'Site Files are not set-up correctly, do the following or download edited files:\nIn the Autoscript, replace this line: \'disable telnet,ssh,api-ssl\'\nwith this: \'disable telnet,api-ssl\'\nIn the wattbox.cfg, replace all three ssids with ReplaceWithSSID', 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()
            
    Publisher.sendMessage('status', ssid = panel.ssid, message = 'Unit-specific files created')
    ssh = sshftpconnection.connectSSH(panel.ip, panel.initPassword)
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'interface ethernet print', panel.ip, panel.initPassword) #get MAC
    time.sleep(1)
    ssh.close()
    index = 0
    index2 = 0
    for line in stdout:
        line = line.strip()
        try:
            index = line.index('MAC-ADDRESS')
            index2 = line.index('ARP')
        except ValueError:
            pass

        try:
            newVar = line.index('ether')
            if (panel.tikMAC == ''):
                panel.tikMAC = line[index:index2 - 1]
                break
            
        except ValueError:
            pass
    Publisher.sendMessage('status', ssid = panel.ssid, message = 'Mikrotik MAC stored')
    
    #gets SN
    ssh = sshftpconnection.connectSSH(panel.ip, panel.initPassword)  
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system routerboard print', panel.ip, panel.initPassword)
    time.sleep(1)
    ssh.close()
    for line in stdout:
        line = line.strip()
        try:
            line.index('serial-number')
            if (panel.tikSN == ''):
                panel.tikSN = line[15:len(line)]
        except ValueError:
            pass
    Publisher.sendMessage('status', ssid = panel.ssid, message = 'Mikrotik SN stored')
    if panel.optionsList['Downgrade'] is True:
        fileList = os.listdir(panel.siteDir)
        routerosFileName = None
        for item in fileList:
            if 'routeros' in item.lower() and '.npk' in item.lower():
                routerosFileName = item
                break
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\' + routerosFileName, panel.ssid) #downgrade package
    if panel.optionsList['Autoscript'] is True:
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, dir_path + '\\Autoscript\\' + panel.ssid + '.rsc', panel.ssid, path = '/flash/') #MTAutoscript file
        if panel.newCerts is True:
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\gd_bundle-g2-g1.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\certificate-request_key.pem', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\be258587ac15fd8a.crt', panel.ssid, path = '/flash/') #certificate file
        elif panel.newCerts is None:
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\server.cer', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\server.key', panel.ssid, path = '/flash/') #certificate file
        else:
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\AddTrustExternalCARoot.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\certificate-request_key.pem', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\COMODORSAAddTrustCA.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\COMODORSADomainValidationSecureServerCA.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot_addmydevice_com.crt', panel.ssid, path = '/flash/') #certificate file
    if panel.optionsList['Autoscript'] is True or panel.optionsList['Downgrade'] is True:
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Files Uploaded')
    
    ssh = sshftpconnection.connectSSH(panel.ip, panel.initPassword)            
    #executes reset commands based on options selected
    if panel.optionsList['Autoscript'] is True and panel.optionsList['Downgrade'] is True:
        panel.initPassword = ''
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system package downgrade', panel.ip, panel.initPassword)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system reset-configuration keep-users=no no-defaults=yes skip-backup=no run-after-reset=flash/' + panel.ssid + '.rsc', panel.ip, panel.initPassword)
    elif panel.optionsList['Autoscript'] is False and panel.optionsList['Downgrade'] is True:
        if panel.optionsList['Routerboard'] is True:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system routerboard upgrade', panel.ip, panel.initPassword)
            
        if panel.optionsList['Packages'] is True:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable mpls,ppp,wireless', panel.ip, panel.initPassword)
            
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package downgrade', panel.ip, panel.initPassword)
        panel.progStatus = 2
    elif panel.optionsList['Autoscript'] is True and panel.optionsList['Downgrade'] is False:
        panel.initPassword = ''
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system reset-configuration keep-users=no no-defaults=yes skip-backup=no run-after-reset=flash/' + panel.ssid + '.rsc', panel.ip, panel.initPassword)
    elif panel.optionsList['Autoscript'] is False and panel.optionsList['Downgrade'] is False:
        if panel.optionsList['Routerboard'] is True:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system routerboard upgrade', panel.ip, panel.initPassword)
            panel.progStatus = 2
        else:
            panel.progStatus = 3
        if panel.optionsList['Packages'] is True:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable mpls,ppp,wireless', panel.ip, panel.initPassword)
        if panel.progStatus == 2:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system reboot', panel.ip, panel.initPassword)
            
    time.sleep(1)
    ssh.close()
    if panel.progStatus == 2 or panel.progStatus == 1:
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Panel Resetting')

    return panel

def progPanel2(panel): #uploads login file, sets password, gets wattbox MAC, gets AP MAC fix ip and pass
    dir_path = os.path.dirname(os.path.realpath(__file__))
    if panel.optionsList['Autoscript'] is False:
        try:
            sshftpconnection.ftpDeleteFile(panel.ip, panel.initPassword, 'MTAutoscript.rsc', panel.ssid, path='/flash')
        except ftplib.error_perm:
            pass
        
    ssh = sshftpconnection.connectSSH(panel.ip, panel.initPassword)
    
    if panel.optionsList['2Stage'] is True:
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, dir_path + '\\Dynu\\' + panel.ssid + '.rsc', panel.ssid)
        time.sleep(.5)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'import ' + panel.ssid + '.rsc', panel.ip, panel.initPassword)
        
    loginDate = datetime.date.today()
    if loginDate.month == 1:
        setDate = 'jan/'
    if loginDate.month == 2:
        setDate = 'feb/'
    if loginDate.month == 3:
        setDate = 'mar/'
    if loginDate.month == 4:
        setDate = 'apr/'
    if loginDate.month == 5:
        setDate = 'may/'
    if loginDate.month == 6:
        setDate = 'jun/'
    if loginDate.month == 7:
        setDate = 'jul/'
    if loginDate.month == 8:
        setDate = 'aug/'
    if loginDate.month == 9:
        setDate = 'sep/'
    if loginDate.month == 10:
        setDate = 'oct/'
    if loginDate.month == 11:
        setDate = 'nov/'
    if loginDate.month == 12:
        setDate = 'dec/'

    if len(str(loginDate.day)) == 1:
        setDate += '0' + str(loginDate.day)
    else:
        setDate += str(loginDate.day)
    setDate += '/'
    setDate += str(loginDate.year)
    
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system clock set date=' + setDate, panel.ip, panel.initPassword) #sets date to ensure files are up to date
    if panel.newCerts is not None and panel.optionsList['Login'] is True:
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\login.html', panel.ssid, path = '/flash/hotspot/') #sends login file
    elif panel.newCerts is None and panel.optionsList['Login'] is True:
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\login.html', panel.ssid, path = '/flash/hotspot/')

    if panel.newCerts is None:    
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\alogin.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\error.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\flogin.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\logout.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\md5.js', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\redirect.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\rlogin.html', panel.ssid, path = '/flash/hotspot/')
        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\status.html', panel.ssid, path = '/flash/hotspot/')

        sshftpconnection.ftpSendFile(panel.ip, panel.initPassword, panel.siteDir + '\\hotspot\\img\\logobottom.png', panel.ssid, path = '/flash/hotspot/img/')
        
    if panel.optionsList['Login'] is True and panel.newCerts is not None:
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Login file uploaded')
    else:
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Hotspot files uploaded')
        
    if panel.optionsList['Login'] is False: # delete login file
         ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file remove flash/hotspot/login.html', panel.ip, panel.initPassword)
         Publisher.sendMessage('status', ssid = panel.ssid, message = 'Login file deleted')

    time.sleep(1)
    ssh.close()
    
    if panel.optionsList['Autoscript'] is True:
        sshftpconnection.ftpDeleteFile(panel.ip, panel.initPassword, panel.ssid + '.rsc', panel.ssid, path = '/flash/')
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'MTAutoscript deleted')
    
    #gets AP MAC
    ssh = sshftpconnection.connectSSH(panel.ip, panel.initPassword)
    if panel.optionsList['AP'] is True:
        doOnce = False
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Searching for AP MAC...')
        numCount = 0
        while panel.apMAC.strip() == '':
            if numCount > 4 and doOnce is False:
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'interface set ether5 name=ether5-trunk-AP', panel.ip, panel.initPassword)
                doOnce = True
            
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip arp print where interface=ether5-trunk-AP', panel.ip, panel.initPassword)
            index = ''
            for line in stdout:
                line = line.strip()
                if index == '':
                    try:
                        index = line.index('MAC-ADDRESS')
                    except ValueError:
                        pass
                elif panel.apMAC.strip() == '':
                    panel.apMAC = line[index:index+17]

            time.sleep(.5)
            numCount += 1
            
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'AP MAC stored')

    #gets Wattbox MAC
    if panel.optionsList['Wattbox'] is True:
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Searching for Wattbox MAC...')
        numCount = 0
        doOnce = False
        while panel.wattMAC.strip() == '':
            if numCount > 4 and doOnce is False:
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'interface set ether2-master name=ether2-wattBox', panel.ip, panel.initPassword)
                doOnce = True
                
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip arp print where interface=ether2-wattBox', panel.ip, panel.initPassword)
            index = ''
            for line in stdout:
                line = line.strip()
                if index == '':
                    try:
                        index = line.index('MAC-ADDRESS')
                    except ValueError:
                        pass
                elif panel.wattMAC.strip() == '':
                    panel.wattMAC = line[index:index+17]
                    
            time.sleep(1)
            numCount += 1
            
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Wattbox MAC stored')
    
    #sets password
    if panel.optionsList['Password'] is True:
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'user set admin password=' + panel.sitePassword, panel.ip, panel.initPassword)
        Publisher.sendMessage('status', ssid = panel.ssid, message = 'Mikrotik password set')
    else:
        panel.sitePassword = panel.initPassword
    time.sleep(1)
    ssh.close()
    
    return panel

def qcPanel(panel): # Need to check the packages for routeros version
    Publisher.sendMessage('status', ssid = panel.ssid, message = 'QCing Mikrotik:', group = 4)
    dir_path = os.path.dirname(os.path.realpath(__file__))
    ssh = sshftpconnection.connectSSH(panel.ip, panel.sitePassword)

    # Checks ddns hostname
    if panel.optionsList['Dynu'] is True:
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system script print without-paging from=Dynu', panel.ip, panel.sitePassword)
        ddnsThere = False
        for line in stdout:
            line = line.strip()
            if '\"' + panel.ddnsHostname + '\"' in line:
                ddnsThere = True
                break
    
        if ddnsThere is False:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tFixing DDNS Hostname', group = 4)
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, dir_path + '\\Dynu\\' + panel.ssid + '.rsc', panel.ssid) # DDNS hostname has not been written
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'import ' + panel.ssid + '.rsc', panel.ip, panel.sitePassword)
            time.sleep(1)

    # Checks for script files
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file print without-paging where type=\"script\"', panel.ip, panel.sitePassword)
    indexNumber = None
    numbers = ''
    for line in stdout:
        line = line.strip()
        if numbers != '':
            numbers = numbers + ','
        if indexNumber is not None:
            numbers = numbers + line[indexNumber:indexNumber+1]
        try:
            indexNumber = line.index('#')
        except ValueError:
            pass

    if numbers != '':
        Publisher.sendMessage('status', ssid = panel.ssid, message = '\tRemoving ' + str(numbers.count(',')) + ' script file(s)', group = 4)
        numbers = numbers[0:len(numbers)-1]
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file remove numbers=' + numbers, panel.ip, panel.sitePassword)
        
    # Checks number of files
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file print count-only', panel.ip, panel.sitePassword)
    for line in stdout:
        line = line.strip()
        if line.isdigit() is True:
            fileNum = int(line)
            break
        
    if panel.optionsList['Login'] is True and panel.newCerts is False:
        if fileNum != 36:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tThere are an incorrect number of files (' + str(fileNum) + '), please check manually', group = 4)
    elif panel.optionsList['Login'] is True and (panel.newCerts is True or panel.newCerts is None):
        if fileNum != 34:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tThere are an incorrect number of files (' + str(fileNum) + '), please check manually', group = 4)
    elif panel.optionsList['Login'] is False and panel.newCerts is False:
        if fileNum != 35:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tThere are an incorrect number of files (' + str(fileNum) + '), please check manually', group = 4)
    elif panel.optionsList['Login'] is False and panel.newCerts is True:
        if fileNum != 33:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tThere are an incorrect number of files (' + str(fileNum) + '), please check manually', group = 4)
    
    # Checks certificates
    certificateNum = None
    while certificateNum is None:
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate print count-only', panel.ip, panel.sitePassword)
        for line in stdout:
            line = line.strip()
            if line.isdigit() is True:
                certificateNum = int(line)
                break
        
    if certificateNum != 4: # Re-imports certificates if needed
        Publisher.sendMessage('status', ssid = panel.ssid, message = '\tMissing certificates, Re-importing...', group = 4)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate print', panel.ip, panel.sitePassword)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate remove numbers=0', panel.ip, panel.sitePassword)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate remove numbers=1', panel.ip, panel.sitePassword)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate remove numbers=2', panel.ip, panel.sitePassword)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate remove numbers=3', panel.ip, panel.sitePassword)
        if panel.newCerts is True:
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\be258587ac15fd8a.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\certificate-request_key.pem', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\gd_bundle-g2-g1.crt', panel.ssid, path = '/flash/') #certificate file

            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/be258587ac15fd8a.crt passphrase=\"\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/gd_bundle-g2-g1.crt passphrase=\"\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/certificate-request_key.pem passphrase=\"cvnlab\"', panel.ip, panel.sitePassword)

            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service set www-ssl disabled=no certificate=be258587ac15fd8a.crt_0', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service set api-ssl disabled=no certificate=be258587ac15fd8a.crt_0', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip hotspot profile set hsprof1 ssl-certificate=be258587ac15fd8a.crt_0', panel.ip, panel.sitePassword)
        elif panel.newCerts is None:
            Publisher.sendMessage('status', ssid = panel.ssid, message = '\tThere are an incorrect number of certificates, please reprogram the panel', group = 4)
        else:
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\AddTrustExternalCARoot.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\certificate-request_key.pem', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\COMODORSAAddTrustCA.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\COMODORSADomainValidationSecureServerCA.crt', panel.ssid, path = '/flash/') #certificate file
            sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\hotspot_addmydevice_com.crt', panel.ssid, path = '/flash/') #certificate file
            
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/AddTrustExternalCARoot.crt passphrase=\"\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/COMODORSAAddTrustCA.crt passphrase=\"\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/COMODORSADomainValidationSecureServerCA.crt passphrase=\"\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/hotspot_addmydevice_com.crt passphrase=\"cvnlab\"', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'certificate import file-name=flash/certificate-request_key.pem passphrase=\"cvnlab\"', panel.ip, panel.sitePassword)
            
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service set www-ssl disabled=no certificate=hotspot_addmydevice_com', panel.ip, panel.sitePassword)
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip hotspot profile set hsprof1 ssl-certificate=hotspot_addmydevice_com.crt_0', panel.ip, panel.sitePassword)
    
    # Checks packages and routeros version
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package print without-paging', panel.ip, panel.sitePassword)
    indexName = 0
    indexVersion = 0
    packagesDisabled = False
    downgrade = False
    for line in stdout:
        line = line.strip()
        
        if indexName != 0 and indexVersion != 0:
            if line[indexName:indexVersion].strip() == 'routeros-mmips':
                if '6.40.9' not in line and '6.43.14' not in line: # RouterOS Version is out of date if this is executed
                    Publisher.sendMessage('status', ssid = panel.ssid, message = '\tRouterOS Version out of date, Updating...', group = 4)
                    fileList = os.listdir(panel.siteDir)
                    routerosFileName = None
                    for item in fileList:
                        if 'routeros' in item.lower() and '.npk' in item.lower():
                            routerosFileName = item
                            break
                    sshftpconnection.ftpSendFile(panel.ip, panel.sitePassword, panel.siteDir + '\\' + routerosFileName, panel.ssid)
                    downgrade = True
            elif line[indexName:indexVersion].strip() == 'ipv6':
                if line[indexName-2:indexName-1] == ' ':
                    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable ipv6', panel.ip, panel.sitePassword)
                    packagesDisabled = True
                    print('ipv6 disabled')
            elif line[indexName:indexVersion].strip() == 'wireless':
                if line[indexName-2:indexName-1] == ' ':
                    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable wireless', panel.ip, panel.sitePassword)
                    packagesDisabled = True
                    print('wireless disabled')
            elif line[indexName:indexVersion].strip() == 'mpls':
                if line[indexName-2:indexName-1] == ' ':
                    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable mpls', panel.ip, panel.sitePassword)
                    packagesDisabled = True
                    print('mpls disabled')
            elif line[indexName:indexVersion].strip() == 'ppp':
                if line[indexName-2:indexName-1] == ' ':
                    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package disable ppp', panel.ip, panel.sitePassword)
                    packagesDisabled = True
                    print('ppp disabled')
                    
        try:
            indexName = line.index('NAME')
            indexVersion = line.index('VERSION') - 1
        except ValueError:
            pass
        
                  
    # Checks routerboard
    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system routerboard print without-paging', panel.ip, panel.sitePassword)
    index = 0
    currentFirmware = False
    for line in stdout:
        line = line.strip()
        if 'current-firmware: 3.41' in line or 'current-firmware: 6.43.14' in line:
            currentFirmware = True
            break
        
    # Commands for resets and such
    if packagesDisabled is True:
        Publisher.sendMessage('status', ssid = panel.ssid, message = '\tDisabling some system packages...', group = 4)
        
    if currentFirmware is False:
        Publisher.sendMessage('status', ssid = panel.ssid, message = '\tSystem firware out of date, Updating...', group = 4)
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system routerboard upgrade', panel.ip, panel.sitePassword) # firmware is out of date

    if downgrade is True:
        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system package downgrade', panel.ip, panel.sitePassword)

    if currentFirmware is False or packagesDisabled is True:
        if downgrade is not True:
            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'system reboot', panel.ip, panel.sitePassword)

    ssh.close()

    Publisher.sendMessage('status', ssid = panel.ssid, message = '\tQC Done', group = 4)
