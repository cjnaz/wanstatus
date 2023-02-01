#!/usr/bin/env python3
"""Description goes here.
Run as:
    ./template LICENSE.txt -c 5 -vv -u 5 -1
        or
    ./template junk:5-@ -c 5 -vv -u 5 -1
        or
    ./template LICENSE.txt -c 5 --service
"""

__version__ = "V1.1 220412"


#==========================================================
#
#  Chris Nelson, Copyright 2021
#
# V1.1 220412  Updated for funcs3 V1.1
#
# Changes pending
#   
#==========================================================

import argparse
import sys
import os.path
import io
# import tempfile
import time
import re
import subprocess
import signal

# sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), './funcs3/'))    # funcs3 in subdir
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../funcs3/'))    # funcs3 in peer dir
from funcs3 import PROGDIR, loadconfig, getcfg, cfg, timevalue, setuplogging, logging, funcs3_min_version_check, funcs3_version, snd_notif, snd_email, requestlock, releaselock, ConfigError, SndEmailError

# Configs / Constants
UPDATE_INTERVAL = 3600          # Seconds, interval between memory usages logs
COMMANDS = "Hello, Goodby, Let'sGo"
PY_MIN_VERSION = 3.6
FUNCS3_MIN_VERSION = 1.1
CONFIG_FILE = os.path.join(PROGDIR, 'template.cfg')
# CONSOLE_LOGGING_FORMAT = '{module:>15}.{funcName:20} - {levelname:>8}:  {message}'
# LOG_FILE = "log_file.txt"       # Specify if config file not being used or not being set in the config file


# is_Windows = False
# is_Linux = False
# if sys.platform == "win32":
#     is_Windows = True
# if "linux" in sys.platform:  # <linux2> on Py2, <linux> on Py3
#     is_Linux = True


def main():
    
    # code examples
    _cmd = ["uptime", "-p"]
    if py_version >= 3.7:
        uptime = subprocess.run(_cmd, capture_output=True, text=True).stdout
    else:   #Py 3.6 .run does not support capture_output, so use the old method.
        uptime = subprocess.run(_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True).stdout
    logging.warning (uptime)


    matchstring = re.compile(r'^([\w:-]+)@$')
    out = matchstring.match(args.Infile)        # matches "junk:5-@"
    if out:
        logging.warning (f"Match: <{out.group(1)}>")

    logging.warning (f"Update switch <{args.update}>")

    with io.open(getcfg("OUTFILE"), "wt", encoding='utf8') as outfile:
        outfile.write("Writing to a file")


def service():
    logging.info ("Entering service loop.  Edit config file 'testvar'.  Ctrl-C to exit")
    next_run = time.time()
    while True:
        if time.time() > next_run:
            if loadconfig(cfgfile = args.config_file, flush_on_reload=True):       # Refresh only if file changes
                logging.warning(f"NOTE - The config file has been reloaded.")
                logging.warning(f"testvar: {getcfg('testvar', None)}  type {type(getcfg('testvar', None))}")
                logging.warning(f"LogFile currently:   {getcfg('LogFile', None)}")
                logging.warning(f"LogLevel currently:  {getcfg('LogLevel', None)}")
                logging.warning(f"Actual logging level:  {logging.getLogger().level}")
                logging.info ("info  level log")
                logging.debug("debug level log")
            next_run += timevalue(getcfg("ServiceLoopTime")).seconds
        time.sleep(0.5)


def cleanup():
    logging.warning ("Cleanup")
    pass


def int_handler(signal, frame):
    logging.warning(f"Signal {signal} received.  Exiting.")
    cleanup()
    sys.exit(0)
signal.signal(signal.SIGINT,  int_handler)      # Ctrl-C
signal.signal(signal.SIGTERM, int_handler)      # kill



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__ + __version__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('Infile',                                               # Argparse argument examples
                        help="The infile")
    parser.add_argument('Command', nargs='?',                                   # optional positional argument
                        help=f"The command  ({COMMANDS})")
    parser.add_argument('-u', '--update', type=int, default=UPDATE_INTERVAL,
                        help=f"Update interval (default = {UPDATE_INTERVAL}s).")
    parser.add_argument('-1', '--once', action='store_true',
                        help="Single run mode.  Logging is to console rather than file.")
    parser.add_argument('--now', dest='format', choices=['std', 'iso', 'unix', 'tz'],
                        help="shows datetime in given format")
    parser.add_argument('-v', '--verbose', action='count',
                        help="Print status and activity messages.")
    parser.add_argument('-c', type=int, required=True, metavar='countvalue',
                        help="Count value.",)
    parser.add_argument('--config-file', type=str, default=CONFIG_FILE,
                        help=f"Path to the config file (Default <{CONFIG_FILE})>.")
    parser.add_argument('--log-file', default=None,         # With config file version
                        help=f"Path to log file (overrides LogFile in config file, default <{None}).")
    # parser.add_argument('--log-file', default=LOG_FILE,     # Without config file version
    #                     help=f"Path to log file (default <{LOG_FILE}).")
    parser.add_argument('--service', action='store_true',
                        help="Enter endless loop for use as a systemd service.")
    parser.add_argument('-V', '--version', action='version', version='%(prog)s ' + __version__,
                        help="Return version number and exit.")

    # if len(sys.argv)==1:      # Useful for empty command line help (all args must be optional)
    #     parser.print_help()
    #     sys.exit()

    args = parser.parse_args()


    # If loadconfig not used then manually call setuplogging
    # if args.once:
    #     setuplogging(logfile=None)
    # else:
    #     setuplogging(logfile=LOG_FILE)


    # Load config file and setup logging
    # If no CLI --log-file, then remove 'cfglogfile=args.log_file' from loadconfig calls
    # If using interactive mode then don't give --log-file so that it defaults to None, thus logging goes to console
    # Calculate logfile_override based on interactive needs.  Add 'or args.log_file' if CLI --log-file should override config LogFile
    logfile_override = True  if args.once or args.log_file is not None  else False
    try:
        loadconfig(args.config_file, cfglogfile=args.log_file, cfglogfile_wins=logfile_override)
    except Exception as e:
        # logging.error(f"Failed loading config file <{args.config_file}> - Aborting.\n  {e}")
        # sys.exit(1)
        raise ConfigError (f"Config file <{args.config_file}> not found.  Aborting.\n{e}") from None


    # Verbosity level
    # To use --verbose, don't include LogLevel in the config file (LogLevel wins)
    if args.once and args.verbose is not None:      # Else logging level is set from config file LogLevel (default cfgloglevel)
        _level = [logging.WARNING, logging.INFO, logging.DEBUG][args.verbose  if args.verbose <= 2  else 2]
        logging.getLogger().setLevel(_level)
        logging.info (f"Logging level set to <{_level}>")


    logging.warning (f"========== {os.path.basename(__file__)} ({__version__}) ==========")
    logging.info (f"Config file <{os.path.abspath(args.config_file)}>")


    # Python min version check
    py_version = float(sys.version_info.major) + float(sys.version_info.minor)/10
    if py_version < PY_MIN_VERSION:
        logging.error (f"Current Python version {py_version} is less than minimum required version {PY_MIN_VERSION}.  Aborting.")
        sys.exit(1)


    # funcs3 min version check
    if not funcs3_min_version_check(FUNCS3_MIN_VERSION):
        logging.error(f"funcs3 module must be at least version <V{FUNCS3_MIN_VERSION}>.  Found <{funcs3_version}>.  Aborting.")
        sys.exit(1)
    else:
        logging.debug(f"funcs3 module version <{funcs3_version}> (min required <V{FUNCS3_MIN_VERSION}>)")


    # Input file existence check (and any other idiot checks)
    if not os.path.exists(args.Infile):
        logging.warning (f"Can't find the input file <{args.Infile}>")
        # sys.exit(1)


    if args.service:
        service()

    main()
    sys.exit()