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
 
import asyncio
import re
from collections import namedtuple
from lxml import html
import cssselect
import aiohttp

import random
import pprint
import operator
import itertools
import copy

from trending_db import TrendingDB
from repo_data import RepoGatherer

ROOT_URL = 'https://github.com/trending'
#TODO This regex is a mess;
#might be suited to just switching to string-split techinques instead...
MACHINE_RE = re.compile(r'(?:https:\/\/github\.com)?(?:\/trending)?\/([^\/]*)\?.*')
#the group captures the machine name between the '/' and '?'
#e.g. 'https://github.com/trending/python?since=daily' -> 'python'
#Assumes the root page will always give us a ?since param in urls

Language = namedtuple('Language', ['machine_name', 'name'])
ALL_LANG = Language('', 'All Languages')

async def main():
    tdb = TrendingDB()
    async with aiohttp.ClientSession() as session:
        #tree = await get_disk_tree()
        tree = await get_page_tree(ROOT_URL, session)
        loop = asyncio.get_event_loop()
        langs, periods = await loop.run_in_executor(None, get_langs_and_periods, tree)

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

        #for now, cut off at 10 jobs
        #jobs = jobs[:10]

        #pprint.pprint(list(map(operator.attrgetter('url'), jobs)))
        #await asyncio.gather(*map(operator.methodcaller('fetch', session), jobs))

        task_list = [job.fetch(session) for job in jobs]
        trend_count = 0
        all_repos = set()
        for fut in asyncio.as_completed(task_list):
            job = await fut
            tdb.insert_trends_from_job(job)
            trend_count += len(job.repos)
            all_repos.update(job.repos)

        print('Done fetching!')

    print('Found {} trending entries.'.format(trend_count))
    print('Found {} unique repos. Gathering...'.format(len(all_repos)))
    pprint.pprint(all_repos)

    key = tdb.get_key()
    gat = RepoGatherer(key)
    await gat.get_many_repos(all_repos, tdb)
    #summaries = await gat.get_many_repos(all_repos, tdb)

    #name_changes = dict(filter(None, map(operator.attrgetter('name_change'), summaries)))
    #for job in jobs:
    #    job.repos = map(lambda r: name_changes.get(r) or r, job.repos)
    #    tdb.insert_trends_from_job(job)

    print('Complete!')


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

    async def fetch(self, session):
        """Fetch the contents at url, populating the repos list.
        Returns self-- read from self.repos after calling this.
        repos will become a list of repo names in ranked order, e.g. [0] is first
        Note that more obscure languages may not have any trending items!"""
        #Heavily modified from https://github.com/ryotarai/github_trends_rss/blob/master/lambda/functions/worker/main.py
        if self.repos is not None: #avoid redundant requests
            return self

        self.repos = []

        if session.closed:
            print('HTTP session was closed before able to fetch '
                    '{0.lang_name}/{0.period_name}!', self)
            return self

        if self.lang_machine_name != ALL_LANG[0]:
            #Random delay to avoid choking on too many requests...
            delay = random.randint(1, 100)
            await asyncio.sleep(delay)

        try:
            tree = await get_page_tree(self.url, session)
            #tree = await get_disk_tree(self.url)
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

                self.repos.append(repo_name)
        except aiohttp.ClientPayloadError as e:
            print('Something went wrong fetching repos for '
                    '{0.lang_name}/{0.period_name}: {1}', self, str(e))

        print('Found {0} repos for {1.lang_name}/{1.period_name}'
                .format(len(self.repos), self))
        return self


def get_langs_and_periods(tree):
    """Parse a document tree created by html.fromstring
    into a set of Language tuples and a list of Period dicts"""
    #Modifed from https://github.com/ryotarai/github_trends_rss/blob/master/lambda/functions/crawl/main.py
    lang_list = tree.cssselect("div#languages-menuitems a")
    period_list = tree.cssselect("details#select-menu-date a")

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

async def get_page_tree(url, session):
    """Returns a document tree parsed from url"""
    print('Fetching {} ...'.format(url))
    async with session.get(url) as resp:
        page = await resp.text()
    loop = asyncio.get_event_loop()
    tree = await loop.run_in_executor(None, html.fromstring, page)
    print('Fetched {}'.format(url))
    return tree

async def get_disk_tree(fake_url=ROOT_URL):
    """Returns a document tree parsed from trending.html
    (for development testing w/o constantly requesting from GH servers)"""
    print('Fetching {} ...'.format(fake_url))
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _disktree)

tree = None
def _disktree():
    global tree
    if tree is None:
        with open('trending.html', 'r') as f:
            page = f.read()
        tree = html.fromstring(page)

    return tree


if __name__ == '__main__':
    import traceback
    from concurrent.futures import ThreadPoolExecutor

    exe = ThreadPoolExecutor(4)
    loop = asyncio.get_event_loop()
    loop.set_default_executor(exe)
    try:
        loop.run_until_complete(main())
        exe.shutdown(wait=True)
    except Exception:
        print("top-level error")
        traceback.print_exc()
        exe.shutdown(wait=False)
    finally:
        loop.close()
