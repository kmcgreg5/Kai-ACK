# Written by David Johnson
# Implemented by Kai McGregor for use in Kai-ACK
# 1.7634, double ap functionality, double not on controller fix

'''
PURPOSE
This file contains functions for communicating with a Ruckus SmartZone
controller.

It also contains functionality to work with Kai-ACK.
'''
# ------------------------------------------------------------------------------
'''
FUNCTIONALITY
MikroTiks tell the AP to connect to a controller through Option 43, which has a
control IP of the first controller in a cluster.

The control IP is usually associated with the first management IP in that
cluster.
'''
# ------------------------------------------------------------------------------
'''
OBJECTS
    --NO KAI-ACK--
    If you want to use RuckusLibrary separate of Kai-ACK, you must create an
    object using the controllerInputObject class.

    Once that's done, create a Session like so:

        with requests.session() as sessionID:

    Then place your code to login within your session. Like so:

    with requests.session() as sessionID:
        for ip in userInputObject.controllerCluster:
            loginAttempt = RuckusLibrary.loginRuckus(sessionID, userInputObject, ip)
            if loginAttempt == 200:
                sessionIP = ip
                break
            time.sleep(1)

        **************YOUR FUNCTIONS GO HERE**************

        RuckusLibrary.logoutRuckus(sessionID, sessionIP)

    Some functions may require previous info to get retrieved. It's good measure
    to create an object using the initializeZoneInfo class if you're doing
    anything AP/zone related.

    --WITH KAI-ACK--
    RuckusLibrary is used alongside Kai-ACK.
    The programKaiACK class is used to program both single and double APs.

    Kai-ACK displays messages to the user through a library called Publisher.
    When 'panel' object is being passed in - Publisher messages are being used.
'''
# ------------------------------------------------------------------------------
# Python/3rd Party Libraries
import requests
import time
import json
import socket
import urllib3
# UI Libraries
import googlesheets
import traceback  # helps identify errors
from pubsub import pub as Publisher  # used to post messages in UI
import wx  # used for login error message

# urllib3.disable_warnings(urllib3.exceptions.NewConnectionError, urllib3.exceptions.MaxRetryError)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# controller API communicates through HTTP requests. It requires each command
# to have certain info sent with it to properly understand what's being sent
# These headers are used in every command except the Login
universalHeaders = {
    'Content-Type': 'application/json;charset=UTF-8'
    }
# These cookies are used in every command except the Login
universalCookies = {
    'Cookie': 'JSESSIONID={JSESSIONID}'
    }

# --------------------------------CLASSES---------------------------------------
class initializeZoneInfo:  # retrieves static zone information
    def __init__(self, userInputObject):
        self.userInputObject = userInputObject
        # --------------------------------------------
        self.apZoneName = userInputObject.apZoneName
        self.apGroupList = ''
        self.apGroupID = ''
        self.apZoneList = ''
        self.apZoneID = ''
        self.sessionIP = ''  # zone info class uses sessionIP inside its functions
        self.validSession = False  # used in each function to check if session is good
    def retrieveZoneInfo(self):
        sessionID = requests.session()  # ID used to store session cookies  # ID used to store session cookies
        print('\n*****************************Retrieving AP lists...*****************************')
        loginAttempt = loginRuckus(sessionID, self, self.userInputObject)
        if loginAttempt == 200:  # login successful
            zoneList = retrieveZoneList(sessionID, self, self.userInputObject)

            if zoneList == 200:
                retrieveAPGroupList(sessionID, self, self.userInputObject)

                logoutRuckus(sessionID, self.sessionIP)
                self.sessionIP = None

                print('******************************AP Lists retrieved.*******************************\n')
                return 200
            elif zoneList == 404:  # zone not found with name given
                return 404  # zone name incorrect

        elif loginAttempt == 202:  # login username/password incorrect
            print('Controller username or password is incorrect.')
            return loginAttempt
        else:  # login not successful
            print(loginAttempt)
            return loginAttempt

        return False  # all ips failed on login

class initializeWLANInfo:  # retrieves IDs for WLAN groups
    def __init__(self):
        self.wlanGroupID = ''
        self.wlanGroupName = ''
        self.wlanGroupGuestID = ''
        self.wlanGroupGuestName = ''

class initializeAP:
    def __init__(self):
        self.apMAC = ''
        self.apSN = ''
        self.apSSID = ''
        self.apIP = ''
        self.apModel = ''
        wlanInfo = initializeWLANInfo()
        self.wlanInfo = wlanInfo

class programKaiACK:  # skeleton class that calls objects for programming APs
    def __init__(self, userInputObject):
        # STORES USER INPUTS & OBJECTS
        self.userInputObject = userInputObject  # used in zoneInfo & prog APs
        # -------------------------------------
        self.zoneInfoObject = None

    def kaiACKRetrieveZoneInfo(self):
        # ZONE INFO
        self.zoneInfoObject = initializeZoneInfo(self.userInputObject)  # initializes zoneInfo object
        zoneInfoStatus = self.zoneInfoObject.retrieveZoneInfo()  # populates zoneInfo object with IDs
        return zoneInfoStatus  # will return True or False

    def kaiACKProgramSingleAP(self, panel):
        print('\n*****************************Programming single AP.*****************************')
        apWLANInfoObj = initializeWLANInfo()  # used to store WLAN group IDs
        apInfoObj = initializeAP()  # creates temp object that uses panel attributes
        apInfoObj.apSSID = panel.ssid
        apInfoObj.apMAC = panel.apMAC
        apInfoObj.apIP = '10.10.10.254'
        panel.apSN = '' # panel obj takes SN at end of process
        self.zoneInfoObject.validSession = False  # used in each function to check if session is good

        # checks for required info from AP Info object
        if self.zoneInfoObject.apZoneID == None:
            print("Couldn't find AP Zone. Please relaunch and enter a valid zone.")
            Publisher.sendMessage('status', ssid=panel.ssid, message="Couldn't find AP Zone. Please relaunch and enter a valid zone.", group = 1)
            return panel

        sessionID = requests.session()  # ID used to store session cookies
        # -------------------------RETRIEVES DATA---------------------------
        # operates if required AP Lists info is retrieved successfully
        # or doesn't recieve the info it needs from a previous command

        while True:  # MASTER BLOCK, REDOES SESSIONS IF INVALID MIDWAY

            # LOGIN BLOCK
            printLoginPublisher = True
            while self.zoneInfoObject.validSession is False:  # loops until session is established
                # selects controller ip to use for programming process
                loginAttempt = loginRuckus(sessionID, self.zoneInfoObject, self.userInputObject)
                if loginAttempt == 200:
                    Publisher.sendMessage('status', ssid=panel.ssid, message='Ruckus Controller logged in.', group = 1)
                    break
                elif printLoginPublisher is True:
                    Publisher.sendMessage('status', ssid=panel.ssid, message='Controller login error. Retrying...', group = 1)
                    printLoginPublisher = False  # stops login publisher messages
                if self.zoneInfoObject.validSession is True:  # ends LOGIN BLOCK
                    break  # continues to next loop

            # PROGRAMMING BLOCK
            while self.zoneInfoObject.validSession is True:
                retrieveWLANGroupList(sessionID, self.zoneInfoObject, self.userInputObject, apInfoObj)
                if 'Guest'.lower() in apInfoObj.wlanInfo.wlanGroupName:
                    print("Guest WLAN used. Couldn't find unit specific WLAN for AP.")
                if apInfoObj.wlanInfo.wlanGroupID != '':
                    Publisher.sendMessage('status', ssid=panel.ssid, message='WLAN IDs retrieved.', group = 1)
                else:  # wlanGroupIDs weren't found
                    Publisher.sendMessage('status', ssid=panel.ssid, message='No WLAN IDs retrieved.', group = 1)
                    return False

                # -------------------------CHANGES DATA-----------------------
                showZoneStatus = True  # variable that sets publisher messages to only print once
                # CHANGE ZONE
                while self.zoneInfoObject.validSession is True:
                    changeAPZoneResponse = changeAPZone(sessionID, self.zoneInfoObject, self.userInputObject, apInfoObj)
                    if changeAPZoneResponse == 204:
                        Publisher.sendMessage('status', ssid=panel.ssid, message='AP zone changed.', group = 1)
                        break
                    elif changeAPZoneResponse == 403:
                        if showZoneStatus == True:
                            Publisher.sendMessage('status', ssid=panel.ssid, message='Controller not accepting commands. Make sure AP is on the controller...', group = 1)
                            showZoneStatus = False
                        time.sleep(10)
                    else:
                        if showZoneStatus == True:
                            Publisher.sendMessage('status', ssid=panel.ssid, message='AP zone changed failed, Retrying...', group = 1)
                            showZoneStatus = False
                        time.sleep(10)

                # CHANGE CONFIG
                changeAPConfigResponse = changeAPConfig(sessionID, self.zoneInfoObject, self.userInputObject, apInfoObj)
                if changeAPConfigResponse is 204:
                    Publisher.sendMessage('status', ssid=panel.ssid, message='AP configured.', group = 1)
                elif changeAPConfigResponse == 211:
                    Publisher.sendMessage('status', ssid=panel.ssid, message='Changing AP config failed. AP Not found on controller...', group = 1)
                else:
                    Publisher.sendMessage('status', ssid=panel.ssid, message='AP configuration failed, Retrying...', group = 1)

                # QC BLOCK
                #  --------------------checkAPConfig return---------------------
                #  [returnStatus, apName, zoneID, apGroupID, wlanGroup24ID, wlanGroup50ID, ipType, modelSpecific]
                #  --------------------incorrect setting format----------------
                #  apName = [retrieveAPConfig['name'], False]
                # returnStatus should return True, and everything else false
                #                         ex. qcAP[ap][y]
                # x refers to returnStatus, and y refers to the setting. y has 2 indexes (name and boolean)
                qcAP = checkAPConfig(sessionID, False, self.zoneInfoObject, self.userInputObject, apInfoObj)
                if qcAP[0] == True:  # ends program single AP
                    print('AP settings correct.')
                    logoutRuckus(sessionID, self.zoneInfoObject.sessionIP)

                    panel.apSN = apInfoObj.apSN
                    print('******************************Programmed single AP.*****************************\n')
                    return panel  # ends program single AP
                elif qcAP[0] == False:  # returnStatus is false
                    print('Detected AP error. Performing quality control.')
                    if qcAP[1][1] is False:  # apName
                        print('AP Name incorrect: ' + str(qcAP[1][0]))
                    if qcAP[2][1] is False:  # zoneID
                        print('Zone incorrect: ' + str(qcAP[2][0]))
                    if qcAP[3][1] is False:  # apGroupID
                        print('AP Group incorrect: ' + str(qcAP[3][0]))
                    if qcAP[4][1] is False:  # wlanGroup24ID
                        print('2.4Ghz WLAN incorrect: ' + str(qcAP[4][0]))
                    if qcAP[5][1] is False:  # wlanGroup50ID
                        print('5.0Ghz WLAN incorrect: ' + str(qcAP[5][0]))
                    if qcAP[6][1] is False:  # ipType
                        print('IP Type incorrect: ' + str(qcAP[6][0]))
                break  # breaks programming block


    def programDoubleAP(self, ssidList, apMACList, doubleAPList):
        # this is one of the messier functions. wasn't really thought out beforehand,
        # but it's functional. at some point we'll rewrite it
        self.zoneInfoObject.validSession = False  # used in each function to check if session is good
        sessionID = requests.session()  # ID used to store session cookies
        print('\n****************************Programming Double APs...***************************')

        if self.zoneInfoObject.apZoneID == None:
            print("Couldn't find AP Zone. Please relaunch and enter a valid zone.")
            Publisher.sendMessage('status', ssid='Double APs', message="Couldn't find AP Zone. Please relaunch and enter a valid zone.")
            return False


        # LOGIN BLOCK
        printLoginPublisher = True
        while self.zoneInfoObject.validSession is False:  # loops until session is established
            # selects controller ip to use for programming process
            loginAttempt = loginRuckus(sessionID, self, self.userInputObject)
            if loginAttempt == 200:
                Publisher.sendMessage('status', ssid='Double APs', message='Ruckus Controller logged in.')
                break
            elif printLoginPublisher is True:
                Publisher.sendMessage('status', ssid='Double APs', message='Controller login error. Retrying...')
                printLoginPublisher = False  # stops login publisher messages

        # PROGRAMMING BLOCK
        # AP Hierarchy:
        #     Primary AP - Original AP attached to panel
        #     Parent AP - AP which child AP is attached to
        #     Child AP - AP which is attached to either primary/parent APs
        # Double AP List works like this:
        #     ap[SSID, MAC, IP]
        #         ap[0] - SSID
        #         ap[1] - MAC
        #         ap[2] - IP
        ap = 0  # indexing through doubleAPList
        while ap < len(doubleAPList):

            # FIRST SECONDARY AP IN SPREADHSEET
            # CHANGES MODEL SPECIFIC FOR MAIN PANEL
            if doubleAPList[ap][2] == '10.10.10.253':
                ssid = 0  # refers to index of ssidList
                while ssid < len(ssidList):
                    if doubleAPList[ap][0] == ssidList[ssid]:
                        # panel = googlesheets.panel(ssidList[ssid-1], '', '', '', '')
                        primaryAP = initializeAP()
                        primaryAP.apSSID = ssidList[ssid-1]
                        primaryAP.apMAC = apMACList[ssid-1]
                        print('Now modifying: ' + primaryAP.apSSID)
                        # print(doubleAPList[ap][0])
                        break
                    ssid += 1
                wlanGroupList = retrieveWLANGroupList(sessionID, self.zoneInfoObject, self.userInputObject, primaryAP)

                # changes config then QCs
                while True:  # loops for model specific of first child AP to operate until correct
                    changeAPSpecific(sessionID, self.zoneInfoObject, self.userInputObject, primaryAP)
                    qcAP = checkAPConfig(sessionID, True, self.zoneInfoObject, self.userInputObject, primaryAP)
                    # ------------------------------QC----------------------
                    # --------------------checkAPConfig return---------------------
                    # [returnStatus, apName, zoneID, apGroupID, wlanGroup24ID, wlanGroup50ID, ipType, modelSpecific]
                    # --------------------incorrect setting format----------------
                    # apName = [retrieveAPConfig['name'], False]
                    # returnStatus should return True, and everything else false
                    #                        ex. qcAP[ap][y]
                    # x refers to returnStatus, and y refers to the setting. y has 2 indexes (name and boolean)
                    if qcAP[0] is True:
                        Publisher.sendMessage('status', ssid='Double APs', message=primaryAP.apSSID + ' model specific option enabled')
                        print('AP settings correct.')
                        break

                    elif qcAP[0] == False:  # returnStatus is false
                        print('Detected AP error. Performing quality control.')
                        if qcAP[7][1] is False:  # modelSpecific
                            print('Model specific incorrect: ' + str(qcAP[7][0]))

            # -------------------------------------------------------------------------------------------------------

            # # NO SECONDARY AP IN SPEADSHEET
            # if primaryAP.wlanInfo.wlanGroupName is '':
            #     Publisher.sendMessage('status', ssid='Double APs', message=primaryAP.apSSID + ' skipped')
            #     continue

            # -------------------------------------------------------------------------------------------------------

            # CHANGES CONFIGURATION FOR CHILD APS
            # doubleAPPanel = googlesheets.panel(doubleAPList[ap][0], '', '', '', '')  # creates panel object to store ssid + mac
            childAP = initializeAP()
            childAP.apSSID = doubleAPList[ap][0]  # sets ap ssid
            childAP.apMAC = doubleAPList[ap][1]  # sets ap mac
            childAP.apIP = doubleAPList[ap][2]  # sets static ip
            childAP.wlanInfo = primaryAP.wlanInfo  # uses parent AP wlan info
            print('\nNow modifying: ' + childAP.apSSID)
            # doubleAPPanel.apMAC = doubleAPList[ap][1]  # sets ap mac
            # doubleAPPanel.ip = doubleAPList[ap][2]  # sets static ip
            while True:
                showAPStatus = True
                while True:  # loop is for zone change
                    changeAPZoneResponse = changeAPZone(sessionID, self.zoneInfoObject, self.userInputObject, childAP)
                    try:
                        if changeAPZoneResponse == 204:
                            break
                        elif (changeAPZoneResponse == 403) and (showAPStatus is True):  # breaks the code in case the second AP MAC is wrong
                            Publisher.sendMessage('status', ssid='Double APs', message=childAP.apSSID + ' not registered on controller. Waiting until AP is added.')
                            showAPStatus = False
                        else:
                            print('changeAPZoneResponse: ' + str(changeAPZoneResponse))
                        time.sleep(10)
                    except TypeError:  # response was None
                        pass
                changeChildAP = changeAPConfig(sessionID, self.zoneInfoObject, self.userInputObject, childAP)

                qcAP = checkAPConfig(sessionID, True, self.zoneInfoObject, self.userInputObject, childAP)
                if qcAP[0] is True:  # returnStatus is True
                    print('AP settings correct.')
                    break
                elif qcAP[0] is False:  # returnStatus is False
                    print('Detected AP error. Performing quality control.')
                    if qcAP[1][1] is False:  # apName
                        print('AP Name incorrect: ' + str(qcAP[1][0]))
                    if qcAP[2][1] is False:  # zoneID
                        print('Zone incorrect: ' + str(qcAP[2][0]))
                    if qcAP[3][1] is False:  # apGroupID
                        print('AP Group incorrect: ' + str(qcAP[3][0]))
                    if qcAP[4][1] is False:  # wlanGroup24ID
                        print('2.4Ghz WLAN incorrect: ' + str(qcAP[4][0]))
                    if qcAP[5][1] is False:  # wlanGroup50ID
                        print('5.0Ghz WLAN incorrect: ' + str(qcAP[5][0]))
                    if qcAP[6][1] is False:  # ipType
                        print('IP Type incorrect: ' + str(qcAP[6][0]))
                    break
                # -------------------------------------------------------------------------------------------------------------

            # MODEL SPECIFIC FOR PARENT APS (More than 2 on a panel)
            #   Modifies Parents for Child APs
            try:
                apIPSuffix = int(doubleAPList[ap][2][len(doubleAPList[ap][2])-3:len(doubleAPList[ap][2])])  # first ap suffixes
                postAPIPSuffix = int(doubleAPList[ap+1][2][len(doubleAPList[ap+1][2])-3:len(doubleAPList[ap+1][2])])  # second ap suffixes
                if apIPSuffix > postAPIPSuffix:
                    parentAP = initializeAP()
                    parentAP.apSSID = doubleAPList[ap][0]
                    parentAP.apMAC = doubleAPList[ap][1]
                    # panel = googlesheets.panel(doubleAPList[ap][0], '', '', '', '')
                    # panel.apMAC = doubleAPList[ap][1]

                    # changes config then QCs
                    while True:  # loops for model specific of first child AP to operate until correct
                        changeAPSpecific(sessionID, self.zoneInfoObject, self.userInputObject, parentAP)
                        qcAP = checkAPConfig(sessionID, True, self.zoneInfoObject, self.userInputObject, parentAP)
                        if qcAP[0] == False:  # returnStatus is false
                            print('Detected AP error. Performing quality control.')
                            if qcAP[7][1] is False:  # apName
                                print('AP Name incorrect: ' + str(qcAP[7][0]))
                        else:
                            Publisher.sendMessage('status', ssid='Double APs', message=parentAP.apSSID + ' model specific option enabled')
                            print('AP settings correct.')
                            break

            except IndexError:
                print('AP list finished configuring.')
                pass

            # apConfig = retrieveAPConfig(sessionID, self.zoneInfoObject, self.userInputObject, ???which ap here?????)

            while True:
                try:
                    # doubleAPList[ap][2] = apConfig['serial']  # overrites previous ip
                    doubleAPList[ap][2] = childAP.apSN
                    break
                except KeyError:
                    Publisher.sendMessage('status', ssid='Double APs', message="Couldn't retrieve " + childAP.apSSID + "'s serial. Make sure MAC is in spreadsheet.")
                    time.sleep(5)
                    pass

            # Publisher.sendMessage('status', ssid='Double APs', message=childAP.apSSID + ' SN stored')
            Publisher.sendMessage('status', ssid='Double APs', message=childAP.apSSID + ' configured')


            ap += 1


        logoutRuckus(sessionID, self.zoneInfoObject.sessionIP)
        print('*****************************Programmed Double APs.*****************************\n')
        return doubleAPList


class controllerInputObject:
    def __init__(self, username, password, controllerCluster, controllerPort, apZoneName):
        self.loginUsername = username
        self.loginPassword = password
        self.controllerCluster = controllerCluster
        self.controllerPort = controllerPort
        self.apZoneName = apZoneName

# -----------------------FUNCTION TEMPLATE----------------------------
# def templateFunction(sessionID, controllerCluster):
#     serverResponse = checkController.checkController(controllerCluster, sessionID)
#     loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
#     # ----------------FUNCTION PURPOSE-------------------
#     # body
#     print('Test function operating...')
#     body = {
#           "value": value,
#     }
#
#     try:
#         while serverResponse is False:
#             time.sleep(1)
#             serverResponse = checkController.checkController(controllerCluster, sessionID)
#         # runs until a valid response is returned from the controller
#         returnVal = sessionID.responsetype('https://' + serverResponse + ':8443/wsg/api/public/v6_1/', headers=universalHeaders, cookies=universalCookies, data=json.dumps(body), verify=False)
#         if returnVal.status_code == 200 or 204:  # checks HTTP response code
#             print('Successful.')
#             return value
#         if returnVal.status_code == 403:  # checks HTTP response code
#             print('Failure.')
#             return value
#         if returnVal.status_code == 404:  # checks HTTP response code
#             print('Command not found.')
#             return value
#         if returnVal.status_code == 422:  # checks HTTP response code
#             print('Semantic error.')
#             return value
#         if loginAttempts >= 4:
#             print('Failed to perform test function.')
#             print(returnVal)
#             return value
#         else:
#             loginAttempts += 1
#             print('Test function failed. Retrying...')
#             time.sleep(1)
#     except (socket.gaierror, requests.exceptions.ConnectionError):
#         time.sleep(1)

# -----------------------PROGRAMMING FUNCTIONS BELOW----------------
def loginRuckus(sessionID, zoneInfoObj, userInputObject):
    printPublisherAmount = True # used in a loop, allows publisher messages
    # ---------------------CONTROLLER LOGIN-------------------------------
    print('Logging into Ruckus controller...')
    # login specific header that sets cookies
    loginInitializeCookies = {
        'Set-Cookie:"JSESSIONID': '{JSESSIONID}"',
        'Path': '/wsg'
    }
    # login specific parameters
    loginRequestParameters = (
        ('username', userInputObject.loginUsername),
        ('password', userInputObject.loginPassword),
        ('apiVersions', '"v6_1"'),
        ('timeZoneUtcOffset', '"-04:00"'),
    )
    # body for login request
    loginRequestBody = {
        'username': userInputObject.loginUsername,
        'password': userInputObject.loginPassword,
        'apiVersions': [
            'v6_1'
        ],
        'timeZoneUtvOffset': '-04:00'
    }
    # ----------------------------------------------
    for ip in userInputObject.controllerCluster:
        try:
            # sends login request
            loginRequest = sessionID.post('https://' + ip + ':8443/wsg/api/public/v6_1/session', params=loginRequestParameters, cookies=loginInitializeCookies, data=json.dumps(loginRequestBody), verify=False)
            if loginRequest.status_code == 200:  # checks HTTP response code
                zoneInfoObj.sessionIP = ip
                zoneInfoObj.validSession = True
                print('Logged into Ruckus controller.')
                return 200
            elif loginRequest.status_code == 401:
                print('Controller username or password is incorrect.')
                print(json.dumps(loginRequest.json(), indent=4))
                return 202
            else:
                time.sleep(1)

            # logins to all IPs weren't successful
            print(json.dumps(loginRequest.json(), indent=4))
            return loginRequest.status_code
        except (socket.gaierror, requests.exceptions.ConnectionError, UnboundLocalError):
            print("Login attempt failed, didn't receive connection to controller...")
            time.sleep(5)

def logoutRuckus(sessionID, ip):
    while True:
        try:
            logoutRequest = sessionID.delete('https://' + ip + ':8443/wsg/api/public/v6_1/session', headers=universalHeaders, cookies=universalCookies, verify=False)
            break
        except requests.exceptions.ConnectionError:
            time.sleep(.2)
    print('Logged out of Ruckus Controller.')
    return logoutRequest

def retrieveSessionInfo(sessionID, ip):
    retrieveSessionInfo = sessionID.get('https://' + ip + ':8443/wsg/api/public/v6_1/session', headers=universalHeaders, cookies=universalCookies, verify=False)
    return retrieveSessionInfo.json()

def retrieveZoneList(sessionID, zoneInfoObject, userInputObject):
    # -----------------GETS AVAILABLE ZONE LISTs---------------
    # parameters
    zoneListParameters = (
        ('listSize', '999'),
    )
    print('Retrieving zone list...')
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            apZoneList = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/rkszones', headers=universalHeaders, cookies=universalCookies, params=zoneListParameters, verify=False)
            if apZoneList.status_code == 200:  # checks HTTP response code
                print('Zone list retrieved.')
                apZoneList = apZoneList.json()
                for zones in apZoneList['list']:  # 'zones' is a variable that iterates through list
                    if zones['name'] == zoneInfoObject.apZoneName:
                        print('Zone ID retrieved.')
                        zoneInfoObject.apZoneID = zones['id']
                        zoneInfoObject.apZoneList = retrieveZoneList
                        return 200
                if zoneInfoObject.apZoneID == '':
                    print('Zone not found. Please check zone spelling.')
                    return 404
            else:  # runs if none of the clusters respond
                print(apZoneList.status_code)
                print(json.dumps(apZoneList, indent=4))
                return apZoneList.status_code

        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession = False

        except (TypeError):
            print('Zone list returned NoneType.')
            pass


def retrieveAPGroupList(sessionID, zoneInfoObject, userInputObject):
    # -----------------GETS AVAILABLE ZONE LISTs---------------
    # parameters
    zoneListParameters = (
        ('listSize', '999'),
        )
    print('Retrieving AP group list...')
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            retrieveAPGroupList = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/rkszones/' + zoneInfoObject.apZoneID + '/apgroups', headers=universalHeaders, cookies=universalCookies, params=zoneListParameters, verify=False)
            if retrieveAPGroupList.status_code == 200:  # checks HTTP response code
                print('AP group list retrieved.')
                zoneInfoObject.apGroupList = retrieveAPGroupList.json()
                zoneInfoObject.apGroupID = zoneInfoObject.apGroupList['list'][0]['id']
                return True
            elif retrieveAPGroupList.status_code == 211:
                print('AP zone not found.')
                return retrieveAPGroupList.status_code
            else:
                print('AP group list retrieval failed.')
                print(retrieveAPGroupList.status_code)
                print(retrieveAPGroupList.json())
                return retrieveAPGroupList.status_code
        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession = False


def retrieveAPConfig(sessionID, zoneInfoObject, userInputObject, apInfoObj):
    # ----------------------RETRIEVE AP CONFIGURATION---------------------------
    while True:
        try:
            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID


            # runs until a valid response is returned from the controller
            # gets ap configuration response
            retrieveAPConfig = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/aps/' + apInfoObj.apMAC, headers=universalHeaders, cookies=universalCookies, verify=False)
            print('Retrieving AP Configuration...')
            if retrieveAPConfig.status_code == 200:  # checks HTTP response code
                print('AP configuration retrieval successful.')
                return retrieveAPConfig.json()
            if retrieveAPConfig.status_code == 211:
                print('AP not detected on controller cluster.')
                return retrieveAPConfig.status_code
            if retrieveAPConfig.status_code == 403:
                print('Access was denied requesting AP configuration.')
                return retrieveAPConfig.status_code
            if retrieveAPConfig.status_code == 404:
                print("Can't read AP MAC.")
                return retrieveAPConfig.status_code
            else:
                print(retrieveAPConfig.status_code)
                print(json.dumps(retrieveAPConfig.json(), indent=4))
                return retrieveAPConfig.status_code
        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession = False

def retrieveWLANGroupList (sessionID, zoneInfoObject, userInputObject, apInfoObj):
    # ----------------RETRIEVE WLAN GROUP LIST-------------------
    print('Retrieving WLAN Group list...')
    # parameters
    wlanListParameters = (
        ('listSize', '99999'),
        )
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            # runs until a valid response is returned from the controller
            wlanGroupList = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/rkszones/' + zoneInfoObject.apZoneID + '/wlangroups', headers=universalHeaders, cookies=universalCookies, params=wlanListParameters, verify=False)
            if wlanGroupList.status_code == 200:  # checks HTTP response code
                wlanGroupList = wlanGroupList.json()
                print('WLAN Group list retrieved.')
                for wlanGroup in wlanGroupList['list']:  # 'zones' is a variable that iterates through list
                    # Sets Guest WLAN group as the default
                    if 'guest' in wlanGroup['name'].lower():
                        apInfoObj.wlanInfo.wlanGroupID = wlanGroup['id']
                        apInfoObj.wlanInfo.wlanGroupName = wlanGroup['name']
                        apInfoObj.wlanInfo.wlanGroupGuestID = wlanGroup['id']
                        apInfoObj.wlanInfo.wlanGroupGuestName = wlanGroup['name']
                        break
                    else:
                        'No guest WLAN Group found.'
                # --------------SSID WLAN Group CHOSEN---------------
                for wlans in wlanGroupList['list']:
                    if wlans['name'] == apInfoObj.apSSID:
                        print('WLAN for AP found.')
                        apInfoObj.wlanInfo.wlanGroupID = wlans['id']
                        apInfoObj.wlanInfo.wlanGroupName = wlans['name']
                        break
                return 200
            else:
                print('WLAN Group list retrieval failed.')
                print(wlanGroupList.status_code)
                print(json.dumps(wlanGroupList.json(), indent=4))

        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession = False


def retrieveWLANGroupConfig (apIDs, apLists, wlanGroupList, sessionID, controllerCluster, panel):
    # ----------------RETRIEVE WLAN GROUP CONFIGURATION-------------------
    print('Retrieving WLAN group configuration...')
    # this block of code runs through the list of wlan groups and gets our
    # wlangroup id that is needed
    # --------------GUEST WLAN CHOSEN---------------
    # WLAN defaults to guest if the SSID isn't found
    for wlans in wlanGroupList['list']:  # 'zones' is a variable that iterates through list
        if 'guest' in wlans['name'].lower():
            apIDs.wlanGroupID = str(wlans['id'])
            apIDs.wlanGroupName = str(wlans['name'])
            break
        else:
            'No guest WLAN Group found.'
    # --------------SSID WLAN CHOSEN---------------
    for wlans in wlanGroupList['list']:
        if wlans['name'] == panel.ssid:
            apIDs.wlanGroupID = str(wlans['id'])
            apIDs.wlanGroupName = str(wlans['name'])
            break
    # runs until a valid response is returned from the controller
    try:
        retrieveWLANGroupConfig = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlangroups/' + apIDs.wlanGroupID, headers=universalHeaders, cookies=universalCookies, verify=False)
        if retrieveWLANGroupConfig.status_code == 200:  # checks HTTP response code
            print('WLAN group configuration retrieved.')
            return retrieveWLANGroupConfig.json()
        else:
            print('WLAN group configuration retrieval failed. Retrying...')
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Error connecting to controller. Check your internet connection.')
        time.sleep(1)


def changeAPZone(sessionID, zoneInfoObject, userInputObject, apInfoObj):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    print('Changing AP zone...')
    # body for request is converted into json through json.dump
    # body used to change the ap zone
    sendAPConfig = {
        "zoneId": zoneInfoObject.apZoneID,
        "apGroupId": zoneInfoObject.apGroupID,
        "network": {
            "ipType": "Dynamic" # APs set to static before cannot be moved without primary and secondary DNS so it is set to dynamic
        }
    }
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            # runs until a valid response is returned from the controller
            changeAPZone = sessionID.patch('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/aps/' + apInfoObj.apMAC, headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
            if changeAPZone.status_code == 204:  # checks HTTP response code
                print('AP zone changed.')
                return changeAPZone.status_code
            elif changeAPZone.status_code == 403:  # checks HTTP response code
                print("Controller error. 'Change Zone' command sent incorrect syntax.")
                print(json.dumps(changeAPZone.json(), indent=4))
                return changeAPZone.status_code
            elif changeAPZone.status_code == 422:  # checks HTTP response code
                print('AP already in a zone.')
                print(json.dumps(changeAPZone.json(), indent=4))
                return changeAPZone.status_code
            else:
                print('Changing AP zone failed. Retrying...')
                print(changeAPZone.status_code)
                print(json.dumps(changeAPZone.json(), indent=4))
                time.sleep(1)
                return changeAPZone.status_code

        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession = False


def changeAPConfig(sessionID, zoneInfoObject, userInputObject, apInfoObj):
    # ----------------CHANGE BASIC  CONFIGURATION-------------------
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # body
    print('Changing AP configuration...')
    sendAPConfig = {
        "name": apInfoObj.apSSID,
        "description": apInfoObj.apSSID,
        "wlanGroup24": {
            "id": apInfoObj.wlanInfo.wlanGroupID,
            "name": apInfoObj.wlanInfo.wlanGroupName
        },
        "wlanGroup50": {
            "id": apInfoObj.wlanInfo.wlanGroupID,
            "name": apInfoObj.wlanInfo.wlanGroupName
        },
        "network": {
            "ipType": "Static",
            "ip": apInfoObj.apIP,
            "netmask": "255.255.255.0",
            "gateway": "10.10.10.1",
            "primaryDns": "10.10.10.1",
            "secondaryDns": "10.10.10.1"
        },
    }
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            # runs until a valid response is returned from the controller
            changeAPConfig = sessionID.patch('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/aps/' + apInfoObj.apMAC, headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
            if changeAPConfig.status_code == 204:  # checks HTTP response code
                print('AP configuration changed.')
                return 204
            elif changeAPConfig.status_code == 211:
                print('AP not on controller.')
                return 211
            else:
                print('Changing AP configuration failed. Retrying...')
                (changeAPConfig.status_code)
                print(json.dumps(changeAPConfig.json(), indent=4))
                time.sleep(1)
                return changeAPConfig.status_code

        except (socket.gaierror, requests.exceptions.ConnectionError):
            time.sleep(1)
            zoneInfoObject.validSession = False


def checkAPConfig(sessionID, poeSpecific, zoneInfoObject, userInputObject, apInfoObj):
    returnStatus = True
    apName = ['', True]
    zoneID = ['', True]
    apGroupID = ['', True]
    wlanGroup24ID = ['', True]
    wlanGroup50ID = ['', True]
    ipType = ['', True]
    modelSpecific = ['', True]
    # ----------------RETRIEVE AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Retrieving AP configuration...')
    print('Checking AP Configuration.')
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            # gets ap configuration response
            retrieveAPConfig = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_0/aps/' + apInfoObj.apMAC, headers=universalHeaders, cookies=universalCookies, verify=False)
            if retrieveAPConfig.status_code == 200:
                retrieveAPConfig = retrieveAPConfig.json()  # converts config to json
                apInfoObj.apSN = retrieveAPConfig['serial']
                # only checks certain values, if these are present then the others are aswell
                # these values return to the programSingleAP function
                # if a setting isn't correct, an array is created, holding the
                #       incorrect setting and a False value to be checked in programSingleAP
                try:
                    if poeSpecific == True:
                        if retrieveAPConfig['specific'] is None:
                            modelSpecific = ['None', False]
                            returnStatus = False
                        if apInfoObj.apModel == "R610" and retrieveAPConfig['specific']['poeModeSetting'] != '_802_3at':
                            modelSpecific = [retrieveAPConfig['specific']['poeModeSetting'], False]
                            returnStatus = False
                            #needs to check for R510's eventually
                    else:
                        if retrieveAPConfig['name'] != apInfoObj.apSSID:
                            apName = [retrieveAPConfig['name'], False]
                            returnStatus = False
                        if retrieveAPConfig['zoneId'] != zoneInfoObject.apZoneID:
                            zoneID = [retrieveAPConfig['name'], False]
                            returnStatus = False
                        if retrieveAPConfig['apGroupId'] != zoneInfoObject.apGroupID:
                            apGroupID = [retrieveAPConfig['apGroupId'], False]
                            returnStatus = False
                        if retrieveAPConfig['wlanGroup24'] is None:
                            wlanGroup24ID = ['No WLAN Assigned', False]
                            returnStatus = False
                        elif retrieveAPConfig['wlanGroup24']['name'] != apInfoObj.apSSID and 'guest' not in retrieveAPConfig['wlanGroup24']['name'].lower():
                            wlanGroup50ID = [retrieveAPConfig['wlanGroup24']['name'], False]
                            returnStatus = False
                        if retrieveAPConfig['wlanGroup50'] is None:
                            wlanGroup50ID = ['No WLAN Assigned', False]
                            returnStatus = False
                        elif retrieveAPConfig['wlanGroup50']['name'] != apInfoObj.apSSID and 'guest' not in retrieveAPConfig['wlanGroup50']['name'].lower():
                            wlanGroup50ID = [retrieveAPConfig['wlanGroup50']['name'], False]
                            returnStatus = False
                        if retrieveAPConfig['network']['ipType'] != 'Static':  # aps are always static
                            ipType = [retrieveAPConfig['network']['ipType'], False]
                            returnStatus = False
                except (TypeError, AttributeError):  # one of the values was a None type
                    returnStatus = False
            else:
                print(retrieveAPConfig.status_code)
                print(json.dumps(retrieveAPConfig.json(), indent=4))
                return retrieveAPConfig.status_code

        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Hiccup occurred at AP QC start. Retrying...')
            time.sleep(1)
            zoneInfoObject.validSession = False
        return [returnStatus, apName, zoneID, apGroupID, wlanGroup24ID, wlanGroup50ID, ipType, modelSpecific]

def retrieveZoneAPModel(apConfig, apLists, sessionID, controllerCluster, panel):
    serverResponse = checkController.checkController(controllerCluster, sessionID)
    apModel = str(apConfig['model'])
    loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # ----------------RETRIEVE AP MODEL-------------------
    try:
        while serverResponse is False:
            time.sleep(1)
            serverResponse = checkController.checkController(controllerCluster, sessionID)
        # runs until a valid response is returned from the controller
        # gets ap configuration response
        retrieveAPModel = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/apmodel/' + apModel, headers=universalHeaders, cookies=universalCookies, verify=False)
        if retrieveAPModel.status_code == 200:  # checks HTTP response code
            print('Zone AP Model retrieved.')
            return retrieveAPModel.json()
        if loginAttempts >= 4:
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='AP configuration retrieval failed.')
            print(retrieveAPModel.text)
            return retrieveAPModel
        else:
            loginAttempts += 1
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='AP configuration retrieval failed. Retrying...')
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeAPSpecific(sessionID, zoneInfoObject, userInputObject, parentAP):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    print('--------Changing parent AP model specific options...--------')
    # portID retrieves ID of LAN port for master AP to use
    try:
        apConfig = retrieveAPConfig(sessionID, zoneInfoObject, userInputObject, parentAP)
        apModel = apConfig['model']  # front end stores serial variable
        parentAP.apModel = apConfig['model']  # front end stores serial variable
    except KeyError:
        print('Model not found in AP Config')

    '''
    Key:
    portIDs[0] - Access port
    portIDs[1] - Trunk port
    '''
    portIDs = retrievePortID(sessionID, zoneInfoObject, userInputObject)

    if apModel == "R610":
        # body
        sendAPConfig = {
            "lldp": {
                "enabled": True,
                "advertiseIntervalInSec": 30,
                "holdTimeInSec": 120,
                "managementIPTLVEnabled": True
            },
            "poeModeSetting": "_802_3at",
            "lanPorts": [
                    {
                        "portName": "LAN1",
                        "ethPortProfile": {
                            "id": portIDs[1]
                        },
                        "enabled": True
                    },
                    {
                        "portName": "LAN2",
                        "ethPortProfile": {
                            "id": portIDs[1]
                        },
                        "enabled": True
                    }
            ],
        }
    elif apModel == "H510":
        # body
        sendAPConfig = {
            "lldp": {
                "enabled": True,
                "advertiseIntervalInSec": 30,
                "holdTimeInSec": 120,
                "managementIPTLVEnabled": True
            },
            "lanPorts": [
                    {
                        "portName": "LAN1",
                        "ethPortProfile": {
                            "id": portIDs[1]
                        },
                        "enabled": True
                    },
                    {
                        "portName": "LAN2",
                        "ethPortProfile": {
                            "id": portIDs[0]
                        },
                        "enabled": True
                    },
                    {
                        "portName": "LAN3",
                        "ethPortProfile": {
                            "id": portIDs[0]
                        },
                        "enabled": True
                    },
                    {
                        "portName": "LAN4",
                        "ethPortProfile": {
                            "id": portIDs[0]
                        },
                        "enabled": True
                    },
                    {
                        "portName": "LAN5",
                        "ethPortProfile": {
                            "id": portIDs[1]
                        },
                        "enabled": True
                    }
            ],
        }
    else:
        # body
        sendAPConfig =  {
          "poeModeSetting": None
        }
    while True:
        try:

            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID


            # runs until a valid response is returned from the controller
            changeAPSpecific = sessionID.put('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/aps/' + parentAP.apMAC + '/specific', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
            # changeAPConfig = sessionID.put('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + panel.apMAC, headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
            if changeAPSpecific.status_code == 204:  # checks HTTP response code
                print('----------Parent AP Model specific options changed.---------')
                return changeAPSpecific.status_code
            elif changeAPSpecific.status_code == 404:  # checks HTTP response code
                print('---Parent AP Model specific options could not be modified.--')
                return changeAPSpecific.status_code
            else:
                print('------Changing Parent AP Model specific options failed.-----')
                print(json.dumps(changeAPSpecific.json(), indent=4))
                return changeAPSpecific.status_code
        except (socket.gaierror, requests.exceptions.ConnectionError):
            time.sleep(1)
            zoneInfoObject.validSession = False

def changeAPConfigDouble(sessionID, zoneInfoObject, apWLANInfoObj, userInputObject, doubleAPPanel):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # body
    sendAPConfig = {
        "name": doubleAPPanel.ssid,
        "description": doubleAPPanel.ssid,
        "wlanGroup24": {
            "id": apWLANInfoObj.wlanGroupID,
            "name": apWLANInfoObj.wlanGroupName
        },
        "wlanGroup50": {
            "id": apWLANInfoObj.wlanGroupID,
            "name": apWLANInfoObj.wlanGroupName
        },
        "network": {
            "ipType": "Static",
            "ip": doubleAPPanel.ip,
            "netmask": "255.255.255.0",
            "gateway": "10.10.10.1",
            "primaryDns": "10.10.10.1",
            "secondaryDns": "10.10.10.1"
        },
    }

    try:
        if zoneInfoObject.validSession is True:
            # runs until a valid response is returned from the controller
            changeAPConfig = sessionID.patch('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/aps/' + doubleAPPanel.apMAC, headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
            if changeAPConfig.status_code == 204:  # checks HTTP response code
                print('AP configuration changed.')
                return True
            else:
                print('Changing AP configuration failed.')
                print(json.dumps(changeAPConfig.json(), indent=4))
                return changeAPConfig.status_code
        else:
            return False  # session was not valid
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        zoneInfoObject.validSession = False

def retrieveWLANList (apZoneName, apLists, sessionID, controllerCluster):
    serverResponse = checkController.checkController(controllerCluster, sessionID)
    retrieveWLANList = None  # initializes response format
    # ----------------RETRIEVE WLAN LIST-------------------
    print('Retrieving WLAN list...')
    # parameters
    wlanListParameters = (
        ('listSize', '99999'),
        )
    if apLists.apZoneID == None:
        print('Skipping retrieveWLANList. No AP Zone ID found.')
        return retrieveWLANList
    else:

        try:
            while serverResponse is False:
                time.sleep(1)
                serverResponse = checkController.checkController(controllerCluster, sessionID)
            # this while loop runs until a valid response is returned from the controller
            retrieveWLANList = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans', headers=universalHeaders, cookies=universalCookies, params=wlanListParameters, verify=False)
            if retrieveWLANList.status_code == 200 or 204:  # checks HTTP response code
                print('WLAN list retrieved.')
                return retrieveWLANList.json()
            else:
                print("WLAN list retrieval failed.")
                print(retrieveWLANList)
                return retrieveWLANList
        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)

def retrieveWLANConfig (wlanList, wlanID, apLists, sessionID, controllerCluster):
    # ----------------RETRIEVE WLAN CONFIGURATION-------------------
    print('Retrieving WLAN configuration...')

    try:
        # runs until a valid response is returned from the controller
        retrieveWLANConfig = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/' + wlanID, headers=universalHeaders, cookies=universalCookies, verify=False)
        if retrieveWLANConfig.status_code == 200:  # checks HTTP response code
            print('WLAN configuration retrieved.')
            return retrieveWLANConfig.json()
        else:
            print('WLAN configuration retrieval failed.')
            print(retrieveWLANConfig)
            return retrieveWLANConfig
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeWLANRadiusOptions(apLists, apIDs, sessionID, controllerCluster, panel):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    sendAPConfig = {
      "nasIdType": "Customized",
      "customizedNasId": "yourtexthere"
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPConfig = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/' + apIDs.wlanID + '/radiusOptions', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        if changeAPConfig.status_code == 204:  # checks HTTP response code
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='AP configuration changed.')
            return True
        else:
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration failed.')
            print(changeAPConfig.text)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeWLANAdvancedOptions(apLists, wlanID, sessionID, controllerCluster):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # sendAPConfig = {
    #   "nasIdType": "Customized",
    #   "customizedNasId": "yourtexthere"
    # }
    sendAPConfig = {
      "setting": 'value',
      "key": 'your value here'
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPConfig = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/' + wlanID + '/advancedOptions', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        if changeAPConfig.status_code == 204:  # checks HTTP response code
            return True
        if loginAttempts >= 4:
            print(changeAPConfig.text)
            return False
        else:
            print('changeWLANAdvancedOptions error occurred.')
            print(json.dumps(changeAPConfig.json(), indent=4))
            loginAttempts += 1
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Connection error.')
        time.sleep(1)
        pass

def changeWLANVLAN(apLists, wlanID, sessionID, controllerCluster):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # sendAPConfig = {
    #   "nasIdType": "Customized",
    #   "customizedNasId": "yourtexthere"
    # }
    sendAPConfig = {
      "accessVlan": 50,
      "vlanPooling": None,
      "aaaVlanOverride": True
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPConfig = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/' + wlanID + '/vlan', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        if changeAPConfig.status_code == 204:  # checks HTTP response code
            return True
        if loginAttempts >= 4:
            print(changeAPConfig.text)
            return False
        else:
            print('changeWLANVLAN error occurred.')
            print(json.dumps(changeAPConfig.json(), indent=4))
            loginAttempts += 1
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Connection error.')
        time.sleep(1)
        pass



def deleteWLAN (apSSID, wlanID, apLists, sessionID, controllerCluster):
    # ----------------RETRIEVE WLAN CONFIGURATION-------------------
    print('Deleting WLAN configuration...')

    try:
        # runs until a valid response is returned from the controller
        deleteWLAN = sessionID.delete('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/' + wlanID, cookies=universalCookies, verify=False)
        print(deleteWLAN)
        if deleteWLAN.status_code == 204:  # checks HTTP response code
            print(apSSID + ' WLAN deleted.')
            return True
        elif deleteWLAN.status_code == 404:  # checks HTTP response code
            print("Couldn't delete WLAN.")
            return True
        elif deleteWLAN.status_code == 403:  # checks HTTP response code
            print('WLAN already deleted.')
            return True
        elif deleteWLAN.status_code == 422:  # checks HTTP response code
            print('WLAN already deleted.')
            return True
        else:
            print(apSSID + " WLAN deletion failed. Controller didn't respond.")
            print(deleteWLAN)
            return False
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def deleteWLANGroup (apSSID, wlanGroupID, apLists, sessionID, controllerCluster):
    # ----------------RETRIEVE WLAN CONFIGURATION-------------------
    print('Deleting WLAN configuration...')

    try:
        while serverResponse is False:
            serverResponse = checkController.checkController(controllerCluster, sessionID)
            time.sleep(1)
        # runs until a valid response is returned from the controller
        deleteWLANGroup = sessionID.delete('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlangroups/' + wlanGroupID, cookies=universalCookies, verify=False)
        print(deleteWLANGroup)
        if deleteWLANGroup.status_code == 204:  # checks HTTP response code
            print(apSSID + ' WLAN Group deleted.')
            return True
        if deleteWLANGroup.status_code == 403:  # checks HTTP response code
            print('WLAN Group deleted.')
            return False
        if deleteWLANGroup.status_code == 404:  # checks HTTP response code
            print('WLAN Group already deleted.')
            return False
        if deleteWLANGroup.status_code == 422:  # checks HTTP response code
            print('WLAN Group already deleted.')
            return False
        else:
            print(apSSID + " WLAN Group deletion failed. Controller didn't respond.")
            print(deleteWLANGroup)
            return False
    except (socket.gaierror, requests.exceptions.ConnectionError):
        print('Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def retrieveZoneAPsList(zoneID, sessionID, controllerCluster):
    # ----------------RETRIEVE AP CONFIGURATION-------------------
    # parameters for the request to get ap list
    apListParameters = (
    ('listSize', '9999'),
    ('zoneId', zoneID),
    )

    try:
        # runs until a valid response is returned from the controller
        # gets ap configuration response
        retrieveZoneAPsList = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps', headers=universalHeaders, cookies=universalCookies, params=apListParameters, verify=False)
        if retrieveZoneAPsList.status_code == 200:  # checks HTTP response code
            print('AP List retrieved.')
            return retrieveZoneAPsList.json()
        else:
            print(retrieveZoneAPsList)
            return retrieveZoneAPsList
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeAPWLANs(apLists, apMAC, apSSID, wlanGroupID, sessionID, controllerCluster):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # body
    print('Changing AP configuration...')
    sendAPConfig = {
      "name": apSSID,
      "description": apSSID,
      "wlanGroup24": {
          "id": wlanGroupID,
          "name": apSSID
        },
      "wlanGroup50": {
          "id": wlanGroupID,
          "name": apSSID
        },
            "network": {
              "ipType": "Dynamic"
      },
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPWLANs = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC, headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        print(changeAPWLANs)
        if changeAPWLANs.status_code == 204:  # checks HTTP response code
            print('AP configuration changed.')
            return True
        else:
            print('Changing AP configuration failed.')
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration failed.')
            print(changeAPWLANs.text)
            return False
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeAPWLAN24(apLists, apMAC, wlanGroupName, wlanGroupID, sessionID, controllerCluster):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # body
    print('Changing AP WLAN 24 groups...')
    sendAPConfig = {
          "id": wlanGroupID,
          "name": wlanGroupName
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPWLAN24 = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC + '/wlanGroup24', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        if changeAPWLAN24.status_code == 204:  # checks HTTP response code
            print('AP WLAN 24 groups changed.')
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='AP configuration changed.')
            return True
        if changeAPWLAN24.status_code == 422:  # checks HTTP response code
            print('Semantic Errors.')
            return False
        else:
            print('Changing AP WLAN 24 groups failed.')
            #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration failed.')
            print(changeAPWLAN24.text)
            return False
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def changeAPWLAN50(apLists, apMAC, wlanGroupName, wlanGroupID, sessionID, controllerCluster):
    # ----------------CHANGE BASIC AP CONFIGURATION-------------------
    #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Changing AP configuration...')
    # body for request is converted into json through json.dump
    # controller doesn't accept blank dns entries currently
    # body
    print('Changing AP WLAN groups...')
    sendAPConfig = {
          "id": wlanGroupID,
          "name": wlanGroupName
    }

    try:
        # runs until a valid response is returned from the controller
        changeAPWLAN50 = sessionID.patch('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC + '/wlanGroup50', headers=universalHeaders, cookies=universalCookies, data=json.dumps(sendAPConfig), verify=False)
        print(changeAPWLAN50)
        if changeAPWLAN50.status_code == 204:  # checks HTTP response code
            print('AP WLAN groups changed.')
            return True
        if changeAPWLAN50.status_code == 403:  # checks HTTP response code
            print(changeAPWLAN50)
            return False
        if changeAPWLAN50.status_code == 422:  # checks HTTP response code
            print('AP WLAN groups already deleted.')
            return True
        else:
            print('Changing AP WLAN groups failed.')
            print(changeAPWLAN50.text)
            return False
    except (socket.gaierror, requests.exceptions.ConnectionError):
        #Publisher.sendMessage('status', ssid=self.panel.ssid, message='Error connecting to controller. Check your internet connection.')
        time.sleep(1)

def retrievePortID (sessionID, zoneInfoObject, userInputObject):
    portID = None
    accessPortID = None
    trunkPortID = None
    '''
    portType Return:
    0 - Access Port
    1 - Trunk Port
    '''
    # ----------------RETRIEVE PORT ID LIST-------------------
    print('Retrieving Ethernet Port Profile list...')
    while True:
        try:
            if zoneInfoObject.validSession is False:
                newSessionID = requests.session()

                loginAttempt = loginRuckus(newSessionID, zoneInfoObject, userInputObject)
                if loginAttempt == 200:
                    sessionID = newSessionID

            # this while loop runs until a valid response is returned from the controller
            retrievePortID = sessionID.get('https://' + zoneInfoObject.sessionIP + ':8443/wsg/api/public/v6_1/rkszones/' + zoneInfoObject.apZoneID + '/profile/ethernetPort', headers=universalHeaders, cookies=universalCookies, verify=False)
            if retrievePortID.status_code == 200:  # checks HTTP response code
                retrievePortID = retrievePortID.json()
                print('Ethernet Port Profile list retrieved.')
                ap = 0  # this will run through the list of port IDs for the zone
                while ap < retrievePortID['totalCount']:
                    if retrievePortID['list'][ap]['name'] == 'Default Access Port':
                        accessPortID = retrievePortID['list'][ap]['id']
                    if retrievePortID['list'][ap]['name'] == 'Default Trunk Port':
                        trunkPortID = retrievePortID['list'][ap]['id']
                    ap += 1
                return [accessPortID, trunkPortID]
            else:
                print("Ethernet Port Profile list retrieval failed.")
                print(json.dumps(retrievePortID.json(), indent=4))
                return retrievePortID.status_code

        except (socket.gaierror, requests.exceptions.ConnectionError):
            print('Error connecting to controller. Check your internet connection.')
            time.sleep(1)
            zoneInfoObject.validSession

# *********************************REFURB AP STUFF*****************************
# def rebootRefurbAP(apMAC, sessionID, clusterList):
    # loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # # ----------------FUNCTION PURPOSE-------------------
    # # body
    # print('Attempting to reboot AP...')
    #
    # try:
    #     for cluster in clusterList:  # initializes variable that interates in loop
    #         response = checkController.serverResponse([cluster][0][0], sessionID)  # log into controller
    #         try:
    #             response.status_code == 200:  # response should be integer
    #             # runs until a valid response is returned from the controller
    #             reboot = sessionID.put('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC + '/reboot', headers=universalHeaders, cookies=universalCookies, verify=False)
    #             try:
    #                 reboot.status_code == 200
    #                 print('****************AP reboot successful.**************')
    #                 return True
    #                 break
    #             except (AttributeError, ValueError):
    #                 pass
    #         except AttributeError:
    #             print('Failed to log into IP: ' + [cluster][0][0])
    #             print(response)



    #     while serverResponse is None:
    #         time.sleep(1)
    #         serverResponse = checkController.checkClusters(clusterList, sessionID)
    #         if serverResponse is None:
    #             print('AP not found on any SmartZone High Scale controller.')
    #             return None
    #             break
    #         else:
        # # runs until a valid response is returned from the controller
        # reboot = sessionID.put('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC + '/reboot', headers=universalHeaders, cookies=universalCookies, verify=False)
        # if reboot.status_code == 204:  # checks HTTP response code
        #     print('****************AP reboot successful.**************')
        #     return True
        # if reboot.status_code == 403:  # checks HTTP response code
        #     print('AP reboot failure.')
        #     return False
        # if reboot.status_code == 404:  # checks HTTP response code
        #     print('Command not found.')
        #     return False
        # if reboot.status_code == 422:  # checks HTTP response code
        #     print('Reboot AP semantic error.')
        #     return False
        # if loginAttempts >= len(clusterList):
        #     print('Failed to reboot AP.')
        #     print(reboot)
        #     return False
        # else:
        #     loginAttempts += 1
        #     print('Rebooting AP failed. Retrying...')
        #     time.sleep(1)
    # except (socket.gaierror, requests.exceptions.ConnectionError):
    #     time.sleep(1)

def deleteRefurbAP(apMAC, sessionID, controllerCluster):
    serverResponse = checkController.checkClusters(clusterList, sessionID)
    loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # ----------------FUNCTION PURPOSE-------------------
    # body
    print('Deleting AP from controller...')

    try:
        while serverResponse is None:
            time.sleep(1)
            serverResponse = checkController.checkClusters(clusterList, sessionID)
            if serverResponse is None:
                print('AP not found on any SmartZone High Scale controller.')
                return None
                break
            else:
                # runs until a valid response is returned from the controller
                deleteAP = sessionID.delete('https://' + serverResponse + ':8443/wsg/api/public/v6_1/aps/' + apMAC, headers=universalHeaders, cookies=universalCookies, verify=False)
                if deleteAP.status_code == 204:  # checks HTTP response code
                    print('AP deletion Successful.')
                    return True
                if deleteAP.status_code == 403:  # checks HTTP response code
                    print('AP deletion failure.')
                    return False
                if deleteAP.status_code == 404:  # checks HTTP response code
                    print('Command not found.')
                    return False
                if deleteAP.status_code == 422:  # checks HTTP response code
                    print('Semantic error.')
                    return False
                if loginAttempts >= 4:
                    print('Failed to delete AP.')
                    print(deleteAP)
                    return False
                else:
                    loginAttempts += 1
                    print('AP deletion failed. Retrying...')
                    time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        time.sleep(1)

# *********************************WLAN STUFF**********************************
def createStandardMAC(masterWLANConfig, ssid, apLists, sessionID, controllerCluster):
    serverResponse = checkController.checkController(controllerCluster, sessionID)
    loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # ----------------CREATE GUEST ACCESS-------------------
    # authenticationOption: Set to 1, 1 is the Guest in API's array of options
    # body for wlan creation modifies the original wlan
    # body
    body = {
        'name': ssid,
        'ssid': ssid,
        'description': ssid,
        'authServiceOrProfile': masterWLANConfig['authServiceOrProfile'],
        'macAuth': masterWLANConfig['macAuth'],
        'encryption': masterWLANConfig['encryption'],
        'vlan': masterWLANConfig['vlan'],
        'radiusOptions': masterWLANConfig['radiusOptions'],
        'advancedOptions': {
            "authServiceOrProfile" : {
                'throughController': True,

            },
            "clientIsolationEnabled": False,
            "priority": "High",
            "hideSsidEnabled": False,
            "clientLoadBalancingEnabled": False,
            "proxyARPEnabled": False,
            "maxClientsPerRadio": 100,
            "support80211dEnabled": True,
            "support80211kEnabled": True,
            "forceClientDHCPTimeoutSec": 0,
            "dhcpOption82Enabled": False,
            "unauthClientStatsEnabled": False,
            "clientIdleTimeoutSec": 120,
            "clientFingerprintingEnabled": True,
            "ofdmOnlyEnabled": True,
            "bssMinRateMbps": "Disable",
            "mgmtTxRateMbps": "6 mbps",
            "bandBalancing": "UseZoneSetting",
            "hs20Onboarding": False,
            "avcEnabled": False,
            "urlFilteringPolicyEnabled": False,
            "urlFilteringPolicyId": "",
            "uplinkEnabled": False,
            "uplinkRate": 0.0,
            "downlinkEnabled": False,
            "downlinkRate": 0.0,
            "dtimInterval": 1,
            "directedThreshold": 5,
            "flowLogEnabled": False,
            "hdOverheadOptimizeEnable": False,
            "transientClientMgmtEnable": False
        }
    }

    print('Creating standard MAC WLAN...')

    try:
        while serverResponse is False:
            time.sleep(1)
            serverResponse = checkController.checkController(controllerCluster, sessionID)
        # runs until a valid response is returned from the controller
        returnVal = sessionID.post('https://' + serverResponse + ':8443/wsg/api/public/v6_1/rkszones/' + apLists.apZoneID + '/wlans/standardmac', headers=universalHeaders, cookies=universalCookies, data=json.dumps(body), verify=False)
        if returnVal.status_code == 201:  # checks HTTP response code
            print('Standard MAC WLAN creation successful.')
            returnStatus = True
            return True
        if returnVal.status_code == 403:  # checks HTTP response code
            print('Standard MAC WLAN failure.')
            return False
        if returnVal.status_code == 404:  # checks HTTP response code
            print('Standard MAC WLAN failure. Command not found')
            return False
        if returnVal.status_code == 422:  # checks HTTP response code
            print('Standard MAC WLAN semantic error.')
        if loginAttempts >= 4:
            print('Failed to perform standard MAC WLAN creation.')
            print(returnVal.text)
            return False
        else:
            loginAttempts += 1
            print('Standard MAC WLAN creation failed. Retrying...')
            print(json.dumps(returnVal.json(), indent=4))
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        time.sleep(1)

def retrieveAuthProfileList(sessionID, controllerCluster):
    serverResponse = checkController.checkController(controllerCluster, sessionID)
    loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # ----------------RETRIEVE AUTH LIST-------------------
    print('retrieveAuthProfileList...')

    params = (
        ('type', 'ALL'),
    )
    try:
        while serverResponse is False:
            time.sleep(1)
            serverResponse = checkController.checkController(controllerCluster, sessionID)
        # runs until a valid response is returned from the controller
        authProfileList = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/profiles/auth/authorizationList', params=params, headers=universalHeaders, cookies=universalCookies, verify=False)
        print(json.dumps(authProfileList.json(), indent=4))
        if authProfileList.status_code == 200:  # checks HTTP response code
            print('retrieveAuthProfileList successful.')
            return authProfileList.json()
        if authProfileList.status_code == 500:  # checks HTTP response code
            print('Controller unresponsive. Retrying...')
            time.sleep(1)
        if authProfileList.status_code == 404:  # checks HTTP response code
            print('retrieveAuthProfileList failure.')
            print(authProfileList)
            return authProfileList.json()
        if loginAttempts >= 4:
            print('Failed to perform retrieveAuthProfileList.')
            print(authProfileList.text)
            return authProfileList
        else:
            loginAttempts += 1
            print('retrieveAuthProfileList failed. Retrying...')
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        time.sleep(1)

def retrieveRadiusAuthServiceList(sessionID, controllerCluster):
    serverResponse = checkController.checkController(controllerCluster, sessionID)
    loginAttempts = 1  # initializes counter used to count up if a controller ip is unresponsive
    # ----------------RETRIEVE AUTH LIST-------------------
    print('retrieveRadiusAuthServiceList...')

    try:
        while serverResponse is False:
            time.sleep(1)
            serverResponse = checkController.checkController(controllerCluster, sessionID)
        # runs until a valid response is returned from the controller
        retrieveRadiusAuthServiceList = sessionID.get('https://' + serverResponse + ':8443/wsg/api/public/v6_1/services/auth/radius', headers=universalHeaders, cookies=universalCookies, verify=False)
        print(json.dumps(retrieveRadiusAuthServiceList.json(), indent=4))
        if retrieveRadiusAuthServiceList.status_code == 200:  # checks HTTP response code
            print('retrieveAuthProfileList successful.')
            return retrieveRadiusAuthServiceList.json()
        if retrieveRadiusAuthServiceList.status_code == 500:  # checks HTTP response code
            print('Controller unresponsive. Retrying...')
            time.sleep(1)
        if retrieveRadiusAuthServiceList.status_code == 404:  # checks HTTP response code
            print('retrieveAuthProfileList failure.')
            print(retrieveRadiusAuthServiceList)
            return retrieveRadiusAuthServiceList.json()
        if loginAttempts >= 4:
            print('Failed to perform retrieveAuthProfileList.')
            print(retrieveRadiusAuthServiceList.text)
            return retrieveRadiusAuthServiceList
        else:
            loginAttempts += 1
            print('retrieveAuthProfileList failed. Retrying...')
            time.sleep(1)
    except (socket.gaierror, requests.exceptions.ConnectionError):
        time.sleep(1)

# ----------------------------CONTROLLER STUFF----------------------------------
def retrieveControlPlanes (sessionID, ip):
    # ----------------RETRIEVE CONTROL PLANES LIST-------------------
    print('retrieveControlPlanes...')

    try:
        # runs until a valid response is returned from the controller
        controlPlanesList = sessionID.get('https://' + ip + ':8443/wsg/api/public/v6_1/controlPlanes', headers=universalHeaders, cookies=universalCookies, verify=False)
        if controlPlanesList.status_code == 200:
            controlPlanesList = controlPlanesList.json()
            controlPlaneArray = []
            # ARRAY STRUCTURE
            # Control Plane Leader always comes first!
            # [ [name, clusterRole, managementIp, controlIp] ]
            for controlPlane in controlPlanesList['list']:
                if controlPlane['clusterRole'] == 'Leader':
                    controlPlaneArray.insert(0, [controlPlane['name'], controlPlane['clusterRole'], controlPlane['managementIp'], controlPlane['controlIp']])
                else:
                    controlPlaneArray.append([controlPlane['name'], controlPlane['clusterRole'], controlPlane['managementIp'], controlPlane['controlIp']])

            return controlPlaneArray
        else:
            print(json.dumps(returnVar.json(), indent=4))
            return returnVar.status_code
    except (socket.gaierror, requests.exceptions.ConnectionError):
        time.sleep(1)
