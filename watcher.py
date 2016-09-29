#!/usr/bin/python3 -u
# Plounge comment and submission gathering bot

import time
import sqlite3
import re

import praw
from praw.errors import APIException, HTTPException

# This causes praw to print out all requests. Useful for debugging.
# import logging
# logging.basicConfig(level=logging.DEBUG)

class PloungeDB:
  def __init__(self, filename):
    self.filename = filename
    self.db = None

  def __enter__(self):
    self.db = sqlite3.connect(self.filename)
    self.db.execute("""CREATE TABLE IF NOT EXISTS submissions (
      id TEXT NOT NULL PRIMARY KEY UNIQUE,
      author TEXT,
      title TEXT,
      selftext TEXT,
      url TEXT,
      udate DATE NOT NULL,
      permalink TEXT
    )""")
    self.db.execute("""CREATE TABLE IF NOT EXISTS comments (
      id TEXT NOT NULL PRIMARY KEY UNIQUE,
      parent_id TEXT,
      author TEXT,
      body TEXT,
      udate DATE NOT NULL,
      permalink TEXT
    )""")
    return self

  def __exit__(self, t, value, tb):
    self.db.close()

  def insert_comment(self, c):
    # the OR IGNORE may be removed in the future, if I can be reasonably
    # certain, that reddit won't give me duplicates
    query = """INSERT OR IGNORE INTO comments (
        id, parent_id, author, body, udate, permalink
      ) VALUES ( ?, ?, ?, ?, ?, ? )"""
    created = time.strftime("%Y-%m-%d %X", time.gmtime(c.created_utc))
    author = c.author.name if c.author != None else "[deleted]"
    # for some reason, the comment listing does not contain the permalink, even
    # though it is really simple to derive frome what we have
    permalink = ''.join(["https://www.reddit.com/r/MLPLounge/comments/",
                         c.link_id[3:],
                         "/",
                         re.sub('[^a-zA-Z0-9]', '_', c.link_title).lower(),
                         "/",
                         c.id])
    data = (c.fullname, c.parent_id, author, c.body, created, permalink)
    self.db.execute(query, data)
    return c.fullname

  def insert_submission(self, s):
    # basically the same as for the comments
    query = """INSERT OR IGNORE INTO submissions (
        id, title, author, selftext, url, udate, permalink
      ) VALUES ( ?, ?, ?, ?, ?, ?, ? )"""
    created = time.strftime("%Y-%m-%d %X", time.gmtime(s.created_utc))
    author = s.author.name if s.author != None else "[deleted]"
    data = (s.fullname, s.title, author, s.selftext, s.url, created, s.permalink)
    self.db.execute(query, data)
    return s.fullname

  def commit(self):
    self.db.commit()

def main():
  with PloungeDB('data/plounge.db') as db:
    print("Starting plounge comment gatherer")
    sub = praw.Reddit('mlplounge.science data collector') \
              .get_subreddit('mlplounge')
    # this variable limits the number of comments/submissions that get
    # retrieved during an iteration. 0 means that the default limit
    # for one page is used. None means that the maximum possible
    # number of results is returned.
    limit = None
    # these variables keep track of the last comment/submission that
    # we have seen. They are useful to be able to catch up if we
    # missed a comment.
    last_comment = last_submission = None
    while True:
      try:

        # the placeholder argument makes praw fetch content until the
        # element with the given id (with the type designator (tx_)
        # removed) has been reached. The difference to my 'before'
        # solution is that in case of an invalid id, the maximum
        # number of items is returned instead of an empty list
        comments = sub.get_comments(limit=limit,
                                    place_holder=last_comment)
        # if this isn't here, we might run into a ValueError due to
        # undefined variables. I would prefer it, if python set i to
        # None automatically upon executing the loop header but I
        # didn't make the rules.
        i = None
        for i, c in enumerate(comments):
          cid = db.insert_comment(c)
          if i == 0:
            # the newest comment is always the first in the iterator
            last_comment = cid[3:]
        if i is None:
          # the iterator didn't return any comments (it should always
          # return at least up until (including) place_holder)
          # Panic and reset last_comment in a hope to fix this
          print("get_comments returned an empty list. PANIC!")
          last_comment = None
        else:
          print("Inserted %d Comments" % (i))

        submissions = sub.get_new(limit=limit,
                                  place_holder=last_submission)
        i = None
        for i, s in enumerate(submissions):
          sid = db.insert_submission(s)
          if i == 0:
            last_submission = sid[3:]
        if i is None:
          # the iterator didn't return any comments (it should always
          # return at least up until (including) place_holder)
          # Panic and reset last_comment in a hope to fix this
          print("get_new returned an empty list. PANIC!")
          last_submission = None
        else:
          print("Inserted %d Submissions" % (i))

        # save the state of the database
        db.commit()

        # Reddit doesn't want you to request the same page more than
        # once every 30 secons. I technically don't request the same
        # page but it is probably a good idea anyway
        time.sleep(118)
        # theoretically, supplying the place_holder to get_content is
        # enough to prevent an absurd number of API requests. However,
        # if the last_comment or last_submission was deleted, it won't
        # be returned and we would request until we read limit things.
        # Since there are unlikely to be more than 100 comments
        # (probably even less than 25 but better safe than sorry) per
        # update, I've set limit to 100 because that is the most we
        # can get with a single request
        limit = 100
      except (APIException, HTTPException):
        print("Got an (probably temporary) exception from praw.")
        print("Delaying for 30 seconds")
        # We don't know how many comments we have potentially lost.
        # Get the maximum number just to be sure
        limit = None
        time.sleep(30)

if __name__ == '__main__':
  main()
