#!/usr/bin/env python3
"""Check internet access and WAN IP address.  Send notification/email after outage is over and
on WAN IP change.
"""

#==========================================================
#
#  Chris Nelson, 2020 - 2023
#
# 3.0 230215 - Converted to package format, updated to cjnfuncs 2.0
# ...
# 0.1 201028 - New
#
#==========================================================

import argparse
import sys
import datetime
import time
import requests
import subprocess
import socket
import re
import signal
import collections
import platform

try:
    import importlib.metadata
    __version__ = importlib.metadata.version(__package__ or __name__)
except:
    try:
        import importlib_metadata
        __version__ = importlib_metadata.version(__package__ or __name__)
    except:
        __version__ = "3.0 X"

# from cjnfuncs.cjnfuncs import set_toolname, setup_logging, logging, config_item, getcfg, mungePath, deploy_files, timevalue, retime, requestlock, releaselock,  snd_notif, snd_email
from cjnfuncs.cjnfuncs import set_toolname, deploy_files, config_item, mungePath, getcfg, timevalue, logging, snd_notif, snd_email


# Configs / Constants
TOOLNAME        = "wanstatus"
CONFIG_FILE     = "wanstatus.cfg"
PRINTLOGLENGTH  = 40
# Logging results field widths
# Internet access:               Working        (DNS server...
# ^^FIELD_WIDTH1                 ^^FIELD_WIDTH2
FIELD_WIDTH1    = 28
FIELD_WIDTH2    = 16


def main():
    global modem_status, router_status
    global tool
    logging.getLogger().setLevel(20)    # Force info level logging for interactive usage

    SavedWANIP = ""

    WANfile = mungePath (getcfg("WANIPFile"), tool.data_dir)
    if WANfile.is_file:
        with WANfile.full_path.open() as ifile:
            SavedWANIP = ifile.read()

    # Check internet access
    status, msg = have_internet()
    if status:
        logging.info   (f"{'Internet access:':{FIELD_WIDTH1}} {'Working':{FIELD_WIDTH2}} {msg}")
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
    global tool
    global config, logfile_override

    SavedWANIP = ""

    WANfile = mungePath (getcfg("WANIPFile"), tool.data_dir)
    if WANfile.is_file:
        with WANfile.full_path.open() as ifile:
            SavedWANIP = ifile.read()

    if getcfg('ModemStatusPage', False):
        modem_status = device("Modem")
    if getcfg('RouterStatusPage', False):
        router_status = device("Router")
    next_check_time = next_WANIP_check_time = time.time()
    
    while 1:
        if config.loadconfig(flush_on_reload=True, call_logfile_wins=logfile_override):       # Refresh if changes
            logging.warning(f"NOTE - The config file has been reloaded.")
            modem_status = device("Modem")     # Recreate device objects since their configs may have changed
            router_status = device("Router")
            next_check_time = next_WANIP_check_time = time.time()

        if time.time() > next_check_time:

            status, msg = have_internet()

            if not status: # INTERNET ACCESS LOST
                outage_timestamp = time.time()
                logging.warning(f"INTERNET ACCESS LOST")
                while 1:
                    # Uncomment for debug - allows changing IAPingAddr or IADNSPage for testing have_internet() logic
                    # if config.loadconfig(flush_on_reload=True, call_logfile_wins=logfile_override):       # Refresh if changes
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

                            with WANfile.full_path.open('w') as ofile:
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
                    if platform.system() == "Windows":
                        _cmd = ["ping", addr, r"/n", "1"] #, r"/w", "5000"]     # Setting timeout /w on Windows fails.  ??
                    else:
                        _cmd = ["ping", addr, "-c", "1", "-W", "5"]     # timeout hardcoded to 5sec
                    ping = subprocess.run(_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
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


def int_handler(signal, frame):
    logging.warning(f"Signal {signal} received.  Exiting.")
    cleanup()
    sys.exit(0)
signal.signal(signal.SIGINT,  int_handler)      # Ctrl-C
signal.signal(signal.SIGTERM, int_handler)      # kill


def cli():
    global tool, config
    global logfile_override

    tool = set_toolname (TOOLNAME)

    parser = argparse.ArgumentParser(description=__doc__ + __version__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--config-file', '-c', type=str, default=CONFIG_FILE,
                        help=f"Path to the config file (Default <{CONFIG_FILE})> in user/site config directory.")
    parser.add_argument('--log-file', '-l', type=str, default=None,
                        help=f"Path to the log file.")
    parser.add_argument('--print-log', '-p', action='store_true',
                        help=f"Print the tail end of the log file (default last {PRINTLOGLENGTH} lines).")
    parser.add_argument('--service', action='store_true',
                        help="Enter endless loop for use as a systemd service.")
    parser.add_argument('--setup-user', action='store_true',
                        help=f"Install starter files in user space.")
    parser.add_argument('--setup-site', action='store_true',
                        help=f"Install starter files in system-wide space. Run with root prev.")
    parser.add_argument('-V', '--version', action='version', version=f"{tool.toolname} {__version__}",
                        help="Return version number and exit.")
    args = parser.parse_args()


    # Deploy template files
    if args.setup_user:
        deploy_files([
            { "source": CONFIG_FILE,         "target_dir": "USER_CONFIG_DIR"},
            { "source": "creds_wanstatus",   "target_dir": "USER_CONFIG_DIR", "file_stat": 0o600},
            { "source": "creds_SMTP",        "target_dir": "USER_CONFIG_DIR", "file_stat": 0o600},
            { "source": "wanstatus.service", "target_dir": "USER_CONFIG_DIR", "file_stat": 0o664},
            ])
        sys.exit()

    if args.setup_site:
        deploy_files([
            { "source": CONFIG_FILE,         "target_dir": "SITE_CONFIG_DIR"},
            { "source": "creds_wanstatus",   "target_dir": "SITE_CONFIG_DIR", "file_stat": 0o600},
            { "source": "creds_SMTP",        "target_dir": "SITE_CONFIG_DIR", "file_stat": 0o600},
            { "source": "wanstatus.service", "target_dir": "SITE_CONFIG_DIR", "file_stat": 0o664},
            ])
        sys.exit()


    # Load config file and setup logging
    logfile_override = True  if not args.service  else False
    try:
        config = config_item(args.config_file)
        config.loadconfig(call_logfile_wins=logfile_override, call_logfile=args.log_file) #, ldcfg_ll=10)
    except Exception as e:
        logging.error(f"Failed loading config file <{args.config_file}>. \
\n  Run with  '--setup-user' or '--setup-site' to install starter files.\n  {e}\n  Aborting.")
        sys.exit(1)


    logging.warning (f"========== {tool.toolname} ({__version__}) ==========")
    logging.warning (f"Config file <{config.config_full_path}>")


    # Print log
    if args.print_log:
        try:
            _lf = mungePath(getcfg("LogFile"), tool.log_dir_base).full_path
            print (f"Tail of  <{_lf}>:")
            _xx = collections.deque(_lf.open(), getcfg("PrintLogLength", 40))
            for line in _xx:
                print (line, end="")
        except Exception as e:
            print (f"Couldn't print the log file.  LogFile defined in the config file?\n  {e}")
        sys.exit()


    # Run in service or interactive modes
    if args.service:
        service()

    sys.exit(main())

    
if __name__ == '__main__':
    sys.exit(cli())