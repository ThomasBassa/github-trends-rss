#!/usr/bin/env python3

from collections import namedtuple
from github import Github
#next 2 used for the "hack"
import github
from github.Repository import Repository

import pprint

RepoSummary = namedtuple('RepoSummary',
        ['repo_name', 'description', 'readme_html'])

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
    def __init__(self, key):
        self.g = Github(key)

    def get_repo_data(self, repo_in):
        """Return a RepoSummary for the provided repo,
        which should be a repo name (not a full url)
        e.g. username/repository"""
        repo = self.g.get_repo(repo_in)

        name = repo.full_name
        descr = repo.description
        #proper api method-- "raw-ish" text
        #readme = repo.get_readme().decoded_content
        html_readme = repo.get_html_readme()
        return RepoSummary(name, descr, html_readme)


def main():
    import sys
    from trending_db import TrendingDB
    if len(sys.argv) < 2:
        print('provide a repo to test against as an arg')
        return

    repo = sys.argv[1]

    tdb = TrendingDB()
    key = tdb.get_key()
    print(RepoGatherer(key).get_repo_data(repo))


if __name__ == '__main__':
    main()
