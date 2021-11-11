# wanstatus

Monitor WAN-side internet access and WAN IP address changes on a home network.  Sends email and/or text notifications for internet outages (after restored) and WAN IP changes.  The tool 
works with dd-wrt and pfSense routers.

wanstatus normally enters an infinite loop, periodically checking the status of internet access and the WAN IP address.  Use the `--once` switch to interactively check status.

- Internet access is detected by contacting an external DNS server, such as the Google public DNS server at 8.8.8.8.
- If there is NO internet access then the outage time is captured and logged, and wanstatus enters a tight loop checking for recovery of internet access.  Once restored, wanstatus sends email/text notifications that internet access was lost and now restored, and how long the outage was.
- If there IS access to the internet, then wanstatus reads and logs the cable modem status page (typically at 192.168.100.1).
- wanstatus then reads the pfSense or dd-wrt router status page for the WAN IP address, and if changed then sends email and notification messages of the change.
- Finally, wanstatus periodically checks with an external web page for the reported WAN IP address.  


All parameters are set in the wanstatus.cfg config file.  On each loop, the config file is checked for changes, and reloaded as needed.  This allows for on-the-fly configuration changes.

wanstatus may be started manually, or may be configured to start at system boot.  An example [systemd unit file](wanstatus.service) is included.  See systemd documentation for how to set it up.


## Usage
```
$ ./wanstatus -h
usage: wanstatus [-h] [-1] [--config-file CONFIG_FILE] [--log-file LOG_FILE]

Check internet access and WAN IP address.  Send notification/email after outage is over or
when WAN IP changes.  

optional arguments:
  -h, --help            show this help message and exit
  -1, --once            Print stats and exit.
  --config-file CONFIG_FILE
                        Path to the config file (Default </pathto/wanstatus.cfg)>.
  --log-file LOG_FILE   Path to log file (Default </pathto/log_wanstatus.txt>).
```

## Example output
```
$ ./wanstatus --once
./wanstatus V1.2 211111
Have internet access
Modem status:               Good (vcm_operational)
Router reported WANIP:      69.214.235.171
Externally reported WANIP:  69.214.235.171
```

## Setup and Usage notes
- Place wanstatus and wanstatus.cfg in a directory.
- Edit/configure wanstatus.cfg as needed.
- Place funcs3.py in the same directory, or a different directory and edit the path in wanstatus.
- Run manually with `--once`, or install the systemd service.
- When running in service mode (continuously looping) the config file may be edited and is reloaded when changed.  This allows for changing settings without having to restart the service.
- Supported on Python3 only.  Developed on Centos 7.8 with Python 3.6.8.

## Customization notes
- Checking the modem status, checking the router reported WAN IP, and checking the external WAN IP address features are optional.  To disable, comment out `ModemWebpage`, `RouterWebpage`, and/or `WANIPWebpage` parameters, respectively.  If all are disabled then only internet access and outage notification are still active.
- What web pages are checked and for what key text (such as the IP address) is defined entirely within the configuration file.  The wanstatus.cfg file has some alternative definitions as additional examples.  For developing and debugging the regular expressions for your needs, do a `curl <webpage.htm> > testfile.txt` and look for the specific phrase in the html that has the desired info.  I recommend https://regexr.com/ for developing your regular expression. 

## Known issues:

## Version history
- V1.2 211111  pfSense support with router status page login
- V1.0 210523  Requires funcs3 V0.7 min for import of credentials file and config dynamic reload.
  Added --config-file and --log-file switches
 	Moved router, modem, external webpage RE definitions into the config file to minimize code dependency.  
- V0.2 - 201203  Changed handling of get_router_WANIP that periodically did not return a valid value.
Changed to use logger for once mode.
- V0.1 201028 - New
