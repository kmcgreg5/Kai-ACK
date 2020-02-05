# Written by Kai McGregor for use in Kai-ACK

# Kai's Libraries
import googlesheets
import panelquery
import programpanel
import sshftpconnection
import wattbox
import optionsMenu

# David's Libraries
import RuckusLibrary
import mikrotikAPI

# Public Libraries
import time
import wx
import re
import os
import sys
from oauth2client.service_account import ServiceAccountCredentials
import datetime
from datetime import date
from pathlib import Path
import pexpect
from pexpect import popen_spawn
import _pickle as cPickle
from cryptography.fernet import Fernet
import json
import select

# Libraries for multitasking
from threading import Thread, Event
from pubsub import pub as Publisher

# Libraries for exceptions
import urllib3
import gspread
import httplib2
import requests
import paramiko
import splinter
import selenium
import ftplib
import pubsub
import librouteros
from xml.etree import ElementTree

# Libraries for error reporting
import traceback
from functools import wraps

urllib3.disable_warnings(paramiko.ssh_exception.SSHException) # Disables error text from ssh connection failure, exception is still caught

programMainThread = None # Main programming thread
programThreads = [] # List of threads for programming panels
MAXPANELS = 8 # Max number of panels allowed to be programmed at a time, constant
   
def resource_path(relative_path): # Get file path of files embeded into exe, there aren't any but its here for future use
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# Catch and report unhandled exceptions
def catchExceptions(eType, value, trace): # This function replaces sys.excepthook and grabs all required information from Kai-ACK
    # Format exception to be readable
    tmp = traceback.format_exception(eType, value, trace)
    exception = "".join(tmp)

    # Get program information
    programmerName = kaiack.UI.programmerNameTextBox.GetValue()
    statusText = []
    for item in kaiack.UI.statusText:
        collectedText = ''
        for text in item:
            collectedText = collectedText + text + '\n'
        statusText.append(collectedText)

    fileList = os.listdir(os.getcwd())
    programVersion = 'Not Found'
    for item in fileList:
        if 'kai-ack' in item.lower() and '.exe' in item.lower():
            programVersion = item
            break

    # Open thread to send report to Google Sheets
    uploadException(programmerName, programVersion, exception, statusText)

    dlg = wx.MessageDialog(None, 'An Error has occurred, it has been uploaded and will be reviewed shortly', 'Error', wx.OK | wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()

sys.excepthook = catchExceptions

# Redirects tracebacks from other threads, @https://bugs.python.org/issue1230540
def use_my_excepthook(view):
    """ Redirect any unexpected tracebacks """ 
    @wraps(view)
    def run(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except:
            sys.excepthook(*sys.exc_info())
    return run

# Uploads exception to the Google Sheets error sheet
class uploadException(Thread):
    def __init__(self, programmerName, programVersion, exception, statusText):
        self.programmerName = programmerName
        self.programVersion = programVersion
        self.exception = exception
        self.statusText = statusText
        Thread.__init__(self)
        self.daemon = False
        self.start()

    def run(self):
        self.writeToDoc()

    def writeToDoc(self):
        while True:
            try:
                # Get sheet information
                scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                
                authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                gc = gspread.authorize(authorization)
                wks = gc.open('Kai-ACK Errors').worksheet('Errors')

                # find row placement of new error
                colValues = wks.col_values(1)
                errorIndex = 0
                while errorIndex < len(colValues):
                    if colValues[errorIndex].strip() == '':
                        break
                    errorIndex += 1
                    
                errorIndex += 1
                # Get time for timestamp
                time = datetime.datetime.now()
                # Create cellList to write
                cellList = []
                cellList.append(gspread.models.Cell(errorIndex, 1, value = time.strftime("%Y-%m-%d %H:%M")))
                cellList.append(gspread.models.Cell(errorIndex, 3, value = self.programVersion))
                cellList.append(gspread.models.Cell(errorIndex, 4, value = self.programmerName))
                cellList.append(gspread.models.Cell(errorIndex, 5, value = self.exception))
                x = 6
                for item in self.statusText:
                    cellList.append(gspread.models.Cell(errorIndex, x, value = item))
                    x += 1

                wks.update_cells(cellList)
                break
            except (httplib2.ServerNotFoundError, AttributeError) as error:
                time.sleep(3)

# Returns a number of spaces according to the int passed in
def numSpaces(num):
    x = 0
    spaces = ''
    while x < num:
        spaces = spaces + ' '
        x += 1

    return spaces

# Tests controller when site data is loaded from file
class testController(Thread):
    def __init__(self, siteData):
        self.siteData = siteData
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook # decorator used to redirect exceptions
    def run(self):
        self.testConnection()

    def testConnection(self):
        message = ''
        kaiack.UI.loadSpreadsheetDataButton.Disable()
        # Uses AP zone if it has been filled in before clicking 'Load Site Data'
        if kaiack.UI.optionsList['No NAF'] is False:
            if self.siteData.apZone is not None and kaiack.UI.apZoneTextBox.GetValue().strip() == '':
                kaiack.UI.apZoneTextBox.SetValue(self.siteData.apZone)
                
            kaiack.UI.controllerIPTextBox.SetValue(self.siteData.controllerIP)
        
        # Tests controller IP if the AP option is enabled
        if kaiack.UI.optionsList['AP'] is True:
            if kaiack.UI.optionsList['No NAF'] is False:
                if self.siteData.controllerIP == '':
                    message = message + 'Controller IP not found on NAF, check worksheet page names to make sure\nthey match \'Network Activation Form\' and \'Programming\'\n'
            if kaiack.UI.apZoneTextBox.GetValue().strip() == '':
                message = message + 'No AP zone name found, please input it manually\n'
                
            if message == '': # Tests controller IP
                # Creates controllerCluster list off of the first IP
                if kaiack.UI.optionsList['No NAF'] is True or kaiack.UI.optionsList['Controller'] is True:
                    username = kaiack.UI.clusterSelection[1]
                    password = kaiack.UI.clusterSelection[2]
                    port = kaiack.UI.clusterSelection[4]
                    ipList = kaiack.UI.clusterSelection[5]

                    kaiack.UI.controllerIPTextBox.SetValue(kaiack.UI.clusterSelection[5][0])
                else:
                    username = kaiack.UI.username
                    password = kaiack.UI.password
                    port = '8443'
                    
                    ipList = []
                    ip = kaiack.UI.controllerIPTextBox.GetValue().strip()
                    x = len(ip) - 1
                    while x < len(ip):
                        if ip[x] == '.':
                            index = x
                            break
                        x -= 1

                    # Get index of last digits in the ip
                    x = 0
                    newIpEnd = int(ip[index+1:len(ip)])
                    while x < 4:
                       ipList.append(ip[0:index+1] + str(newIpEnd + x))
                       x += 1
                

                # Test the connection here
                controllerConnection = RuckusLibrary.programKaiACK(RuckusLibrary.controllerInputObject(username, password, ipList, port, kaiack.UI.apZoneTextBox.GetValue().strip()))
                response = controllerConnection.kaiACKRetrieveZoneInfo()
                
                if response == 200: # Success
                    kaiack.UI.controller = controllerConnection
                elif response is False: # No response from IPs
                    message = message + 'No response from the controller IPs\n'
                elif response is None: # No internet connection or something
                    message = message + 'No response from the controller IPs\n'
                elif response == 202: # Bad login
                    message = message + 'Authentication is incorrect, this can be changed in Advanced Options\n'
                elif response == 404: # AP zone name not found in list
                    message = message + 'AP zone name is not found on the controller\n'
                    
            else:    
                kaiack.UI.controllerIPTextBox.SetValue('')

        # Returns site data to the UI
        Publisher.sendMessage('spreadsheet', sheetData = self.siteData, message = message)
        
# Blinking dots when site data is loaded, very important
class dots(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.blinkingDots()

    def blinkingDots(self):
        # Write and clears the status textbox
        while kaiack.UI.loadSpreadsheetDataButton.IsEnabled() is False and kaiack.UI.sheetData is None:
            kaiack.UI.panelStatusText.SetValue('')
            kaiack.UI.panelStatusText.write('\n\n\n\n\n\n\n\n\n\t\t\t         ')
    
            kaiack.UI.panelStatusText.write('Retrieving Site Data')
            time.sleep(.5)
            kaiack.UI.panelStatusText.write('.')
            time.sleep(.5)
            kaiack.UI.panelStatusText.write('.')
            time.sleep(.5)
            kaiack.UI.panelStatusText.write('.')
            time.sleep(.5)
            kaiack.UI.panelStatusText.write('.')

        kaiack.UI.panelStatusText.SetValue('')

# Timer to stop progress to next step until mikrotik has been downgraded
class panelTimer(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.timer()

    def timer(self):
        x = 0
        sendMessage = True
        while x < 211:
            Publisher.sendMessage('timer', time = x)
            time.sleep(1)
            if kaiack.UI.downgradeConfigPanel is False:
                sendMessage = False
            else:
                sendMessage = True
            x += 1

        if sendMessage is True:
            Publisher.sendMessage('status', ssid = 'Downgrade Config', message='1st Panel is ready for step 2')
            
        kaiack.UI.panelReady = True

# Generically downgrades and runs the autoscript on connected panels with the ip 192.168.88.1 and 192.168.87.1 with the refurb option checked
class resetPanelsThread(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.resetMikrotik()

    def resetMikrotik(self):
        countNum = 1 # Display number for how many panels have been programmed in the current session
        macList = [] # List of previously programmed mac addresses
        kaiack.UI.downgradeThreadOpen = True
        time.sleep(5)
        while kaiack.UI.downgradeConfigPanel:
            ipMACList = panelquery.getPanelList() #gets arp table
            panelFound = False
            ip = None
            for x in ipMACList: #searches for panel ip
                panelMAC = ''
                if x[0] == "192.168.88.1":
                    panelFound = True
                    ip = '192.168.88.1'
                    panelMAC = x[1]
                    break
                if kaiack.UI.optionsList['Refurb'] is True and x[0] == "192.168.87.1":
                    panelFound = True
                    ip = '192.168.87.1'
                    panelMAC = x[1]
                    break

            # Searches previously reset panels and doesnt reset them
            for mac in macList:
                if mac == panelMAC or panelquery.getHexNum(mac) == panelMAC:
                    panelFound = False

            # Resets the found panel
            if panelFound is True:
                macList.append(panelMAC)
                if countNum == 1 and kaiack.UI.optionsList['Timer'] is True:
                    kaiack.UI.panelReady = False
                    
                Publisher.sendMessage('status', ssid = 'Downgrade Config', message=str(countNum))
                countNum += 1
                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Panel Found')

                # Test credentials here
                password = ''
                passwordTested = False
                panelPasswordTested = False
                APITried = False
                if kaiack.UI.optionsList['Refurb'] is True:
                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Checking Panel Password')
                    while True:
                        message = ''
                        try:
                            sshftpconnection.testMikrotikAuth(ip, password)
                            ssh = sshftpconnection.connectSSH(ip, password)
                            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service enable ftp', ip, password)
                            ssh.close()
                            break
                        except paramiko.ssh_exception.NoValidConnectionsError: # port disabled
                            Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Enabling SSH...')
                            passwordTested = False
                            ftpTried = False
                            panelPasswordTested = False
                            while True:
                                message = ''
                                try:
                                    sshftpconnection.enableSSH(ip, password, 'enableSSH.auto.rsc')
                                    break
                                except ConnectionRefusedError: # Both ssh and ftp are disabled, use API to enable ssh and ftp
                                    passwordTested = False
                                    panelPasswordTested = False
                                    while True:
                                        try:
                                            mikrotikAPI.enableServices(ip, password)
                                            break
                                        except librouteros.exceptions.FatalError as error:
                                            if 'not logged in' in str(error):
                                                if password == '' and passwordTested is False and APITried is False:
                                                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message = 'Enabling SSH and FTP, authentication failed, defaulting to site password')
                                                    passwordFile = open(kaiack.UI.siteDir + '\\Password.txt','r')
                                                    password = passwordFile.read().strip() #gets password from file
                                                    passwordFile.close()
                                                    passwordTested = True
                                                elif passwordTested is True and password != '' and panelPasswordTested is False and APITried is False:
                                                    if kaiack.UI.panelPassword is None:
                                                        panelPasswordTested = True
                                                    else:
                                                        Publisher.sendMessage('status', ssid = 'Downgrade Config', message = 'Authentication Failed, testing previous credentials')
                                                        password = kaiack.UI.panelPassword
                                                        panelPasswordTested = True
                                                elif passwordTested is True and password != '' and panelPasswordTested is True and APITried is False:
                                                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message = 'Authentication Failed, searching master password list')
                                                    scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                                    
                                                    authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                                    
                                                    wks = None
                                                    while True:
                                                        try:
                                                            gc = gspread.authorize(authorization)
                                                            wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                                            break
                                                        except gspread.exceptions.SpreadsheetNotFound:
                                                            #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                                            passwordTested = ''
                                                            break
                                                        except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                                            #No Internet Connection
                                                            print('Connection Error')
                                                        except IndexError: # Just in case
                                                            #Error Getting Data From Spreadsheet
                                                            passwordTested = ''
                                                            break
                                                        
                                                    if wks is not None:
                                                        passwordFound = False
                                                        passList = wks.col_values(2)
                                                        del passList[0]
                                                        x = 0
                                                        while x < len(passList):
                                                            passList[x] = passList[x].strip()
                                                            x += 1
                                                            
                                                        x = 0
                                                        while x < len(passList):
                                                            if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                                                x += 1
                                                                continue
                                                            try:
                                                                mikrotikAPI.enableServices(ip, passList[x])
                                                                Publisher.sendMessage('status', ssid = 'Downgrade Config', message = 'Password Found: ' + passList[x])
                                                                password = passList[x]
                                                                kaiack.UI.panelPassword = passList[x]
                                                                passwordFound = True
                                                                break
                                                            except (OSError, ConnectionResetError, ConnectionAbortedError):
                                                                x -= 1
                                                            except librouteros.exceptions.FatalError as error:
                                                                if 'not logged in' not in str(error):
                                                                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message = 'Password Found: ' + passList[x])
                                                                    password = passList[x]
                                                                    kaiack.UI.panelPassword = passList[x]
                                                                    passwordFound = True
                                                                    break
                                                            x += 1

                                                        if passwordFound is False:
                                                            APITried = True
                                                            passwordTested = ''
                                                else:
                                                    #Authentication failed, reset
                                                    password = ''
                                                    message = 'Authentication Failed, please reset Mikrotik password'
                                                    
                                                    dlg = wx.MessageDialog(None, message, 'Error', wx.OK)
                                                    dlg.ShowModal()
                                                    dlg.Destroy()
                                                    message = ''
                                                    break
                                            else:
                                                message = ''
                                                break
                                            
                                except (OSError, ConnectionResetError, ConnectionAbortedError):
                                    print('connection error')
                                    time.sleep(2)
                                except ftplib.error_perm:
                                    if password == '' and passwordTested is False and ftpTried is False:
                                        # Publisher message
                                        Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Site Password')
                                        passwordFile = open(kaiack.UI.siteDir + '\\Password.txt', 'r')
                                        password = passwordFile.read().strip()
                                        passwordFile.close()
                                        passwordTested = True
                                    elif passwordTested is True and password != '' and ftpTried is False and panelPasswordTested is False:
                                        
                                        if kaiack.UI.panelPassword is None:
                                            panelPasswordTested = True
                                        else:
                                            # Publisher message
                                            Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Previous Password')
                                            password = kaiack.UI.panelPassword
                                            panelPasswordTested = True
                                    elif passwordTested is True and password != '' and ftpTried is False and panelPasswordTested is True:
                                        # Publisher message
                                        Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Master Password List')
                                        scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                        
                                        authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                        
                                        wks = None
                                        while True:
                                            try:
                                                gc = gspread.authorize(authorization)
                                                wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                                break
                                            except gspread.exceptions.SpreadsheetNotFound:
                                                #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                                passwordTested = ''
                                                break
                                            except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                                #No Internet Connection
                                                print('Connection Error')
                                            except IndexError: # Just in case
                                                #Error Getting Data From Spreadsheet
                                                passwordTested = ''
                                                break

                                        if wks is not None:
                                            passwordFound = False
                                            passList = wks.col_values(2)
                                            del passList[0]
                                            x = 0
                                            while x < len(passList):
                                                passList[x] = passList[x].strip()
                                                x += 1
                                                
                                            x = 0
                                            while x < len(passList):
                                                if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                                    x += 1
                                                    continue
                                                
                                                try:
                                                    sshftpconnection.enableSSH(ip, passList[x], 'enableSSH.auto.rsc')
                                                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Password Found: ' + passList[x])
                                                    password = passList[x]
                                                    kaiack.UI.panelPassword = passList[x]
                                                    passwordFound = True
                                                    break
                                                except (OSError, ConnectionResetError, ConnectionAbortedError):
                                                    x -= 1
                                                except ftplib.error_perm:
                                                    pass
                                                x += 1

                                            if passwordFound is False:
                                                message = 'Reset Mikrotik Password'
                                                passwordTested = ''

                                    else:
                                        # Authentication Failed, reset
                                        # Publisher message
                                        message = 'Reset Mikrotik Password'
                                        password = ''
                                        ftpTried = True
                                        break

                                if message != '':
                                    dlg = wx.MessageDialog(None, message, 'Error', wx.OK)
                                    dlg.ShowModal()
                                    dlg.Destroy()
                                    
                        except paramiko.ssh_exception.AuthenticationException:
                            if password == '' and passwordTested is False:
                                # Publisher message
                                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Site Password')
                                passwordFile = open(kaiack.UI.siteDir + '\\Password.txt', 'r')
                                password = passwordFile.read().strip()
                                passwordFile.close()
                                passwordTested = True
                            elif passwordTested is True and panelPasswordTested is False:
                                print(kaiack.UI.panelPassword)
                                if kaiack.UI.panelPassword is None:
                                    panelPasswordTested = True
                                else:
                                    # Publisher message
                                    Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Previous Password')
                                    password = kaiack.UI.panelPassword
                                    panelPasswordTested = True

                            elif passwordTested is True and password != '' and panelPasswordTested is True:
                                # Publisher message
                                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Testing Master Password List')
                                scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                
                                authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                
                                wks = None
                                while True:
                                    try:
                                        gc = gspread.authorize(authorization)
                                        wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                        break
                                    except gspread.exceptions.SpreadsheetNotFound:
                                        #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                        passwordTested = ''
                                        break
                                    except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                        #No Internet Connection
                                        print('Connection Error')
                                    except IndexError: # Just in case
                                        #Error Getting Data From Spreadsheet
                                        passwordTested = ''
                                        break
                                    
                                if wks is not None:
                                    passwordFound = False
                                    passList = wks.col_values(2)
                                    del passList[0]
                                    x = 0
                                    while x < len(passList):
                                        passList[x] = passList[x].strip()
                                        x += 1
                                        
                                    x = 0
                                    while x < len(passList):
                                        if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                            x += 1
                                            continue
                                        
                                        try:
                                            sshftpconnection.testMikrotikAuth(ip, passList[x])
                                            Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Password Found: ' + passList[x])
                                            password = passList[x]
                                            kaiack.UI.panelPassword = passList[x]
                                            passwordFound = True
                                            break
                                        except paramiko.ssh_exception.AuthenticationException:
                                            pass

                                        x += 1

                                    if passwordFound is False:
                                        message = 'Reset Mikrotik Password'
                                        passwordTested = ''

                            else:
                                message = 'Reset Mikrotik Password'
                                password = ''

                        except (paramiko.ssh_exception.SSHException, TimeoutError, ConnectionAbortedError, ConnectionResetError, EOFError):
                            print('exception caught')

                        if message != '':
                            dlg = wx.MessageDialog(None, message, 'Error', wx.OK)
                            dlg.ShowModal()
                            dlg.Destroy()

                        time.sleep(3)
                                        
                # Connects to SSH
                ssh = sshftpconnection.connectSSH(ip, password)
                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='SSH Connected')

                # Clears files that are not recognized
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file print without-paging detail', ip, password)

                numbers = []
                for line in stdout:
                    line = line.strip()
                    if len(line) != 0:
                        
                        if line[0].isdigit() and (line[2:6] == 'name' or line[3:7] == 'name'):
                            index1 = line.index('\"') + 1
                            index2 = line.index('\"', index1)
                            name = line[index1:index2]
                            if name != 'flash' and name != 'flash/skins':
                                numbers.append(line[0:2].strip())

                # Format found files with commas
                filesRemoved = ''
                for num in numbers:
                    filesRemoved = filesRemoved + num + ','
                if len(filesRemoved) >= 1:
                    if filesRemoved[len(filesRemoved)-1] == ',':
                        filesRemoved = filesRemoved[0:len(filesRemoved)-1]

                ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'file remove numbers=' + filesRemoved, ip, password)
                
                # Uploads the required files
                fileList = os.listdir(kaiack.UI.siteDir)
                routerosFileName = None
                for item in fileList:
                    if 'routeros' in item.lower() and '.npk' in item.lower():
                        routerosFileName = item
                        break
                sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\' + routerosFileName, 'Downgrade Config') #downgrade package
                sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\MTAutoscript.rsc', 'Downgrade Config', path = '/flash/') #MTAutoscript file
                # Uploads new or old certs depending on the site files chosen
                if kaiack.UI.newCerts is True:
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\gd_bundle-g2-g1.crt', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\certificate-request_key.pem', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\be258587ac15fd8a.crt', 'Downgrade Config', path = '/flash/') #certificate file
                elif kaiack.UI.newCerts is None:
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\server.cer', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\server.key', 'Downgrade Config', path = '/flash/') #certificate file
                else:
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\AddTrustExternalCARoot.crt', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\certificate-request_key.pem', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\COMODORSAAddTrustCA.crt', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\COMODORSADomainValidationSecureServerCA.crt', 'Downgrade Config', path = '/flash/') #certificate file
                    sshftpconnection.ftpSendFile(ip, password, kaiack.UI.siteDir + '\\hotspot_addmydevice_com.crt', 'Downgrade Config', path = '/flash/') #certificate file
                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Files Uploaded')

                
                # Executes reset commands
                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Panel Resetting...')
                # Enable packages in order to indicate MTAutoscript progress
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system package enable mpls', ip, password)
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system package enable ppp', ip, password)
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system package enable wireless', ip, password)
                # Execute reset commands
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system package downgrade', ip, password)
                ssh, stdout = sshftpconnection.sshSendCommand(ssh, ':system reset-configuration keep-users=no no-defaults=yes skip-backup=no run-after-reset=flash/MTAutoscript.rsc', ip, password)
                time.sleep(1)
                ssh.close()

                # Wait until ip is out of the arp table
                exceptionVar = True
                while exceptionVar:
                    if kaiack.UI.downgradeConfigPanel is False:
                        break
                    time.sleep(2)
                    ipMACList = panelquery.getPanelList()
                    exceptionVar = False
                    for x in ipMACList:
                        if x[0] == ip:
                            exceptionVar = True

                Publisher.sendMessage('status', ssid = 'Downgrade Config', message='Panel Done \n \n')
                if countNum == 2 and kaiack.UI.optionsList['Timer'] is True:
                    panelTimer()

        print('Downgrade thread down')
        kaiack.UI.downgradeThreadOpen = False

# Thread to start the programming of double APs
class programDoubleAPsThread(Thread):
    def __init__(self, sheetData):
        Thread.__init__(self)
        self.sheetData = sheetData
        
        self.daemon = True
        self.start()
        
    @use_my_excepthook
    def run(self):
        self.programDoubleAPs()

    def programDoubleAPs(self):
        doubleAPList = self.sheetData.programDoubleAPList(kaiack.UI.programmerNameTextBox.GetValue())
        if len(doubleAPList) == 0: # Displays message if no double aps are found
            dlg = wx.MessageDialog(None, 'No Double APs Found', 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            apMACList = googlesheets.getNewList(self.sheetData.wks.col_values(self.sheetData.apMACIndex), self.sheetData.panelStartIndex, self.sheetData.panelEndIndex)
            doubleAPList = kaiack.UI.controller.programDoubleAP(self.sheetData.ssidList, apMACList, doubleAPList)
            if doubleAPList != 403 and doubleAPList is not False:
                self.sheetData.writeDoubleAP(doubleAPList)
            Publisher.sendMessage('status', ssid='Double APs', message='\nDone')
        
        kaiack.UI.programDoubleAPsButton.Enable()

class spreadsheetThread(Thread): # Thread for gathering spreadsheet data
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.getSheetData()        

    def getSheetData(self):
        message = ''
        try:
            kaiack.UI.loadSpreadsheetDataButton.Disable()
            sheetData = googlesheets.spreadsheetData(kaiack.UI.siteNameTextBox.GetValue(), kaiack.UI.siteDir)
            if sheetData.apZone is not None and kaiack.UI.apZoneTextBox.GetValue().strip() == '':
                kaiack.UI.apZoneTextBox.SetValue(sheetData.apZone)
                
            kaiack.UI.controllerIPTextBox.SetValue(sheetData.controllerIP)
            
            if kaiack.UI.optionsList['AP'] is True:
                if sheetData.controllerIP == '':
                    message = message + 'Controller IP not found on NAF, check worksheet page names to make sure\nthey match \'Network Activation Form\' and \'Programming\'\n'
                if kaiack.UI.apZoneTextBox.GetValue().strip() == '':
                    message = message + 'No AP zone name found, please input it manually\n'
                    
                if message == '': # Tests controller IP
                    # Creates controllerCluster list off of the first IP
                    if kaiack.UI.optionsList['Controller'] is True:
                        ipList = kaiack.UI.clusterSelection[5]
                        username = kaiack.UI.clusterSelection[1]
                        password = kaiack.UI.clusterSelection[2]
                        port = kaiack.UI.clusterSelection[4]
                        kaiack.UI.controllerIPTextBox.SetValue(kaiack.UI.clusterSelection[5][0])
                    else:
                        username = kaiack.UI.username
                        password = kaiack.UI.password
                        port = '8443'
                        ipList = []
                        Ip = kaiack.UI.controllerIPTextBox.GetValue().strip()
                        x = 0
                        index = Ip.index('.', 7)
                        newIpEnd = int(Ip[index+1:len(Ip)])
                        while x < 4:
                           ipList.append(Ip[0:index+1] + str(newIpEnd + x))
                           x += 1

                    controllerConnection = RuckusLibrary.programKaiACK(RuckusLibrary.controllerInputObject(username, password, ipList, port, kaiack.UI.apZoneTextBox.GetValue().strip()))
                    response = controllerConnection.kaiACKRetrieveZoneInfo()

                    if response == 200: # Success
                        kaiack.UI.controller = controllerConnection
                    elif response is False: # No response from IPs
                        message = message + 'No response from the controller IPs\n'
                    elif response is None: # No response from IPs
                        message = message + 'No response from the controller IPs\n'
                    elif response == 202: # Bad login
                        message = message + 'Authentication is incorrect, this can be changed in Advanced Options\n'
                    elif response == 404: # AP zone name not found in list
                        message = message + 'AP zone name is not found on the controller\n'
                        
                else:    
                    kaiack.UI.controllerIPTextBox.SetValue('')
                            
        except gspread.exceptions.SpreadsheetNotFound:
            sheetData = None
            message = "Spreadsheet Not Found \nMake sure the service account has been added \nor check the spreadsheet name entered"
            
        except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
            sheetData = None
            message = "No Internet Connection"

        except IndexError as error: # Just in case
            sheetData = None
            traceback.print_tb(error.__traceback__)
            message = "Error Getting Data From Spreadsheet"

        Publisher.sendMessage('spreadsheet', sheetData = sheetData, message = message)

class programmerPanelsThread(Thread): # Gets panel list for programmer name
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.getPanels()

    def getPanels(self):
        kaiack.UI.getPanelsThreadOpen = True
        message = ''
        
        programmerList = None
        if kaiack.UI.sheetData is None:
            message = 'Site Data Not Loaded'
        else:
            try:
                kaiack.UI.sheetData.completedList = kaiack.UI.sheetData.getCompletedPanels()
                programmerList = kaiack.UI.sheetData.getProgrammerList(kaiack.UI.programmerNameTextBox.GetValue())
                message = 'Panel List Grabbed for ' + kaiack.UI.programmerNameTextBox.GetValue()
                text = ''    
                for ssid in programmerList:
                    continueVar = False
                    for panel in kaiack.UI.currentPanelList:
                        if ssid == panel.ssid:
                            programmerList.remove(ssid)
                            continueVar = True
                    if continueVar is True:
                        continue
                    text = text + ssid + ', '
                text = text[:len(text)-2]
                print('Panels Grabbed: ' + text)
            except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError):
                message = 'No Internet Connection'
                
        Publisher.sendMessage('panelList', panelList = programmerList, message = message)
        kaiack.UI.getPanelsThreadOpen = False

class panelQueryThread(Thread): # Gets panels ips and macs from arp table
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.panelQuery()

    def panelQuery(self):
        kaiack.UI.panelQueryThreadOpen = True
        while kaiack.UI.programPanel == True:
            Publisher.sendMessage('panelquery', panelList = panelquery.getPanelList())
            time.sleep(3)

        kaiack.UI.panelQueryThreadOpen = False

class panelProgramMainThread(Thread): # Loop that starts programming process
    def __init__(self, currentPanelList):
        Thread.__init__(self)
        self.currentPanelList = currentPanelList
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.startProgram()

    def startProgram(self):
        global programThreads
        global MAXPANELS
        kaiack.UI.mainPanelThreadOpen = True
        while kaiack.UI.programPanel == True:
            time.sleep(3)
            x = 0
            while x < len(self.currentPanelList):
                if self.currentPanelList[x].progStatus == 0:
                    self.currentPanelList[x].progStatus = 1
                    if len(programThreads) < MAXPANELS: # Max number of panels programming at once
                        programThreads.append([self.currentPanelList[x].ssid, panelProgramThread(self.currentPanelList[x])])
                x += 1
                
        kaiack.UI.mainPanelThreadOpen = False
   
class wattboxProgramThread(Thread):
    def __init__(self, panel, ip):
        self.panel = panel
        self.ip = ip
        self._return = None
        Thread.__init__(self)
        self.threadStopped = Event()
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.programWattbox()

    def join(self):
        Thread.join(self)
        return self._return

    def programWattbox(self):
        passwordTested = False
        panelPasswordTested = False
        while True:
            try:
                if self.threadStopped.is_set() is True: # Event for stopping the thread
                    print('Wattbox Thread Stopped')
                    return None
                
                self.panel = wattbox.configWattbox(self.panel, self.ip, passwordTested) # config the wattbox and get wattbox serial number
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Wattbox SN Stored', group = 2)
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Wattbox configured', group = 2)
                break
            except splinter.exceptions.ElementDoesNotExist: # Catches error if the wattbox is not at default configuration
                if passwordTested is False: # Site Password
                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Wattbox credentials are not default, testing site credentials', group = 2)
                    passwordTested = True
                elif passwordTested is True and kaiack.UI.panelPassword is not None and panelPasswordTested is False: # Previous Password
                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Wattbox credentials are not default, testing previous credentials', group = 2)
                    passwordTested = kaiack.UI.panelPassword
                    panelPasswordTested = True
                elif passwordTested is True or panelPasswordTested is True: # Master Password List
                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Testing master password list for Wattbox authentication...', group = 2)
                    scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                    
                    authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)

                    # Load Master Password List Sheet
                    wks = None
                    while True:
                        try:
                            gc = gspread.authorize(authorization)
                            wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                            break
                        except gspread.exceptions.SpreadsheetNotFound:
                            #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                            passwordTested = ''
                            break
                        except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                            #No Internet Connection
                            print('Connection Error')
                        except IndexError: # Just in case
                            #Error Getting Data From Spreadsheet
                            passwordTested = ''
                            break
                        
                    if wks is not None:
                        passwordFound = False
                        passList = wks.col_values(2)
                        del passList[0]
                        x = 0
                        while x < len(passList):
                            passList[x] = passList[x].strip()
                            x += 1
                            
                        x = 0
                        while x < len(passList): # Tests authentication from the loaded list
                            if self.threadStopped.is_set() is True: # Event for stopping the thread
                                print('Wattbox Thread Stopped')
                                return None
                            
                            if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                x += 1
                                continue
                            response = requests.get('http://192.168.88.254', auth=('admin',passList[x]))
                            try:
                                response.text.index('Unauthorized')
                            except ValueError:
                                passwordTested = passList[x]
                                kaiack.UI.panelPassword = passList[x]
                                passwordFound = True
                                break
                            
                            x += 1

                        if passwordFound is False:
                            passwordTested = ''
                            
                    else:
                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Worksheet not found, please configure manually', group = 2)
                        passwordTested = ''
                        break
                else:
                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Wattbox default and site passwords failed, please configure manually', group = 2)
                    passwordTested = ''
                    break
                
            except selenium.common.exceptions.WebDriverException as error: # Missing chromedriver.exe
                dlg = wx.MessageDialog(None, 'Missing chromedriver.exe in Kai-ACK folder or chromedriver.exe is out of date', 'Error', wx.OK)
                dlg.ShowModal()
                dlg.Destroy()
            except requests.exceptions.ConnectionError: # Connection Error
                dlg = wx.MessageDialog(None, 'Error connecting to wattbox, please check cables or retry', 'Error', wx.OK)
                dlg.ShowModal()
                dlg.Destroy()
            except ElementTree.ParseError:
                time.sleep(.25)

        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'QCing Wattbox:', group = 3)
        if self.threadStopped.is_set() is True: # Event for stopping the thread
            print('Wattbox Thread Stopped')
            return None
        try:
            wattboxQC = wattbox.qcWattbox(self.panel)
            if wattboxQC[0] is True and wattboxQC[1] is True and wattboxQC[2] is True:
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tAll fields correct', group = 3)
            if wattboxQC[0] is False:
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tIncorrect hostname, please correct manually', group = 3)
            if wattboxQC[1] is False:
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tIncorrect domain name, please correct manually', group = 3)
            if wattboxQC[2] is False:
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tIncorrect email address, please correct manually', group = 3)
        except splinter.exceptions.ElementDoesNotExist:
            Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tLogin attempt failed, please correct manually', group = 3)
        except requests.exceptions.ConnectionError:
            Publisher.sendMessage('status', ssid = self.panel.ssid, message = '\tError occurred, please correct manually', group = 3)
            
        self._return = self.panel

class apProgramThread(Thread):
    def __init__(self, panel = None, ip = None):
        self.panel = panel
        self.ip = ip
        self._return = None
        Thread.__init__(self)
        self.threadStopped = Event()
        self.daemon = True
        self.start()
        
    @use_my_excepthook
    def run(self):
        self.programAP()

    def join(self):
        Thread.join(self)
        return self._return

    def programAP(self):
        if self.threadStopped.is_set() is True: # Event for stopping the thread
            print('AP Thread Stopped')
            return None
        # Factory reset AP
        if self.ip is not None:
            controllerFailed = False
            defaultFailed = False
            controller2Failed = False
            controller3Failed = False

            # Pexpect lines to pass in responses for authorization, functions like a terminal session
            try: 
                # Authentication for APs in a zone
                child = pexpect.popen_spawn.PopenSpawn('ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -tt awssupport@' + self.ip)
                
                child.expect('Please login:')
                child.sendline('awssupport')
                child.expect('password :')
                child.sendline('kT$JGYty%3')
                child.expect('rkscli:')
                time.sleep(.3)
                child.sendline('set factory')
                child.sendline('reboot')
                child.sendline('exit\r')
            except pexpect.ExceptionPexpect as error:
                print('controller login failed')
                controllerFailed = True
                
            if self.threadStopped.is_set() is True:
                print('AP Thread Stopped')
                return None
            
            if controllerFailed is True:
                try: 
                    # Authentication for APs in a zone
                    child = pexpect.popen_spawn.PopenSpawn('ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -tt admin@' + self.ip)
                    
                    child.expect('Please login:')
                    child.sendline('admin')
                    child.expect('password :')
                    child.sendline('p@ssW0rd')
                    child.expect('rkscli:')
                    time.sleep(.3)
                    child.sendline('set factory')
                    child.sendline('reboot')
                    child.sendline('exit\r')
                except pexpect.ExceptionPexpect:
                    print('controller login failed')
                    controller2Failed = True
                    
            if self.threadStopped.is_set() is True: # Event for stopping the thread
                print('AP Thread Stopped')
                return None
        
            if controllerFailed is True and controller2Failed is True:
                # Pexpect lines to pass in responses for authorization, functions like a terminal session
                try: 
                    # Authentication for APs not in a zone
                    child = pexpect.popen_spawn.PopenSpawn('ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -tt super@' + self.ip)
                    
                    child.expect('Please login:')
                    child.sendline('super')
                    child.expect('password :')
                    child.sendline('sp-admin')
                    child.expect('rkscli:')
                    time.sleep(.3)
                    child.sendline('set factory')
                    child.sendline('reboot')
                    child.sendline('exit\r')
                except pexpect.ExceptionPexpect:
                    print('default login failed')
                    defaultFailed = True
                    
            if self.threadStopped.is_set() is True: # Event for stopping the thread
                print('AP Thread Stopped')
                return None
        
            if controllerFailed is True and controller2Failed is True and defaultFailed is True:
                try: 
                    # Authentication for APs in a zone
                    child = pexpect.popen_spawn.PopenSpawn('ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -tt programming@' + self.ip)
                    
                    child.expect('Please login:')
                    child.sendline('programming')
                    child.expect('password :')
                    child.sendline('V9mDXzhm%Q')
                    child.expect('rkscli:')
                    time.sleep(.3)
                    child.sendline('set factory')
                    child.sendline('reboot')
                    child.sendline('exit\r')
                except pexpect.ExceptionPexpect:
                    print('controller login failed')
                    controller3Failed = True
                    
            if self.threadStopped.is_set() is True: # Event for stopping the thread
                print('AP Thread Stopped')
                return None
            
            if defaultFailed is True and controllerFailed is True and controller2Failed is True and controller3Failed is True: # Sends publisher message if both passwords failed
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Failed to Factory Reset AP', group = 1)
            else:
                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'AP has been factory reset', group = 1)
                x = 0
                while x < 8:
                    if self.threadStopped.is_set() is True: # Event for stopping the thread
                        print('AP Thread Stopped')
                        return None
                    time.sleep(5)
                    x += 1

            self._return = None
        
        # Program AP
        else:
            Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Connecting to Ruckus Controller...', group = 1)
            apReturn = kaiack.UI.controller.kaiACKProgramSingleAP(self.panel)
            while apReturn is False:
                dlg = wx.MessageDialog(None, 'SSID-specific and Guest WLAN not found, check that they have\nbeen created. These are required for the programming process\nand should be created before retrying', 'Retry?', wx.YES_NO)
                dlgReturn = dlg.ShowModal()
                dlg.Destroy()
                if dlgReturn == wx.ID_NO:
                    break
                
                apReturn = kaiack.UI.controller.kaiACKProgramSingleAP(self.panel)

            if apReturn is not False:
                self.panel = apReturn
                
            self._return = self.panel
        
class panelProgramThread(Thread): # Programming proccess thread
    def __init__(self, panel):
        self.panel = panel # panel object for the programming process
        self.initPanel = panel # panel object for use if an error occurs
        Thread.__init__(self)
        self.daemon = True
        self.start()

    @use_my_excepthook
    def run(self):
        self.programPanel()

    def programPanel(self):
        self.panel.state = True #sets proper states at beginning just in case
        self.panel.stateChanged = False #sets proper states at beginning just in case

        dlg = wx.MessageDialog(None, self.panel.ssid + ' Added \n' + self.panel.ip + '\n' + self.panel.int3MAC, 'Continue?', wx.YES_NO)
        dlgReturn = dlg.ShowModal()
        dlg.Destroy()
        if dlgReturn == wx.ID_NO: # Remove panel and pause programming
            kaiack.UI.panelList.insert(0, self.panel.ssid)
                
            x = 0
            while x < len(kaiack.UI.currentPanelList):
                if kaiack.UI.currentPanelList[x].ssid == self.panel.ssid:
                    del kaiack.UI.currentPanelList[x]
                    break
                x += 1

            x = 0
            while x < len(kaiack.UI.statusText):
                if kaiack.UI.statusText[x][0] == self.panel.ssid:
                    del kaiack.UI.statusText[x]
                    try:
                        del kaiack.UI.panelGroups[x]
                    except IndexError:
                        pass
                    break
                x += 1

            kaiack.UI.panelStatusLabel.SetLabel('No Panels Found')
            kaiack.UI.panelStatusText.SetValue('')
            kaiack.UI.panelStatusGauge.SetValue(0)

            kaiack.UI.programPanels('event')
        else:
            while True:
                try:
                    time1 = datetime.datetime.now()
                    # Checks that the ssh and ftp port is enabled and authentication is correct through SSH -> FTP -> API to make sure all are enabled, the Master Password List is used to test authentication
                    passwordTested = False
                    panelPasswordTested = False
                    APITried = False
                    while True:
                        message = ''
                        try:
                            sshftpconnection.testMikrotikAuth(self.panel.ip, self.panel.initPassword) # Tests Auth and enables FTP
                            ssh = sshftpconnection.connectSSH(self.panel.ip, self.panel.initPassword)
                            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service enable ftp', self.panel.ip, self.panel.initPassword)
                            break
                        except paramiko.ssh_exception.NoValidConnectionsError: # Occurs when the SSH port is disabled

                            # Uploads a .auto.rsc script to enable SSH through FTP
                            passwordTested = False
                            ftpTried = False
                            panelPasswordTested = False
                            while True:
                                try:
                                    sshftpconnection.enableSSH(self.panel.ip, self.panel.initPassword, 'enableSSH.auto.rsc') # Uploads the file through FTP
                                    break
                                except ConnectionRefusedError: # Both ssh and ftp are disabled, use API to enable ssh and ftp

                                    # Mikrotik API is used to enable FTP and SSH as well as to test authentication along the way, this seems to be much faster then SSH
                                    passwordTested = False
                                    panelPasswordTested = False
                                    while True:
                                        try:
                                            mikrotikAPI.enableServices(self.panel.ip, self.panel.initPassword) # The exit command on the API throws an error which is accounted for in this section
                                            break
                                        except librouteros.exceptions.FatalError as error: # Error thrown by failed authentication and logout
                                            if 'not logged in' in str(error): # error message from authentication failure, tests default, site password, previous password, and master password list
                                                if self.panel.initPassword == '' and passwordTested is False and APITried is False: # Site Password
                                                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Enabling SSH and FTP, authentication failed, defaulting to site password')
                                                    password = open(self.panel.siteDir + '\\Password.txt','r')
                                                    self.panel.initPassword = password.read().strip() #gets password from file
                                                    password.close()
                                                    passwordTested = True
                                                elif passwordTested is True and self.panel.initPassword != '' and panelPasswordTested is False and APITried is False: # Previous Password
                                                    if kaiack.UI.panelPassword is None:
                                                        panelPasswordTested = True
                                                    else:
                                                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, testing previous credentials')
                                                        self.panel.initPassword = kaiack.UI.panelPassword
                                                        panelPasswordTested = True
                                                elif passwordTested is True and self.panel.initPassword != '' and panelPasswordTested is True and APITried is False: # Master Password List
                                                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, searching master password list')
                                                    scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                                    
                                                    authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                                    
                                                    wks = None
                                                    while True: # Opens Master Password List Sheet
                                                        try:
                                                            gc = gspread.authorize(authorization)
                                                            wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                                            break
                                                        except gspread.exceptions.SpreadsheetNotFound:
                                                            #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                                            passwordTested = ''
                                                            break
                                                        except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                                            #No Internet Connection
                                                            print('Connection Error')
                                                        except IndexError: # Just in case
                                                            #Error Getting Data From Spreadsheet
                                                            passwordTested = ''
                                                            break
                                                        
                                                    if wks is not None:
                                                        passwordFound = False
                                                        passList = wks.col_values(2)
                                                        del passList[0] # Deletes unneeded value, constant
                                                        x = 0
                                                        while x < len(passList):
                                                            passList[x] = passList[x].strip()
                                                            x += 1
                                                            
                                                        x = 0
                                                        while x < len(passList): # Tests passwords from the list
                                                            if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                                                x += 1
                                                                continue
                                                            try:
                                                                mikrotikAPI.enableServices(self.panel.ip, passList[x])
                                                                # The function above breaks no matter what so nothing else in this try matters
                                                                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Password Found: ' + passList[x])
                                                                self.panel.initPassword = passList[x]
                                                                kaiack.UI.panelPassword = passList[x]
                                                                passwordFound = True
                                                                break
                                                            except (OSError, ConnectionResetError, ConnectionAbortedError): # Connection error, retry
                                                                x -= 1
                                                            except librouteros.exceptions.FatalError as error:
                                                                if 'not logged in' not in str(error): # Error from terminating connection after successful authentication
                                                                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Password Found: ' + passList[x])
                                                                    self.panel.initPassword = passList[x]
                                                                    kaiack.UI.panelPassword = passList[x]
                                                                    passwordFound = True
                                                                    break

                                                            x += 1

                                                        if passwordFound is False:
                                                            APITried = True
                                                            passwordTested = ''
                                                else:
                                                    #Authentication failed, reset
                                                    self.panel.initPassword = ''
                                                    message = self.panel.ssid + '\nAuthentication Failed, please reset Mikrotik password'
                                                    
                                                    dlg = wx.MessageDialog(None, message, 'Error', wx.OK)
                                                    dlg.ShowModal()
                                                    dlg.Destroy()
                                                    message = ''
                                                    break
                                            else:
                                                message = ''
                                                break
                                                        
                                except (OSError, ConnectionResetError, ConnectionAbortedError):
                                    print('connection error')
                                    time.sleep(2)
                                except ftplib.error_perm:
                                    if self.panel.initPassword == '' and passwordTested is False and ftpTried is False: # Site Password
                                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Enabling SSH, authentication failed, defaulting to site password')
                                        password = open(self.panel.siteDir + '\\Password.txt','r')
                                        self.panel.initPassword = password.read().strip() #gets password from file
                                        password.close()
                                        passwordTested = True
                                    elif passwordTested is True and self.panel.initPassword != '' and ftpTried is False and panelPasswordTested is False: # Previous Password
                                        if kaiack.UI.panelPassword is None:
                                            panelPasswordTested = True
                                        else:
                                            Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, testing previous credentials')
                                            self.panel.initPassword = kaiack.UI.panelPassword
                                            panelPasswordTested = True

                                            
                                    elif passwordTested is True and self.panel.initPassword != '' and ftpTried is False and panelPasswordTested is True: # Master Password List
                                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, searching master password list')
                                        scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                        
                                        authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                        
                                        wks = None
                                        while True: # Loads Master Password List
                                            try:
                                                gc = gspread.authorize(authorization)
                                                wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                                break
                                            except gspread.exceptions.SpreadsheetNotFound:
                                                #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                                passwordTested = ''
                                                break
                                            except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                                #No Internet Connection
                                                print('Connection Error')
                                            except IndexError: # Just in case
                                                #Error Getting Data From Spreadsheet
                                                passwordTested = ''
                                                break
                                            
                                        if wks is not None:
                                            passwordFound = False
                                            passList = wks.col_values(2)
                                            del passList[0]
                                            x = 0
                                            while x < len(passList):
                                                passList[x] = passList[x].strip()
                                                x += 1
                                                
                                            x = 0
                                            while x < len(passList): # Tests Passwords in the Master List
                                                if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                                    x += 1
                                                    continue
                                                try:
                                                    sshftpconnection.enableSSH(self.panel.ip, passList[x], 'enableSSH.auto.rsc')
                                                    # Breaks here if unsuccessful
                                                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = passList[x])
                                                    self.panel.initPassword = passList[x]
                                                    kaiack.UI.panelPassword = passList[x]
                                                    passwordFound = True
                                                    break
                                                except (OSError, ConnectionResetError, ConnectionAbortedError): # Connection error or something, retry
                                                    x -= 1
                                                except ftplib.error_perm:
                                                    pass

                                                x += 1

                                            if passwordFound is False:
                                                passwordTested = ''

                                    else:
                                        #Authentication failed, reset
                                        self.panel.initPassword = ''
                                        message = 'Authentication Failed, please reset Mikrotik password'
                                        ftpTried = True
                                        break
                                    
                        except paramiko.ssh_exception.AuthenticationException: # Authentication failed, ports already enabled
                            message = 'Authentication Failed, please reset Mikrotik password'
                            if self.panel.initPassword == '' and passwordTested is False: # Site Password
                                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, defaulting to site password')
                                message = ''
                                password = open(self.panel.siteDir + '\\Password.txt','r')
                                self.panel.initPassword = password.read().strip() #gets password from file
                                password.close()
                                passwordTested = True
                            elif passwordTested is True and panelPasswordTested is False: # Previous Password
                                message = ''
                                if kaiack.UI.panelPassword is None:
                                    panelPasswordTested = True
                                else:
                                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, testing previous credentials')
                                    self.panel.initPassword = kaiack.UI.panelPassword
                                    panelPasswordTested = True
                                
                            elif passwordTested is True and self.panel.initPassword != '' and panelPasswordTested is True: # Master Password List
                                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Authentication Failed, searching master password list')
                                message = ''
                                scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')
                                
                                authorization = ServiceAccountCredentials.from_json_keyfile_dict(googlesheets.credentials, scope)
                                
                                wks = None
                                while True: # Opens Master Password Sheet
                                    try:
                                        gc = gspread.authorize(authorization)
                                        wks = gc.open('Site Password Master List').worksheet('Programming Passwords')
                                        break
                                    except gspread.exceptions.SpreadsheetNotFound:
                                        #Spreadsheet Not Found Make sure the service account has been added or check the spreadsheet name entered
                                        passwordTested = ''
                                        break
                                    except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
                                        #No Internet Connection
                                        print('Connection Error')
                                    except IndexError: # Just in case
                                        #Error Getting Data From Spreadsheet
                                        passwordTested = ''
                                        break
                                    
                                if wks is not None:
                                    passwordFound = False
                                    passList = wks.col_values(2)
                                    del passList[0] # Delete unneeded value, constant
                                    x = 0
                                    while x < len(passList):
                                        passList[x] = passList[x].strip()
                                        x += 1
                                        
                                    x = 0
                                    while x < len(passList): # Tests passwords in the master password list
                                        if x > 4 and passList[x] == '': # Skips blank passwords in the list after the fifth entry
                                            x += 1
                                            continue
                                        
                                        try:
                                            sshftpconnection.testMikrotikAuth(self.panel.ip, passList[x])
                                            # Breaks here if authentication is incorrect 
                                            self.panel.initPassword = passList[x]
                                            kaiack.UI.panelPassword = passList[x]
                                            passwordFound = True
                                            break
                                        except paramiko.ssh_exception.AuthenticationException: # Error from incorrect authentication
                                            pass

                                        x += 1

                                    if passwordFound is False: # Resets password to blank if no password is found
                                        passwordTested = ''

                            else:
                                #Authentication failed, reset
                                self.panel.initPassword = ''
                                
                        except (paramiko.ssh_exception.SSHException, TimeoutError, ConnectionAbortedError, ConnectionResetError, EOFError): # who the fuck knows
                            print('exception caught')
                            pass

                        if message != '': # Displays message if needed
                            dlg = wx.MessageDialog(None, self.panel.ssid + '\n' + message, 'Error', wx.OK)
                            dlg.ShowModal()
                            dlg.Destroy()
                        
                        time.sleep(3)

                    # Checks packages to determine when to continue
                    printOnce = True
                    while True: # Looped until all three packages are disabled, indicating that the MTAutoscript has finished running
                        time.sleep(3)
                        try:
                            # Reconnect to SSH server each time because of potential restarts while the MTAutoscript is running
                            ssh = paramiko.SSHClient()
                            ssh.load_system_host_keys()
                            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                            ssh.connect(self.panel.ip, '22', 'admin', self.panel.initPassword) # Connect to SSH
                            (stdin, stdout, stderr) = ssh.exec_command('system package print without-paging') # Print package list

                            # Code to properly read the stdout buffer in chunks so it doesnt fill up
                            timeout = 2
                            
                            channel = stdout.channel
                            stdin.close()
                            channel.shutdown_write()

                            stdout_chunks = []
                            stdout_chunks.append(stdout.channel.recv(len(stdout.channel.in_buffer)))

                            while not channel.closed or channel.recv_ready() or channel.recv_stderr_ready(): 
                                # stop if channel was closed prematurely, and there is no data in the buffers.
                                got_chunk = False
                                readq, _, _ = select.select([stdout.channel], [], [], timeout)
                                for c in readq:
                                    if c.recv_ready(): 
                                        stdout_chunks.append(stdout.channel.recv(len(c.in_buffer)))
                                        got_chunk = True
                                    if c.recv_stderr_ready(): 
                                        # make sure to read stderr to prevent stall    
                                        stderr.channel.recv_stderr(len(c.in_stderr_buffer))  
                                        got_chunk = True
                                if not got_chunk and stdout.channel.exit_status_ready() and not stderr.channel.recv_stderr_ready() and not stdout.channel.recv_ready(): 
                                    # indicate that we're not going to read from this channel anymore
                                    stdout.channel.shutdown_read()  
                                    # close the channel
                                    stdout.channel.close()
                                    break    # exit as remote side is finished and our bufferes are empty

                            # close all the pseudofiles
                            stdout.close()
                            stderr.close()
                            
                            collectedLines = ''
                            x = 0
                            while x < len(stdout_chunks):
                                stdout_chunks[x] = stdout_chunks[x].decode()
                                collectedLines = collectedLines + stdout_chunks[x]
                                x += 1

                            stdout = collectedLines.splitlines()
                            
                            indexName = 0
                            indexVersion = 0
                            packagesDisabled = True
                            for line in stdout: # Checks for an X in the return indicating the package is disabled
                                line = line.strip()
                                
                                if indexName != 0 and indexVersion != 0:
                                    if line[indexName:indexVersion].strip() == 'wireless':
                                        if line[indexName-2:indexName-1] == ' ':
                                            packagesDisabled = False
                                    elif line[indexName:indexVersion].strip() == 'mpls':
                                        if line[indexName-2:indexName-1] == ' ':
                                            packagesDisabled = False
                                    elif line[indexName:indexVersion].strip() == 'ppp':
                                        if line[indexName-2:indexName-1] == ' ':
                                            packagesDisabled = False
                                            
                                try:
                                    indexName = line.index('NAME')
                                    indexVersion = line.index('VERSION') - 1
                                except ValueError:
                                    if printOnce is True:
                                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Waiting for MTAutoscript to finish running...')
                                        printOnce = False

                            if packagesDisabled is True:
                                break
                            
                            ssh.close()
                        except (paramiko.ssh_exception.SSHException, paramiko.ssh_exception.NoValidConnectionsError, TimeoutError, ConnectionAbortedError, EOFError, ConnectionResetError):
                            if printOnce is True:
                                Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Waiting for MTAutoscript to finish running...')
                                printOnce = False

                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'MTAutoscript done runnning')
                    
                    # Checks cable connection to Wattbox and AP
                    ssh = sshftpconnection.connectSSH(self.panel.ip, self.panel.initPassword)
                    while True: # Loop to wait unitl all needed devices are connected
                        connected = True
                        index = None
                        numConnections = []
                        message = 'One or more devices are not connected to the Mikrotik\nCheck all cable connections for:\n'
                        # Cable-test ether2 if wattbox option is enabled
                        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'interface ethernet cable-test ether2 once', self.panel.ip, self.panel.initPassword)
                        for line in stdout:
                            line = line.strip()
                            if 'no-link' in line and self.panel.optionsList['Wattbox'] is True:
                                message = message + 'Wattbox\n'
                                connected = False
                                break

                        # Cable-test ether5 if AP option is enabled
                        ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'interface ethernet cable-test ether5 once', self.panel.ip, self.panel.initPassword)
                        for line in stdout:
                            line = line.strip()
                            if 'no-link' in line and self.panel.optionsList['AP'] is True:
                                message = message + 'AP\n'
                                connected = False
                                break
                            
                        if connected is True: # Exits loop if cables are connected
                            break
                        else: # Message box if a cable is disconnected
                            dlg = wx.MessageDialog(None, self.panel.ssid + '\n' + message, 'Error', wx.OK)
                            dlg.ShowModal()
                            dlg.Destroy()
                            
                        time.sleep(2)

                    ssh.close()
                    
                    # Start Programming process
                    self.panel = programpanel.progPanel1(self.panel)
                        
                    Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel) # Return panel to main thread
                    returned = False
                    while self.panel.progStatus < 3: # Wait for MTAutoscript to finish running
                        if self.panel.progStatus == 2 and returned is False: # Return panel after stage 2 is reached
                            Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)
                            returned = True
                        time.sleep(3)

                    time.sleep(.5) # Wait time for ip to update, just in case
                    Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)

                    # Factory Reset AP
                    if self.panel.optionsList['ResetAP'] is True and self.panel.optionsList['AP'] is True: # Checks that Refurb and AP option are checked
                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Factory Resetting AP...', group = 1)
                        
                        ssh = sshftpconnection.connectSSH(self.panel.ip, self.panel.initPassword)

                        index1 = None
                        index2 = None
                        ip = None
                        # Get the AP IP from the Mikrotik ARP table
                        while True:
                            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip arp print where interface=ether5-trunk-AP', self.panel.ip, self.panel.initPassword)
                            for line in stdout:
                                line = line.strip()
                                if index1 is not None and index2 is not None:
                                    if line[index2:index2+17].strip() != '':
                                        ip = line[index1:index1+12].strip()
                                        break
                                        
                                try:
                                    index1 = line.index('ADDRESS')
                                    index2 = line.index('MAC-ADDRESS')
                                except ValueError:
                                    pass
                                
                            if ip is not None:
                                break

                        ssh.close()

                        # Thread opened for factory resetting the AP
                        factoryResetAP = apProgramThread(panel = self.panel, ip = ip)

                    # Second step in the mikrotik programming process
                    self.panel = programpanel.progPanel2(self.panel)
                    
                    self.panel.progStatus = 4 # At this point the mikrotik is configured

                    Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)
                    
                    # Configure Wattbox
                    # Selenium/Splinter Web Browser Automation library is used to load the config
                    if self.panel.optionsList['Wattbox'] is True:
                        # Get wattbox IP
                        ssh = sshftpconnection.connectSSH(self.panel.ip, self.panel.initPassword)

                        index1 = None
                        index2 = None
                        ip = None
                        # Get the wattbox IP from the Mikrotik ARP table
                        while True:
                            ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip arp print where interface=ether2-wattBox', self.panel.ip, self.panel.sitePassword)
                            for line in stdout:
                                line = line.strip()
                                if index1 is not None and index2 is not None:
                                    if line[index2:index2+17].strip() != '':
                                        ip = line[index1:index1+14].strip()
                                        break
                                        
                                try:
                                    index1 = line.index('ADDRESS')
                                    index2 = line.index('MAC-ADDRESS')
                                except ValueError:
                                    pass
                                
                            if ip is not None:
                                break

                        ssh.close()

                        # Thread to program wattbox
                        programWattbox = wattboxProgramThread(self.panel, ip)
                        
                        Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)
                    
                    # Program panel AP here
                    if self.panel.optionsList['AP'] is True:
                        try:
                            factoryResetAP.join()
                        except NameError:
                            pass
                        programAP = apProgramThread(panel = self.panel)
                        Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)
                        
                    try:
                        wattboxPanel = programWattbox.join()
                        try:
                            self.panel.wattSN = wattboxPanel.wattSN
                        except AttributeError:
                            raise Exception
                    except NameError:
                        pass
                    
                    try:
                        apPanel = programAP.join()
                        try:
                            self.panel.apSN = apPanel.apSN
                        except AttributeError:
                            raise Exception
                    except NameError:
                        pass
                    
                    # QC Mikrotik
                    programpanel.qcPanel(self.panel)

                    # Disables ssh on the mikrotik
                    ssh = sshftpconnection.connectSSH(self.panel.ip, self.panel.sitePassword)
                    ssh, stdout = sshftpconnection.sshSendCommand(ssh, 'ip service disable ssh', self.panel.ip, self.panel.sitePassword)
                    time.sleep(1)

                    ssh.close()

                    mikrotikAPI.disableSSH(self.panel.ip, self.panel.sitePassword)

                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'SSH Disabled', group = 5)

                    # Write to Google Sheets
                    if self.panel.optionsList['Write'] is True and self.panel.optionsList['No NAF'] is False:
                        time.sleep(1)
                        while True: # Catches connection error to google sheets and retries until success
                            try:
                                Publisher.sendMessage('write', panel = self.panel)
                                break
                            except requests.exceptions.ConnectionError:
                                print('Host is not responding')
                                time.sleep(2)
                                
                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Panel Written', group = 5)

                    if self.panel.optionsList['No NAF'] is True:
                        writeHeader = True
                        # Ensure the file is there before trying to read from it
                        fileList = os.listdir(os.getcwd())
                        for item in fileList:
                            if 'panelinformation.txt' == item.lower():
                                writeHeader = False
                                break
                            
                        # Write headers if need be
                        if writeHeader is True:
                            with open('PanelInformation.txt', 'w') as file:
                                text = 'SSID' + numSpaces(len(self.panel.ssid) + 2 - 4) + 'Mikrotik MAC' + numSpaces(len(self.panel.tikMAC) + 2 - 12) + 'Mikrotik SN' + numSpaces(len(self.panel.tikSN) + 2 - 11) + 'AP MAC' + numSpaces(len(self.panel.apMAC) + 2 - 6) + 'AP SN' + numSpaces(len(self.panel.apSN) + 2 - 5) + 'WattBox MAC' + numSpaces(len(self.panel.wattMAC) + 2 - 11) + 'WattBox SN\n'
                                file.write(text)
                        # Append panel information to the file
                        with open('PanelInformation.txt', 'a') as file:
                            text = self.panel.ssid + ', ' + self.panel.tikMAC + ', ' + self.panel.tikSN + ', ' + self.panel.apMAC + ', ' + self.panel.apSN + ', ' + self.panel.wattMAC + ', ' + self.panel.wattSN + '\n'
                            file.write(text)

                        Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Panel Written', group = 5)

                    self.panel.progStatus = 5 # Panel has been written to sheet
                    
                    Publisher.sendMessage(self.panel.ssid + 'return', panel = self.panel)
                    time2 = datetime.datetime.now()
                    time3 = time2 - time1
                    time3 = divmod(time3.days * 86400 + time3.seconds, 60)
                    print('Time Elapsed: ' + str(time3[0]) + ':' + str(time3[1]).zfill(2))
                    Publisher.sendMessage('status', ssid = self.panel.ssid, message = 'Panel Done', group = 5) # Panel finished message
                    break
                except Exception:
                    # Get error info
                    errInfo = sys.exc_info()
                    # upload error info
                    catchExceptions(errInfo[0], errInfo[1], errInfo[2])

                    dlg = wx.MessageDialog(None, 'An error has occured, would you like to retry?', 'Error', wx.ICON_ERROR | wx.YES_NO)
                    dlgReturn = dlg.ShowModal()
                    dlg.Destroy()
                    if dlgReturn == wx.ID_NO:
                        # Unsubscribe Publisher
                        # Set event flags to stop open threads
                        try:
                            factoryResetAP.threadStopped.set()
                        except NameError:
                            pass
                        try:
                            programAP.threadStopped.set()
                        except NameError:
                            pass
                        try:
                            programWattbox.threadStopped.set()
                        except NameError:
                            pass
                        # Join threads to wait for them to end
                        try:
                            factoryResetAP.join()
                            factoryResetAP.threadStopped.clear()
                        except NameError:
                            pass
                        try:
                            programAP.join()
                            programAP.threadStopped.clear()
                        except NameError:
                            pass
                        try:
                            programWattbox.join()
                            programWattbox.threadStopped.clear()
                        except NameError:
                            pass
                        
                        kaiack.UI.panelList.insert(0, self.panel.ssid)
                
                        x = 0
                        while x < len(kaiack.UI.currentPanelList):
                            if kaiack.UI.currentPanelList[x].ssid == self.panel.ssid:
                                del kaiack.UI.currentPanelList[x]
                                break
                            x += 1

                        x = 0
                        while x < len(kaiack.UI.statusText):
                            if kaiack.UI.statusText[x][0] == self.panel.ssid:
                                del kaiack.UI.statusText[x]
                                try:
                                    del kaiack.UI.panelGroups[x]
                                except IndexError:
                                    pass
                                break
                            x += 1
                        
                        kaiack.UI.panelStatusLabel.SetLabel('No Panels Found')
                        kaiack.UI.panelStatusText.SetValue('')
                        kaiack.UI.panelStatusGauge.SetValue(0)

                        kaiack.UI.programPanels('event')
                        
                        break
                    else:
                        self.panel = self.initPanel
                        x = 0
                        while x < len(kaiack.UI.currentPanelList):
                            if kaiack.UI.currentPanelList[x].ssid == self.panel.ssid:
                                kaiack.UI.currentPanelList[x] = self.panel
                                break
                            x += 1

                        x = 0
                        while x < len(kaiack.UI.statusText):
                            if kaiack.UI.statusText[x][0] == self.panel.ssid:
                                y = 0
                                while y < len(kaiack.UI.statusText[x]):
                                    if y != 0 and y != 1:
                                        del kaiack.UI.statusText[x][y]
                                        try:
                                            del kaiack.UI.panelGroups[x][y]
                                        except IndexError:
                                            pass
                                        y -= 1
                                    y += 1
                                
                                break
                            x += 1

                        kaiack.UI.panelStatusText.SetValue('Panel Added')
                        kaiack.UI.panelStatusGauge.SetValue(self.panel.progStatus)

                        self.panel.state = True #sets proper states at beginning just in case
                        self.panel.stateChanged = False

                        # Set event flags to stop open threads
                        try:
                            factoryResetAP.threadStopped.set()
                        except NameError:
                            pass
                        try:
                            programAP.threadStopped.set()
                        except NameError:
                            pass
                        try:
                            programWattbox.threadStopped.set()
                        except NameError:
                            pass
                        # Join threads to wait for them to end
                        try:
                            factoryResetAP.join()
                            factoryResetAP.threadStopped.clear()
                        except NameError:
                            pass
                        try:
                            programAP.join()
                            programAP.threadStopped.clear()
                        except NameError:
                            pass
                        try:
                            programWattbox.join()
                            programWattbox.threadStopped.clear()
                        except NameError:
                            pass

                        kaiack.UI.panelStatusText.SetValue('Panel Added')
                        kaiack.UI.panelStatusGauge.SetValue(self.panel.progStatus)
        
class panelProgramUI(wx.Frame): # Get input and initialize form
    def __init__(self, parent, title):
        # Setting up variables
        self.downgradeConfigPanel = False # Bool for generally downgrading and configing panels
        self.sheetData = None # Spreadsheet data
        self.panelList = [] # List of ssids for a Programmer name
        self.programPanel = False # Var for Program Panel button toggle
        self.currentPanelList = [] # List of panels being programmed
        self.statusText = [] # Status text list for panels being programmed
        self.zoneName = None # AP zone name
        self.panelReady = True # Variable for timer that disables progression to next button step until it is done
        self.panelPassword = None # Password found from a mikrotik cached for future use
        self.downgradeThreadOpen = False # Prevent multiple downgrade threads from opening
        self.mainPanelThreadOpen = False # Prevent multiple main panel threads from opening
        self.panelQueryThreadOpen = False # Prevent multiple query threads from opening
        self.getPanelsThreadOpen = False # Prevent multiple get panel threads from opening
        self.optionsList = None # Options list from options window
        self.encompDir = None # Encompassing directory for site file folders
        self.siteDir = None # Directory that has site files
        self.username = None # Controller username
        self.password = None # Controller password
        self.newCerts = False # Site is using the new certificates, changes filenames
        self.passwordUpdated = False # Var used to load options from file instead of default menu on first
        self.panelGroups = [] # List of groups for status messages (for use with only one status text up)
        self.clusterSelection = None # Cluster chosen from the advanced options menu
        self.key = None

        # Get encryption key
        try:
            with open(resource_path('key.key'), 'rb') as file:
                self.key = Fernet(file.read())
        except FileNotFoundError:
            print('Key not found')
        
        # Initialize frame
        wx.Frame.__init__(self, parent, title=title, size=(300,200), style = wx.CAPTION | wx.CLOSE_BOX | wx.MINIMIZE_BOX)
        self.statusbar = self.CreateStatusBar(2) # A Statusbar in the bottom of the window
        self.statusbar.SetStatusWidths([475, -1])
        self.statusbar.SetStatusText('0:00', 1)

        # Setting up the menu elements
        optionMenu = wx.Menu()
        ID_ADVANCED_OPTION = wx.Window.NewControlId()
        ID_FACTORY_OPTION = wx.Window.NewControlId()
        ID_REFURB_OPTION = wx.Window.NewControlId()
        ID_ENTERPRISE_OPTION = wx.Window.NewControlId()
        ID_SITEFILE_OPTION = wx.Window.NewControlId()
        ID_IMPORT_SSID_OPTION = wx.Window.NewControlId()

        # Options List
        self.menuFactory = optionMenu.AppendCheckItem(ID_FACTORY_OPTION, 'Factory New', ' Panels are factory new')
        self.menuRefurb = optionMenu.AppendCheckItem(ID_REFURB_OPTION, 'Refurbished', ' Panels have been previously programmed')
        self.menuEnterprise = optionMenu.AppendCheckItem(ID_ENTERPRISE_OPTION, 'Enterprise Site', ' Panels are for an enterprise site')
        optionMenu.AppendSeparator()
        menuAdvanced = optionMenu.Append(ID_ADVANCED_OPTION, 'Advanced Options', ' Opens advanced options for further customization')
        
        filemenu= wx.Menu()
        menuAbout= filemenu.Append(wx.ID_ABOUT, "About", " Information about this program")
        menuFile = filemenu.Append(ID_SITEFILE_OPTION, 'Site Files', ' Choose the site file folder for programming')
        menuSSID = filemenu.Append(ID_IMPORT_SSID_OPTION, 'Import SSIDs', ' Import SSIDs seperated by new lines from a text file')
        menuExit = filemenu.Append(wx.ID_EXIT, "Exit", " Terminate the program")

        self.getPanelsMenu = wx.Menu()

        # Default Options
        self.menuFactory.Check(True)
        
        # Creating the menubar.
        self.menuBar = wx.MenuBar()
        self.menuBar.Append(filemenu, "File") # Adding the "filemenu" to the MenuBar
        self.menuBar.Append(optionMenu, "Options")
        self.menuBar.Append(self.getPanelsMenu, 'Get Panels')
        self.SetMenuBar(self.menuBar)  # Adding the MenuBar to the Frame content.

        # Programmer name and textbox initiation
        self.programmerNameLabel = wx.StaticText(self, label='Programmer Name:', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.programmerNameTextBox = wx.TextCtrl(self, size=(360, 25), style=wx.TE_LEFT)
        self.programmerNameSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.programmerNameSizer.AddSpacer(25)
        self.programmerNameSizer.Add(self.programmerNameLabel,0, wx.SHAPED)
        self.programmerNameSizer.AddSpacer(25)
        self.programmerNameSizer.Add(self.programmerNameTextBox,1, wx.EXPAND)
        self.programmerNameSizer.AddSpacer(25)

        # Site name label and textbox initiation
        self.siteNameLabel = wx.StaticText(self, label='Site Name:', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.siteNameTextBox = wx.TextCtrl(self, size=(360, 25), style=wx.TE_LEFT)
        self.siteNameSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.siteNameSizer.AddSpacer(25)
        self.siteNameSizer.Add(self.siteNameLabel,0, wx.SHAPED)
        self.siteNameSizer.AddSpacer(131 - self.siteNameLabel.GetSize()[0])
        self.siteNameSizer.Add(self.siteNameTextBox,1, wx.EXPAND)
        self.siteNameSizer.AddSpacer(25)

        # Controller ip label and textbox initiation
        self.controllerIPLabel = wx.StaticText(self, label='Controller IP:', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.controllerIPTextBox = wx.TextCtrl(self, size=(360, 25), style=wx.TE_LEFT | wx.TE_READONLY)
        self.controllerIPSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.controllerIPSizer.AddSpacer(25)
        self.controllerIPSizer.Add(self.controllerIPLabel,0, wx.SHAPED)
        self.controllerIPSizer.AddSpacer(131 - self.controllerIPLabel.GetSize()[0])
        self.controllerIPSizer.Add(self.controllerIPTextBox,1, wx.EXPAND)
        self.controllerIPSizer.AddSpacer(25)

        # AP Zone label and textbox initiation
        self.apZoneLabel = wx.StaticText(self, label='AP Zone:', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.apZoneTextBox = wx.TextCtrl(self, size=(360, 25), style=wx.TE_LEFT)
        self.apZoneSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.apZoneSizer.AddSpacer(25)
        self.apZoneSizer.Add(self.apZoneLabel,0, wx.SHAPED)
        self.apZoneSizer.AddSpacer(131 - self.apZoneLabel.GetSize()[0])
        self.apZoneSizer.Add(self.apZoneTextBox,1, wx.EXPAND)
        self.apZoneSizer.AddSpacer(25)

        # Panel status label and button initiation
        self.panelStatusLabelSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panelStatusLabel = wx.StaticText(self, label='No Panels Found', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.panelStatusPrevButton = wx.Button(self, size=(100,25), label='Previous Panel')
        self.panelStatusNextButton = wx.Button(self, size=(100,25), label='Next Panel')
        self.panelStatusLabelSizer.AddSpacer(10)
        self.panelStatusLabelSizer.Add(self.panelStatusPrevButton, 0, wx.SHAPED)
        self.panelStatusLabelSizer.AddSpacer(10)
        self.panelStatusLabelSizer.Add(self.panelStatusLabel, 1, wx.EXPAND)
        self.panelStatusLabelSizer.AddSpacer(10)
        self.panelStatusLabelSizer.Add(self.panelStatusNextButton, 0, wx.SHAPED)
        self.panelStatusLabelSizer.AddSpacer(10)

        # Panel status initiation
        self.panelStatusTextSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panelStatusText = wx.TextCtrl(self, size=(520, 300), style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        self.panelStatusTextSizer.AddSpacer(10)
        self.panelStatusTextSizer.Add(self.panelStatusText, 1, wx.SHAPED)
        self.panelStatusTextSizer.AddSpacer(10)

        # Gauge initiation
        self.panelStatusGaugeSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.panelStatusGauge = wx.Gauge(self, range=5, size=(520,25), style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.panelStatusGaugeSizer.AddSpacer(10)
        self.panelStatusGaugeSizer.Add(self.panelStatusGauge, 0, wx.SHAPED)
        self.panelStatusGaugeSizer.AddSpacer(10)
        
        # Button initiation
        self.programPanelsButton = wx.Button(self, size=(135,25), label='Program Panels')
        self.loadSpreadsheetDataButton = wx.Button(self, size=(135,25), label='Load Site Data')
        self.resetPanelsButton = wx.Button(self, size=(135,25), label='Reset Panels')
        self.programDoubleAPsButton = wx.Button(self, size=(135,25), label='Program Double APs')
        self.buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buttonSizer.Add(self.loadSpreadsheetDataButton,1, wx.SHAPED)
        self.buttonSizer.Add(self.resetPanelsButton,1, wx.SHAPED)
        self.buttonSizer.Add(self.programPanelsButton, 1, wx.SHAPED)
        self.buttonSizer.Add(self.programDoubleAPsButton,1, wx.SHAPED)

        # Set button colors
        self.programPanelsButton.SetBackgroundColour(wx.Colour(255, 0, 0))
        self.resetPanelsButton.SetBackgroundColour(wx.Colour(255, 0, 0))

        ####Event initiation####
        # Button events
        self.Bind(wx.EVT_BUTTON, self.programDoubleAPs, self.programDoubleAPsButton)
        self.Bind(wx.EVT_BUTTON, self.loadSpreadsheetData, self.loadSpreadsheetDataButton)
        self.Bind(wx.EVT_BUTTON, self.resetPanels, self.resetPanelsButton)
        self.Bind(wx.EVT_BUTTON, self.programPanels, self.programPanelsButton)
        self.Bind(wx.EVT_BUTTON, self.nextButton, self.panelStatusNextButton)
        self.Bind(wx.EVT_BUTTON, self.prevButton, self.panelStatusPrevButton)
        # Menubar events
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.advancedOptions, menuAdvanced)
        self.Bind(wx.EVT_MENU, self.factoryOption, self.menuFactory)
        self.Bind(wx.EVT_MENU, self.refurbOption, self.menuRefurb)
        self.Bind(wx.EVT_MENU, self.enterpriseOption, self.menuEnterprise)
        self.Bind(wx.EVT_MENU, self.chooseSiteFiles, menuFile)
        self.Bind(wx.EVT_MENU, self.importSSIDText, menuSSID)
        self.Bind(wx.EVT_MENU_OPEN, self.getPanels)
                  
        
        # Main vertical sizer initiation
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.siteNameSizer, 0, wx.EXPAND)
        self.sizer.Add(self.programmerNameSizer, 0, wx.EXPAND)
        self.sizer.Add(self.controllerIPSizer, 0, wx.EXPAND)
        self.sizer.Add(self.apZoneSizer, 0, wx.EXPAND)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.panelStatusLabelSizer, 0, wx.EXPAND)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.panelStatusTextSizer, 0, wx.EXPAND)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.panelStatusGaugeSizer, 0, wx.EXPAND)
        self.sizer.AddSpacer(10)
        self.sizer.Add(self.buttonSizer, 0, wx.EXPAND)
        self.sizer.AddSpacer(10)

        #Idle pipelines
        Publisher.subscribe(self.writeToSheet, 'write')
        Publisher.subscribe(self.updateStatus, 'status')
        Publisher.subscribe(self.statusTimer, 'timer')
        Publisher.subscribe(self.catchProgrammerPanels, 'panelList')
        Publisher.subscribe(self.catchOptions, 'optionsList')
        Publisher.subscribe(self.catchCluster, 'clusterSelection')

        #Load Last Input
        if self.key is not None:
            try:
                with open('settings.encrypted', 'rb') as file:
                    data = file.read()

                decrypted = self.key.decrypt(data)

                with open(resource_path('settings.txt'), 'w') as file:
                    file.write(decrypted.decode())

                with open(resource_path('settings.txt'), 'r') as file:
                    settings = json.load(file)
                
                self.programmerNameTextBox.SetValue(settings['Name'])
                self.siteNameTextBox.SetValue(settings['SiteName'])
                self.encompDir = settings['EncompDir']
                self.username = settings['Username']
                self.password = settings['Password']

                print('Settings loaded')
            except FileNotFoundError:
                print('No settings file found')
        
        #Layout and organize main sizer and frame
        self.SetSizer(self.sizer)
        self.SetAutoLayout(1)
        self.sizer.Fit(self)
        self.Show()

        # Checks for all required files, aside from site files
        message = ''
        try:
            with open('dynuscript.rsc', 'r') as file:
                pass
        except FileNotFoundError:
            message = message + 'Missing dynuscript.rsc\n'

        try:
            with open('chromedriver.exe', 'r') as file:
                pass
        except FileNotFoundError:
            message = message + 'Missing chromedriver.exe\n'

        try:
            with open('enableSSH.auto.rsc', 'r') as file:
                pass
        except FileNotFoundError:
            message = message + 'Missing enableSSH.auto.rsc'

        if message != '':
            dlg = wx.MessageDialog(None, message, 'Missing Files', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()

    # Pulls open file menu to get txt file with ssids in it
    def importSSIDText(self, event):
        # Prompt for ssid file list
        if self.encompDir is None:
            fileMenu = wx.FileDialog(None, 'Choose SSID Text File', style = wx.FD_DEFAULT_STYLE)
        else:
            fileMenu = wx.FileDialog(None, 'Choose SSID Text File', defaultDir = self.encompDir, style = wx.FD_DEFAULT_STYLE)
        fileMenuReturn = fileMenu.ShowModal()
        if fileMenuReturn == wx.ID_OK:
            with open(fileMenu.GetPath(), 'r') as file:
                ssidList = file.readlines()

            # Remove blank entries from the ssid list
            x = 0
            while x < len(ssidList):
                ssidList[x] = ssidList[x].strip()
                if ssidList[x] == '':
                    del ssidList[x]
                    continue
                x += 1

            # Add SSIDs to a message to display for verification
            x = 0
            message = ''
            while x < len(ssidList):
                ssidList[x] = ssidList[x].strip()
                if message == '':
                    message = ssidList[x]
                else:
                    message = message + ', ' + ssidList[x]
                x += 1

            dlg = wx.MessageDialog(None, message, 'Are these SSIDs correct?', wx.YES_NO)
            dlgReturn = dlg.ShowModal()
            dlg.Destroy()
            if dlgReturn == wx.ID_YES:
                self.panelList = ssidList

        fileMenu.Destroy()

    # Catches the cluster selection from the options menu
    def catchCluster(self, cluster):
        self.clusterSelection = cluster
        
    # Event for menu open Get Panels icon
    def getPanels(self, event):
        if event.GetMenu() == self.getPanelsMenu and self.optionsList['No NAF'] is False:
            print('\nRefreshing Panel List\n')
            if self.getPanelsThreadOpen is False:
                programmerPanelsThread()

    # Event for menu to choose a site directory
    def chooseSiteFiles(self, event):
        if self.encompDir is None:
            dlg = wx.DirDialog(None, 'Choose site file directory', '', wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        else:
            dlg = wx.DirDialog(None, 'Choose site file directory', self.encompDir, wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        dirReturn = dlg.ShowModal()
        if dirReturn == wx.ID_OK:
            directory = dlg.GetPath() + '\\'
            dlg.Destroy()
            encompDir = None
            siteDir = None
            x = len(directory) - 2
            while x > 0:
                if directory[x] == '\\':
                    encompDir = directory[:x] # encompassing directory
                    siteDir = directory
                    break
                x -= 1

            while encompDir[len(encompDir)-1] == '\\':
                encompDir = encompDir[:len(encompDir)-1]

            while siteDir[len(siteDir)-1] == '\\':
                siteDir = siteDir[:len(siteDir)-1]

            fileList = os.listdir(siteDir)
            missingFiles = [False, False, False, False]
            for item in fileList:
                if 'MTAutoscript.rsc' == item:
                    missingFiles[0] = True
                if 'WattBox.cfg' == item:
                    missingFiles[1] = True
                if 'Password.txt' == item:
                    missingFiles[2] = True
                if 'routeros' in item.lower() and '.npk' in item.lower():
                    missingFiles[3] = True

            x = 0
            fileNames = ''
            while x < len(missingFiles):
                if missingFiles[x] is False:
                    if x == 0:
                        fileNames = fileNames + 'MTAutoscript.rsc, '
                    elif x == 1:
                        fileNames = fileNames + 'Wattbox.cfg, '
                    elif x == 2:
                        fileNames = fileNames + 'Password.txt, '
                    elif x == 3:
                        fileNames = fileNames + 'RouterOS File'
                elif missingFiles[x] is True and x == 0:
                    with open(siteDir + '\\MTAutoscript.rsc', 'r') as file:
                        script = file.read()
                    if 'be258587ac15fd8a.crt' in script:
                        self.newCerts = True
                    elif 'server.cer' in script:
                        self.newCerts = None
                        found = False
                        for item in fileList:
                            if item == 'hotspot':
                                found = True
                        if found is False:
                            fileNames = fileNames + 'Hotpot Folder, '
                    else:
                        self.newCerts = False
                        dlg = wx.MessageDialog(None, 'This autoscript/site is not set up to use the new certificates', 'Warning', wx.OK)
                        dlg.ShowModal()
                        dlg.Destroy()
                x += 1
            if fileNames == '':
                self.encompDir = encompDir
                self.siteDir = siteDir
                print(self.siteDir)
                print(self.encompDir)
            else:
                dlg = wx.MessageDialog(None, 'The following files cannot be found in this directory:\n\t' + fileNames, 'Warning', wx.OK)
                dlg.ShowModal()
                dlg.Destroy()
                    
    # Change options when Factory and Refurbished is pressed
    def factoryOption(self, event):
        if self.menuFactory.IsChecked() is True:
            self.optionsList['Refurb'] = False
            self.menuRefurb.Check(False)
        elif self.menuRefurb.IsChecked() is False:
            self.menuRefurb.Check(True)
            self.refurbOption('e')

    # Change option when Refurbished is pressed
    def refurbOption(self, event):
        if self.menuRefurb.IsChecked() is True:
            self.optionsList['Refurb'] = True
            self.menuFactory.Check(False)
        elif self.menuFactory.IsChecked() is False:
            self.menuFactory.Check(True)
            self.factoryOption('e')
            
    # Enterprise option to toggle login
    def enterpriseOption(self, event):
        if self.menuEnterprise.IsChecked() is True:
            self.optionsList['Login'] = False
        else:
            self.optionsList['Login'] = True

    # Recieve optionsList from the optionsMenu
    def catchOptions(self, optionsList, username, password):
        if self.menuRefurb.IsChecked() is True:
            optionsList['Refurb'] = True
            
        self.optionsList = optionsList
        if self.passwordUpdated is True or self.username is None or self.password is None:
            self.username = username
            self.password = password
        self.passwordUpdated = True
            
    # Sets time for downgrading panels
    def statusTimer(self, time):
        time = 210 - time
        sec = datetime.timedelta(seconds=time)
        d = datetime.datetime(1,1,1) + sec
        if len(str(d.second)) == 1:
            self.statusbar.SetStatusText('%d:0%d' % (d.minute, d.second), 1)
        else:
            self.statusbar.SetStatusText('%d:%d' % (d.minute, d.second), 1)
        
    # Opens the advanced options menu
    def advancedOptions(self, event):
        kaiack.options.loadOptions(self.optionsList, self.username, self.password)
        kaiack.options.Show()

    # Starts the programming process of Double APs
    def programDoubleAPs(self, event):
        x = 0
        while x < len(self.statusText):
            if self.statusText[x][0] == 'Double APs':
                del self.statusText[x]
                try:
                    del self.panelGroups[x]
                except IndexError:
                    pass
                break
            x += 1
            
        text = self.panelStatusLabel.GetLabel() # Gets identifier from status label
        text = text[0:len(text)-7]
        if text == 'Double APs':
            self.panelStatusLabel.SetLabel('No Panels Found')
            self.panelStatusText.SetValue('')
            self.panelStatusGauge.SetValue(0)
        
        if self.sheetData is not None:
            self.programDoubleAPsButton.Disable()
            self.statusText.append(['Double APs'])
            self.nextButton('event')
            programDoubleAPsThread(self.sheetData)
        else:
            message = 'Site data must be loaded before APs are programmed'
            dlg = wx.MessageDialog(self, message, 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()

    # Updates status label from progamming panels
    def updateStatus(self, ssid, message, group = 0):
        # panelGroups was added to organize messages that are to be displayed on the the same 'sheet' and are being sent from threads that are running simultaniously
        text = self.panelStatusLabel.GetLabel() # Gets ssid from status label
        text = text[0:len(text)-7]

        x = 0
        while x < len(self.statusText): # Adds message to static text list
            if self.statusText[x][0] == ssid:
                self.statusText[x].append(message)
                while len(self.panelGroups) < len(self.statusText):
                    self.panelGroups.append([])
                    
                if len(self.panelGroups[x]) == 0:
                    self.panelGroups[x].append([0,ssid])
                    if self.statusText[x][0] != 'Downgrade Config' and self.statusText[x][0] != 'Double APs':
                        self.panelGroups[x].append([0, 'Panel Added'])
                    
                self.panelGroups[x].append([group, message])
                
                self.panelGroups[x].sort(key=lambda x: int(x[0]))
                y = 1
                while y < len(self.panelGroups[x]):
                    self.statusText[x][y] = self.panelGroups[x][y][1]
                    y += 1

                if text == ssid:
                    wx.CallAfter(self.panelStatusText.SetValue, '')
                        
                    for line in self.statusText[x]:
                        if line == ssid:
                            continue
                        wx.CallAfter(self.panelStatusText.write, line + '\n')
                break
            
            x += 1
        
    # Next button event to cycle through panels
    def nextButton(self, event):
        text = self.panelStatusLabel.GetLabel()
        text = text[0:len(text)-7]

        if self.panelStatusLabel.GetLabel() == 'No Panels Found':
            if len(self.statusText) != 0:
                self.panelStatusLabel.SetLabel(self.statusText[0][0] + ' Status')
                try:
                    self.panelStatusGauge.SetValue(self.currentPanelList[0].progStatus)
                except IndexError:
                    self.panelStatusGauge.SetValue(0)
                x = 1
                while x < len(self.statusText[0]):
                    self.panelStatusText.write(self.statusText[0][x] + '\n')
                    x += 1
        elif len(self.statusText) == 0:
            self.panelStatusLabel.SetLabel('No Panels Found')
            self.panelStatusText.SetValue('')
            self.panelStatusGauge.SetValue(0)
        else:
            changeNext = False
            x = 0
            while x < len(self.statusText):
                if changeNext is True:
                    self.panelStatusLabel.SetLabel(self.statusText[x][0] + ' Status')
                    try:
                        self.panelStatusGauge.SetValue(self.currentPanelList[x].progStatus)
                    except IndexError:
                        self.panelStatusGauge.SetValue(0)
                        
                    self.panelStatusText.SetValue('')
                    y = 1
                    while y < len(self.statusText[x]):
                        self.panelStatusText.write(self.statusText[x][y] + '\n')
                        y += 1
                    break
                if self.statusText[x][0] == text:
                    changeNext = True
                    if len(self.statusText) - 1 == x:
                        x = -1
                x += 1

        self.sizer.Fit(self)

    # Prev button to update status and labels and such
    def prevButton(self, event):
        text = self.panelStatusLabel.GetLabel() # Gets ssid from status label
        text = text[0:len(text)-7]

        if self.panelStatusLabel.GetLabel() == 'No Panels Found':
            if len(self.statusText) != 0:
                self.panelStatusLabel.SetLabel(self.statusText[0][0] + ' Status')
                try:
                    self.panelStatusGauge.SetValue(self.currentPanelList[0].progStatus)
                except IndexError:
                    self.panelStatusGauge.SetValue(0)
        elif len(self.statusText) == 0:
            self.panelStatusLabel.SetLabel('No Panels Found')
            self.panelStatusText.SetValue('') 
            self.panelStatusGauge.SetValue(0)
        else:
            changeNext = False
            reverseList = self.statusText.reverse()
            x = len(self.statusText) - 1
            while x >= 0:
                if changeNext is True:
                    if x == 0:
                        x = 0
                    self.panelStatusLabel.SetLabel(self.statusText[x][0] + ' Status')
                    try:
                        self.panelStatusGauge.SetValue(self.currentPanelList[x].progStatus)
                    except IndexError:
                        self.panelStatusGauge.SetValue(0)
                        
                    self.panelStatusText.SetValue('')
                    y = 1
                    while y < len(self.statusText[x]):
                        self.panelStatusText.write(self.statusText[x][y] + '\n')
                        y += 1
                    break
                if self.statusText[x][0] == text:
                    changeNext = True
                    if x == 0:
                        x = len(self.statusText)
                x -= 1

        self.sizer.Fit(self)

    # Loads site data from user input
    def loadSpreadsheetData(self, event):
        message = ''
        if self.siteNameTextBox.GetValue().strip() == '' and self.optionsList['No NAF'] is False:
            message = message + 'No site name entered\n'
        if self.siteDir is None:
            message = message + 'No site directory chosen\n'
        if (self.optionsList['No NAF'] is True or self.optionsList['Controller'] is True) and self.clusterSelection is None:
            message = message + 'A Cluster must be selected from the options menu for use with no NAF or when overriding the NAF controller\n'
                
        if message == '':
            siteData = None
            filename = Path('SiteData/')
            filename.mkdir(parents=True, exist_ok=True)
            fileList = os.listdir(os.getcwd() + '\\SiteData\\')
            x = 0
            while x < len(fileList):
                y = len(fileList[x]) - 1
                while y >= 0:
                    if fileList[x][y] == '.':
                        fileList[x] = fileList[x][:y]
                    y -= 1
                x += 1
                    
            for item in fileList:
                if self.siteNameTextBox.GetValue().strip() == item and self.optionsList['No NAF'] is False:
                    dlg = wx.MessageDialog(self, 'This data has been loaded previously\nWould you like to load the cached information instead of refreshing it?\nThis reduces load on the Google Sheets API', 'Load Cached Data?', wx.YES_NO)
                    dlgReturn = dlg.ShowModal()
                    dlg.Destroy()
                    if dlgReturn == wx.ID_YES:
                        with open('SiteData/' + item + '.pkl', 'rb') as file:
                            siteData = cPickle.load(file)
                    break
                
            if siteData is None and self.optionsList['No NAF'] is False:
                Publisher.subscribe(self.catchSpreadsheetData, "spreadsheet")
                spreadsheetThread()
                dots()
            elif siteData is None and self.optionsList['No NAF'] is True:
                Publisher.subscribe(self.catchSpreadsheetData, "spreadsheet")
                testController(siteData)
                dots()
            else:
                Publisher.subscribe(self.catchSpreadsheetData, "spreadsheet")
                testController(siteData)
                dots()
                
        else:
            dlg = wx.MessageDialog(self, message, 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()
        
    # Catches and stores site data from Google Sheets on other threads
    def catchSpreadsheetData(self, sheetData, message): # Spreadsheet listener
        if message == '':
            message = 'Site Data Loaded'
            dlg = wx.MessageDialog(self, message, 'Success', wx.OK)
            if self.optionsList['No NAF'] is False:
                self.sheetData = sheetData
                filename = Path('SiteData/')
                filename.mkdir(parents=True, exist_ok=True)
                del filename
                with open('SiteData/' + self.siteNameTextBox.GetValue().strip() + '.pkl', 'wb') as file:
                    cPickle.dump(sheetData, file, -1)
            else:
                self.sheetData = 'No NAF'
                    
            self.apZoneTextBox.SetEditable(False)
            self.siteNameTextBox.SetEditable(False)
            
        else:
            dlg = wx.MessageDialog(self, message, 'Error', wx.OK)
            self.loadSpreadsheetDataButton.Enable()
       
        dlg.ShowModal()
        dlg.Destroy()
        Publisher.unsubscribe(self.catchSpreadsheetData, "spreadsheet")
    
    def resetPanels(self, event): # Reset panels toggle button
        if self.sheetData is not None:
            if self.downgradeConfigPanel is False and self.programPanel is False and self.optionsList['2Stage'] is True:
                self.downgradeConfigPanel = True
                self.programPanel = False
                newStatusText = True
                for name in self.statusText:
                    if name[0] == 'Downgrade Config':
                        newStatusText = False
                        break
                if newStatusText is True:
                    self.statusText.append(['Downgrade Config'])
                    self.nextButton('event')
                
                self.resetPanelsButton.SetBackgroundColour(wx.Colour(0, 255, 0))
                if self.downgradeThreadOpen is False:
                    resetPanelsThread()
            else:
                x = 0
                while x < len(self.statusText): # Remove from statusText list
                    if 'Downgrade Config' == self.statusText[x][0]:
                        del self.statusText[x]
                        try:
                            del self.panelGroups[x]
                        except IndexError:
                            pass
                        break
                    x += 1
                if len(self.statusText) == 0:
                    self.panelStatusLabel.SetLabel('No Panels Found')
                    self.panelStatusText.SetValue('')
                    self.panelStatusGauge.SetValue(0)
                
                self.downgradeConfigPanel = False
                self.resetPanelsButton.SetBackgroundColour(wx.Colour(255, 0, 0))

        else:
            message = 'Site data not loaded'
            dlg = wx.MessageDialog(self, message, 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()

    # Gets panelList and adds it to a kaiack Var
    def catchProgrammerPanels(self, panelList, message): # Panel List listener, cleared messages as its been taken off of a button
        if panelList is None:
            pass
        elif len(panelList) == 0:
            pass
        else:
            self.panelList = panelList
        
    # Button event that starts and stops the programmng
    def programPanels(self, event):
        global programMainThread
        # Checks to make sure sheetData is properly Format 
        if self.sheetData is not None: 
            if self.downgradeConfigPanel is False and self.programPanel is False and self.panelReady is True:
                x = 0
                # Clears status text and panelgroups related to panel
                while x < len(self.statusText):
                    if 'Downgrade Config' == self.statusText[x][0]:
                        del self.statusText[x]
                        try:
                            del self.panelGroups[x]
                        except IndexError:
                            pass
                        break
                    x += 1

                # Set default label 
                if len(self.statusText) == 0:
                    self.panelStatusLabel.SetLabel('No Panels Found')
                    self.panelStatusText.SetValue('')
                    self.panelStatusGauge.SetValue(0)

                # Subscribe to publisher pipelines
                Publisher.subscribe(self.catchPanelQuery, "panelquery") # gets arp table
                Publisher.subscribe(self.catchIP, 'ip') # updates panel ips
                Publisher.subscribe(self.catchProgStatus, 'panelprogress') # updates panel progress
                self.programPanel = True

                if self.panelQueryThreadOpen is False:
                    panelQueryThread()
                self.programPanelsButton.SetBackgroundColour(wx.Colour(0, 255, 0))
                if self.mainPanelThreadOpen is False:
                    programMainThread = panelProgramMainThread(self.currentPanelList)
                
            elif len(self.currentPanelList) == 0:
                try:
                    Publisher.unsubscribe(self.catchPanelQuery, "panelquery")
                    Publisher.unsubscribe(self.catchProgStatus, 'panelprogress')
                    Publisher.unsubscribe(self.catchIP, 'ip')
                except pubsub.core.topicexc.TopicNameError:
                    pass
                
                try:
                    del programMainThread
                except NameError:
                    pass
                
                self.programPanel = False
            
                if len(self.statusText) == 0:
                    self.panelStatusLabel.SetLabel('No Panels Found')
                    self.panelStatusText.SetValue('')
                    self.panelStatusGauge.SetValue(0)
                
                self.programPanelsButton.SetBackgroundColour(wx.Colour(255, 0, 0))
        else:
            message = 'Site data not loaded'
            dlg = wx.MessageDialog(self, message, 'Error', wx.OK)
            dlg.ShowModal()
            dlg.Destroy()
        
    # Receives panel query from seperate thread, returns 87 and 88 ips on an interface 
    def catchPanelQuery(self, panelList): # Gets arp table list and adds new panels to be programmed, increases program state on disconnect
        global programThreads
        
        if len(self.panelList) == 0 and len(self.currentPanelList) == 0 and self.getPanelsThreadOpen is False and self.optionsList['No NAF'] is False:
            programmerPanelsThread()
            
        x = 0
        while x < len(panelList): # Adds new panels to list
            beingProgrammed = False
            y = 0
            while y < len(self.currentPanelList): # updates int3MAC on state changes
                if panelquery.getHexNum(self.currentPanelList[y].int3MAC) == panelList[x][1]:
                    self.currentPanelList[y].int3MAC = panelList[x][1]
                y += 1
            for y in self.currentPanelList: # Checks that panel is not being programmed
                if y.int3MAC == panelList[x][1]:
                    beingProgrammed = True    
            if beingProgrammed is False: # Add to list and pick ssid for panel if False
                z = 0
                while z < len(self.panelList):
                    ssidUsed = False
                    for y in self.currentPanelList:
                        if self.panelList[z] == y.ssid:
                            ssidUsed = True
                    if ssidUsed is False:
                        if self.optionsList['No NAF'] is True:
                            ddnsHostname = self.panelList[z].replace('_', '-') + '.dynu.net'
                        else:
                            ddnsHostname = self.sheetData.getDDNSHostname(self.panelList[z])
                            
                        self.currentPanelList.append(googlesheets.panel(self.panelList[z], panelList[x][0], ddnsHostname, panelList[x][1], self.optionsList, self.siteDir, self.newCerts))
                        self.statusText.append([self.panelList[z]])
                        self.statusText[len(self.statusText) - 1].append('Panel Added')
                        Publisher.subscribe(self.updatePanel, self.panelList[z] + 'return')
                        
                        del self.panelList[z] # removes ssid from the programmer list
                        if len(self.currentPanelList) == 1:
                            self.nextButton('event')
                            
                        break
                    z += 1
            x += 1

        time.sleep(1)
        x = 0
        while x < len(self.currentPanelList): # updates states for progress tracking (whether current panels are connected or not)
            isActive = False
            for y in panelList:
                if self.currentPanelList[x].int3MAC == y[1]:
                    isActive = True
            if self.currentPanelList[x].state is True and isActive is True:
                self.currentPanelList[x].state = True
                self.currentPanelList[x].stateChanged = False  
            elif self.currentPanelList[x].state is True and isActive is False:
                if self.currentPanelList[x].progStatus == 5: # Panel is done and has been unplugged
                    y = 0
                    while y < len(self.statusText): # Remove from statusText list
                        if self.currentPanelList[x].ssid == self.statusText[y][0]:
                            del self.statusText[y]
                            try:
                                del self.panelGroups[y]
                            except IndexError:
                                pass
                            break
                        y += 1
                    self.panelStatusLabel.SetLabel('No Panels Found')
                    self.panelStatusText.SetValue('')
                    self.panelStatusGauge.SetValue(0)

                    z = 0
                    while z < len(programThreads): # Deletes programming thread
                        if self.currentPanelList[x].ssid == programThreads[z][0]:
                            del programThreads[z]
                            break
                        z += 1
                    del self.currentPanelList[x]

                    if len(self.panelList) == 0:
                        self.programPanels('event')
                    
                    continue
                    
                else:
                    self.currentPanelList[x].state = False
                    self.currentPanelList[x].stateChanged = True
            elif self.currentPanelList[x].state is False and isActive is True:
                self.currentPanelList[x].state = True
                self.currentPanelList[x].stateChanged = True
            elif self.currentPanelList[x].state is False and isActive is False:
                
                self.currentPanelList[x].state = False
                self.currentPanelList[x].stateChanged = False

                if self.currentPanelList[x].progStatus == 5: # Panel is done and has been unplugged
                    y = 0
                    while y < len(self.statusText): # Remove from statusText list
                        if self.currentPanelList[x].ssid == self.statusText[y][0]:
                            del self.statusText[y]
                            try:
                                del self.panelGroups[y]
                            except IndexError:
                                pass
                            break
                        y += 1
                    self.panelStatusLabel.SetLabel('No Panels Found')
                    self.panelStatusText.SetValue('')
                    self.panelStatusGauge.SetValue(0)

                    z = 0
                    while z < len(programThreads): # Deletes programming thread
                        if self.currentPanelList[x].ssid == programThreads[z][0]:
                            del programThreads[z]
                            break
                        z += 1
                    del self.currentPanelList[x]

                    if len(self.panelList) == 0:
                        self.programPanels('event')
                        
                    continue
            x += 1

        # update panel ips
        x = 0
        while x < len(self.currentPanelList):
            for y in panelList:
                if self.currentPanelList[x].int3MAC == y[1]:
                    if self.currentPanelList[x].ip != y[0]:
                        self.currentPanelList[x].ip = y[0]
                        z = 0
                        while z < len(programThreads):
                            if self.currentPanelList[x].ssid == programThreads[z][0]:
                                Publisher.sendMessage('ip',  ip = self.currentPanelList[x].ip, ssid = self.currentPanelList[x].ssid)
                            z += 1
            x += 1

        # use states to change program status for downgrade and autoscript process
        x = 0
        while x < len(self.currentPanelList): 
            if self.currentPanelList[x].state is True and self.currentPanelList[x].stateChanged is True and self.currentPanelList[x].progStatus == 1: #first reset after downgrade
                self.currentPanelList[x].progStatus = 2
                y = 0
                while y < len(programThreads):
                    if self.currentPanelList[x].ssid == programThreads[y][0]:
                        Publisher.sendMessage('panelprogress', progStatus = self.currentPanelList[x].progStatus, ssid = self.currentPanelList[x].ssid)
                    y += 1
            elif self.currentPanelList[x].state is True and self.currentPanelList[x].stateChanged is True and self.currentPanelList[x].progStatus == 2: # second reset after autoscript has finished running
                self.currentPanelList[x].progStatus = 3
                y = 0
                while y < len(programThreads):
                    if self.currentPanelList[x].ssid == programThreads[y][0]:
                        Publisher.sendMessage('panelprogress', progStatus = self.currentPanelList[x].progStatus, ssid = self.currentPanelList[x].ssid)
                    y += 1
            x += 1

    # Updates currentPanelList from threads
    def updatePanel(self, panel):
        x = 0
        while x < len(self.currentPanelList):
            if self.currentPanelList[x].ssid == panel.ssid:
                self.currentPanelList[x] = panel
                break
            x += 1
            
        ssid = self.panelStatusLabel.GetLabel() # Gets ssid from status label
        ssid = ssid[0:len(ssid)-7]

        if panel.ssid == ssid: # Updates gauge if currently displayed
            self.panelStatusGauge.SetValue(panel.progStatus)

    # Get uo from panelQuery   
    def catchIP(self, ip, ssid): # Updates panel ip in panel program threads
        global programThreads
        x = 0
        while x < len(programThreads):
            if ssid == programThreads[x][0]:
                programThreads[x][1].panel.ip = ip
                break

    # Gets programming from a panel thread        
    def catchProgStatus(self, progStatus, ssid): # Update program status
        global programThreads
        x = 0
        while x < len(programThreads):
            if ssid == programThreads[x][0]:
                programThreads[x][1].panel.progStatus = progStatus
                break

    #Simple function to write to google sheets after programming
    def writeToSheet(self, panel): # Write panel data to sheet
        self.sheetData.write(panel)

    # Opens "About" menu when pressed
    def OnAbout(self, event): # About menu button
        # Create a message dialog box
        dlg = wx.MessageDialog(self, "GUI made by Kai McGregor\nUnderlying code written by David Johnson and Kai McGregor\n", "About Kai-ACK", wx.OK)
        dlg.ShowModal() # Shows it
        dlg.Destroy() # finally destroy it when finished.

    # Exit menu button, closes all things required and saves everything to encrypted dict files
    def OnExit(self, event): # Exit menu button
        with open(resource_path('settings.txt'), 'w') as file:
            if self.encompDir is None:
                self.encompDir = ''
            if self.username is None:
                self.username = ''
            if self.password is None:
                self.password = ''

            settings = { 'Name' : self.programmerNameTextBox.GetValue(),
                         'SiteName' : self.siteNameTextBox.GetValue(),
                         'EncompDir' : self.encompDir,
                         'Username' : self.username,
                         'Password' : self.password
                        }
                
            json.dump(settings, file)

        with open('settings.encrypted', 'wb') as file:
            with open(resource_path('settings.txt'), 'r') as file2:
                file.write(self.key.encrypt(file2.read().encode()))
        
        self.programPanel = False # Change toggle var on exit to end the loop
        try:
            global programThreads
            del programThreads
        except NameError:
            pass

        kaiack.options.Close(True)
        self.Close(True)# Close the frame.

# Class to hold UI objects
class UIApp(wx.App):
    def createUI(self):
        self.UI = panelProgramUI(None, 'Kai-ACK')

    def createOptions(self):
        self.options = optionsMenu.menuOptionsUI(self.UI, wx.ID_ANY, "")
        
# Start GUI
if __name__ == '__main__':
    kaiack = UIApp(False)
    kaiack.createUI()
    kaiack.createOptions()

    kaiack.MainLoop()
