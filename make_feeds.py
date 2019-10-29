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
        print('Generating feed for {}, {}'.format(lang, period))

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
        if composite:
            feed['items'] = list(map(row_to_rss_item, composite))
        else:
            #TODO today's date as string
            feed['items'] = [PyRSS2Gen.RSSItem(
                title='No repos in {}, {} today'.format(hlang, hperiod),
                pubDate=datetime.utcnow()
            )]

        rss = PyRSS2Gen.RSS2(**feed)

        os.makedirs(out_path, exist_ok=True)
        rss.write_xml(open(out_file, 'w'), 'utf-8')
        print('Generated feed for {}, {}'.format(lang, period))
    print('Complete!')

def row_to_rss_item(row):
    #lang_name, period_name, rank, date,
    #repo_name, description, readme_html, last_seen, first_seen
    item = dict()

    # Use \x23 instead of '#' if .format trips on it
    item['title'] = ('{0.repo_name} #{0.rank} in {0.lang_name}, {0.period_name}'
            .format(row))
    item['link'] = 'https://github.com/{}'.format(row.repo_name)
    item['author'] = row.repo_name.split('/')[0]
    item['guid'] = PyRSS2Gen.Guid(item['link'], isPermaLink=False)

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
