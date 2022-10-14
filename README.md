# wanstatus

Monitor WAN-side internet access and WAN IP address changes on a home network.  Sends email and/or text notifications for internet outages (after restored) and WAN IP changes.  The tool 
works with dd-wrt and pfSense routers.

`./wanstatus --service` enters an infinite loop, periodically checking the status of internet access and the WAN IP address.  `./wanstatus` interactively check status.

- Internet access is detected by contacting an external DNS server (faster), such as the Google public DNS server at 8.8.8.8.  Alternately, web addresses may be pinged to detect internet access (slower).
- If there is NO internet access then the outage time is captured and logged, and wanstatus enters a tight loop checking for recovery of internet access.  Once restored, wanstatus sends email and/or text notifications that internet access was lost and now restored, and how long the outage was.
- If there IS access to the internet, then wanstatus reads and logs the cable modem status page (typically at 192.168.100.1).
- wanstatus then reads the pfSense or dd-wrt router status page for the WAN IP address, and if changed then sends email and/or notification messages of the change.
- Finally, wanstatus periodically checks with an external web page for the reported WAN IP address.  


All parameters are set in the wanstatus.cfg config file.  On each loop, the config file is checked for changes, and reloaded as needed.  This allows for on-the-fly configuration changes.

wanstatus may be started manually, or may be configured to start at system boot.  An example [systemd unit file](wanstatus.service) is included.  See systemd documentation for how to set it up.

## Notable changes since prior release
V2.1:
- Changed from implicit service mode to explicit service mode with `--service` switch.  Removed `--once` switch for manual/single runs.
- Log file is now specified in the config file (func3 min version 1.1).
- have_internet() now supports either ping mode or DNS server mode via the `IACheckMethod` config parameter.  Multiple target addresses may be specified as a whitespace separated list of ping addresses or DNS server addresses.


## Usage
```
$ ./wanstatus -h
usage: wanstatus [-h] [--config-file CONFIG_FILE] [--service] [-V]

Check internet access and WAN IP address.  Send notification/email after outage is over and
on WAN IP changes.  
V2.1 221013

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE
                        Path to the config file (Default </script/path/wanstatus.cfg)>.
  --service             Enter endless loop for use as a systemd service.
  -V, --version         Return version number and exit.

```

## Example output
```
$ ./wanstatus
 WARNING:  ========== wanstatus (V2.1 221013) ==========
    INFO:  Internet access:             Working          (DNS server 68.105.29.16, command run time    7.7 ms)
    INFO:  Modem status:                vcm_operational  (command run time 1184.7 ms)
    INFO:  Router reported WANIP:       68.230.19.222    (command run time 2434.3 ms)
    INFO:  Externally reported WANIP:   68.230.19.222    (command run time  373.7 ms)

```

## Setup and Usage notes
- Place wanstatus and wanstatus.cfg in a directory.
- Edit/configure wanstatus.cfg as needed.
- Create credential files in a secure location for your email SMTP server (i.e., ~/creds_SMTP) and router and modem login params (i.e.: ~/creds_wanstatus).  Make these files read-only by yourself, and also accessible to the service mode user.  Example files supplied.
- Place funcs3.py in the same directory, or a different directory and edit the path in wanstatus.
- Run manually as `./wanstatus`, or install the systemd service.
- When running in service mode (continuously looping) the config file may be edited and is reloaded when changed.  This allows for changing settings without having to restart the service.
- Supported on Python3 only.  Developed on Centos 7.8 with Python 3.6.8.

## Customization notes
- Checking for internet access can be done by either pinging internet servers (slower) or by doing connections to DNS servers (faster).  The internet access check method is selected via the  `IACheckMethod` config parameter.  Multiple target addresses may be specified as a whitespace separated list of ping addresses or DNS server addresses.  The first server in the list is tried, and if access should fail (after `nRetries` attempts) then the next server in the list is tried, and so on.
- Checking the modem status, checking the router reported WAN IP, and checking the external WAN IP address features are optional.  To disable, comment out `ModemStatusPage`, `RouterStatusPage`, and/or `WANIPWebpage` parameters, respectively.  If all three are disabled then only internet access checking and outage notification are still active.
- If your modem requires a login in order to access the status page, then define `ModemLoginText` with text that will only be found on the modem's login page.  Also define `ModemLoginPage`, `Modem_USER`, and `Modem_PASS` (the latter two in a secure credentials file).  FYI, the Motorola MB7621 modem login is not tied to a given session.  Once the modem is logged into it remains logged in for all access from any computer on your network for a period of time.  wanstatus does not issue a modem logout.
- What web pages are checked and for what key text (such as the IP address) is defined entirely within the configuration file.  The wanstatus.cfg file has some alternative definitions as additional examples.  For developing and debugging the regular expressions for your needs, do a `curl <webpage.htm> > testfile.txt` and look for the specific phrase in the html that has the desired info.  I recommend https://regexr.com/ for developing your regular expression. 
- The external WAN IP check servers may not tolerate too frequent requests.  Set `ExternalWANRecheckPeriod` to a big value, such as 1 hour, to avoid being blacklisted.

## Known issues:

## Version history
- V2.1 221013  Revamped.
- V1.2 211111  pfSense support with router status page login
- V1.0 210523  Requires funcs3 V0.7 min for import of credentials file and config dynamic reload.
  Added --config-file and --log-file switches
 	Moved router, modem, external webpage RE definitions into the config file to minimize code dependency.  
- V0.2 - 201203  Changed handling of get_router_WANIP that periodically did not return a valid value.
Changed to use logger for once mode.
- V0.1 201028 - New
