# wanstatus - Monitoring the health of the WAN connection

Monitors WAN-side internet access and WAN IP address changes on a home network.  Sends email and/or text notifications for internet outages (after restored) and WAN IP changes.  The tool is highly configurable for which modem and router you may be using.  Configurations for dd-wrt and pfSense routers, and Motorola and Technicolor/Cox gateway modems are included.

Supported on Python3.6+ on Linux and Windows.


`wanstatus --service` enters an infinite loop, periodically checking the status of internet access and the WAN IP address.  `wanstatus` interactively checks status.

- Internet access is detected by contacting an external DNS server (faster) such as the Google public DNS server at 8.8.8.8.  Alternately, web addresses may be pinged to detect internet access (slower).
- If there is NO internet access then the outage time is captured and logged, and wanstatus enters a tight loop checking for recovery of internet access.  Once restored, wanstatus sends email and/or text notifications that internet access was lost and now restored, and how long the outage was.
- If there IS access to the internet, then wanstatus reads and logs the modem status page (typically at 192.168.100.1).
- wanstatus then reads the pfSense or dd-wrt router status page for the WAN IP address, and if changed then sends email and/or notification messages of the change.
- Finally, wanstatus periodically checks with an external web page for the reported WAN IP address.  


All parameters are set in the `wanstatus.cfg` config file.  On each loop in service mode the config file is checked for changes, and reloaded as needed.  This allows for on-the-fly configuration changes.

wanstatus may be started manually, or may be configured to start at system boot.  An example systemd unit file is included.  See systemd documentation for how to set it up.

<br/>

---

## Notable changes since prior release
V3.0 - Converted to package format, updated to cjnfuncs 2.0

<br/>

---

## Usage
```
$ wanstatus -h
usage: wanstatus [-h] [--config-file CONFIG_FILE] [--log-file LOG_FILE]
                 [--print-log] [--service] [--setup-user] [--setup-site] [-V]

Check internet access and WAN IP address.  Send notification/email after outage is over and
on WAN IP change.
3.0

optional arguments:
  -h, --help            show this help message and exit
  --config-file CONFIG_FILE, -c CONFIG_FILE
                        Path to the config file (Default <wanstatus.cfg)> in user/site config directory.
  --log-file LOG_FILE, -l LOG_FILE
                        Path to the log file.
  --print-log, -p       Print the tail end of the log file (default last 40 lines).
  --service             Enter endless loop for use as a systemd service.
  --setup-user          Install starter files in user space.
  --setup-site          Install starter files in system-wide space. Run with root prev.
  -V, --version         Return version number and exit.
```

<br/>

---

## Example output
```
$$ wanstatus 
 WARNING:  ========== wanstatus (3.0) ==========
 WARNING:  Config file </home/me/.config/wanstatus/wanstatus.cfg>
    INFO:  Internet access:             Working          (DNS server 72.105.29.22, command run time   11.3 ms)
    INFO:  Modem status:                Locked           (command run time 6550.7 ms)
    INFO:  Router reported WANIP:       27.177.61.124    (command run time 2300.2 ms)
    INFO:  Externally reported WANIP:   27.177.61.124    (command run time  350.1 ms)
```

<br/>

---

## Setup and Usage notes
- Install wanstatus from PyPI (pip install wanstatus).
- Install the initial configuration files (`wanstatus --setup-user` places files at ~/.config/wanstatus).
- Edit/configure `wanstatus.cfg`, `creds_SMTP`, and `creds_wanstatus` as needed.
- Run manually as `./wanstatus`, or install the systemd service.
- When running in service mode (continuously looping) the config file may be edited and is reloaded when changed.  This allows for changing settings without having to restart the service.


<br/>

---

## Customization notes
- Logging in interactive mode goes to the console per the `ConsoleLogFormat` param in the config file.  Logging in `--service`
mode goes to `log_wanstatus.txt` in the configuration directory. 
- Checking the modem status, checking the router reported WAN IP, and checking the external WAN IP address features are optional.  To disable, comment out `ModemStatusPage`, `RouterStatusPage`, and/or `WANIPWebpage` parameters, respectively.  If all three are disabled then only internet access checking and outage notification is still active.
- Configuration examples are provided for dd-wrt and pfSense routers, and certain Cisco, Motorola, and Technicolor/Vantiva modems.
- Checking for internet access can be done by either pinging internet servers (slower) or by doing connections to DNS servers (faster).  The internet access check method is selected via the  `IACheckMethod` config parameter.  Multiple target addresses may be specified as a whitespace separated list of ping addresses or DNS server addresses.  The first server in the list is tried, and if access should fail (after `nRetries` attempts) then the next server in the list is tried, and so on.
- For developing and debugging the regular expressions for your needs, do a View Page Source in your browser and look for the specific phrase in the html that has the desired info.  I recommend https://regexr.com/ for developing your regular expressions for extracting the modem status and WAN IP address. 
- The external WAN IP check servers may not tolerate too frequent requests.  Set `ExternalWANRecheckPeriod` to a big value, such as 1 hour, to avoid being blacklisted.

The modem and router ('device') access configurations use a common set of parameters, with `xxx` replaced by `Modem` and `Router`, respectively.  Notably:
- If logging into a device is not needed in order to access the `xxxStatusPage`, then don't specify the `xxxLoginUsernameField` parameter.
- If login for a device is required (`xxxLoginUsernameField` specified), but a specific login page is not used then don't specify `xxxLoginPage`.  The username and password will be passed to the `xxxStatusPage`.  This method is used by pfSense routers.
- To disable the device status check completely, don't specify (or comment out) the `xxxStatusPage` parameter (as noted above).
- csrf security access mode is supported, such as used by pfSense routers.  This feature is enabled in the `xxxLoginAdditionalKeys`.  logging.debug statements are commented out in the code to avoid leaking login credentials.

Modem and Router config parameters:
```
    Config parameters using 'xxx' as a placeholder prefix (with examples):
        xxxLoginPage               http://routerurl.lan/login
            If login on a specific page is required.  Optional.  If not given then login attempt 
            at the xxxStatusPage.
        xxxLoginRequiredText   <title>CSRF Error</title>
            Unique text found on the page returned by the device that indicates that a login is needed.
        xxxLoginUsernameField      usernamefld
            Name of the username field on the login page.  Optional.  If not given then username and 
            password parameters are not used.  EG dd-wrt router doesn't need a password to access status.
        xxx_USER
            Login Username
        xxxLoginPasswordField      passwordfld
            Name of the password field on the login page.
        xxx_PASS
            Login Password
        xxxLoginAdditionalKeys     login : Login, '__csrf_magic' : "None"
            Any other needed keys related to login. All, including username and password, are
            passed on all posts to the xxxLoginPage and xxxStatusPage.  
            Csrf token parsing and updating is done if 'csrf' is found in these additional keys.
        xxxCsrfRE                  csrfMagicToken = "(.*)";var
            RE for parsing the csrf token out of pages returned from xxxLoginPage and xxxStatusPage.
        xxxStatusPage              http://routerurl.lan/index.php
            Page for extracting info from using the xxxStatusRE.
        xxxStatusRE                <td.+title="via.dhcp">\s+([\d]+\.[\d]+\.[\d]+\.[\d]+)
            RE for extracting modem status or router WAN IP from the xxxRouterStatusPage.
        xxxTimeout
            Max time allowed for response from the device.
```

<br/>

---

## Version history
- 3.0 230215 - Converted to package format, updated to cjnfuncs 2.0
- ...
- 0.1 201028 - New
