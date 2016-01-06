#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of Plex:CS.
#
#  Plex:CS is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Plex:CS is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Plex:CS.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

# Ensure lib added to path, before any other imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib/'))

from plexcs import webstart, logger, web_socket

import locale
import time
import signal
import argparse
import plexcs

# Register signals, such as CTRL + C
signal.signal(signal.SIGINT, plexcs.sig_handler)
signal.signal(signal.SIGTERM, plexcs.sig_handler)


def main():
    """
    Plex:CS application entry point. Parses arguments, setups encoding and
    initializes the application.
    """

    # Fixed paths to Plex:CS
    if hasattr(sys, 'frozen'):
        plexcs.FULL_PATH = os.path.abspath(sys.executable)
    else:
        plexcs.FULL_PATH = os.path.abspath(__file__)

    plexcs.PROG_DIR = os.path.dirname(plexcs.FULL_PATH)
    plexcs.ARGS = sys.argv[1:]

    # From sickbeard
    plexcs.SYS_PLATFORM = sys.platform
    plexcs.SYS_ENCODING = None

    try:
        locale.setlocale(locale.LC_ALL, "")
        plexcs.SYS_ENCODING = locale.getpreferredencoding()
    except (locale.Error, IOError):
        pass

    # for OSes that are poorly configured I'll just force UTF-8
    if not plexcs.SYS_ENCODING or plexcs.SYS_ENCODING in ('ANSI_X3.4-1968', 'US-ASCII', 'ASCII'):
        plexcs.SYS_ENCODING = 'UTF-8'

    # Set up and gather command line arguments
    parser = argparse.ArgumentParser(
        description='A Python based monitoring and tracking tool for Plex Media Server.')

    parser.add_argument(
        '-v', '--verbose', action='store_true', help='Increase console logging verbosity')
    parser.add_argument(
        '-q', '--quiet', action='store_true', help='Turn off console logging')
    parser.add_argument(
        '-d', '--daemon', action='store_true', help='Run as a daemon')
    parser.add_argument(
        '-p', '--port', type=int, help='Force Plex:CS to run on a specified port')
    parser.add_argument(
        '--datadir', help='Specify a directory where to store your data files')
    parser.add_argument('--config', help='Specify a config file to use')
    parser.add_argument('--nolaunch', action='store_true',
                        help='Prevent browser from launching on startup')
    parser.add_argument(
        '--pidfile', help='Create a pid file (only relevant when running as a daemon)')

    args = parser.parse_args()

    if args.verbose:
        plexcs.VERBOSE = True
    if args.quiet:
        plexcs.QUIET = True

    # Do an intial setup of the logger.
    logger.initLogger(console=not plexcs.QUIET, log_dir=False,
                      verbose=plexcs.VERBOSE)

    if args.daemon:
        if sys.platform == 'win32':
            sys.stderr.write(
                "Daemonizing not supported under Windows, starting normally\n")
        else:
            plexcs.DAEMON = True
            plexcs.QUIET = True

    if args.pidfile:
        plexcs.PIDFILE = str(args.pidfile)

        # If the pidfile already exists, plexcs may still be running, so
        # exit
        if os.path.exists(plexcs.PIDFILE):
            raise SystemExit("PID file '%s' already exists. Exiting." %
                             plexcs.PIDFILE)

        # The pidfile is only useful in daemon mode, make sure we can write the
        # file properly
        if plexcs.DAEMON:
            plexcs.CREATEPID = True

            try:
                with open(plexcs.PIDFILE, 'w') as fp:
                    fp.write("pid\n")
            except IOError as e:
                raise SystemExit("Unable to write PID file: %s", e)
        else:
            logger.warn("Not running in daemon mode. PID file creation " \
                        "disabled.")

    # Determine which data directory and config file to use
    if args.datadir:
        plexcs.DATA_DIR = args.datadir
    else:
        plexcs.DATA_DIR = plexcs.PROG_DIR

    if args.config:
        config_file = args.config
    else:
        config_file = os.path.join(plexcs.DATA_DIR, 'config.ini')

    # Try to create the DATA_DIR if it doesn't exist
    if not os.path.exists(plexcs.DATA_DIR):
        try:
            os.makedirs(plexcs.DATA_DIR)
        except OSError:
            raise SystemExit(
                'Could not create data directory: ' + plexcs.DATA_DIR + '. Exiting....')

    # Make sure the DATA_DIR is writeable
    if not os.access(plexcs.DATA_DIR, os.W_OK):
        raise SystemExit(
            'Cannot write to the data directory: ' + plexcs.DATA_DIR + '. Exiting...')

    # Put the database in the DATA_DIR
    plexcs.DB_FILE = os.path.join(plexcs.DATA_DIR, 'plexcs.db')

    # Read config and start logging
    plexcs.initialize(config_file)

    if plexcs.DAEMON:
        plexcs.daemonize()

    # Force the http port if neccessary
    if args.port:
        http_port = args.port
        logger.info('Using forced web server port: %i', http_port)
    else:
        http_port = int(plexcs.CONFIG.HTTP_PORT)

    # Check if pyOpenSSL is installed. It is required for certificate generation
    # and for CherryPy.
    if plexcs.CONFIG.ENABLE_HTTPS:
        try:
            import OpenSSL
        except ImportError:
            logger.warn("The pyOpenSSL module is missing. Install this " \
                        "module to enable HTTPS. HTTPS will be disabled.")
            plexcs.CONFIG.ENABLE_HTTPS = False

    # Try to start the server. Will exit here is address is already in use.
    web_config = {
        'http_port': http_port,
        'http_host': plexcs.CONFIG.HTTP_HOST,
        'http_root': plexcs.CONFIG.HTTP_ROOT,
        'http_proxy': plexcs.CONFIG.HTTP_PROXY,
        'enable_https': plexcs.CONFIG.ENABLE_HTTPS,
        'https_cert': plexcs.CONFIG.HTTPS_CERT,
        'https_key': plexcs.CONFIG.HTTPS_KEY,
        'http_username': plexcs.CONFIG.HTTP_USERNAME,
        'http_password': plexcs.CONFIG.HTTP_PASSWORD,
    }
    webstart.initialize(web_config)

    # Start the background threads
    plexcs.start()

    # Open connection for websocket
    if plexcs.CONFIG.MONITORING_USE_WEBSOCKET:
        try:
            web_socket.start_thread()
        except:
            logger.warn(u"Websocket :: Unable to open connection.")
            # Fallback to polling
            plexcs.POLLING_FAILOVER = True
            plexcs.initialize_scheduler()

    # Open webbrowser
    if plexcs.CONFIG.LAUNCH_BROWSER and not args.nolaunch:
        plexcs.launch_browser(plexcs.CONFIG.HTTP_HOST, http_port,
                              plexcs.CONFIG.HTTP_ROOT)

    # Wait endlessy for a signal to happen
    while True:
        if not plexcs.SIGNAL:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                plexcs.SIGNAL = 'shutdown'
        else:
            logger.info('Received signal: %s', plexcs.SIGNAL)

            if plexcs.SIGNAL == 'shutdown':
                plexcs.shutdown()
            elif plexcs.SIGNAL == 'restart':
                plexcs.shutdown(restart=True)
            else:
                plexcs.shutdown(restart=True, update=True)

            plexcs.SIGNAL = None

# Call main()
if __name__ == "__main__":
    main()
