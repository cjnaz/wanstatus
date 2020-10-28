# wanstatus

Monitor WAN-side internet access and WAN IP address changes on a home network.  Sends email and/or text notifications for internet outages (after restored) and WAN IP changes.

This tool relies on the [funcs3](https://github.com/cjnaz/funcs3-Python-script-framework) Python module.  Place funcs3 in the same directory as the wanstatus script, or in a different directory and adjust the path in wanstatus.

wanstatus normally enters an infinite loop, periodically checking the status of internet access and the WAN IP address.  

- Internet access is detected by contacting the Google public DNS server.
- If there is NO internet access then the outage time is captured and logged, and wanstatus enters a tight loop checking for recovery of internet access.  Once restored, wanstatus send email/text notifications that internet access was lost and now restored, and how long the outage was.
- If there IS access to the internet, then wanstatus reads and logs the cable modem status page (typically at 192.168.100.1).
- wanstatus then reads the dd-wrt router status page for the WAN IP address, and if changed then sends email and notification messages of the change.
- Finally, wanstatus periodically checks with an external web page for the reported WAN IP address.  Set `WanIpWebpage = none` in the config file to disable this check.


All parameters are set in the wanstatus.cfg config file.  On each loop, the config file is checked for changes, and reloaded as needed.  This allows for on-the-fly configuration changes.

wanstatus may be started manually, or may be configured to start at system boot.  An example [systemd unit file](wanstatus.service) is included.  See systemd documentation for how to set it up.

NOTE that this tool is written and tested on a home network using a Cisco cable modem and dd-wrt-based router.  Porting it to other applications may or may not be easy.  Fork the project as you see fit.  Enhancement suggestions are welcome.


## Usage
```
$ ./wanstatus -h
usage: wanstatus [-h] [-1]

Check internet access and WAN IP address.  Send email after outage over or
when WAN IP changes.  
Runs in forever loop.  Intended to be run by systemd at boot.

optional arguments:
  -h, --help  show this help message and exit
  -1, --once  Print stats and exit.
```

## Setup and Usage notes
- Place wanstatus and wanstatus.cfg in a directory.
- Edit/configure wanstatus.cfg as needed.
- Place funcs3 in the same directory, or a different directory and edit the path in wanstatus.
- Run manually, or install the systemd service.
- Supported on Python3 only.  Developed on Centos 7.8 with Python 3.6.8.

## Known issues:

## Version history

- V0.1 201028 - New
