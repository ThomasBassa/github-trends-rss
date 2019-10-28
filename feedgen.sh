#!/bin/bash

set -e

cd ~/ghtrends
source ./bin/activate
python3 ./ghtrends.py &>fetch.log
python3 ./make_feeds.py &>feedgen.log

cp -rf feeds/ ~/trends_site/

cd ~/trends_site
git add feeds/
git commit -m ":pager: Auto feed update @ $(date -Idate)"
git push origin gh-pages
