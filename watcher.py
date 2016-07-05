#!/usr/bin/env python3
# Plounge comment and submission gathering bot

import time
import sqlite3
import praw
import logging
import re

# This causes praw to print out all requests. Useful for debugging.
# logging.basicConfig(level=logging.DEBUG)

class PloungeDB:
  def __init__(self, filename):
    self.filename = filename

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

  def __exit__(self, type, value, tb):
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
    return data

  def insert_submission(self, s):
    # basically the same as for the comments
    query = """INSERT OR IGNORE INTO submissions (
        id, title, author, selftext, url, udate, permalink
      ) VALUES ( ?, ?, ?, ?, ?, ?, ? )"""
    created = time.strftime("%Y-%m-%d %X", time.gmtime(c.created_utc))
    author = s.author.name if c.author != None else "[deleted]"
    data = (s.fullname, s.title, author, s.selftext, s.url, created, s.permalink)
    self.db.execute(query, data)
    return data

  def commit(self):
    self.db.commit()

with PloungeDB('plounge.db') as db:
  sub = praw.Reddit('mlplounge.science data collector') \
            .get_subreddit('mlplounge')
  last_comment = None
  last_submission = None
  while True:
    # the 'before' argument means that we only want to get comments which are
    # newer than the given id (which is the last one from the previous request)
    comments = sub.get_comments(limit=24, params={'before' : last_comment})
    # Praw by default returns lists from newest to oldest. We want the other
    # direction to be able to update last_comment
    for c in reversed(list(comments)):
      (cid, cpid, author, body, created, permalink) = db.insert_comment(c)
      print("Got comment %s by %s at %s" % (cid, author, created))
      last_comment = cid
    submissions = sub.get_new(limit=12, params={'before' : last_submission})
    for s in reversed(list(submissions)):
      (sid, title, author, text, url, created, link) = db.insert_submission(s)
      print("Got submission %s by %s" % (sid, author))
      last_submission = sid
    db.commit()
    print("Commited database")
    # Reddit doesn't want you to request the same page more than once every 30
    # secons. I technically don't request the same page (because 'before' is
    # different) but it is probably a good idea anyway
    time.sleep(31)
