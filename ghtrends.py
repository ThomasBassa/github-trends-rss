#!/usr/bin/env python3
 
import re
from collections import namedtuple
from lxml import html
import cssselect
import requests

import pprint
import operator
import itertools

from trending_db import TrendingDB
from repo_data import RepoGatherer

ROOT_URL = 'https://github.com/trending'
MACHINE_RE = re.compile(ROOT_URL + r'/(.*)\?.*')
#the group captures the machine name between the '/' and '?'
#e.g. 'https://github.com/trending/python?since=daily' -> 'python'
#Assumes the root page will always give us a ?since param in urls

Language = namedtuple('Language', ['machine_name', 'name'])
ALL_LANG = Language('all', 'All Languages')

def main():
    #tree = get_root_tree()
    tdb = TrendingDB()
    tree = get_disk_tree()
    langs, periods = get_langs_and_periods(tree)

    #languages = sorted(langs, key=operator.attrgetter('name'))
    #pprint.pprint(languages)
    #pprint.pprint(periods)

    tdb.update_langs(langs | frozenset((ALL_LANG,)))
    tdb.update_periods(periods)
    
    jobs = []
    #Use periods to construct jobs for the "all" lang
    for period in periods:
        job = FetchJob(ALL_LANG, period)
        #Don't use usual contruction of URL...
        job.url = period['all_url']
        jobs.append(job)

    #The rest of the jobs are formed from langs cross periods
    for lang, period in itertools.product(langs, periods):
        jobs.append(FetchJob(lang, period))

    #pprint.pprint(list(map(operator.attrgetter('url'), jobs)))
    all_repos = set()
    for job in jobs:
        job.fetch()
        tdb.insert_trends_from_job(job)
        all_repos.update(map(operator.itemgetter(1), job.repos))

    pprint.pprint(all_repos)


class FetchJob:
    def __init__(self, language, period):
        """Create a FetchJob.
        language is expected to be a Language tuple.
        period is expected to be a dict containing
        period_machine_name, period_name and period_suffix"""
        self.lang_machine_name, self.lang_name = language

        self.period_machine_name = period['period_machine_name']
        self.period_name = period['period_name']
        self.period_suffix = period['period_suffix']

        self.url = '{}/{}{}'.format(ROOT_URL,
            self.lang_machine_name, self.period_suffix)
        self.repos = None

    def __repr__(self):
        return 'FetchJob({}, {})'.format(
            repr(Language(self.lang_machine_name, self.lang_name)),
            repr({'period_machine_name': self.period_machine_name,
                  'period_name': self.period_name,
                  'period_suffix': self.period_suffix}))

    def fetch(self):
        """Fetch the contents at url, populating the repos list.
        Does not return a value-- read from self.repos after calling this.
        repos will become a list of tuples of (rank, repo name)
        Note that more obscure languages may not have any trending items!"""
        #Heavily modified from https://github.com/ryotarai/github_trends_rss/blob/master/lambda/functions/worker/main.py
        if self.repos is not None: #avoid redundant requests
            return

        self.repos = []
        rank = 1

        #tree = self._get_page()
        tree = get_disk_tree(self.url)
        articles = tree.cssselect("article.Box-row")
        for li in articles:
            a = li.cssselect("h1 a")[0]
            repo_name = a.get("href")[1:] #remove the leading /

            #We can get descr here, but let's use GH api instead
            #description = ""
            #ps = li.cssselect("p")
            #if len(ps) > 0:
            #    description = ps[0].text_content().strip()
            #repo['description'] = description

            self.repos.append((rank, repo_name))
            rank += 1

    def _get_page(self):
        print('Fetching {} ...'.format(self.url))
        page = requests.get(self.url)
        return html.fromstring(page.content)


def get_langs_and_periods(tree):
    """Parse a document tree created by html.fromstring
    into a set of Language tuples and a list of Period dicts"""
    #Modifed from https://github.com/ryotarai/github_trends_rss/blob/master/lambda/functions/crawl/main.py
    menu_lists = tree.cssselect("div.select-menu-list")
    lang_list = menu_lists[0].cssselect("a")
    period_list = menu_lists[1].cssselect("a")

    #The language list contains duplicates-- use a set to avoid that
    languages = set()
    for a in lang_list:
        url = a.get("href")
        machine_name = MACHINE_RE.match(url).group(1)
        name = a.cssselect("span.select-menu-item-text")[0].text.strip()
        languages.add(Language(machine_name, name))

    #I'd call them "ranges" except 'range' is a python function...
    periods = []
    for a in period_list:
        rooturl = a.get("href")
        suffix = '?' + rooturl.split("?")[-1]
        name = a.cssselect("span.select-menu-item-text")[0].text.strip()
        machine_name = suffix.split("=")[-1]
        periods.append({"all_url": rooturl, "period_suffix": suffix,
            "period_name": name, "period_machine_name": machine_name})

    return languages, periods

def get_root_tree():
    print('fetching...')
    page = requests.get(ROOT_URL)
    tree = html.fromstring(page.content)
    print('done')
    return tree

page = ''
def get_disk_tree(fake_url=ROOT_URL):
    """Returns a document tree parsed from trending.html
    (for development testing w/o constantly requesting from GH servers)"""
    global page
    print('Fetching {} ...'.format(fake_url))
    if not page:
        with open('trending.html', 'r') as f:
            page = f.read()
    tree = html.fromstring(page)

    return tree


if __name__ == '__main__':
    main()
