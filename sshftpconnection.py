# Written by Kai McGregor for use in Kai-ACK

import paramiko
from ftplib import FTP
import ftplib
import time
from pubsub import pub as Publisher
import urllib3
import select

def testMikrotikAuth(hostname, password, port = '22', username = 'admin'): # Tests mikrotik password
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port, username, password)

    ssh.close()
    
def connectSSH(hostname, password, port = '22', username = 'admin'): #create ssh connection with desired host
    urllib3.disable_warnings(paramiko.ssh_exception.SSHException)
    while True:
        try:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname, port, username, password)
            return ssh
        except (paramiko.ssh_exception.SSHException, TimeoutError, ConnectionAbortedError, paramiko.ssh_exception.NoValidConnectionsError, ConnectionResetError) as error:
            if 'Authentication failed' in str(error):
                return False
            time.sleep(2)

def ftpGetDirs(ftpConnection):
    contents = ftpConnection.nlst()
    folderList = []
    for item in contents:
        if '.' not in item:
            folderList.append('/' + item)

    x = 0
    while x < len(folderList):
        try:
            contents = ftpConnection.nlst(folderList[x])
            for item in contents:
                if '.' not in item:
                    folderList.append(folderList[x] + '/' + item)
        except ftplib.error_perm:
            pass
        
        x += 1

    folderList.insert(0, '/')
    
    return folderList
        
        
def ftpGetFileList(hostname, password, username = 'admin', path = '/'):
    while True:
        try:
            ftpConnection = FTP(hostname, username, password)
            ftpConnection.cwd(path)
            folderList = ftpGetDirs(ftpConnection)
            fileList = []
            for item in folderList:
                try:
                    contents = ftpConnection.nlst(item)
                    for item in contents:
                        if '.' in item and item != '.' and item != '..':
                            fileList.append(item)
                except ftplib.error_perm:
                    pass
                
            loginSize = None
            if '/flash/hotspot' in folderList:
                ftpConnection.sendcmd("TYPE i")
                ftpConnection.cwd('/flash/hotspot')
                loginSize = ftpConnection.size('login.html')
                ftpConnection.sendcmd("TYPE A")
            ftpConnection.quit()
            return fileList, folderList, loginSize
        except (OSError, ConnectionResetError, ftplib.error_perm, EOFError) as error:
            print(error)
            time.sleep(.5)

def ftpSendFile(hostname, password, fileName, ssid, username = 'admin', path = '/'): #send file to desired host and path
    printOnce = True
    while True:
        try:
            fileTransfer = FTP(hostname, username, password)
            fileTransfer.cwd(path)
            file = open(fileName, 'rb')
            x = len(fileName) - 1
            while x >= 0:
                if fileName[x] == '\\':
                    fileName = fileName[x+1:]
                    break
                x -= 1
            fileTransfer.storbinary('STOR ' + fileName, file)
            file.close()
            fileTransfer.quit()
            break
        except (OSError, ConnectionResetError, ftplib.error_perm, EOFError):
            if printOnce is True:
                Publisher.sendMessage('status', ssid = ssid, message = 'FTP Failed on ' + fileName)
                printOnce = False
            time.sleep(2)

def ftpDeleteFile(hostname, password, fileName, ssid, username = 'admin', path = '/'): #delete file from desired host and path
    printOnce = True
    while True:
        try:
            fileTransfer = FTP(hostname, username, password)
            fileTransfer.cwd(path)
            fileTransfer.delete(fileName)
            break
        except (OSError, ConnectionResetError):
            if printOnce is True:
                Publisher.sendMessage('status', ssid = ssid, message = 'FTP Failed on ' + fileName)
                printOnce = False
            time.sleep(2)

def sshSendCommand(ssh, command, hostname, password, port = '22', username = 'admin'):
    timeout = 2
    while True:
        try:
            while ssh is False:
                ssh = connectSSH(hostname, password, port, username)
                time.sleep(.2)
            (stdin, stdout, stderr) = ssh.exec_command(command)
            #@https://github.com/paramiko/paramiko/issues/563 credit for reading paramiko output
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
                if not got_chunk \
                    and stdout.channel.exit_status_ready() \
                    and not stderr.channel.recv_stderr_ready() \
                    and not stdout.channel.recv_ready(): 
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
            
            return [ssh, collectedLines.splitlines()]
        except (paramiko.ssh_exception.SSHException, ConnectionResetError, EOFError):
            print('Command failed to send, re-establishing connection...')
            ssh = False

def enableSSH(hostname, password, fileName, username = 'admin', path = '/'):
    fileTransfer = FTP(hostname, username, password)
    fileTransfer.cwd(path)
    file = open(fileName, 'rb')
    fileTransfer.storbinary('STOR ' + fileName, file)
            
    file.close()
    fileTransfer.quit()


#ftpGetFileList('192.168.87.1', 'mDu185608')
