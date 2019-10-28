#!/usr/bin/env python3

from datetime import datetime, timezone
import itertools
import os

import PyRSS2Gen

from trending_db import TrendingDB
from ghtrends import ROOT_URL

def main():
    tdb = TrendingDB()

    langs = tdb.get_langs()
    periods = tdb.get_periods()

    for lang_t, period_t in itertools.product(langs, periods):
        lang = lang_t[0]
        period = period_t[0]
        hlang = lang_t[1]
        hperiod = period_t[1]

        out_path = 'feeds/{}'.format(period)
        out_file = '{}/{}.xml'.format(out_path, lang)

        feed = dict()
        feed['title'] = 'GitHub Trending: {}, {}'.format(hlang, hperiod)
        feed['link'] = '{}/{}?since={}'.format(ROOT_URL, lang, period)
        feed['description'] = ('The top repositories on GitHub for {}, measured {}'
                .format(lang, period))
        feed['ttl'] = 1400 #1 day is 1440 minutes; shave some off as margin of error

        feed['pubDate'] = datetime.now(timezone.utc)
        #This is probably wrong
        feed['lastBuildDate'] = feed['pubDate']

        composite = tdb.get_composite_trends(lang, period)
        feed['items'] = list(map(row_to_rss_item, composite))

        rss = PyRSS2Gen.RSS2(**feed)

        os.makedirs(out_path, exist_ok=True)
        rss.write_xml(open(out_file, 'w'), 'utf-8')

def row_to_rss_item(row):
    #lang_name, period_name, rank, date,
    #repo_name, description, readme_html, last_seen, first_seen
    item = dict()

    # Use \x23 instead of '#' if .format trips on it
    item['title'] = ('{0.repo_name} #{0.rank} in {0.lang_name}, {0.period_name}'
            .format(row))
    item['link'] = 'https://github.com/{}'.format(row.repo_name)
    item['author'] = row.repo_name.split('/')[0]
    #TODO gid?
    #TODO categories? Language(s)? (that'd only be relevant for 'all'...)

    #Sqlite stores dates as YYYY-MM-DD
    #wrong alt: item['pubDate'] = date(*map(int, row.date.split('-')))
    item['pubDate'] = datetime.strptime(row.date, '%Y-%m-%d')

    row_descr = row.description or '[No description found.]'

    descr = '<p><i>{}</i></p> <p>Last seen <b>{}</b>; First seen <b>{}</b></p>'.format(
            row_descr, row.last_seen, row.first_seen)

    descr += row.readme_html or '<p>No README was found for this project.</p>'
    item['description'] = descr

    return PyRSS2Gen.RSSItem(**item)


if __name__ == '__main__':
    main()
