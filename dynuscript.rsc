system script remove [find]
system script add name=Dynu owner=admin policy=\
ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source=":\
global ddnsuser \"CVN5504\"\r\
\n:global ddnspass \"Clearview1\"\r\
\n:global theinterface \"ether1-WAN\"\r\
\n:global ddnshost \"ReplaceWithDynu\"\r\
\n:global ipddns [:resolve \$ddnshost];\r\
\n:global ipfresh [ /ip address get [/ip address find \\\r\
\ninterface=\$theinterface ] address ]\r\
\n:if ([ :typeof \$ipfresh ] = nil ) do={\r\
\n:log info (\"DynuDDNS: No IP address on \$theinterface .\")\r\
\n} else={\r\
\n:for i from=( [:len \$ipfresh] - 1) to=0 do={\r\
\n:if ( [:pick \$ipfresh \$i] = \"/\") do={\r\
\n:set ipfresh [:pick \$ipfresh 0 \$i];\r\
\n}\r\
\n}\r\
\n:if (\$ipddns != \$ipfresh) do={\r\
\n:log info (\"DynuDDNS: IP-Dynu = \$ipddns\")\r\
\n:log info (\"DynuDDNS: IP-Fresh = \$ipfresh\")\r\
\n:log info \"DynuDDNS: Update IP needed, Sending UPDATE...!\"\r\
\n:global str \"/nic/update\?hostname=\$ddnshost&myip=\$ipfresh\"\r\
\n/tool fetch address=api.dynu.com src-path=\$str mode=http user=\$ddnsuse\
r \\\r\
\npassword=\$ddnspass dst-path=(\"/Dynu.\".\$ddnshost)\r\
\n:delay 1\r\
\n:global str [/file find name=\"Dynu.\$ddnshost\"];\r\
\n/file remove \$str\r\
\n:global ipddns \$ipfresh\r\
\n:log info \"DynuDDNS: IP updated to \$ipfresh!\"\r\
\n} else={\r\
\n:log info \"DynuDDNS: does not need changes\";\r\
\n}\r\
\n}"