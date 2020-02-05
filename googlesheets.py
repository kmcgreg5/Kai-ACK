# Written by Kai McGregor for use in Kai-ACK

import gspread
import math
from oauth2client.client import HttpAccessTokenRefreshError
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

credentials = {} #dict containing credential information that was removed before making this repo public

def getHeaderIndex(cellList, stringMatch, startPosition = 1): #looks for matching strings in list, stripped of spaces and lowercased
    headerIndex = 1
    for x in cellList:
        if headerIndex >= startPosition:
            
            if stringMatch[0].strip().lower() in x.strip().lower():
                if stringMatch[0].strip().lower() == '1' or stringMatch[0].strip().lower() == '':
                    if stringMatch[0].strip().lower() == x.strip().lower():
                        break
                elif len(stringMatch) == 1:
                    break
                elif stringMatch[1].strip().lower() in x.strip().lower():
                    break
        headerIndex += 1
    return headerIndex

def getNewList(cellList, startPosition, endPosition): #grabs lists of SSIDS and DDNS hostnames
    cellCount = 1
    newList = []
    for x in cellList:
        x = x.strip()
        if (cellCount >=startPosition and cellCount <= endPosition):
            newList.append(x)
        elif (cellCount > endPosition):
            break
        cellCount += 1
    return newList

class panel(): #class for individual panels
    def __init__(self, panelSSID, ip, ddnsHostname, int3MAC, optionsList, siteDir, newCerts, state = True, stateChanged = False, initPassword = '', panelProgStatus = 0):
        self.ssid = panelSSID #panel ssid
        self.ip = ip #panel ip
        self.sitePassword = '' #site password
        self.initPassword = initPassword #initial password, normally blank
        self.int3MAC = int3MAC # MAC address for mikrotik on port three, needed to keep track of panels
        self.tikMAC = '' #mikrotik MAC
        self.tikSN = '' #mikrotik SN
        self.apMAC = '' #ap MAC
        self.apSN = '' #ap SN
        self.wattMAC = '' #wattbox MAC
        self.wattSN = '' #wattbox SN
        self.siteDir = siteDir
        self.newCerts = newCerts
        self.state = state # whether panel is on or off
        self.stateChanged = stateChanged # whether state changed on last query or not
        self.ddnsHostname = ddnsHostname #ddns hostname for dynu script
        self.progStatus = panelProgStatus #indicates the stage that the panel is at in the programming process
        self.optionsList = optionsList # list of alternate programming methods from front-end

# Populates spreadsheet data
class spreadsheetData():
    def __init__(self, sheetName, siteDir):
        # Finds and opens spreadsheet based on the sheet name
        scope = ('https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive')

        authorization = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
        self.gc = gspread.authorize(authorization)
            
        # Gets the AP Zone name and Controller IP off of the NAF
        worksheetFound = True
        self.apZone = ''
        self.controllerIP = ''
        try:
            self.wks = self.gc.open(sheetName).worksheet('Network Activation Form')
        except gspread.exceptions.WorksheetNotFound:
            try:
                self.wks = self.gc.open(sheetName).worksheet('NETWORK ACTIVATION FORM')
            except gspread.exceptions.WorksheetNotFound:
                worksheetFound = False
                
        if worksheetFound is True:
            colValues = self.wks.col_values(1)
            apZoneIndex = getHeaderIndex(colValues, ['Property', 'Name'])
            ruckusController = getHeaderIndex(colValues, ['Ruckus', 'Controller'])
            self.apZone = self.wks.cell(apZoneIndex, 2).value.strip()
            self.controllerIP = self.wks.cell(ruckusController, 2).value.strip()
            while True:
                if self.controllerIP[len(self.controllerIP)-1].isdigit() is False:
                    self.controllerIP = self.controllerIP[:len(self.controllerIP)-1]
                else:
                    break
                
            try:
                index = 0
                while True:
                    if self.controllerIP[index:index+3].isdigit() is False:
                        index = index + 1
                    else:
                        break
                    
                self.controllerIP = self.controllerIP[index:len(self.controllerIP)-5]
            except ValueError:
                self.controllerIP = None

        # Adds site password to master list
        worksheetFound = True
        try:
            passwordWKS = self.gc.open('Site Password Master List').worksheet('Programming Passwords')
        except gspread.exceptions.SpreadsheetNotFound:
            worksheetFound = False
        except (httplib2.ServerNotFoundError, requests.exceptions.ConnectionError, TimeoutError):
            worksheetFound = False
        except IndexError:
            worksheetFound = False

        if worksheetFound is True:
            siteList = passwordWKS.col_values(1)
            passList = passwordWKS.col_values(2)

            x = 0
            while x < len(passList):
                passList[x] = passList[x].strip()
                x += 1

            x =  1
            index1 = None
            index2 = None
            for site in siteList:
                site = site.strip()
                if site == '':
                    index2 = index1
                    index1 = x
                    if index1 is not None and index2 is not None:
                        if (index1 - 1) == index2:
                            break

                x += 1

            if index1 is not None and index2 is not None:
                if (index1 - 1) != index2:
                    index2 = len(siteList) + 1
            else:
                index2 = len(siteList) + 1

            password = open(siteDir + '\\Password.txt','r')
            sitePassword = password.read().strip()
            password.close()
            addToList = True
            for password in passList:
                password = password.strip()
                if password == sitePassword:
                    addToList = False

            if addToList is True:
                print('Site Password added to Master List')
                passwordWKS.update_cell(index2, 1, self.apZone)
                passwordWKS.update_cell(index2, 2, sitePassword)

        # Load sheetData
        try:
            self.wks = self.gc.open(sheetName).worksheet('Programming')
        except gspread.exceptions.WorksheetNotFound:
            self.wks = self.gc.open(sheetName).worksheet('Asset Inventory')

        sheetValues = self.wks.get_all_values()
        
        col1List = []
        x = 0
        while x < len(sheetValues):
            col1List.append(sheetValues[x][0])
            x += 1
            
        headerIndex = getHeaderIndex(col1List, ['count']) - 1
        self.ssidIndex = getHeaderIndex(sheetValues[headerIndex],['ssid'])
        self.ddnsHostnameIndex = getHeaderIndex(sheetValues[headerIndex],['ddns', 'hostname'])
        self.dateIndex = getHeaderIndex(sheetValues[headerIndex], ['date'])
        self.mtMACIndex = getHeaderIndex(sheetValues[headerIndex],['mikrotik', 'mac'])
        self.mtSNIndex = getHeaderIndex(sheetValues[headerIndex],['mikrotik', 'sn'])
        self.apMACIndex = getHeaderIndex(sheetValues[headerIndex],['ruckus', 'mac'])
        self.apSNIndex = getHeaderIndex(sheetValues[headerIndex],['ruckus', 'sn'])
        self.wbMACIndex = getHeaderIndex(sheetValues[headerIndex],['watt box', 'mac'])
        self.wbSNIndex = getHeaderIndex(sheetValues[headerIndex],['watt box', 'sn'])
        self.programmerIndex = getHeaderIndex(sheetValues[headerIndex], ['programmer'])
        self.panelStartIndex = getHeaderIndex(col1List, ['1'])

        ssidPanelEndList = []
        x = 0
        while x < len(sheetValues):
            ssidPanelEndList.append(sheetValues[x][self.ssidIndex - 1])
            x += 1
            
        self.panelEndIndex = getHeaderIndex(ssidPanelEndList,[''],self.panelStartIndex) - 1
        
        self.ddnsList = []
        x = 0
        while x < len(sheetValues):
            if x >= self.panelStartIndex - 1 and x <= self.panelEndIndex - 1:
                self.ddnsList.append(sheetValues[x][self.ddnsHostnameIndex - 1])
            x += 1
        
        x = 0
        while x < len(self.ddnsList):
            self.ddnsList[x] = self.ddnsList[x].replace('\"','') # removes quotation marks from ddns hostnames
            x += 1

        self.ssidList = []
        x = 0
        while x < len(sheetValues):
            if x >= self.panelStartIndex - 1 and x <= self.panelEndIndex - 1:
                self.ssidList.append(sheetValues[x][self.ssidIndex - 1])
            x += 1
          
        while (len(self.ddnsList) < len(self.ssidList)): #makes lists equal in size
            self.ddnsList.append('None')

        self.doubleAPList = self.getDoubleAPList() # list of double aps, needs 'fixing'
        self.completedList = self.getCompletedPanels()

    # Returns wbSN list indicating completed panels
    def getWbSNList(self):
        wbSNList = getNewList(self.wks.col_values(self.wbSNIndex), self.panelStartIndex, self.panelEndIndex)
        while (len(wbSNList) < len(self.ssidList)):
            wbSNList.append('None')
        return wbSNList

    # Gets programmer list based on a programmers name
    def getProgrammerList(self, programmerName):
        while True:
            try:
                allProgrammerList = getNewList(self.wks.col_values(self.programmerIndex), self.panelStartIndex, self.panelEndIndex)
                self.completedList = self.getCompletedPanels()
                programmerList = []
                x = 0
                while x < len(allProgrammerList):
                    if allProgrammerList[x] == programmerName and self.ssidList[x] != self.completedList[x]:
                        programmerList.append(self.ssidList[x])

                    x += 1
                    
                break
                    
            except gspread.exceptions.APIError:
                print('credentials refreshed')
                while True:
                    try:
                        self.gc.login()
                        break
                    except HttpAccessTokenRefreshError:
                        time.sleep(1)
                

        return programmerList

    # Gets a list of double APs
    def getDoubleAPList(self): # Used to remove panels from the programmer lists and other lists
        x = 0
        doubleAPList = []
        while x < len(self.ssidList):
            if (self.ddnsList[x] == ''):
                doubleAPList.append(self.ssidList[x])
            else:
                doubleAPList.append('None')
            x += 1
            
        return doubleAPList

    def programDoubleAPList(self, programmerName):
        while True:
            try:
                allProgrammerList = getNewList(self.wks.col_values(self.programmerIndex), self.panelStartIndex, self.panelEndIndex)
                apMACList = getNewList(self.wks.col_values(self.apMACIndex), self.panelStartIndex, self.panelEndIndex)
                apSNList = getNewList(self.wks.col_values(self.apSNIndex), self.panelStartIndex, self.panelEndIndex)
                allDoubleAPList = self.getDoubleAPList()
                completedList = self.getCompletedPanels()
                lowestLen = len(apMACList)
                while max(len(allProgrammerList), len(apMACList), len(apSNList), len(allDoubleAPList), len(completedList)) != lowestLen or min(len(allProgrammerList), len(apMACList), len(apSNList), len(allDoubleAPList), len(completedList)) != lowestLen:
                    if len(allProgrammerList) > lowestLen:
                        del allProgrammerList[len(allProgrammerList)-1]
                    elif len(allProgrammerList) < lowestLen:
                        allProgrammerList.append('')
                    if len(apMACList) > lowestLen:
                        del apMACList[len(apMACList)-1]
                    elif len(apMACList) < lowestLen:
                        apMACList.append('')
                    if len(apSNList) > lowestLen:
                        del apSNList[len(apSNList)-1]
                    elif len(apSNList) < lowestLen:
                        apSNList.append('')
                    if len(allDoubleAPList) > lowestLen:
                        del allDoubleAPList[len(allDoubleAPList)-1]
                    elif len(allDoubleAPList) < lowestLen:
                        allDoubleAPList.append('')
                    if len(completedList) > lowestLen:
                        del completedList[len(completedList)-1]
                    elif len(completedList) < lowestLen:
                        completedList.append('')
            
                x = 0
                doubleAPList = []
                y = 253
                while x < len(apMACList):
                    if allDoubleAPList[x] == self.ssidList[x] and programmerName == allProgrammerList[x + (y - 254)] and apMACList[x].strip() != ''  and apSNList[x].strip() == '' and self.ssidList[x + (y - 254)] == completedList[x + (y - 254)]:
                        doubleAPList.append([self.ssidList[x], ':'.join(a+b for a,b in zip(apMACList[x][::2], apMACList[x][1::2])), '10.10.10.' + str(y)])
                        y = y - 1
                    else:
                        y = 253
                    x += 1
                    
                break
            except gspread.exceptions.APIError:
                print('credentials refreshed')
                while True:
                    try:
                        self.gc.login()
                        break
                    except HttpAccessTokenRefreshError:
                        time.sleep(1)
                    
        return doubleAPList
        
    def getCompletedPanels(self): #returns list of completed panels
        while True:
            try:
                wbSNList = self.getWbSNList()
                completedList = [] 
                x = 0
                while x < len(wbSNList):
                    
                    if wbSNList[x].strip() != '' and wbSNList[x].strip() != 'None' and self.ssidList[x].strip() != self.doubleAPList[x].strip():
                        completedList.append(self.ssidList[x].strip())
                    else:
                        completedList.append('None')
                    x += 1
                break
            except gspread.exceptions.APIError:
                print('credentials refreshed')
                while True:
                    try:
                        self.gc.login()
                        break
                    except HttpAccessTokenRefreshError:
                        time.sleep(1)
            
        return completedList
    
    def getDDNSHostname(self, panelSSID):
        index = self.ssidList.index(panelSSID)
        return self.ddnsList[index]
        
    def ssidPosition(self, panelSSID): #returns panel position on spreadsheet based on ssidList and given ssid
        return self.ssidList.index(panelSSID) + self.panelStartIndex
            
    def write(self, panelWrite): #object from panel class should be passed, writes to spreadsheet
        while True:
            try:
                panelPosition = self.ssidPosition(panelWrite.ssid)
                cellList = []
                cellList.append(gspread.models.Cell(panelPosition, self.mtMACIndex, value = panelWrite.tikMAC))
                cellList.append(gspread.models.Cell(panelPosition, self.mtSNIndex, value = panelWrite.tikSN))
                d = date.today()
                cellList.append(gspread.models.Cell(panelPosition, self.dateIndex, value = str(d.month) + '/' + str(d.day) + '/' + str(d.year)))
                if panelWrite.optionsList['AP'] is True:
                    cellList.append(gspread.models.Cell(panelPosition, self.apMACIndex, value = panelWrite.apMAC))
                    cellList.append(gspread.models.Cell(panelPosition, self.apSNIndex, value = panelWrite.apSN))
                if panelWrite.optionsList['Wattbox'] is True:
                    cellList.append(gspread.models.Cell(panelPosition, self.wbMACIndex, value = panelWrite.wattMAC))
                    cellList.append(gspread.models.Cell(panelPosition, self.wbSNIndex, value = panelWrite.wattSN))
                self.wks.update_cells(cellList)
                break
                
            except gspread.exceptions.APIError as error:
                if '\"code\": 400' in str(error.response.content):
                    print('old write process used')
                    panelPosition = self.ssidPosition(panelWrite.ssid) #determine location on sheet based on SSID
                    self.wks.update_cell(panelPosition, self.mtMACIndex, panelWrite.tikMAC) #write Mikrotik MAC
                    self.wks.update_cell(panelPosition, self.mtSNIndex, panelWrite.tikSN) #write Mikrotik SN
                    d = date.today()
                    self.wks.update_cell(panelPosition, self.dateIndex, str(d.month) + '/' + str(d.day) + '/' + str(d.year))
                    if panelWrite.optionsList['AP'] is True:
                        self.wks.update_cell(panelPosition, self.apMACIndex, panelWrite.apMAC) #write AP MAC
                        self.wks.update_cell(panelPosition, self.apSNIndex, panelWrite.apSN) #write AP SN
                    if panelWrite.optionsList['Wattbox'] is True:
                        self.wks.update_cell(panelPosition, self.wbMACIndex, panelWrite.wattMAC) #write Wattbox MAC
                        self.wks.update_cell(panelPosition, self.wbSNIndex, panelWrite.wattSN) #write Wattbox SN
                    break
                
                print('credentials refreshed')
                while True:
                    try:
                        self.gc.login()
                        break
                    except HttpAccessTokenRefreshError:
                        time.sleep(1)

    def writeDoubleAP(self, apWrite):
        while True:
            try:
                for ap in apWrite:
                    panelPosition = self.ssidPosition(ap[0])
                    self.wks.update_cell(panelPosition, self.apMACIndex, ap[1]) # Write AP MAC of doubleAP list to spreadsheet
                    self.wks.update_cell(panelPosition, self.apSNIndex, ap[2])
                break
            except gspread.exceptions.APIError:
                print('credentials refreshed')
                while True:
                    try:
                        self.gc.login()
                        break
                    except HttpAccessTokenRefreshError:
                        time.sleep(1)

'''
import _pickle as cPickle
siteData = spreadsheetData('35 east 75th st - new york ny naf', 'C:\\Users\\HDTVCI-User\\Desktop\\50 West Fourth')
'''
