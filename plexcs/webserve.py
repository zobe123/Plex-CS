﻿# This file is part of Plex:CS.
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

from plexcs import logger, notifiers, plextv, pmsconnect, common, log_reader, datafactory, graphs, users, helpers
from plexcs.helpers import checked, radio

from mako.lookup import TemplateLookup
from mako import exceptions

import plexcs
import threading
import cherrypy
import hashlib
import random
import json
import os

try:
    # pylint:disable=E0611
    # ignore this error because we are catching the ImportError
    from collections import OrderedDict
    # pylint:enable=E0611
except ImportError:
    # Python 2.6.x fallback, from libs
    from ordereddict import OrderedDict


def serve_template(templatename, **kwargs):
    interface_dir = os.path.join(str(plexcs.PROG_DIR), 'data/interfaces/')
    template_dir = os.path.join(str(interface_dir), plexcs.CONFIG.INTERFACE)

    _hplookup = TemplateLookup(directories=[template_dir], default_filters=['unicode', 'h'])

    server_name = plexcs.CONFIG.PMS_NAME

    try:
        template = _hplookup.get_template(templatename)
        return template.render(server_name=server_name, **kwargs)
    except:
        return exceptions.html_error_template().render()


class WebInterface(object):

    def __init__(self):
        self.interface_dir = os.path.join(str(plexcs.PROG_DIR), 'data/')

    @cherrypy.expose
    def index(self):
        if plexcs.CONFIG.FIRST_RUN_COMPLETE:
            raise cherrypy.HTTPRedirect("home")
        else:
            raise cherrypy.HTTPRedirect("welcome")

    @cherrypy.expose
    def home(self):
        config = {
            "home_stats_length": plexcs.CONFIG.HOME_STATS_LENGTH,
            "home_stats_cards": plexcs.CONFIG.HOME_STATS_CARDS,
            "home_library_cards": plexcs.CONFIG.HOME_LIBRARY_CARDS,
            "pms_identifier": plexcs.CONFIG.PMS_IDENTIFIER,
            "pms_name": plexcs.CONFIG.PMS_NAME,
            "pms2_name": plexcs.CONFIG.PMS_NAME
        }
        return serve_template(templatename="index.html", title="Home", config=config)

    @cherrypy.expose
    def welcome(self, **kwargs):
        config = {
            "launch_browser": checked(plexcs.CONFIG.LAUNCH_BROWSER),
            "refresh_users_on_startup": checked(plexcs.CONFIG.REFRESH_USERS_ON_STARTUP),
            "pms_identifier": plexcs.CONFIG.PMS_IDENTIFIER,
            "pms_ip": plexcs.CONFIG.PMS_IP,
            "pms_is_remote": checked(plexcs.CONFIG.PMS_IS_REMOTE),
            "pms_port": plexcs.CONFIG.PMS_PORT,
            "pms_token": plexcs.CONFIG.PMS_TOKEN,
            "pms_ssl": checked(plexcs.CONFIG.PMS_SSL),
            "pms_uuid": plexcs.CONFIG.PMS_UUID,
            "movie_notify_enable": checked(plexcs.CONFIG.MOVIE_NOTIFY_ENABLE),
            "tv_notify_enable": checked(plexcs.CONFIG.TV_NOTIFY_ENABLE),
            "music_notify_enable": checked(plexcs.CONFIG.MUSIC_NOTIFY_ENABLE),
            "movie_notify_on_start": checked(plexcs.CONFIG.MOVIE_NOTIFY_ON_START),
            "tv_notify_on_start": checked(plexcs.CONFIG.TV_NOTIFY_ON_START),
            "music_notify_on_start": checked(plexcs.CONFIG.MUSIC_NOTIFY_ON_START),
            "movie_logging_enable": checked(plexcs.CONFIG.MOVIE_LOGGING_ENABLE),
            "tv_logging_enable": checked(plexcs.CONFIG.TV_LOGGING_ENABLE),
            "music_logging_enable": checked(plexcs.CONFIG.MUSIC_LOGGING_ENABLE),
            "logging_ignore_interval": plexcs.CONFIG.LOGGING_IGNORE_INTERVAL,
            "check_github": checked(plexcs.CONFIG.CHECK_GITHUB)
            
        }

        # The setup wizard just refreshes the page on submit so we must redirect to home if config set.
        if plexcs.CONFIG.FIRST_RUN_COMPLETE:
            plexcs.initialize_scheduler()
            raise cherrypy.HTTPRedirect("home")
        else:
            return serve_template(templatename="welcome.html", title="Welcome", config=config)

    @cherrypy.expose
    def get_date_formats(self):
        if plexcs.CONFIG.DATE_FORMAT:
            date_format = plexcs.CONFIG.DATE_FORMAT
        else:
            date_format = 'YYYY-MM-DD'
        if plexcs.CONFIG.TIME_FORMAT:
            time_format = plexcs.CONFIG.TIME_FORMAT
        else:
            time_format = 'HH:mm'

        formats = {'date_format': date_format,
                   'time_format': time_format}

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(formats)

    @cherrypy.expose
    def home_stats(self, **kwargs):
        data_factory = datafactory.DataFactory()

        grouping = plexcs.CONFIG.GROUP_HISTORY_TABLES
        time_range = plexcs.CONFIG.HOME_STATS_LENGTH
        stats_type = plexcs.CONFIG.HOME_STATS_TYPE
        stats_count = plexcs.CONFIG.HOME_STATS_COUNT
        stats_cards = plexcs.CONFIG.HOME_STATS_CARDS.split(', ')
        notify_watched_percent = plexcs.CONFIG.NOTIFY_WATCHED_PERCENT

        stats_data = data_factory.get_home_stats(grouping=grouping,
                                                 time_range=time_range,
                                                 stats_type=stats_type,
                                                 stats_count=stats_count,
                                                 stats_cards=stats_cards,
                                                 notify_watched_percent=notify_watched_percent)

        return serve_template(templatename="home_stats.html", title="Stats", data=stats_data)

    @cherrypy.expose
    def library_stats(self, **kwargs):
        pms_connect = pmsconnect.PmsConnect()

        library_cards = plexcs.CONFIG.HOME_LIBRARY_CARDS.split(', ')

        if library_cards == ['library_statistics_first']:
            library_cards = ['library_statistics']
            server_children = pms_connect.get_server_children()
            server_libraries = server_children['libraries_list']

            for library in server_libraries:
                library_cards.append(library['key'])

            plexcs.CONFIG.HOME_LIBRARY_CARDS = ', '.join(library_cards)
            plexcs.CONFIG.write()

        stats_data = pms_connect.get_library_stats(library_cards=library_cards)

        return serve_template(templatename="library_stats.html", title="Library Stats", data=stats_data)

    @cherrypy.expose
    def compare(self):
        return serve_template(templatename="compare.html", title="Compare")

    @cherrypy.expose
    def users(self):
        return serve_template(templatename="users.html", title="Users")

    @cherrypy.expose
    def graphs(self):

        config = {
            "graph_type": plexcs.CONFIG.GRAPH_TYPE,
            "graph_days": plexcs.CONFIG.GRAPH_DAYS,
            "graph_tab": plexcs.CONFIG.GRAPH_TAB,
            "music_logging_enable": plexcs.CONFIG.MUSIC_LOGGING_ENABLE
        }

        return serve_template(templatename="graphs.html", title="Graphs", config=config)

    @cherrypy.expose
    def sync(self):
        return serve_template(templatename="sync.html", title="Sync")

    @cherrypy.expose
    def user(self, user=None, user_id=None):
        user_data = users.Users()
        if user_id:
            try:
                user_details = user_data.get_user_details(user_id=user_id)
            except:
                logger.warn("Unable to retrieve friendly name for user_id %s " % user_id)
        elif user:
            try:
                user_details = user_data.get_user_details(user=user)
            except:
                logger.warn("Unable to retrieve friendly name for user %s " % user)
        else:
            logger.debug(u"User page requested but no parameters received.")
            raise cherrypy.HTTPRedirect("home")

        return serve_template(templatename="user.html", title="User", data=user_details)

    @cherrypy.expose
    def edit_user_dialog(self, user=None, user_id=None, **kwargs):
        user_data = users.Users()
        if user_id:
            result = user_data.get_user_friendly_name(user_id=user_id)
            status_message = ''
        elif user:
            result = user_data.get_user_friendly_name(user=user)
            status_message = ''
        else:
            result = None
            status_message = 'An error occured.'

        return serve_template(templatename="edit_user.html", title="Edit User", data=result, status_message=status_message)

    @cherrypy.expose
    def edit_user(self, user=None, user_id=None, friendly_name=None, **kwargs):
        if 'do_notify' in kwargs:
            do_notify = kwargs.get('do_notify')
        else:
            do_notify = 0
        if 'keep_history' in kwargs:
            keep_history = kwargs.get('keep_history')
        else:
            keep_history = 0
        if 'thumb' in kwargs:
            custom_avatar = kwargs['thumb']
        else:
            custom_avatar = ''

        user_data = users.Users()
        if user_id:
            try:
                user_data.set_user_friendly_name(user_id=user_id,
                                                 friendly_name=friendly_name,
                                                 do_notify=do_notify,
                                                 keep_history=keep_history)
                user_data.set_user_profile_url(user_id=user_id,
                                               profile_url=custom_avatar)

                status_message = "Successfully updated user."
                return status_message
            except:
                status_message = "Failed to update user."
                return status_message
        if user:
            try:
                user_data.set_user_friendly_name(user=user,
                                                 friendly_name=friendly_name,
                                                 do_notify=do_notify,
                                                 keep_history=keep_history)
                user_data.set_user_profile_url(user=user,
                                               profile_url=custom_avatar)

                status_message = "Successfully updated user."
                return status_message
            except:
                status_message = "Failed to update user."
                return status_message

    @cherrypy.expose
    def get_stream_data(self, row_id=None, user=None, **kwargs):

        data_factory = datafactory.DataFactory()
        stream_data = data_factory.get_stream_details(row_id)

        return serve_template(templatename="stream_data.html", title="Stream Data", data=stream_data, user=user)

    @cherrypy.expose
    def get_ip_address_details(self, ip_address=None, **kwargs):
        import socket

        try:
            socket.inet_aton(ip_address)
        except socket.error:
            ip_address = None

        return serve_template(templatename="ip_address_modal.html", title="IP Address Details", data=ip_address)

    @cherrypy.expose
    def get_user_list(self, **kwargs):

        user_data = users.Users()
        user_list = user_data.get_user_list(kwargs=kwargs)

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(user_list)

    @cherrypy.expose
    def checkGithub(self):
        from plexcs import versioncheck

        versioncheck.checkGithub()
        raise cherrypy.HTTPRedirect("home")

    @cherrypy.expose
    def logs(self):
        return serve_template(templatename="logs.html", title="Log", lineList=plexcs.LOG_LIST)

    @cherrypy.expose
    def clearLogs(self):
        plexcs.LOG_LIST = []
        logger.info("Web logs cleared")
        raise cherrypy.HTTPRedirect("logs")

    @cherrypy.expose
    def toggleVerbose(self):
        plexcs.VERBOSE = not plexcs.VERBOSE
        logger.initLogger(console=not plexcs.QUIET,
                          log_dir=plexcs.CONFIG.LOG_DIR, verbose=plexcs.VERBOSE)
        logger.info("Verbose toggled, set to %s", plexcs.VERBOSE)
        logger.debug("If you read this message, debug logging is available")
        raise cherrypy.HTTPRedirect("logs")

    @cherrypy.expose
    def getLog(self, start=0, length=100, **kwargs):
        start = int(start)
        length = int(length)
        search_value = ""
        search_regex = ""
        order_column = 0
        order_dir = "desc"

        if 'order[0][dir]' in kwargs:
            order_dir = kwargs.get('order[0][dir]', "desc")

        if 'order[0][column]' in kwargs:
            order_column = kwargs.get('order[0][column]', "0")

        if 'search[value]' in kwargs:
            search_value = kwargs.get('search[value]', "")

        if 'search[regex]' in kwargs:
            search_regex = kwargs.get('search[regex]', "")

        filtered = []
        if search_value == "":
            filtered = plexcs.LOG_LIST[::]
        else:
            filtered = [row for row in plexcs.LOG_LIST for column in row if search_value.lower() in column.lower()]

        sortcolumn = 0
        if order_column == '1':
            sortcolumn = 2
        elif order_column == '2':
            sortcolumn = 1
        filtered.sort(key=lambda x: x[sortcolumn], reverse=order_dir == "desc")

        rows = filtered[start:(start + length)]
        rows = [[row[0], row[2], row[1]] for row in rows]

        return json.dumps({
            'recordsFiltered': len(filtered),
            'recordsTotal': len(plexcs.LOG_LIST),
            'data': rows,
        })

    @cherrypy.expose
    def get_plex_log(self, window=1000, **kwargs):
        log_lines = []
        try:
            log_lines = {'data': log_reader.get_log_tail(window=window)}
        except:
            logger.warn("Unable to retrieve Plex Logs.")

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(log_lines)

    @cherrypy.expose
    def generateAPI(self):
        apikey = hashlib.sha224(str(random.getrandbits(256))).hexdigest()[0:32]
        logger.info("New API generated")
        return apikey

    @cherrypy.expose
    def settings(self):
        interface_dir = os.path.join(plexcs.PROG_DIR, 'data/interfaces/')
        interface_list = [name for name in os.listdir(interface_dir) if
                          os.path.isdir(os.path.join(interface_dir, name))]

        # Initialise blank passwords so we do not expose them in the html forms
        # but users are still able to clear them
        if plexcs.CONFIG.HTTP_PASSWORD != '':
            http_password = '    '
        else:
            http_password = ''

        config = {
            "http_host": plexcs.CONFIG.HTTP_HOST,
            "http_username": plexcs.CONFIG.HTTP_USERNAME,
            "http_port": plexcs.CONFIG.HTTP_PORT,
            "http_password": http_password,
            "launch_browser": checked(plexcs.CONFIG.LAUNCH_BROWSER),
            "enable_https": checked(plexcs.CONFIG.ENABLE_HTTPS),
            "https_cert": plexcs.CONFIG.HTTPS_CERT,
            "https_key": plexcs.CONFIG.HTTPS_KEY,
            "api_enabled": checked(plexcs.CONFIG.API_ENABLED),
            "api_key": plexcs.CONFIG.API_KEY,
            "update_db_interval": plexcs.CONFIG.UPDATE_DB_INTERVAL,
            "freeze_db": checked(plexcs.CONFIG.FREEZE_DB),
            "log_dir": plexcs.CONFIG.LOG_DIR,
            "cache_dir": plexcs.CONFIG.CACHE_DIR,
            "check_github": checked(plexcs.CONFIG.CHECK_GITHUB),
            "interface_list": interface_list,
            "cache_sizemb": plexcs.CONFIG.CACHE_SIZEMB,
            "pms_identifier": plexcs.CONFIG.PMS_IDENTIFIER,
            "pms_ip": plexcs.CONFIG.PMS_IP,
            "pms_logs_folder": plexcs.CONFIG.PMS_LOGS_FOLDER,
            "pms_port": plexcs.CONFIG.PMS_PORT,
            "pms_token": plexcs.CONFIG.PMS_TOKEN,
            "pms_ssl": checked(plexcs.CONFIG.PMS_SSL),
            "pms_use_bif": checked(plexcs.CONFIG.PMS_USE_BIF),
            "pms_uuid": plexcs.CONFIG.PMS_UUID,
            "date_format": plexcs.CONFIG.DATE_FORMAT,
            "time_format": plexcs.CONFIG.TIME_FORMAT,
            "grouping_global_history": checked(plexcs.CONFIG.GROUPING_GLOBAL_HISTORY),
            "grouping_user_history": checked(plexcs.CONFIG.GROUPING_USER_HISTORY),
            "grouping_charts": checked(plexcs.CONFIG.GROUPING_CHARTS),
            "movie_notify_enable": checked(plexcs.CONFIG.MOVIE_NOTIFY_ENABLE),
            "tv_notify_enable": checked(plexcs.CONFIG.TV_NOTIFY_ENABLE),
            "music_notify_enable": checked(plexcs.CONFIG.MUSIC_NOTIFY_ENABLE),
            "tv_notify_on_start": checked(plexcs.CONFIG.TV_NOTIFY_ON_START),
            "movie_notify_on_start": checked(plexcs.CONFIG.MOVIE_NOTIFY_ON_START),
            "music_notify_on_start": checked(plexcs.CONFIG.MUSIC_NOTIFY_ON_START),
            "tv_notify_on_stop": checked(plexcs.CONFIG.TV_NOTIFY_ON_STOP),
            "movie_notify_on_stop": checked(plexcs.CONFIG.MOVIE_NOTIFY_ON_STOP),
            "music_notify_on_stop": checked(plexcs.CONFIG.MUSIC_NOTIFY_ON_STOP),
            "tv_notify_on_pause": checked(plexcs.CONFIG.TV_NOTIFY_ON_PAUSE),
            "movie_notify_on_pause": checked(plexcs.CONFIG.MOVIE_NOTIFY_ON_PAUSE),
            "music_notify_on_pause": checked(plexcs.CONFIG.MUSIC_NOTIFY_ON_PAUSE),
            "monitor_remote_access": checked(plexcs.CONFIG.MONITOR_REMOTE_ACCESS),
            "monitoring_interval": plexcs.CONFIG.MONITORING_INTERVAL,
            "monitoring_use_websocket": checked(plexcs.CONFIG.MONITORING_USE_WEBSOCKET),
            "refresh_users_interval": plexcs.CONFIG.REFRESH_USERS_INTERVAL,
            "refresh_users_on_startup": checked(plexcs.CONFIG.REFRESH_USERS_ON_STARTUP),
            "ip_logging_enable": checked(plexcs.CONFIG.IP_LOGGING_ENABLE),
            "movie_logging_enable": checked(plexcs.CONFIG.MOVIE_LOGGING_ENABLE),
            "tv_logging_enable": checked(plexcs.CONFIG.TV_LOGGING_ENABLE),
            "music_logging_enable": checked(plexcs.CONFIG.MUSIC_LOGGING_ENABLE),
            "logging_ignore_interval": plexcs.CONFIG.LOGGING_IGNORE_INTERVAL,
            "pms_is_remote": checked(plexcs.CONFIG.PMS_IS_REMOTE),
            "notify_consecutive": checked(plexcs.CONFIG.NOTIFY_CONSECUTIVE),
            "notify_recently_added": checked(plexcs.CONFIG.NOTIFY_RECENTLY_ADDED),
            "notify_recently_added_grandparent": checked(plexcs.CONFIG.NOTIFY_RECENTLY_ADDED_GRANDPARENT),
            "notify_recently_added_delay": plexcs.CONFIG.NOTIFY_RECENTLY_ADDED_DELAY,
            "notify_watched_percent": plexcs.CONFIG.NOTIFY_WATCHED_PERCENT,
            "notify_on_start_subject_text": plexcs.CONFIG.NOTIFY_ON_START_SUBJECT_TEXT,
            "notify_on_start_body_text": plexcs.CONFIG.NOTIFY_ON_START_BODY_TEXT,
            "notify_on_stop_subject_text": plexcs.CONFIG.NOTIFY_ON_STOP_SUBJECT_TEXT,
            "notify_on_stop_body_text": plexcs.CONFIG.NOTIFY_ON_STOP_BODY_TEXT,
            "notify_on_pause_subject_text": plexcs.CONFIG.NOTIFY_ON_PAUSE_SUBJECT_TEXT,
            "notify_on_pause_body_text": plexcs.CONFIG.NOTIFY_ON_PAUSE_BODY_TEXT,
            "notify_on_resume_subject_text": plexcs.CONFIG.NOTIFY_ON_RESUME_SUBJECT_TEXT,
            "notify_on_resume_body_text": plexcs.CONFIG.NOTIFY_ON_RESUME_BODY_TEXT,
            "notify_on_buffer_subject_text": plexcs.CONFIG.NOTIFY_ON_BUFFER_SUBJECT_TEXT,
            "notify_on_buffer_body_text": plexcs.CONFIG.NOTIFY_ON_BUFFER_BODY_TEXT,
            "notify_on_watched_subject_text": plexcs.CONFIG.NOTIFY_ON_WATCHED_SUBJECT_TEXT,
            "notify_on_watched_body_text": plexcs.CONFIG.NOTIFY_ON_WATCHED_BODY_TEXT,
            "notify_on_created_subject_text": plexcs.CONFIG.NOTIFY_ON_CREATED_SUBJECT_TEXT,
            "notify_on_created_body_text": plexcs.CONFIG.NOTIFY_ON_CREATED_BODY_TEXT,
            "notify_on_extdown_subject_text": plexcs.CONFIG.NOTIFY_ON_EXTDOWN_SUBJECT_TEXT,
            "notify_on_extdown_body_text": plexcs.CONFIG.NOTIFY_ON_EXTDOWN_BODY_TEXT,
            "notify_on_intdown_subject_text": plexcs.CONFIG.NOTIFY_ON_INTDOWN_SUBJECT_TEXT,
            "notify_on_intdown_body_text": plexcs.CONFIG.NOTIFY_ON_INTDOWN_BODY_TEXT,
            "notify_on_extup_subject_text": plexcs.CONFIG.NOTIFY_ON_EXTUP_SUBJECT_TEXT,
            "notify_on_extup_body_text": plexcs.CONFIG.NOTIFY_ON_EXTUP_BODY_TEXT,
            "notify_on_intup_subject_text": plexcs.CONFIG.NOTIFY_ON_INTUP_SUBJECT_TEXT,
            "notify_on_intup_body_text": plexcs.CONFIG.NOTIFY_ON_INTUP_BODY_TEXT,
            "home_stats_length": plexcs.CONFIG.HOME_STATS_LENGTH,
            "home_stats_type": checked(plexcs.CONFIG.HOME_STATS_TYPE),
            "home_stats_count": plexcs.CONFIG.HOME_STATS_COUNT,
            "home_stats_cards": plexcs.CONFIG.HOME_STATS_CARDS,
            "home_library_cards": plexcs.CONFIG.HOME_LIBRARY_CARDS,
            "buffer_threshold": plexcs.CONFIG.BUFFER_THRESHOLD,
            "buffer_wait": plexcs.CONFIG.BUFFER_WAIT,
            "group_history_tables": checked(plexcs.CONFIG.GROUP_HISTORY_TABLES)
        }

        return serve_template(templatename="settings.html", title="Settings", config=config)

    @cherrypy.expose
    def configUpdate(self, **kwargs):
        # Handle the variable config options. Note - keys with False values aren't getting passed

        checked_configs = [
            "launch_browser", "enable_https", "api_enabled", "freeze_db", "check_github",
            "grouping_global_history", "grouping_user_history", "grouping_charts", "pms_use_bif", "pms_ssl",
            "movie_notify_enable", "tv_notify_enable", "music_notify_enable", "monitoring_use_websocket",
            "tv_notify_on_start", "movie_notify_on_start", "music_notify_on_start",
            "tv_notify_on_stop", "movie_notify_on_stop", "music_notify_on_stop",
            "tv_notify_on_pause", "movie_notify_on_pause", "music_notify_on_pause", "refresh_users_on_startup",
            "ip_logging_enable", "movie_logging_enable", "tv_logging_enable", "music_logging_enable",
            "pms_is_remote", "home_stats_type", "group_history_tables", "notify_consecutive",
            "notify_recently_added", "notify_recently_added_grandparent", "monitor_remote_access"
        ]
        for checked_config in checked_configs:
            if checked_config not in kwargs:
                # checked items should be zero or one. if they were not sent then the item was not checked
                kwargs[checked_config] = 0

        # If http password exists in config, do not overwrite when blank value received
        if 'http_password' in kwargs:
            if kwargs['http_password'] == '    ' and plexcs.CONFIG.HTTP_PASSWORD != '':
                kwargs['http_password'] = plexcs.CONFIG.HTTP_PASSWORD

        for plain_config, use_config in [(x[4:], x) for x in kwargs if x.startswith('use_')]:
            # the use prefix is fairly nice in the html, but does not match the actual config
            kwargs[plain_config] = kwargs[use_config]
            del kwargs[use_config]

        # Check if we should refresh our data
        refresh_users = False
        reschedule = False

        if 'monitoring_interval' in kwargs and 'refresh_users_interval' in kwargs:
            if (kwargs['monitoring_interval'] != str(plexcs.CONFIG.MONITORING_INTERVAL)) or \
                    (kwargs['refresh_users_interval'] != str(plexcs.CONFIG.REFRESH_USERS_INTERVAL)):
                reschedule = True

        if 'notify_recently_added' in kwargs and \
            (kwargs['notify_recently_added'] != plexcs.CONFIG.NOTIFY_RECENTLY_ADDED):
            reschedule = True

        if 'monitor_remote_access' in kwargs and \
            (kwargs['monitor_remote_access'] != plexcs.CONFIG.MONITOR_REMOTE_ACCESS):
            reschedule = True

        if 'pms_ip' in kwargs:
            if kwargs['pms_ip'] != plexcs.CONFIG.PMS_IP:
                refresh_users = True

        if 'home_stats_cards' in kwargs:
            if kwargs['home_stats_cards'] != 'watch_statistics':
                kwargs['home_stats_cards'] = ', '.join(kwargs['home_stats_cards'])

        if 'home_library_cards' in kwargs:
            if kwargs['home_library_cards'] != 'library_statistics':
                kwargs['home_library_cards'] = ', '.join(kwargs['home_library_cards'])

        plexcs.CONFIG.process_kwargs(kwargs)

        # Write the config
        plexcs.CONFIG.write()

        # Get new server URLs for SSL communications.
        plextv.get_real_pms_url()
        
        # Get new server friendly name
        pmsconnect.get_server_friendly_name()

        # Reconfigure scheduler if intervals changed
        if reschedule:
            plexcs.initialize_scheduler()

        # Refresh users table if our server IP changes.
        if refresh_users:
            threading.Thread(target=plextv.refresh_users).start()

        raise cherrypy.HTTPRedirect("settings")

    @cherrypy.expose
    def set_notification_config(self, **kwargs):

        for plain_config, use_config in [(x[4:], x) for x in kwargs if x.startswith('use_')]:
            # the use prefix is fairly nice in the html, but does not match the actual config
            kwargs[plain_config] = kwargs[use_config]
            del kwargs[use_config]

        plexcs.CONFIG.process_kwargs(kwargs)

        # Write the config
        plexcs.CONFIG.write()

        cherrypy.response.status = 200

    @cherrypy.expose
    def do_state_change(self, signal, title, timer):
        message = title
        quote = self.random_arnold_quotes()
        plexcs.SIGNAL = signal

        return serve_template(templatename="shutdown.html", title=title,
                              message=message, timer=timer, quote=quote)

    @cherrypy.expose
    def get_history(self, user=None, user_id=None, grouping=0, **kwargs):

        if grouping == 'false':
            grouping = 0
        else:
            grouping = plexcs.CONFIG.GROUP_HISTORY_TABLES

        watched_percent = plexcs.CONFIG.NOTIFY_WATCHED_PERCENT

        custom_where = []
        if user_id:
            custom_where.append(['session_history.user_id', user_id])
        elif user:
            custom_where.append(['session_history.user', user])
        if 'rating_key' in kwargs:
            rating_key = kwargs.get('rating_key', "")
            custom_where.append(['session_history.rating_key', rating_key])
        if 'parent_rating_key' in kwargs:
            rating_key = kwargs.get('parent_rating_key', "")
            custom_where.append(['session_history.parent_rating_key', rating_key])
        if 'grandparent_rating_key' in kwargs:
            rating_key = kwargs.get('grandparent_rating_key', "")
            custom_where.append(['session_history.grandparent_rating_key', rating_key])
        if 'start_date' in kwargs:
            start_date = kwargs.get('start_date', "")
            custom_where.append(['strftime("%Y-%m-%d", datetime(started, "unixepoch", "localtime"))', start_date])
        if 'reference_id' in kwargs:
            reference_id = kwargs.get('reference_id', "")
            custom_where.append(['session_history.reference_id', reference_id])
        if 'media_type' in kwargs:
            media_type = kwargs.get('media_type', "")
            if media_type != 'all':
               custom_where.append(['session_history.media_type', media_type])

        data_factory = datafactory.DataFactory()
        compare = data_factory.get_history(kwargs=kwargs, custom_where=custom_where, grouping=grouping, watched_percent=watched_percent)

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(compare)

    @cherrypy.expose
    def history_table_modal(self, start_date=None, **kwargs):

        return serve_template(templatename="history_table_modal.html", title="History Data", data=start_date)

    @cherrypy.expose
    def shutdown(self):
        return self.do_state_change('shutdown', 'Shutting Down', 15)

    @cherrypy.expose
    def restart(self):
        return self.do_state_change('restart', 'Restarting', 30)

    @cherrypy.expose
    def update(self):
        return self.do_state_change('update', 'Updating', 120)

    @cherrypy.expose
    def api(self, *args, **kwargs):
        from plexcs.api import Api

        a = Api()
        a.checkParams(*args, **kwargs)

        return a.fetchData()

    @cherrypy.expose
    def test_notifier(self, config_id=None, subject='Plex:CS', body='Test notification', **kwargs):
        cherrypy.response.headers['Cache-Control'] = "max-age=0,no-cache,no-store"

        if config_id.isdigit():
            agents = notifiers.available_notification_agents()
            for agent in agents:
                if int(config_id) == agent['id']:
                    this_agent = agent
                    break
                else:
                    this_agent = None
            
            if this_agent:
                logger.debug("Sending test %s notification." % this_agent['name'])
                notifiers.send_notification(this_agent['id'], subject, body)
                return "Notification sent."
            else:
                logger.debug("Unable to send test notification, invalid notification agent ID %s." % config_id)
                return "Invalid notification agent ID %s." % config_id
        else:
            logger.debug("Unable to send test notification, no notification agent ID received.")
            return "No notification agent ID received."
            
    @cherrypy.expose
    def twitterStep1(self):
        cherrypy.response.headers['Cache-Control'] = "max-age=0,no-cache,no-store"
        tweet = notifiers.TwitterNotifier()
        return tweet._get_authorization()

    @cherrypy.expose
    def twitterStep2(self, key):
        cherrypy.response.headers['Cache-Control'] = "max-age=0,no-cache,no-store"
        tweet = notifiers.TwitterNotifier()
        result = tweet._get_credentials(key)
        logger.info(u"result: " + str(result))
        if result:
            return "Key verification successful"
        else:
            return "Unable to verify key"

    @cherrypy.expose
    def osxnotifyregister(self, app):
        cherrypy.response.headers['Cache-Control'] = "max-age=0,no-cache,no-store"
        from osxnotify import registerapp as osxnotify

        result, msg = osxnotify.registerapp(app)
        if result:
            osx_notify = notifiers.OSX_NOTIFY()
            osx_notify.notify('Registered', result, 'Success :-)')
            logger.info('Registered %s, to re-register a different app, delete this app first' % result)
        else:
            logger.warn(msg)
        return msg

    @cherrypy.expose
    def get_pms_token(self):

        token = plextv.PlexTV()
        result = token.get_token()

        if result:
            return result
        else:
            logger.warn('Unable to retrieve Plex.tv token.')
            return False

    @cherrypy.expose
    def get_pms_sessions_json(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_sessions('json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')
            return False

    @cherrypy.expose
    def get_current_activity(self, **kwargs):

        try:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_current_activity()

            data_factory = datafactory.DataFactory()
            for session in result['sessions']:
                if not session['ip_address']:
                    ip_address = data_factory.get_session_ip(session['session_key'])
                    session['ip_address'] = ip_address

        except:
            return serve_template(templatename="current_activity.html", data=None)

        if result:
            return serve_template(templatename="current_activity.html", data=result)
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="current_activity.html", data=None)

    @cherrypy.expose
    def get_current_activity_header(self, **kwargs):

        try:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_current_activity()
        except IOError as e:
            return serve_template(templatename="current_activity_header.html", data=None)

        if result:
            return serve_template(templatename="current_activity_header.html", data=result['stream_count'])
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="current_activity_header.html", data=None)

    @cherrypy.expose
    def get_recently_added(self, count='0', **kwargs):

        try:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_recently_added_details(count)
        except IOError as e:
            return serve_template(templatename="recently_added.html", data=None)

        if result:
            return serve_template(templatename="recently_added.html", data=result['recently_added'])
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="recently_added.html", data=None)

    @cherrypy.expose
    def pms_image_proxy(self, img='', width='0', height='0', fallback=None, **kwargs):
        try:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_image(img, width, height)
            cherrypy.response.headers['Content-type'] = result[1]
            return result[0]
        except:
            logger.warn('Image proxy queried but errors occured.')
            if fallback == 'poster':
                logger.info('Trying fallback image...')
                try:
                    fallback_image = open(self.interface_dir + common.DEFAULT_POSTER_THUMB, 'rb')
                    cherrypy.response.headers['Content-type'] = 'image/png'
                    return fallback_image
                except IOError as e:
                    logger.error('Unable to read fallback image. %s' % e)
            elif fallback == 'cover':
                logger.info('Trying fallback image...')
                try:
                    fallback_image = open(self.interface_dir + common.DEFAULT_COVER_THUMB, 'rb')
                    cherrypy.response.headers['Content-type'] = 'image/png'
                    return fallback_image
                except IOError as e:
                    logger.error('Unable to read fallback image. %s' % e)

            return None

    @cherrypy.expose
    def info(self, item_id=None, source=None, **kwargs):
        metadata = None
        query = None

        config = {
            "pms_identifier": plexcs.CONFIG.PMS_IDENTIFIER
        }

        if source == 'compare':
            data_factory = datafactory.DataFactory()
            metadata = data_factory.get_metadata_details(row_id=item_id)
        elif item_id == 'movie':
            metadata = {'media_type': 'library', 'library': 'movie', 'media_type_filter': 'movie', 'title': 'Movies'}
        elif item_id == 'show':
            metadata = {'media_type': 'library', 'library': 'show', 'media_type_filter': 'episode', 'title': 'TV Shows'}
        elif item_id == 'artist':
            metadata = {'media_type': 'library', 'library': 'artist', 'media_type_filter': 'track', 'title': 'Music'}
        else:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_metadata_details(rating_key=item_id)
            if result:
                metadata = result['metadata']
            else:
                data_factory = datafactory.DataFactory()
                query = data_factory.get_search_query(rating_key=item_id)

        if metadata:
            return serve_template(templatename="info.html", data=metadata, title="Info", config=config)
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="info.html", data=None, query=query, title="Info")

    @cherrypy.expose
    def get_user_recently_watched(self, user=None, user_id=None, limit='10', **kwargs):

        data_factory = datafactory.DataFactory()
        result = data_factory.get_recently_watched(user_id=user_id, user=user, limit=limit)

        if result:
            return serve_template(templatename="user_recently_watched.html", data=result,
                                  title="Recently Watched")
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="user_recently_watched.html", data=None,
                                  title="Recently Watched")

    @cherrypy.expose
    def get_user_watch_time_stats(self, user=None, user_id=None, **kwargs):

        user_data = users.Users()
        result = user_data.get_user_watch_time_stats(user_id=user_id, user=user)

        if result:
            return serve_template(templatename="user_watch_time_stats.html", data=result, title="Watch Stats")
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="user_watch_time_stats.html", data=None, title="Watch Stats")

    @cherrypy.expose
    def get_user_player_stats(self, user=None, user_id=None, **kwargs):

        user_data = users.Users()
        result = user_data.get_user_player_stats(user_id=user_id, user=user)

        if result:
            return serve_template(templatename="user_player_stats.html", data=result,
                                  title="Player Stats")
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="user_player_stats.html", data=None, title="Player Stats")

    @cherrypy.expose
    def get_item_children(self, rating_key='', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_item_children(rating_key)

        if result:
            return serve_template(templatename="info_children_list.html", data=result, title="Children List")
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="info_children_list.html", data=None, title="Children List")

    @cherrypy.expose
    def get_metadata_json(self, rating_key='', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_metadata(rating_key, 'json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_metadata_xml(self, rating_key='', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_metadata(rating_key)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/xml'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_recently_added_json(self, count='0', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_recently_added(count, 'json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_episode_list_json(self, rating_key='', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_episode_list(rating_key, 'json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_user_ips(self, user_id=None, user=None, **kwargs):

        custom_where = []
        if user_id:
            custom_where = [['user_id', user_id]]
        elif user:
            custom_where = [['user', user]]

        user_data = users.Users()
        history = user_data.get_user_unique_ips(kwargs=kwargs,
                                                custom_where=custom_where)

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(history)

    @cherrypy.expose
    def set_graph_config(self, graph_type=None, graph_days=None, graph_tab=None):
        if graph_type:
            plexcs.CONFIG.__setattr__('GRAPH_TYPE', graph_type)
            plexcs.CONFIG.write()
        if graph_days:
            plexcs.CONFIG.__setattr__('GRAPH_DAYS', graph_days)
            plexcs.CONFIG.write()
        if graph_tab:
            plexcs.CONFIG.__setattr__('GRAPH_TAB', graph_tab)
            plexcs.CONFIG.write()

        return "Updated graphs config values."

    @cherrypy.expose
    def get_plays_by_date(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_per_day(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_dayofweek(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_per_dayofweek(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_hourofday(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_per_hourofday(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_per_month(self, y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_per_month(y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_top_10_platforms(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_by_top_10_platforms(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_top_10_users(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_by_top_10_users(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_stream_type(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_per_stream_type(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_source_resolution(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_by_source_resolution(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plays_by_stream_resolution(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_total_plays_by_stream_resolution(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_stream_type_by_top_10_users(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_stream_type_by_top_10_users(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_stream_type_by_top_10_platforms(self, time_range='30', y_axis='plays', **kwargs):

        graph = graphs.Graphs()
        result = graph.get_stream_type_by_top_10_platforms(time_range=time_range, y_axis=y_axis)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_friends_list(self, **kwargs):

        plex_tv = plextv.PlexTV()
        result = plex_tv.get_plextv_friends('json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_user_details(self, **kwargs):

        plex_tv = plextv.PlexTV()
        result = plex_tv.get_plextv_user_details('json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_server_list(self, **kwargs):

        plex_tv = plextv.PlexTV()
        result = plex_tv.get_plextv_server_list('json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_sync_lists(self, machine_id='', **kwargs):

        plex_tv = plextv.PlexTV()
        result = plex_tv.get_plextv_sync_lists(machine_id=machine_id, output_format='json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_servers(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_server_list(output_format='json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_servers_info(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_servers_info()

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_server_friendly_name(self, **kwargs):

        result = pmsconnect.get_server_friendly_name()

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_server_prefs(self, pref=None, **kwargs):

        if pref:
            pms_connect = pmsconnect.PmsConnect()
            result = pms_connect.get_server_pref(pref=pref)
        else:
            result = None

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_server_children(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_server_children()

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_activity(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_current_activity()

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_full_users_list(self, **kwargs):

        plex_tv = plextv.PlexTV()
        result = plex_tv.get_full_users_list()

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def refresh_users_list(self, **kwargs):
        threading.Thread(target=plextv.refresh_users).start()
        logger.info('Manual user list refresh requested.')

    @cherrypy.expose
    def get_sync(self, machine_id=None, user_id=None, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        server_id = pms_connect.get_server_identity()

        plex_tv = plextv.PlexTV()
        if not machine_id:
            result = plex_tv.get_synced_items(machine_id=server_id['machine_identifier'], user_id=user_id)
        else:
            result = plex_tv.get_synced_items(machine_id=machine_id, user_id=user_id)

        if result:
            output = {"data": result}
        else:
            logger.warn('Unable to retrieve sync data for user.')
            output = {"data": []}

        cherrypy.response.headers['Content-type'] = 'application/json'
        return json.dumps(output)

    @cherrypy.expose
    def get_sync_item(self, sync_id, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_sync_item(sync_id, output_format='json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_sync_transcode_queue(self, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_sync_transcode_queue(output_format='json')

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_server_pref(self, pref=None, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_server_pref(pref=pref)

        if result:
            return result
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_plexwatch_export_data(self, database_path=None, table_name=None, import_ignore_interval=0, **kwargs):
        from plexcs import plexwatch_import

        db_check_msg = plexwatch_import.validate_database(database=database_path,
                                                          table_name=table_name)
        if db_check_msg == 'success':
            threading.Thread(target=plexwatch_import.import_from_plexwatch,
                             kwargs={'database': database_path,
                                     'table_name': table_name,
                                     'import_ignore_interval': import_ignore_interval}).start()
            return 'Import has started. Check the Plex:CS logs to monitor any problems.'
        else:
            return db_check_msg

    @cherrypy.expose
    def plexwatch_import(self, **kwargs):
        return serve_template(templatename="plexwatch_import.html", title="Import PlexWatch Database")

    @cherrypy.expose
    def get_server_id(self, hostname=None, port=None, identifier=None, ssl=0, remote=0, **kwargs):
        from plexcs import http_handler

        if hostname and port:
            # Set PMS attributes to get the real PMS url
            plexcs.CONFIG.__setattr__('PMS_IP', hostname)
            plexcs.CONFIG.__setattr__('PMS_PORT', port)
            plexcs.CONFIG.__setattr__('PMS_IDENTIFIER', identifier)
            plexcs.CONFIG.__setattr__('PMS_SSL', ssl)
            plexcs.CONFIG.__setattr__('PMS_IS_REMOTE', remote)
            plexcs.CONFIG.write()
            
            plextv.get_real_pms_url()
            
            pms_connect = pmsconnect.PmsConnect()
            request = pms_connect.get_local_server_identity()
            
            if request:
                cherrypy.response.headers['Content-type'] = 'application/xml'
                return request
            else:
                logger.warn('Unable to retrieve data.')
                return None
        else:
            return None

    @cherrypy.expose
    def random_arnold_quotes(self, **kwargs):
        from random import randint
        quote_list = ['To crush your enemies, see them driven before you, and to hear the lamentation of their women!',
                      'Your clothes, give them to me, now!',
                      'Do it!',
                      'If it bleeds, we can kill it',
                      'See you at the party Richter!',
                      'Let off some steam, Bennett',
                      'I\'ll be back',
                      'Get to the chopper!',
                      'Hasta La Vista, Baby!',
                      'It\'s not a tumor!',
                      'Dillon, you son of a bitch!',
                      'Benny!! Screw you!!',
                      'Stop whining! You kids are soft. You lack discipline.',
                      'Nice night for a walk.',
                      'Stick around!',
                      'I need your clothes, your boots and your motorcycle.',
                      'No, it\'s not a tumor. It\'s not a tumor!',
                      'I LIED!',
                      'See you at the party, Richter!',
                      'Are you Sarah Conner?',
                      'I\'m a cop you idiot!',
                      'Come with me if you want to live.',
                      'Who is your daddy and what does he do?'
                      ]

        random_number = randint(0, len(quote_list) - 1)
        return quote_list[int(random_number)]

    @cherrypy.expose
    def get_notification_agent_config(self, config_id, **kwargs):
        if config_id.isdigit():
            config = notifiers.get_notification_agent_config(config_id=config_id)
            agents = notifiers.available_notification_agents()
            for agent in agents:
                if int(config_id) == agent['id']:
                    this_agent = agent
                    break
                else:
                    this_agent = None
        else:
            return None

        checkboxes = {'email_tls': checked(plexcs.CONFIG.EMAIL_TLS)}

        return serve_template(templatename="notification_config.html", title="Notification Configuration",
                              agent=this_agent, data=config, checkboxes=checkboxes)

    @cherrypy.expose
    def get_notification_agent_triggers(self, config_id, **kwargs):
        if config_id.isdigit():
            agents = notifiers.available_notification_agents()
            for agent in agents:
                if int(config_id) == agent['id']:
                    this_agent = agent
                    break
                else:
                    this_agent = None
        else:
            return None

        return serve_template(templatename="notification_triggers_modal.html", title="Notification Triggers",
                              data=this_agent)

    @cherrypy.expose
    def delete_history_rows(self, row_id, **kwargs):
        data_factory = datafactory.DataFactory()

        if row_id:
            delete_row = data_factory.delete_session_history_rows(row_id=row_id)

            if delete_row:
                cherrypy.response.headers['Content-type'] = 'application/json'
                return json.dumps({'message': delete_row})
        else:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': 'no data received'})

    @cherrypy.expose
    def delete_all_user_history(self, user_id, **kwargs):
        data_factory = datafactory.DataFactory()

        if user_id:
            delete_row = data_factory.delete_all_user_history(user_id=user_id)

            if delete_row:
                cherrypy.response.headers['Content-type'] = 'application/json'
                return json.dumps({'message': delete_row})
        else:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': 'no data received'})

    @cherrypy.expose
    def delete_user(self, user_id, **kwargs):
        data_factory = datafactory.DataFactory()

        if user_id:
            delete_row = data_factory.delete_user(user_id=user_id)

            if delete_row:
                cherrypy.response.headers['Content-type'] = 'application/json'
                return json.dumps({'message': delete_row})
        else:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': 'no data received'})

    @cherrypy.expose
    def undelete_user(self, user_id=None, username=None, **kwargs):
        data_factory = datafactory.DataFactory()

        if user_id:
            delete_row = data_factory.undelete_user(user_id=user_id)

            if delete_row:
                cherrypy.response.headers['Content-type'] = 'application/json'
                return json.dumps({'message': delete_row})
        elif username:
            delete_row = data_factory.undelete_user(username=username)

            if delete_row:
                cherrypy.response.headers['Content-type'] = 'application/json'
                return json.dumps({'message': delete_row})
        else:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': 'no data received'})

    @cherrypy.expose
    def search(self, query=''):

        return serve_template(templatename="search.html", title="Search", query=query)

    @cherrypy.expose
    def search_results(self, query, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_search_results(query)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_search_results_children(self, query, media_type=None, season_index=None, **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_search_results(query)

        if media_type:
            result['results_list'] = {media_type: result['results_list'][media_type]}
        if media_type == 'season' and season_index:
            for season in result['results_list']['season']:
                if season['index'] == season_index:
                    result['results_list']['season'] = [season]
                    break

        if result:
            return serve_template(templatename="info_search_results_list.html", data=result, title="Search Result List")
        else:
            logger.warn('Unable to retrieve data.')
            return serve_template(templatename="info_search_results_list.html", data=None, title="Search Result List")

    @cherrypy.expose
    def update_history_rating_key(self, old_rating_key, new_rating_key, media_type, **kwargs):
        data_factory = datafactory.DataFactory()
        pms_connect = pmsconnect.PmsConnect()

        old_key_list = data_factory.get_rating_keys_list(rating_key=old_rating_key, media_type=media_type)
        new_key_list = pms_connect.get_rating_keys_list(rating_key=new_rating_key, media_type=media_type)

        update_db = data_factory.update_rating_key(old_key_list=old_key_list,
                                                   new_key_list=new_key_list,
                                                   media_type=media_type)

        if update_db:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': update_db})
        else:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps({'message': 'no data received'})

    # test code
    @cherrypy.expose
    def get_new_rating_keys(self, rating_key='', media_type='', **kwargs):

        pms_connect = pmsconnect.PmsConnect()
        result = pms_connect.get_rating_keys_list(rating_key=rating_key, media_type=media_type)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_old_rating_keys(self, rating_key='', media_type='', **kwargs):

        data_factory = datafactory.DataFactory()
        result = data_factory.get_rating_keys_list(rating_key=rating_key, media_type=media_type)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def get_map_rating_keys(self, old_rating_key, new_rating_key, media_type, **kwargs):

        data_factory = datafactory.DataFactory()
        pms_connect = pmsconnect.PmsConnect()

        if new_rating_key:
            old_key_list = data_factory.get_rating_keys_list(rating_key=old_rating_key, media_type=media_type)
            new_key_list = pms_connect.get_rating_keys_list(rating_key=new_rating_key, media_type=media_type)

            result = data_factory.update_rating_key(old_key_list=old_key_list,
                                                    new_key_list=new_key_list,
                                                    media_type=media_type)

        if result:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return json.dumps(result)
        else:
            logger.warn('Unable to retrieve data.')

    @cherrypy.expose
    def discover(self, token=''):
        """
        Returns the servers that you own as a
        list of dicts (formatted for selectize)
        """
        # Need to set token so result dont return http 401
        plexcs.CONFIG.__setattr__('PMS_TOKEN', token)
        plexcs.CONFIG.write()

        result = plextv.PlexTV()
        servers = result.discover()
        if servers:
            cherrypy.response.headers['Content-type'] = 'application/json'
            return servers
