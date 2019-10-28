# Github Trends RSS Generator

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
