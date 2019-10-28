#!/usr/bin/env python3

#Copyright (C) 2019 Thomas Bassa
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>.

from collections import namedtuple
import operator
import pprint
import sqlite3

DB_PATH = 'GHTrends.db'

CompositeTrend = namedtuple('CompositeTrend',
            ['lang_name', 'period_name', 'rank', 'date', 'repo_name',
            'description', 'readme_html', 'last_seen', 'first_seen'])

class TrendingDB:
    def __init__(self, db_path=DB_PATH):
        self.path = db_path

    def create_new_db(self):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.executescript('''\
CREATE TABLE Languages(
    lang_machine_name TEXT NOT NULL PRIMARY KEY, lang_name TEXT NOT NULL);
CREATE TABLE Periods(
    period_machine_name TEXT NOT NULL PRIMARY KEY, period_name TEXT NOT NULL);
CREATE TABLE Repos(
    repo_name TEXT NOT NULL PRIMARY KEY,
    description TEXT,
    readme_html TEXT,
    last_seen TEXT NOT NULL DEFAULT CURRENT_DATE,
    first_seen TEXT NOT NULL DEFAULT CURRENT_DATE);
CREATE TABLE Trends(
    lang_machine_name TEXT NOT NULL REFERENCES Languages(lang_machine_name) ON UPDATE CASCADE,
    period_machine_name TEXT NOT NULL REFERENCES Periods(period_machine_name) ON UPDATE CASCADE,
    repo_name TEXT NOT NULL REFERENCES Repos(repo_name) ON UPDATE CASCADE,
    rank INTEGER NOT NULL,
    date TEXT NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY(lang_machine_name, period_machine_name, rank));
CREATE TABLE GHKey(id INTEGER PRIMARY KEY, key TEXT NOT NULL);''')
            db.commit()

    #TODO do we need to do more to update langs & periods "properly"?
    def set_key(self, key):
        #Just hardcoding 0 as id since I only expect storing 1 value here...
        k = (0, key)
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('INSERT OR REPLACE INTO GHKey VALUES (?, ?)', k)
            db.commit()

    def get_key(self):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT key from GHKey WHERE id = 0')
            return str(c.fetchone()[0])

    def update_langs(self, langs):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.executemany('INSERT OR REPLACE INTO Languages VALUES (?, ?)', langs)
            db.commit()

    def get_langs(self):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT * FROM Languages')
            return c.fetchall()

    #TODO Should we also save the period suffix?
    def update_periods(self, periods):
        name_pairs = map(lambda p: (p['period_machine_name'], p['period_name']), periods)
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.executemany('INSERT OR REPLACE INTO Periods VALUES (?, ?)', name_pairs)
            db.commit()

    def get_periods(self):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT * FROM Periods')
            return c.fetchall()

    def insert_trends_from_job(self, fetchjob):
        trends = map(lambda rp: (
            fetchjob.lang_machine_name,
            fetchjob.period_machine_name,
            rp[1],
            rp[0] + 1
            ), enumerate(fetchjob.repos))
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('PRAGMA foreign_keys = ON')
            c.executemany('INSERT OR IGNORE INTO Repos '
                    '(repo_name) VALUES (?)', ((e,) for e in fetchjob.repos))
            c.executemany('INSERT OR REPLACE INTO Trends'
                    '(lang_machine_name, period_machine_name, repo_name, rank) '
                    'VALUES (?, ?, ?, ?)', trends)
            db.commit()

    def get_blanked_repos(self):
        #Might be temporary for the sake of testing repo_data...
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT repo_name FROM Repos '
                    'WHERE description IS NULL or readme_html IS NULL')
            return list(map(operator.itemgetter(0), c.fetchall()))

    def upsert_repo_summary(self, repo_summary):
        #we don't have 'INSERT ... ON CONFLICT DO UPDATE'
        #so we have to check whether to insert or update...
        if repo_summary.name_change:
            #TODO do we need 2 connects + commits? Doing this for "safety" reasons
            with sqlite3.connect(self.path) as db:
                c = db.cursor()
                c.execute('PRAGMA foreign_keys = ON')
                #Update (old, new) --reverse the tuple for sql order
                c.execute('UPDATE Repos SET repo_name=? WHERE repo_name=?',
                        repo_summary.name_change[::-1])
                db.commit()
            print('Updated repo name {}->{}'.format(*repo_summary.name_change))

        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('PRAGMA foreign_keys = ON')
            c.execute('SELECT count(*) FROM Repos WHERE repo_name=?',
                    (repo_summary.repo_name,))
            #if present (count != 0), update
            if int(c.fetchone()[0]): 
                c.execute('UPDATE Repos SET '
                        'description=?, readme_html=?, last_seen=CURRENT_DATE '
                        'WHERE repo_name=?',
                        (repo_summary.description, repo_summary.readme_html,
                            repo_summary.repo_name))
                print('Updated {}'.format(repo_summary.repo_name))
            else:
                #otherwise insert
                c.execute('INSERT INTO Repos(repo_name, description, readme_html) '
                        'VALUES (?, ?, ?) ', repo_summary[:3])
                print('Saved {}'.format(repo_summary.repo_name))
            db.commit()

    def get_composite_trends(self, lang, period):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT lang_name, period_name, rank, date, repo_name, '
                    'description, readme_html, last_seen, first_seen FROM '
                    'Trends NATURAL JOIN Repos NATURAL JOIN Languages '
                    'NATURAL JOIN Periods '
                    'WHERE lang_machine_name=? AND period_machine_name=?',
                    (lang, period))
            return list(map(CompositeTrend._make, c.fetchall()))


def main():
    import os
    tdb = TrendingDB()
    if not os.path.exists(tdb.path):
        tdb.create_new_db()
        ghkey = input('Input a GitHub API key: ')
        if ghkey:
            tdb.set_key(ghkey)
            print('Key saved.')
        else:
            print('No key provided...')
    else:
        print('DB already exists, listing all/daily')
        pprint.pprint(tdb.get_composite_trends('all', 'daily'))
        #from repo_data import RepoSummary
        #print('Adding test repo...')
        #summary = RepoSummary('test/test', 'This is a test', '<p>Seriously a test</p>')
        #tdb.upsert_repo_summary(summary)

if __name__ == '__main__':
    main()
