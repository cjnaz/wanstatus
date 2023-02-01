#!/usr/bin/env python3
"""Check internet access and WAN IP address.  Send notification/email after outage is over and
on WAN IP change.
"""

__version__ = "3.0"

#==========================================================
#
#  Chris Nelson, 2020 - 2021
#
# V2.2 221106  Converged modem and router check code into device class
# V2.1 221013  have_internet() ping and dns servers may be more than 1.
# V2.0 221003  Revamp. have_internet() supports both DNS connect and ping modes. Support Motorola MB7621 modem login.
# V1.5 220915  Added error traps on snd_notif/snd_email calls
# V1.4 220411  Incorporated use of timevalue
# V1.3 220203  Updated to funcs3 V1.0
# V1.2 211111  pfSense support with router status page login
# V1.1 210617  Added RouterTimeout, WANIPWebpageTimeout, socket close in have_internet
# V1.0 210523  Requires funcs3 V0.7 min for import of credentials file and config dynamic reload.
#   Added --config-file and --log-file switches
#	Moved router, modem, external webpage RE definitions into the config file to minimize code dependency.  
# V0.2 201203  Changed handling of get_router_WANIP that periodically did not return a valid value.
#   Changed to use logger for once mode.
# V0.1 201028  New
#
# Changes pending
#
#==========================================================

import argparse
# from asyncio import start_unix_server
import sys
import datetime
import time
import os
import io
import requests
import subprocess
import socket
import re
import signal
from pathlib import Path
import shutil

# sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), './funcs3/'))    # funcs3 in subdir
# sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../funcs3/'))    # funcs3 in peer dir
from cjnfuncs.cjnfuncs import settoolname, deploy_files, config_item, mungePath, getcfg, timevalue, logging, snd_notif, snd_email

settoolname("xyzjunk")

def cli():
    deploy_files( [
        ['wanstatus.cfg', '/tmp'],
        ['junk.txt', '$HOME/junk'],
        ['junk.txt', 'USER_CONFIG_DIR'],
        ['junk.txt', 'USER_CONFIG_DIR/logs'],
        ['junk.txt', 'USER_CONFIG_DIR/../xyz2/logs'],
        ['junk.txt', 'USER_CONFIG_DIR/junk.txt'],
        ['more/x1.txt', 'USER_CONFIG_DIR'],
    ] )

cli()
exit()

# Configs / Constants
TOOLNAME = "wanstatus"
PY_MIN_VERSION = 3.6
FUNCS3_MIN_VERSION = 1.1
# CONFIG_FILE = os.path.join(PROGDIR, 'wanstatus.cfg')
CONFIG_FILE = 'wanstatus.cfg'
CONSOLE_LOGGING_FORMAT = '{levelname:>8}:  {message}'
# Internet access:               Working        (DNS server...
# ^^FIELD_WIDTH1                 ^^FIELD_WIDTH2
FIELD_WIDTH1 = 28
FIELD_WIDTH2 = 16

def main():
    global modem_status, router_status
    global toolname, config
    logging.getLogger().setLevel(20)    # Force info level logging for interactive usage

    SavedWANIP = ""

    # WANfile = getcfg("WANIPFile")
    # if not os.path.isabs(WANfile):
        # WANfile = os.path.join(PROGDIR, WANfile)
    _xx = mungePath (getcfg("WANIPFile"), toolname.data_dir, mkdir=True) #os.path.join(PROGDIR, WANfile)
    if _xx.is_file: #os.path.exists(WANfile):
        with io.open(_xx.full_path, encoding="utf8") as ifile:
            SavedWANIP = ifile.read()

    # Check internet access
    status, msg = have_internet()
    if status:
        logging.info   (f"{'Internet access:':{FIELD_WIDTH1}} {'Working':{FIELD_WIDTH2}} {msg}")
        # print   (f"{'Internet access:':{FIELD_WIDTH1}} {'Working':{FIELD_WIDTH2}} {msg}")
    else:
        logging.warning(f"{'Internet access:':{FIELD_WIDTH1}} {'NONE':{FIELD_WIDTH2}} {msg}")

    # Check modem status
    if getcfg('ModemStatusPage', False):
        modem_status = device("Modem")
        status, state, msg = modem_status.get_data()
        if status:
            logging.info    (f"{'Modem status:':{FIELD_WIDTH1}} {state:{FIELD_WIDTH2}} {msg}")
        else:
            logging.warning (f"{'Modem status:':{FIELD_WIDTH1}} {state:{FIELD_WIDTH2}} {msg}")

    # Check for router WAN IP address change
    if getcfg('RouterStatusPage', False):
        router_status = device("Router")
        status, WANIP, msg = router_status.get_data()
        if status:
            logging.info     (f"{'Router reported WANIP:':{FIELD_WIDTH1}} {WANIP:{FIELD_WIDTH2}} {msg}")
            if WANIP != SavedWANIP:
                logging.info (f"{'Prior stored WANIP:':{FIELD_WIDTH1}} {SavedWANIP:{FIELD_WIDTH2}}")
        else:
            logging.warning(f"Failed getting WANIP address from router:\n{msg}")

    # Check external web page for WANIP
    if getcfg('WANIPWebpage', False):
        status, ext_WANIP = get_external_WANIP()
        if status:
            logging.info (f"{'Externally reported WANIP:':{FIELD_WIDTH1}} {ext_WANIP:{FIELD_WIDTH2}}")
        else:
            logging.warning (f"Failed getting externally reported WANIP:  {ext_WANIP}")


def service():
    global modem_status, router_status
    global toolname
    global config, logfile_override

    SavedWANIP = ""

    _xx = mungePath (getcfg("WANIPFile"), toolname.data_dir, mkdir=True) #os.path.join(PROGDIR, WANfile)
    WANfile = _xx.full_path
    if _xx.is_file: #os.path.exists(WANfile):
        with io.open(WANfile, encoding="utf8") as ifile:
            SavedWANIP = ifile.read()

    # WANfile = getcfg("WANIPFile")
    # if not os.path.isabs(WANfile):
    #     WANfile = os.path.join(PROGDIR, WANfile)
    # if os.path.exists(WANfile):
    #     with io.open(WANfile, encoding="utf8") as ifile:
    #         SavedWANIP = ifile.read()

    if getcfg('ModemStatusPage', False):
        modem_status = device("Modem")
    if getcfg('RouterStatusPage', False):
        router_status = device("Router")
    next_check_time = next_WANIP_check_time = time.time()
    
    while 1:
        if config.loadconfig(flush_on_reload=True, cfglogfile_wins=logfile_override):       # Refresh if changes
            # config.loadconfig(cfglogfile_wins=logfile_override)
            logging.warning(f"NOTE - The config file has been reloaded.")
            modem_status = device("Modem")     # Recreate device objects since their config has possibly changed
            router_status = device("Router")
            next_check_time = next_WANIP_check_time = time.time()

        if time.time() > next_check_time:

            status, msg = have_internet()

            if not status: # INTERNET ACCESS LOST
                outage_timestamp = time.time()
                logging.warning(f"INTERNET ACCESS LOST")
                while 1:
                    # Uncomment for debug - allows changing IAPingAddr or IADNSPage for testing have_internet() logic
                    # if loadconfig(cfgfile = args.config_file, flush_on_reload=True, cfglogfile_wins=logfile_override):       # Refresh if changes
                    #     logging.warning(f"NOTE - The config file has been reloaded.")

                    if getcfg('ModemStatusPage', False):           # Check if we can get past the router to the modem (for diagnostic purposes)
                        status, state, msg = modem_status.get_data()
                        logging.info (f"{'Modem status:':{FIELD_WIDTH1}} {state:{FIELD_WIDTH2}} {msg}")


                    status, msg = have_internet()
                    logging.debug (f"have_internet() call returned {status}, {msg}")
                    if status: # INTERNET ACCESS RECOVERED
                        outage_period = int(time.time() - outage_timestamp)

                        logging.info (f"Doing <{getcfg('RecoveryDelay')}> internet access recovery delay")
                        time.sleep (timevalue(getcfg('RecoveryDelay')).seconds)

                        subject = "NOTICE:  HOME INTERNET OUTAGE ENDED"
                        message = f"Outage time:  {datetime.timedelta(seconds = outage_period)}"    # Cast int seconds to "00:00:00" format
                        if getcfg("NotifList", False):
                            try:
                                snd_notif (subj=subject, msg=message, log=True)
                            except Exception as e:
                                logging.warning(f"snd_notif error for <{subject}>:  {e}")
                        if getcfg("EmailTo", False):
                            try:
                                snd_email (subj=subject, body=message, to='EmailTo', log=True)
                            except Exception as e:
                                logging.warning(f"snd_email error for <{subject}>:  {e}")
                        if not getcfg("NotifList", False)  and  not getcfg("EmailTo", False):
                            logging.warning(f"{subject} - {message}")

                        next_check_time = next_WANIP_check_time = time.time()
                        break
                    time.sleep (timevalue(getcfg('OutageRecheckPeriod')).seconds)

            else:   # HAVE INTERNET
                logging.info   (f"{'Internet access:':{FIELD_WIDTH1}} {'Working':{FIELD_WIDTH2}} {msg}")

                # Check modem status
                if getcfg('ModemStatusPage', False):
                    status, state, msg = modem_status.get_data()
                    if status:
                        logging.info    (f"{'Modem status:':{FIELD_WIDTH1}} {state:{FIELD_WIDTH2}} {msg}")
                    else:
                        logging.warning (f"{'Modem status:':{FIELD_WIDTH1}} {state:{FIELD_WIDTH2}} {msg}")

                # Check for router WAN IP address change
                if getcfg('RouterStatusPage', False):
                    status, WANIP, msg = router_status.get_data()
                    if status:
                        logging.info     (f"{'Router reported WANIP:':{FIELD_WIDTH1}} {WANIP:{FIELD_WIDTH2}} {msg}")
                        if WANIP != SavedWANIP:
                            subject = "NOTICE:  HOME WAN IP CHANGED"
                            message = f"New WAN IP: <{WANIP}>, Prior WAN IP: <{SavedWANIP}>."
                            if getcfg("NotifList", False):
                                try:
                                    snd_notif (subj=subject, msg=message, log=True)
                                except Exception as e:
                                    logging.warning(f"snd_notif error for <{subject}>:  {e}")
                            if getcfg("EmailTo", False):
                                try:
                                    snd_email (subj=subject, body=message, to='EmailTo', log=True)
                                except Exception as e:
                                    logging.warning(f"snd_email error for <{subject}>:  {e}")
                            if not getcfg("NotifList", False)  and  not getcfg("EmailTo", False):
                                logging.warning(f"{subject} - {message}")

                            with io.open(WANfile, 'w', encoding="utf8") as ofile:
                                ofile.write (WANIP)
                            SavedWANIP = WANIP
                    else:
                        logging.warning(f"Failed getting WANIP address from router:\n{msg}")

                # Periodically check external web page for WANIP
                if getcfg('WANIPWebpage', False):
                    if (time.time() > next_WANIP_check_time):
                        status, ext_WANIP = get_external_WANIP()
                        if status:
                            logging.info (f"{'Externally reported WANIP:':{FIELD_WIDTH1}} {ext_WANIP:{FIELD_WIDTH2}}")
                        else:
                            logging.warning (f"Failed getting externally reported WANIP:  {ext_WANIP}")
                        
                        next_WANIP_check_time += timevalue(getcfg('ExternalWANRecheckPeriod')).seconds

            next_check_time += timevalue(getcfg('StatusRecheckPeriod')).seconds
        time.sleep (10)


def have_internet():
    """Check for internet access by pinging an external address, or by making a socket connection to an 
        external DNS server.
    Config params:
        IACheckMethod (Internet Access check methods: 'DNS' or 'ping', case insensitive)
            ping mode
                IAPingAddrs - a whitespace separated list of addresses to ping
                IAPingMaxTime
            DNS mode
                IADNSAddrs - a whitespace separated list of DNS server IP addresses
                IADNSTimeout
    Returns True on successful ping time < IAPingMaxTime (in ms)  or  successful DNS connection within 
    IADNSTimeout (based on IACheckMethod), else False.
    Also returns target address and response time
    """
    msg = f"have_internet() failed - Invalid IACheckMethod <{getcfg('IACheckMethod')}>?"
    if getcfg("IACheckMethod", "none").lower() == "ping":
        for addr in getcfg("IAPingAddrs").split():
            for _ in range (getcfg('nRetries')):
                logging.debug (f"have_internet() try {_} ")
                try:
                    logging.debug (f"Attempting ping to {addr}")
                    start_time = time.time()
                    ping = subprocess.run(["ping", addr, "-c", "1", "-W", "5"],     # timeout hardcoded to 5sec
                        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                    cmd_time = time.time() - start_time
                    ping.check_returncode()
                    ping_time = float(re.search("time=([\d.]*)", ping.stdout).group(1))
                    msg = f"(ping {addr} {ping_time:6.1f} ms, command run time {cmd_time*1000:6.1f} ms)"
                    if ping_time < float(getcfg("IAPingMaxTime")):
                        return True, msg
                    else:
                        return False, msg
                except Exception as e:
                    msg = (f"Ping errored:\n  {e}")
            logging.info (f"Ping to <{addr}> failed.  Trying next server, if specified.")
        # logging.debug (f"have_internet() checks errored:\n  {msg}")

    if getcfg("IACheckMethod", "none").lower() == "dns":
        # Host: 8.8.8.8 (google-public-dns-a.google.com)
        # OpenPort: 53/tcp
        # Service: domain (DNS/TCP)
        # From:  https://stackoverflow.com/questions/3764291/checking-network-connection
        for addr in getcfg("IADNSAddrs").split():
            for _ in range (getcfg('nRetries')):
                logging.debug (f"have_internet() try {_} ")
                try:
                    # socket.setdefaulttimeout(getcfg("IADNSTimeout"))
                    logging.debug (f"Attempting socket connection to {addr}")
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(timevalue(getcfg('IADNSTimeout')).seconds)
                    start_time = time.time()
                    s.connect((addr, 53))
                    cmd_time = time.time() - start_time
                    s.close()
                    msg = f"(DNS server {addr}, command run time {cmd_time*1000:6.1f} ms)"
                    return True, msg
                except Exception as e:
                    msg = "DNS connection errored:\n  " + repr(e)
            logging.info (f"DNS connection to <{addr}> failed.  Trying next server, if specified.")
        # logging.debug (f"have_internet() checks errored:\n  {msg}")
    return False, msg


class device:
    """ Manage the connection to a router or modem, and extract specific data.

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

    Return info - device.get_data() returns a 3-tuple:
        True/False for the success of the call.
        The data item of interest per xxxStatusRE (modem state or WANIP from the router).
        Formatted text message - command run time on success, or an error message.
    """

    def __init__(self, device_name):
        self.device_name           = device_name
        self.status_page           = getcfg(device_name + "StatusPage", "")
        self.status_RE             = getcfg(device_name + "StatusRE", "")
        self.login_page            = getcfg(device_name + "LoginPage", None)
        self.login_required_text   = getcfg(device_name + "LoginRequiredText", "nosuchtext")
        self.login_username_field  = getcfg(device_name + "LoginUsernameField", False)
        self.login_username        = getcfg(device_name + "_USER", "")
        self.login_password_field  = getcfg(device_name + "LoginPasswordField", "")
        self.login_password        = getcfg(device_name + "_PASS", "")
        self.login_additional_keys = getcfg(device_name + "LoginAdditionalKeys", "")
        self.csrf_RE               = getcfg(device_name + "CsrfRE", "")
        self.timeout               = timevalue(getcfg(device_name + "Timeout", 1)).seconds

        self.session = requests.session()
        self.payload = {}
        self.csrf_mode = False
        self.csrf_key = ""

        if self.login_username_field:
            self.payload[self.login_username_field] = self.login_username
            self.payload[self.login_password_field] = self.login_password
        for dict_item in self.login_additional_keys.split(","):
            if ":" in dict_item:
                key, value = dict_item.split(":")
                self.payload[key.strip(" '\"")] = value.strip(" '\"")
                if "csrf" in key.lower():
                    self.csrf_mode = True
                    self.csrf_key = key.strip(" '\"")

    def close(self):
        if self.session:
            self.session.close()

    def update_csrf(self, page_text):
        csrf = re.search(self.csrf_RE, page_text)
        if csrf:
            self.payload[self.csrf_key] = csrf.group(1)
            # logging.debug (f"Updated csrf token:  {csrf.group(1)}")
        else:
            logging.warning (f"No csrf response from the {self.device_name}")

    def get_data(self):
        msg = f"Invalid web page response from {self.device_name}"

        for _ in range (getcfg('nRetries')):
            try:
                logging.debug (f"{self.device_name} try {_} ")
                # logging.debug(f"{self.device_name} payload:  {self.payload}")
                start_time = time.time()
                if not self.csrf_mode:
                    status_page = self.session.get(self.status_page, timeout=self.timeout, verify = False)
                else:
                    status_page = self.session.post(self.status_page, data=self.payload, timeout=self.timeout, verify = False)
                    self.update_csrf(status_page.text)
                cmd_time = time.time() - start_time

                if self.login_required_text in status_page.text:
                    logging.debug(f"{self.device_name} login executed")
                    # logging.debug(f"{self.device_name} payload:  {self.payload}")
                    if self.login_page is not None:
                        login_page = self.session.post(self.login_page, data=self.payload, timeout=self.timeout, verify = False)
                        if self.csrf_mode:
                            self.update_csrf(login_page.text)
                    start_time = time.time()
                    if not self.csrf_mode:
                        status_page = self.session.get(self.status_page, timeout=self.timeout, verify = False)
                    else:
                        status_page = self.session.post(self.status_page, data=self.payload, timeout=self.timeout, verify = False)
                        self.update_csrf(status_page.text)
                    cmd_time = time.time() - start_time

                out = re.search(self.status_RE, status_page.text, re.DOTALL)
                if out:
                    msg = f"(command run time {cmd_time*1000:6.1f} ms)"
                    return True, out.group(1), msg
            except Exception as e:
                msg = f"{self.device_name} access errored:\n  " + repr(e)
        return False, "", msg


def get_external_WANIP():
    """Get WAN IP from external web page.
    Config params:
        WANIPWebpage
        WANIPWebpageRE
        WANIPWebpageTimeout
    On success, returns True and the IP address returned from the webpage, else False and the error message.
    """
    WANIP_FORMAT = re.compile(getcfg("WANIPWebpageRE"))
    msg = f"Invalid web page response from external webpage {getcfg('WANIPWebpage')}"
    for _ in range (getcfg('nRetries')):
        try:
            start_time = time.time()
            web_page = requests.get(getcfg('WANIPWebpage'), timeout=timevalue(getcfg('WANIPWebpageTimeout')).seconds)
            cmd_time = time.time() - start_time
            out = WANIP_FORMAT.search(web_page.text)
            if out:
                msg = f"{out.group(1):{FIELD_WIDTH2}} (command run time {cmd_time*1000:6.1f} ms)"
                return True, msg
        except Exception as e:
            msg = "Checking external WANIPage errored:\n  " + repr(e)
    return False, msg


def cleanup():
    global modem_status, router_status
    logging.warning ("Cleanup")
    if getcfg('ModemStatusPage', False):
        modem_status.close()
    if getcfg('RouterStatusPage', False):
        router_status.close()
    pass


def int_handler(signal, frame):
    logging.warning(f"Signal {signal} received.  Exiting.")
    cleanup()
    sys.exit(0)
signal.signal(signal.SIGINT,  int_handler)      # Ctrl-C
signal.signal(signal.SIGTERM, int_handler)      # kill

def cli():
    global toolname, config
    global logfile_override
# if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__ + __version__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--config-file', '-c', type=str, default=CONFIG_FILE,
                        help=f"Path to the config file (Default <{CONFIG_FILE})>.")
    parser.add_argument('--log-file', '-l', type=str, default=None,
                        help=f"Path to the log file.")
    parser.add_argument('--print-log', '-p', action='store_true',
                        help="Print the tail end of the log file (last 40 lines).")
    parser.add_argument('--service', action='store_true',
                        help="Enter endless loop for use as a systemd service.")
    parser.add_argument('-V', '--version', action='version', version='%(prog)s ' + __version__,
                        help="Return version number and exit.")

    args = parser.parse_args()

    toolname = settoolname (TOOLNAME)
    # Load config file and setup logging
    logfile_override = True  if not args.service  else False

    deploy_files('hi')

    if args.config_file == "newuserconfig":
        try:
            template_config_file = mungePath(CONFIG_FILE, Path(__file__).parent).full_path
            target_config_dir = mungePath("dummy", toolname.user_config_dir, mkdir=True).parent
            shutil.copy(template_config_file, target_config_dir)
            print (f"Copied  <{CONFIG_FILE}>  to  <{target_config_dir}>")
        except Exception as e:
            print (f"Failed copying <{CONFIG_FILE}> to <{target_config_dir}>\n  {e}")
        sys.exit()

    if args.config_file == "newsiteconfig":
        try:
            template_config_file = mungePath(CONFIG_FILE, Path(__file__).parent).full_path
            target_config_dir = mungePath("dummy", toolname.site_config_dir).parent
            mungePath("dummy", toolname.site_config_dir, mkdir=True) # force creation of directory
            shutil.copy(template_config_file, target_config_dir)
            print (f"Copied  <{CONFIG_FILE}>  to  <{target_config_dir}>")
        except Exception as e:
            print (f"Failed copying <{CONFIG_FILE}> to <{target_config_dir}>\n  {e}")
        sys.exit()

    try:
        config = config_item(args.config_file)
        config.loadconfig(cfglogfile_wins=logfile_override, cfglogfile=args.log_file) #, cfgloglevel=10)
        # print (toolname.log_full_path)
        # loadconfig(args.config_file, cfglogfile_wins=logfile_override)
    except Exception as e:
        logging.error(f"Failed loading config file <{args.config_file}>. \n  Run with  '--config-file newuserconfig'  to place a template config file at {toolname.user_config_dir}\n  {e}\n  Aborting.")
        sys.exit(1)

    logging.warning (f"========== {os.path.basename(__file__)} ({__version__}) ==========")
    # logging.info (f"Config file <{os.path.abspath(args.config_file)}>")
    logging.warning (f"Config file <{config.config_full_path}>")


    # Print the tail end of the log file
    if args.print_log:
        # _fp = getcfg("LogFile")
        # if not os.path.isabs(_fp):
        #     _fp = os.path.join(PROGDIR, _fp)
        # subprocess.run(["tail", "-40", _fp])
        print (f"Tail of  <{toolname.log_full_path}>:")
        subprocess.run(["tail", "-40", toolname.log_full_path])
        sys.exit()

    if args.service:
        service()

    main()
    sys.exit()