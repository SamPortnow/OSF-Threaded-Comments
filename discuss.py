__author__ = 'samportnow'

from flask import Flask, request, session, url_for, render_template, redirect
from flask.ext.pymongo import PyMongo
import datetime
import bson
import pymongo
import re

app = Flask(__name__)
mongo = PyMongo(app)


@app.route('/', methods=['GET','POST'])
def home():
    if request.method == 'POST':
        if 'comment' in request.form:
            get_comment()
        elif 'reply' in request.form:
            get_reply()
    cursor = mongo.db.comments.find()
    comments = get_all_comments(cursor=cursor)
    return render_template('commenting.html', comments=comments)

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    text=text.strip()
    result = []
    for word in _punct_re.split(text.lower()):
        if word:
            result.append(word)
    return unicode(delim.join(result))


def get_comment():
    posted = datetime.datetime.utcnow()
    text = request.form['comment']
    slug = slugify(text)
    full_slug = posted.strftime('%Y.%m.%d.%H.%M.%S') + ':' + slug
    mongo.db.comments.insert({
        'slug':slug,
        'full_slug':full_slug,
        'posted':posted,
        'text': text,
    })
    return redirect(url_for('home'))

def get_reply():
    posted = datetime.datetime.utcnow()
    text = request.form['reply']
    slug_part = slugify(text)
    full_slug_part = posted.strftime('%Y.%m.%d.%H.%M.%S') + ':' + slug_part
    parent = request.form['parent']
    parent_slug = slugify(parent)
    full_slug = parent_slug + '/' + full_slug_part
    mongo.db.comments.update(
        {'slug':parent_slug},
        {'$push': {'children': {
            'slug':slug_part,
            'full_slug':full_slug,
    }}})
    mongo.db.comments.insert(
        {
            'slug':slug_part,
            'full_slug':full_slug,
            'posted':posted,
            'text': text,
            'parent': parent_slug
        }
    )
    return redirect(url_for('home'))

def get_all_comments(cursor=None, index=-1, comments=[]):
    visited = False
    for comment in cursor:
        for placed_comment in comments:
            if comment['full_slug'] == placed_comment['full_slug']:
                visited = True
        if not visited:
            mongo.db.comments.update(
                {'full_slug':comment['full_slug']},
                {
                '$set':{'indentation':index},
                }
            )
            comment['indentation'] = index
            comments.append(comment)
        if 'children' in comment:
            for child in comment['children']:
                index = comment['indentation'] + 1
                get_all_comments(mongo.db.comments.find({'full_slug':child['full_slug']}), index, comments=comments)
        index = -1
    return comments

if __name__ == '__main__':
    app.run(debug=True)