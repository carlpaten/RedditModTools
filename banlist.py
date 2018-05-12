# sscbanlist

# Find all the bans made, then for each ban, try to find the post responsible
# Can take a date (YYYY-MM-DD) as a command line argument, in which case it will
# retrieve all bans after that date. If no argument is given, it will retrieve all
# bans it can.
#
# Originally authored by /u/marinuso


import datetime
import praw
import prawcore.exceptions as ex
import sys

### configuration ###

SUBREDDIT='slatestarcodex'

# scan comments this much time before a ban (in seconds)
COMMENT_TIME_WINDOW=3*24*60*60

# if two bans for the same user are issued shortly after each other,
# ignore the first ban (in seconds)
TIME_BETWEEN_BANS=12*60*60

# site name to use to read connection info from praw.ini
SITE_NAME='ssc'

# ignore bans whose description contains one of these
IGNORE=['stupid bot', 'bad bot', 'useless bot', 'spam']

# the format to output the bans in
#  Fields:
#   * {user} - the name of the banned user
#   * {date} - the date of the ban
#   * {duration} - the duration of the ban
#   * {description} - ban description (empty if not given)
#   * {comment} - Reddit link to user comment (empty if not found)
#   * {sample} - First non-quoted line of the user comment that has three
#                     or more words. This tends to help explain the ban. (empty if not found)
FORMAT='{date} | /u/{user} | {duration} | {comment} {sample}'

#####################

def main():
    timestamp = 0

    # take a date on the command line
    if len(sys.argv) == 2:
        timestamp = datetime.datetime.strptime(sys.argv[1],"%Y-%m-%d").timestamp()

    sb = SSCBanList()
    bans = sb.getBans(minTimestamp = timestamp)

    for ban in bans: print(ban.format(FORMAT))

class SSCBanList(object):
    """List all the bans of users in the subreddit, and for each ban,
    try to find the post that caused it (the post that had a mod response
    nearest to the ban)."""

    def __init__( self,
                   # defaults
                   subreddit=SUBREDDIT,
                   site_name=SITE_NAME,
                   # more arguments will be passed to praw.Reddit
                   **kwargs):
        """Connect to Reddit. subreddit may be changed, site_name may be
        emptied if you don't want to use praw.ini. Other arguments will
        be passed on to praw.Reddit."""


        # if someone manages to pass no subreddit, error
        if not subreddit: raise Exception("no subreddit")
        # only use the site name if it is set
        if site_name: kwargs['site_name'] = site_name

        self.reddit = praw.Reddit(user_agent="sscbanlist by /u/marinuso", **kwargs)
        self.reddit.user.me() # fail early if not logged in
        self.sub = self.reddit.subreddit(subreddit)

        self.user_comment_objs = {}
        self.user_comment_cache = {}

    def getBans(self, minTimestamp=0, window=COMMENT_TIME_WINDOW,
                  minDiff=TIME_BETWEEN_BANS, ignore=IGNORE):
        """Get all bans after a given timestamp."""
        banned_user_ts = {}
        bans = self.sub.mod.log(action='banuser', limit=None)
        r = []
        for ban in bans: # the bans are provided latest-first by the API
            # stop after minimum time reached
            if minTimestamp>ban.created_utc: break

            # disregard deleted users
            if ban.target_author == '[deleted]': continue

            # skip bans involving ignored reasons
            if any(x in (ban.description or []) for x in ignore): continue

            if ban.target_author in banned_user_ts \
            and banned_user_ts[ban.target_author]-ban.created_utc < minDiff:
                continue # disregard duplicate ban
            else:
                banned_user_ts[ban.target_author] = ban.created_utc

            sys.stderr.write("processing ban @%d: %s\n"%(ban.created_utc, ban.target_author))
            r.append(Ban(self, ban, window))
        return r

    def getUserComments(self, user):
        """Retrieve an user's comments (from cache if possible).
        Keep a list so it can be iterated over multiple times."""
        if not user in self.user_comment_cache:
            self.user_comment_cache[user] = []
            self.user_comment_objs[user] = user.comments.new(limit=None)

        idx = 0
        cache = self.user_comment_cache[user]
        obj = self.user_comment_objs[user]

        # next() will raise StopIteration and that's what breaks the loop
        while True:
            if idx >= len(cache):
                cache.append(next(obj))
            yield cache[idx]
            idx += 1

class Ban(object):
    """Represents a ban."""

    def __init__(self, sscbl, bandata, window):
        """Given a ModAction representing a ban, find the rest of the data."""
        self.sscbl = sscbl
        self.window = window

        # ban details
        self.duration = bandata.details
        self.description = bandata.description or ""
        self.timestamp = bandata.created_utc

        # banned user
        self.user = self.sscbl.reddit.redditor(bandata.target_author)

        # find the moderator comment
        try: (self.comment, self.mod_comment) = self.__findcomment()
        except (ex.NotFound, ex.Forbidden): # user may be deleted or suspended
            self.comment = None

    def format(self, fmt, datefmt="%Y-%m-%d", linktitle='Comment'):
        """Return formatted output for the ban.

        Fields:
         * {user} - the name of the banned user
         * {date} - the date of the ban
         * {duration} - the duration of the ban
         * {description} - ban description (empty if not given)
         * {comment} - Reddit link to moderator comment (empty if not found)
         * {sample} - First non-quoted line of the user comment that has three
                      or more words. This tends to help explain the ban. (empty if not found)

        The date will be formatted using the given format (using strftime).
        """

        if not self.comment: commentlink = sample = ''
        else:
            # comment link
            commentlink = '[{lt}](https://www.reddit.com/{link}?context=1)'.format(
                             lt=linktitle, link=self.comment.permalink)
            # try to extract a sample from the comment
            sample = ([
                line for line in self.comment.body.split("\n")
                     if line.strip()
                     and line.strip()[0]!='>'
                     and len(line.split())>=3] + [''])[0]

        return fmt.format(
                 user = self.user.name,
                 date = datetime.datetime.fromtimestamp(self.timestamp).strftime(datefmt),
                 duration = self.duration,
                 description = self.description,
                 comment = commentlink,
                 sample = sample)



    def __findcomment(self):
        """Find the offending comment."""

        # get the user's comments
        comments = self.sscbl.getUserComments(self.user)

        # the comments appear latest-first
        for comment in comments:
            # ignore comments created after ban
            if comment.created_utc > self.timestamp: continue
            # ignore comments outside the time window
            if comment.created_utc < self.timestamp-self.window: break
            # ignore comments not in the right subreddit
            if comment.subreddit != self.sscbl.sub: continue

            # check replies for distinguished moderator comment
            try:
                if len(comment.replies) == 0:
                    comment.refresh() # this sometimes fails, if that's the case don't give up
            except praw.exceptions.ClientException:
                continue

            replies = list(comment.replies)
            for reply in replies:
                if isinstance(reply, praw.models.MoreComments):
                    replies.append(reply.comments())
                    continue

                if reply.distinguished == 'moderator':
                    # found it
                    return (comment, reply)

        # didn't find it
        return (None, None)



if __name__=='__main__': main()
