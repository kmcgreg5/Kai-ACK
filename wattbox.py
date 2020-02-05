# Written by Kai McGregor for use in Kai-ACK

from splinter import Browser
import os
import requests
from xml.etree import ElementTree
import subprocess
import time
import selenium
import splinter

def configWattbox(panel, ip, passwordTested):
    # Get wattbox SN
    ip = ip.strip()
    url = 'http://' + ip + '/wattbox_info.xml'
    if passwordTested is False:
        with requests.session() as sessionID:
            r = sessionID.get(url, auth=('wattbox', 'wattbox'))
            r = ElementTree.fromstring(r.content)
            panel.wattSN = r.findtext('serial_number')
            dir_path = os.path.dirname(os.path.realpath(__file__))
            
            browser = Browser('chrome', headless=True) 
            browser.visit('http://wattbox:wattbox@' + ip + '/save_restore.htm')
            try:
                browser.attach_file('settings_file', dir_path + '/WattBox/' + panel.ssid + '.cfg')
            except splinter.exceptions.ElementDoesNotExist:
                browser.quit()
                raise splinter.exceptions.ElementDoesNotExist
            browser.find_by_value('Restore').first.click()
            browser.quit()
            
    elif passwordTested is True:
        with requests.session() as sessionID:
            r = sessionID.get(url, auth=('admin', panel.sitePassword))
            r = ElementTree.fromstring(r.content)
            panel.wattSN = r.findtext('serial_number')
            dir_path = os.path.dirname(os.path.realpath(__file__))
            
            browser = Browser('chrome', headless=True) 
            browser.visit('http://admin:'+ panel.sitePassword + '@' + ip + '/save_restore.htm')
            try:
                browser.attach_file('settings_file', dir_path + '/WattBox/' + panel.ssid + '.cfg')
            except splinter.exceptions.ElementDoesNotExist:
                browser.quit()
                raise splinter.exceptions.ElementDoesNotExist
            browser.find_by_value('Restore').first.click()
            browser.quit()
    else:
        with requests.session() as sessionID:
            r = sessionID.get(url, auth=('admin', passwordTested))
            r = ElementTree.fromstring(r.content)
            panel.wattSN = r.findtext('serial_number')
            dir_path = os.path.dirname(os.path.realpath(__file__))

            browser = Browser('chrome', headless=True) 
            browser.visit('http://admin:' + passwordTested + '@' + ip + '/save_restore.htm')
            try:
                browser.attach_file('settings_file', dir_path + '/WattBox/' + panel.ssid + '.cfg')
            except splinter.exceptions.ElementDoesNotExist:
                browser.quit()
                raise splinter.exceptions.ElementDoesNotExist
            browser.find_by_value('Restore').first.click()
            browser.quit()

    return panel

def qcWattbox(panel):
    x = 0
    while True:
        CREATE_NO_WINDOW = 0x08000000
        cmdCommand = subprocess.Popen(['ping', '/n', '1', '192.168.88.254'], stdout = subprocess.PIPE, creationflags = CREATE_NO_WINDOW)
        pingReturn = cmdCommand.communicate()
        if 'Received = 1' in str(pingReturn[0]) and 'Destination host unreachable' not in str(pingReturn[0]):
            if x == 0 or x == 1:
                time.sleep(3)
            else:
                break

        time.sleep(1)
        x += 1
    
    while True:
        try:
            browser = Browser('chrome', headless = True)
            browser.visit('http://admin:'+ panel.sitePassword + '@192.168.88.254/ipaddr.htm')
            try:
                hostname = browser.find_by_id('mib_name').first.value
            except splinter.exceptions.ElementDoesNotExist:
                browser.quit()
                raise splinter.exceptions.ElementDoesNotExist
            domain = browser.find_by_id('wbx_domain').first.value
            browser.visit('http://admin:'+ panel.sitePassword + '@192.168.88.254/mailsetting.htm')
            email = browser.find_by_id('sender').first.value
            email = email[0:email.index('@')]
            browser.quit()
            break
        except selenium.common.exceptions.TimeoutException:
            browser.quit()
            time.sleep(.75)
    
    if panel.ssid == hostname and panel.ssid == domain and panel.ssid == email:
        
        return [True, True, True]
    else:
        returnList = []
        if panel.ssid != hostname:
            returnList.append(False)
        else:
            returnList.append(True)

        if panel.ssid != domain:
            returnList.append(False)
        else:
            returnList.append(True)

        if panel.ssid != email:
            returnList.append(False)
        else:
            returnList.append(True)

        return returnList
