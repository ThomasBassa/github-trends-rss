#!/usr/bin/env python3

import operator
import sqlite3

DB_PATH = 'GHTrends.db'

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

    def update_periods(self, periods):
        name_pairs = map(lambda p: (p['period_machine_name'], p['period_name']), periods)
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.executemany('INSERT OR REPLACE INTO Periods VALUES (?, ?)', name_pairs)
            db.commit()

    def insert_trends_from_job(self, fetchjob):
        trends = map(lambda rp: (
            fetchjob.lang_machine_name,
            fetchjob.period_machine_name,
            rp[1],
            rp[0] + 1
            ), enumerate(fetchjob.repos))
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
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
                #Update (old, new) --reverse the tuple for sql order
                c.execute('UPDATE Repos SET repo_name=? WHERE repo_name=?',
                        repo_summary.name_change[::-1])
                db.commit()

        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('SELECT count(*) FROM Repos WHERE repo_name=?',
                    (repo_summary.repo_name,))
            #if present (count != 0), update
            if int(c.fetchone()[0]): 
                c.execute('UPDATE Repos SET '
                        'description=?, readme_html=?, last_seen=CURRENT_DATE '
                        'WHERE repo_name=?',
                        (repo_summary.description, repo_summary.readme_html,
                            repo_summary.repo_name))
            else:
                #otherwise insert
                c.execute('INSERT INTO Repos(repo_name, description, readme_html) '
                        'VALUES (?, ?, ?) ', repo_summary[:3])
            db.commit()


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
        print('DB already exists')
        #from repo_data import RepoSummary
        #print('Adding test repo...')
        #summary = RepoSummary('test/test', 'This is a test', '<p>Seriously a test</p>')
        #tdb.upsert_repo_summary(summary)

if __name__ == '__main__':
    main()
