#!/usr/bin/env python3

import http.cookiejar
import os
import sys
import time
from datetime import datetime
import urllib.request, urllib.parse, urllib.error
from bs4 import BeautifulSoup
import json

"""
Save this config file in $HOME/.adp-downloader-config.json with the right
credentials.

{
    "username": "XXXXX",
    "password": "XXXXX",
    "request_limit": 100,
    "debug": false
}

"""

# defaults
ALREADY_DOWNLOADED_MAX = 10
REQUEST_LIMIT = 200
HOME = os.getenv('HOME')

class PayCheckFetcher:
    paycheck_url = 'https://my.adp.com/static/redbox/1.19.0.119/#/pay'
    cj = None
    time_between_requests = 1
    last_request_time = 0
    only_year = None
    request_limit = REQUEST_LIMIT
    already_downloaded_max = ALREADY_DOWNLOADED_MAX

    def __init__(self, config):
        already_downloaded_max = ALREADY_DOWNLOADED_MAX
        self.request_limit = config.get("request_limit", REQUEST_LIMIT)
        username = config.get("username", "")
        password = config.get("password", "")
        self.only_year = config.get("only_year", str(datetime.now().year))

        # why is this so verbose
        pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pm.add_password(None, 'http://agateway.adp.com', username, password)
        # need cookies so auth works properly
        self.cj = http.cookiejar.LWPCookieJar()
        o = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(pm), urllib.request.HTTPCookieProcessor(self.cj))
        urllib.request.install_opener(o)

        # make an intial request. we need to do this
        # as it updates our session cookie appropriately, so that
        # child frames know that this is the parent (they apparently
        # don't look at referrer)
        self.getResponse(url='https://ipay.adp.com/iPay/private/index.jsf')

    def getPayStubIndex(self):
        r = self.getResponse(url="https://my.adp.com/v1_0/O/A/payStatements?adjustments=no&numberoflastpaydates=%d" % (self.request_limit, ))
        j = json.loads(r.read())
        #print(json.dumps(j['payStatements'], indent=4, sort_keys=True))
        #print(json.dumps(j, indent=4, sort_keys=True))
        #print len(j['payStatements'])
        #for item in j['payStatements']:
        #    print item['payDate']
        return j['payStatements']

    def downloadPayStubs(self):
        paystubs = self.getPayStubIndex()
        paydates = {}
        already_downloaded = 0

        for paystub in paystubs:
            paydate = paystub['payDate']
            year = paydate.split('-')[0]
            if not os.path.isdir(year):
                os.mkdir(year)
            if not paydate.startswith(self.only_year):
                continue
            paystub_pdf = paystub['statementImageUri']['href'].replace('/l2', '')
            check_url = 'https://my.adp.com' + paystub_pdf
            save_as = '%s/%s.pdf' % (year, paydate)
            if paystub['payDate'] in paydates:
                save_as = "%s/%s-%d.pdf" % (year, paydate, paydates[paydate])
                paydates[paydate] = paydates[paydate] + 1
            else:
                paydates[paydate] = 0

            if not self.downloadFile(check_url, save_as):
                already_downloaded += 1
                if already_downloaded >= self.already_downloaded_max:
                    print(('Already downloaded the previous %d paystubs.' % (already_downloaded)))
                    break

            if already_downloaded >= self.already_downloaded_max:
                break
        print("Done")

    # given some data and a url, makes magical request for data using urllib2
    def getResponse(self, data=None, url=None):
        if (url == None):
            url = self.paycheck_url

        time_to_wait = self.time_between_requests - (time.time() - self.last_request_time)
        if (time_to_wait > 0):
            time.sleep(time_to_wait)

        # pretend to be chrome so the jsf renders as i expect
        #ua = 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_4; en-US) AppleWebKit/534.13 (KHTML, like Gecko) Chrome/9.0.597.19 Safari/534.13'
        ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/602.2.14 (KHTML, like Gecko) Version/10.0.1 Safari/602.2.14'
        headers = { 'User-Agent' : ua }
        req = urllib.request.Request(url, data, headers)
        response = urllib.request.urlopen(req)
        return response

    # calls getResponse and throws it into soup. use prettify to view
    # the contents because adp has super ugly markup
    def getSoupResponse(self, data=None):
        soup = BeautifulSoup(self.getResponse(data))
        return soup

    # downloads a file maybe. note that this will break if
    # adp adds a new check for the day you run this on. TODO: i should change
    # the filename to a key with the check number
    def downloadFile(self, url, filename):
        path = os.path.abspath(filename)
        if (os.path.exists(path)):
            # already downloaded this file, continue in our cron
            print('skipping (already downloaded): '+filename)
            return False

        print('downloading '+url+' to '+filename)
        fd = open(path, 'wb')
        response = self.getResponse(url = url)
        fd.write(response.read())
        fd.close()
        return True

def main(argv):
    with open('%s/.adp-downloader-config.json' % (HOME,), 'r') as f:
        config = json.load(f)

    print("Downloading paystubs for %s" % (config.get('username'),))

    fetcher = PayCheckFetcher(config)
    fetcher.downloadPayStubs()


if __name__ == "__main__":
    main(sys.argv[1:])

