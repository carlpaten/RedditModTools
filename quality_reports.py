import collections
import praw
import re

reddit = praw.Reddit(
    user_agent="reports-tool",
    site_name="ssc"
)

mod_queue = list(reddit.subreddit('slatestarcodex').mod.reports(limit=None))

for comment in mod_queue:
    comment.all_reports = collections.defaultdict(lambda: 0)
    for (reason, count) in comment.user_reports:
        comment.all_reports[reason] += count
    for (mod, reason) in comment.mod_reports:
        comment.all_reports[reason] += 1
    comment.quality_reports = comment.all_reports["Actually a quality contribution"]
    comment.non_quality_reports = sum(comment.all_reports.values()) - comment.quality_reports

q1 = filter(lambda comment: comment.quality_reports > 0 and comment.non_quality_reports == 0, mod_queue)
q2 = sorted(q1, key=lambda comment: comment.non_quality_reports)
sorted_mod_queue = sorted(q2, key=lambda comment: comment.quality_reports, reverse=True)


# Formatting


def first_n_words(s, n):
    return " ".join(s.split(" ")[:n])


def first_non_quote_line(s):
    try:
        return next(x for x in s.splitlines() if len(x) > 0 and x[0] != ">")
    except Exception as e:
        print("Comment is all shit? " + str(e))
        return s


# huge hack
def sanitize(s):
    without_links = re.sub(r"\[([^\[]*)\]\(http.*\)", r"\1", s)
    without_opening_brackets = re.sub(r"\[", r"\[", without_links)
    return without_opening_brackets


def make_blurb(comment):
    body_blurb = sanitize(first_n_words(first_non_quote_line(comment.body), 20))
    return '/u/{0}: ["{1}..."](https://www.reddit.com{2}?context=3&sort=best)'.format(
        comment.author,
        body_blurb,
        comment.permalink
    )


summary = "".join([make_blurb(comment) + "\n\n" for comment in sorted_mod_queue])

with open("quality_reports.txt", 'a') as out:
    out.write(summary)

for comment in sorted_mod_queue:
    if comment.non_quality_reports == 0:
        print(comment.mod.approve())
    else:
        print(comment.non_quality_reports)