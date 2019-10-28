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
from collections import namedtuple
import traceback
from github import Github
from github.GithubException import UnknownObjectException, RateLimitExceededException
#next 2 used for the "hack"
import github
from github.Repository import Repository

import itertools
import pprint
import random

RepoSummary = namedtuple('RepoSummary',
        ['repo_name', 'description', 'readme_html', 'name_change'])

#via the python docs for itertools
def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)

#Hacks to manipulate request headers for get_readme
#This is modified from github/Repository.py's get_readme method
def get_html_readme(self, ref=github.GithubObject.NotSet):
    assert ref is github.GithubObject.NotSet or isinstance(ref, (str, six.text_type)), ref
    url_parameters = dict()
    if ref is not github.GithubObject.NotSet:
        url_parameters["ref"] = ref

    html_get_header = dict()
    html_get_header['Accept'] = 'application/vnd.github.v3.html'

    headers, data = self._requester.requestJsonAndCheck(
        "GET",
        self.url + "/readme",
        parameters=url_parameters,
        headers=html_get_header
    )
    return data['data'] #Just give us the good stuff

Repository.get_html_readme = get_html_readme

class RepoGatherer:
    _NO_README_HTML = '<p><i>This repo does not have a README.</i></p>'

    def __init__(self, key):
        self.g = Github(key)
        self.exceeded = False

    def get_rate_limit(self):
        return self.g.get_rate_limit().core

    async def get_many_repos(self, repos, db=None):
        """Get the data for many repos with proper rate limiting/delays.
        Immediately save them to an optional TrendingDB as encountered.
        Returns the list of results."""
        all_repos = list(repos)

        #Enforce rate limit; reduce job count if needed
        limits = self.get_rate_limit()
        print('Limits: {0.remaining}/{0.limit} reqests; reset {0.reset}'.format(limits))
        possible_repos = limits.remaining // 2; #possibly worse than 2...

        repo_count = len(all_repos)
        if repo_count > possible_repos:
            print('Warning: Need to fetch {} repos but rate limit is only good for {}'
                    .format(repo_count, possible_repos))
            all_repos = all_repos[:possible_repos]

        if not all_repos:
            print('Rate limit exceeded for now or nothing to do...')
            return []

        tasks = []
        #Split the repos into groups of 5
        #(5 is arbitrary-- approx. how many fetches at a time)
        batches = grouper(all_repos, 5)
        #delay eatch batch's items by an additional second
        for delay, batch in enumerate(batches):
            for repo in batch:
                if repo is not None: #grouper adds extra Nones...
                    tasks.append(self.get_repo_data(repo, delay))

        results = []
        for fut in asyncio.as_completed(tasks):
            summary = await fut
            if db:
                db.upsert_repo_summary(summary)
            results.append(summary)

        print('Got data for {} repos.'.format(len(results)))
        return results

    async def get_repo_data(self, repo_in, delay=0):
        """Async wrapper for _get_repo (returns RepoSummary),
        optionally delays by delay seconds"""
        if delay:
            #print('Delayed by {}s'.format(delay))
            await asyncio.sleep(delay)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_repo, repo_in)

    def _get_repo(self, repo_in):
        """Return a RepoSummary for the provided repo,
        which should be a repo name (not a full url)
        e.g. username/repository"""
        print('Gathering data for {}...'.format(repo_in))
        try:
            if self.exceeded:
                raise RuntimeError('Previously exceeded rate limit; stop!')
            repo = self.g.get_repo(repo_in)

            name_change = None
            name = repo.full_name
            if name != repo_in:
                name_change = (repo_in, name)
            descr = repo.description
            try:
                #proper api method-- "raw-ish" text
                #readme = repo.get_readme().decoded_content
                html_readme = repo.get_html_readme()
            except UnknownObjectException:
                html_readme = self._NO_README_HTML
        except RateLimitExceededException:
            self.exceeded = True
            raise RuntimeError('Rate limit exceeded!')

        print('Done gathering {}'.format(repo_in))
        return RepoSummary(name, descr, html_readme, name_change)


async def main():
    #import sys
    from trending_db import TrendingDB
    #if len(sys.argv) < 2:
    #    print('provide a repo to test against as an arg')
    #    return
    #repo = sys.argv[1]

    tdb = TrendingDB()
    key = tdb.get_key()
    #print(await RepoGatherer(key).get_repo_data(repo))

    all_repos = tdb.get_blanked_repos()
    if not all_repos:
        print('Nothing to do...')
        return

    #This whole bit is a short-circuit of ghtrends' last phase of main()
    gat = RepoGatherer(key)

    try:
        await gat.get_many_repos(all_repos, tdb)
        #summaries = await gat.get_many_repos(all_repos)
        #print('Got data for {} repos. Saving...'.format(len(summaries)))
        #for summary in summaries:
        #    tdb.upsert_repo_summary(summary)
        print('Complete!')
    except RuntimeError:
        print('RuntimeError in "main"')
        traceback.print_exc()


if __name__ == '__main__':
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
