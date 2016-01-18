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

from plexcs import logger

import sqlite3
import os
import plexcs
import time
import threading

db_lock = threading.Lock()

def drop_session_db():
    monitor_db = MonitorDatabase()
    monitor_db.action('DROP TABLE sessions')

def clear_history_tables():
    logger.debug(u"Plex:CS Database :: Deleting all session_history records... No turning back now bub.")
    monitor_db = MonitorDatabase()
    monitor_db.action('DELETE FROM session_history')
    monitor_db.action('DELETE FROM session_history_media_info')
    monitor_db.action('DELETE FROM session_history_metadata')
    monitor_db.action('VACUUM;')

def db_filename(filename="plexcs.db"):

    return os.path.join(plexcs.DATA_DIR, filename)

def get_cache_size():
    # This will protect against typecasting problems produced by empty string and None settings
    if not plexcs.CONFIG.CACHE_SIZEMB:
        # sqlite will work with this (very slowly)
        return 0
    return int(plexcs.CONFIG.CACHE_SIZEMB)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]

    return d


class MonitorDatabase(object):

    def __init__(self, filename='plexcs.db'):
        self.filename = filename
        self.connection = sqlite3.connect(db_filename(filename), timeout=20)
        # Don't wait for the disk to finish writing
        self.connection.execute("PRAGMA synchronous = OFF")
        # Journal disabled since we never do rollbacks
        self.connection.execute("PRAGMA journal_mode = %s" % plexcs.CONFIG.JOURNAL_MODE)
        # 64mb of cache memory, probably need to make it user configurable
        self.connection.execute("PRAGMA cache_size=-%s" % (get_cache_size() * 1024))
        self.connection.row_factory = dict_factory

    def action(self, query, args=None, return_last_id=False):
        if query is None:
            return

        with db_lock:
            sql_result = None
            attempts = 0

            while attempts < 5:
                try:
                    with self.connection as c:
                        if args is None:
                            sql_result = c.execute(query)
                        else:
                            sql_result = c.execute(query, args)
                    # Our transaction was successful, leave the loop
                    break

                except sqlite3.OperationalError as e:
                    if "unable to open database file" in e.message or "database is locked" in e.message:
                        logger.warn('Database Error: %s', e)
                        attempts += 1
                        time.sleep(1)
                    else:
                        logger.error('Database error: %s', e)
                        raise

                except sqlite3.DatabaseError as e:
                    logger.error('Fatal Error executing %s :: %s', query, e)
                    raise

            return sql_result

    def select(self, query, args=None):

        sql_results = self.action(query, args).fetchall()

        if sql_results is None or sql_results == [None]:
            return []

        return sql_results

    def select_single(self, query, args=None):

        sql_results = self.action(query, args).fetchone()

        if sql_results is None or sql_results == "":
            return ""

        return sql_results

    def upsert(self, table_name, value_dict, key_dict):

        trans_type = 'update'
        changes_before = self.connection.total_changes

        gen_params = lambda my_dict: [x + " = ?" for x in my_dict.keys()]

        update_query = "UPDATE " + table_name + " SET " + ", ".join(gen_params(value_dict)) + \
                       " WHERE " + " AND ".join(gen_params(key_dict))

        self.action(update_query, value_dict.values() + key_dict.values())

        if self.connection.total_changes == changes_before:
            trans_type = 'insert'
            insert_query = (
                "INSERT INTO " + table_name + " (" + ", ".join(value_dict.keys() + key_dict.keys()) + ")" +
                " VALUES (" + ", ".join(["?"] * len(value_dict.keys() + key_dict.keys())) + ")"
            )
            try:
                self.action(insert_query, value_dict.values() + key_dict.values())
            except sqlite3.IntegrityError:
                logger.info('Queries failed: %s and %s', update_query, insert_query)

        # We want to know if it was an update or insert
        return trans_type
