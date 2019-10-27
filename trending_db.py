#!/usr/bin/env python3

import sqlite3

DB_PATH = 'GHTrends.db'

class TrendingDB:
    def __init__(self, db_path=DB_PATH):
        self.path = db_path

    def create_new_db(self):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()

            c.execute('''CREATE TABLE Languages(
                    lang_machine_name TEXT PRIMARY KEY, lang_name TEXT NOT NULL)''')
            c.execute('''CREATE TABLE Periods(
                    period_machine_name TEXT PRIMARY KEY, period_name TEXT NOT NULL)''')
            c.execute('''CREATE TABLE Repos(
                    repo_name TEXT PRIMARY KEY,
                    description TEXT,
                    readme_html TEXT,
                    last_seen TEXT NOT NULL DEFAULT CURRENT_DATE,
                    first_seen TEXT NOT NULL DEFAULT CURRENT_DATE)''')
            c.execute('''CREATE TABLE Trends(
                    lang_machine_name TEXT NOT NULL,
                    period_machine_name TEXT NOT NULL,
                    repo_name TEXT NOT NULL,
                    rank INTEGER NOT NULL,
                    date TEXT NOT NULL DEFAULT CURRENT_DATE,
                    PRIMARY KEY(lang_machine_name, period_machine_name, repo_name, rank))''')
            c.execute('''CREATE TABLE GHKey(
                    id INTEGER PRIMARY KEY, key TEXT NOT NULL)''')
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
            rp[0]
            ), fetchjob.repos)
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.executemany('INSERT OR IGNORE INTO Trends'
                    '(lang_machine_name, period_machine_name, repo_name, rank) '
                    'VALUES (?, ?, ?, ?)', trends)
            db.commit()

    def upsert_repo_summary(self, repo_summary):
        with sqlite3.connect(self.path) as db:
            c = db.cursor()
            c.execute('INSERT INTO Repos'
                    '(repo_name, description, readme_html) '
                    'VALUES (?, ?, ?) '
                    'ON CONFLICT(repo_name) DO UPDATE SET '
                    'description=excluded.description, '
                    'readme_html=excluded.readme_html, '
                    'last_seen=CURRENT_DATE', repo_summary)
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

if __name__ == '__main__':
    main()
