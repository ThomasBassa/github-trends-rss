# Github Trends RSS Generator

This project has been abandoned; I've stopped maintaining it for a while.
I ran this project on a Raspberry Pi, which frequently ran out of memory running this.
I'd correct that and other flaws, except there are already
multiple other projects that accomplish the same goals.

See https://github.com/mshibanami/GitHubTrendingRSS and https://mshibanami.github.io/GitHubTrendingRSS/
for an active implementation of this project. (It even predates mine!)

## Motivation

GitHub sadly lacks an API for getting trending repositories,
and I wanted to be able to track them easily.
This had previously been done by https://github.com/ryotarai/github_trends_rss
but that had several flaws:

* No updates to the source since late 2016
    * GitHub has long since updated the format of the Trending pages (CSS selectors outdated)
* Very little information in the RSS feed, amounting to name and ranking only
* Dependency on AWS services

This repo solves these issues:

* Updated for 2019!
* Uses the GitHub API to fetch additional repo information (e.g. READMEs)
* Runs entirely locally using Python and SQLite

More on the design to come...

## Licence

GPLv3 or later
