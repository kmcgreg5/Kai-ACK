# Kai-ACK
This program configures network panels according to specifications set by Vaughan Technologies. These panels have a Mikrotik, Wattbox, and a Ruckus AP. The Mikrotik is configured using SSH, FTP, and the Mikrotik API. The Ruckus AP is configured through the Ruckus controller API. The Wattbox is configured using splinter (a branch of selenium) to access it's web page. The GUI is handled by wx python and provides a simplistic interface to gather input and display information. Chromedriver.exe is required for wattbox configuration.

All code was written by me, Kai McGregor, except the RuckusLibrary.py and MikrotikAPI.py file which was written by another co-worker.


TODO:
  UI.py: Add catch for OSError in line 1544
  UI.py: Add catch for OSError in line 1638
  UI.py: Add catch for OSError in line 641
  ?Not sure if this is the fix? UI.py: Remove except hooks on the ap and wattbox threads so as to prevent duplicate uploads to the error sheet
  UI.py: Add a try except loop to retry the connection on line 1011
  UI.py: Add catch for requests.exceptions.InvalidURL in line 1038
  UI.py: Add except block for ConnectionResetError to retry password in line 1533
  UI.py: Change line 213 to "while x >= 0:"
  sshftpconnection.py: Add catch for EOFError in line 28
  googlesheets.py: Import httplib2
  *Not needed as I dont want the spreadsheet thread infinite looping if it encounters this error* googlesheets.py: Add try except loop for ConnectionAbortedError in line 77
  
  Display a message when the spreadsheet is not setup correctly
  Add a retry loop that waits 60s when the read/write limit to Google Sheets is exceeded
