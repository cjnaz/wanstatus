# wanstatus

Monitor WAN-side internet access and WAN IP address changes on a home network.  Sends email and/or text notifications for internet outages (after restored) and WAN IP changes.

This tool relies on the [funcs3](https://github.com/cjnaz/funcs3-Python-script-framework) Python module.  Place `funcs3.py` in the same directory as the wanstatus script, or in a different directory and adjust the path in wanstatus.

wanstatus normally enters an infinite loop, periodically checking the status of internet access and the WAN IP address.  Use the `--once` switch to interactively check status.

- Internet access is detected by contacting the Google public DNS server.
- If there is NO internet access then the outage time is captured and logged, and wanstatus enters a tight loop checking for recovery of internet access.  Once restored, wanstatus sends email/text notifications that internet access was lost and now restored, and how long the outage was.
- If there IS access to the internet, then wanstatus reads and logs the cable modem status page (typically at 192.168.100.1).
- wanstatus then reads the dd-wrt router status page for the WAN IP address, and if changed then sends email and notification messages of the change.
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
                        Path to the config file (Default </mnt/share/dev/python/wanstatus/wanstatus.cfg)>.
  --log-file LOG_FILE   Path to log file (Default </mnt/share/dev/python/wanstatus/log_wanstatus.txt>).

```

## Setup and Usage notes
- Place wanstatus and wanstatus.cfg in a directory.
- Edit/configure wanstatus.cfg as needed.
- Place funcs3.py in the same directory, or a different directory and edit the path in wanstatus.
- Run manually with `--once`, or install the systemd service.
- When running in service mode (continuously looping) the config file may be edited and is reloaded when changed.  This allows for changing settings without having to restart the service.
- Supported on Python3 only.  Developed on Centos 7.8 with Python 3.6.8.

## Customization notes
- Checking the modem status and checking the external WAN IP address features are optional.  To disable, don't define (comment out) the `ModemWebpage` and `WANIPWebpage` parameters, respectively.
- What web pages are checked and for what key text (such as the IP address) is defined entirely within the configuration file.  The wanstatus.cfg file has some alternative definitions as additional examples.  For developing and debugging the regular expressions for your needs, do a `curl <webpage.htm> > testfile.txt` and look for the specific phrase in the html that has the desired info.  I recommend https://regexr.com/ for developing your regular expression. 

## Known issues:

## Version history
- V1.0 210523  Requires funcs3 V0.7 min for import of credentials file and config dynamic reload.
  Added --config-file and --log-file switches
 	Moved router, modem, external webpage RE definitions into the config file to minimize code dependency.  
- V0.2 - 201203  Changed handling of get_router_WANIP that periodically did not return a valid value.
Changed to use logger for once mode.
- V0.1 201028 - New
