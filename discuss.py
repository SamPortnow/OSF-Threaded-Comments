__author__ = 'samportnow'

from flask import Flask, request, url_for, render_template, redirect, session
from flask.ext.pymongo import PyMongo
import datetime
from bson.objectid import ObjectId
import markdown2
from werkzeug.contrib.cache import SimpleCache

app = Flask(__name__)
mongo = PyMongo(app)

cache = SimpleCache()
cached_comments = None
#
app.jinja_env.filters['markdownify'] = markdown2.markdown

@app.route('/clear/')
def clear():
    mongo.db.comments.remove()
    cache.clear()
    return redirect(url_for('home'))

@app.route('/', methods=['GET', 'POST'])
def home():
    #cached_comments is going to be global, so we can update it
    #as needed when users vote, without querying the database
    global cached_comments
    #if there's a post, we add the comment
    if request.method == 'POST':
        add_comment()
    #in order to render the comments, we first get a cursor that
    #is the all of the comments without parent. these are
    #our first level comments
    cursor = mongo.db.comments.find({'parent': None})
    #once we have this cursor, we look up all the comments
    if cache.get('comments') is None:
        comments = get_all_comments(cursor=cursor)
        cache.set('comments', comments, timeout=500000)
        cached_comments = cache.get('comments')
    return render_template('commenting.html', comments=cached_comments)


def add_comment():
    """ Add a comment or reply. """

    # Validate parent ID, if there is one
    parent_id = request.form.get('parent', None)
    if parent_id:
        parent_id = ObjectId(parent_id)
        if not mongo.db.comments.find({'_id': parent_id}).count():
            raise Exception('Parent ID doesn\'t exist.')
    # Validate indent, the indent is where you get the
    # 'threading'. if there's no indent val, this
    # defaults to 0
    #we want to know when the comments were posted
    posted = datetime.datetime.utcnow()
    #we want to know the text
    text = request.form['comment']
    if not text.strip():
        return
    if parent_id:
        mongo.db.comments.update(
            {'_id':parent_id},
            {'$set':{'last':False}})
        cursor = mongo.db.comments.find_one({
            'parent': parent_id,
        })
    new_id = mongo.db.comments.insert({
        'posted': posted,
        'text': text,
        'parent': parent_id,
        'children': [],
        'votes': 1
    })
    #if this is a reply, we update that 'document'
    #to include a ref to its a child (the reply)
    if parent_id:
        mongo.db.comments.update(
            {'_id': parent_id},
            {'$push': {'children': {
                'ref_id': str(new_id),
            }}})

    # Refresh home page
    cache.clear()
    return redirect(url_for('home'))


def get_all_comments(cursor):
    """
     we recursively go through the db. we go
     through all of the first level comments,
     but if they have children, hit those directly
     after so we get the children before we get the
     rest of the first level comments.
     each time we add to our list of comments

    """

    comments = list(cursor)
    for comment_idx in range(len(comments)):
        comment = comments[comment_idx]
        child_refs = comment['children']
        children = []
        for child_idx in range(len(child_refs)):
            children += get_all_comments(
                mongo.db.comments.find({
                    '_id' : ObjectId(child_refs[child_idx]['ref_id']),
                })
            )
        comment['children'] = children
    return comments

@app.route('/vote/', methods=['GET','POST'])
def vote():
    val = request.form.get("val", None)
    id = request.form.get("id", None)
    votes = mongo.db.comments.find_one({'_id':ObjectId(id)})['votes']
    votes += int(val)
    mongo.db.comments.update(
        {'_id':ObjectId(id)},
        {'$set':{'votes':votes}})
    #update the comment to store the vote
    update_comment(cached_comments, ObjectId(id), 'votes', int(val))
    return ''

def update_comment(comment_cache, _id, key, value):
    #queue is a copy of our comment cache
    queue = comment_cache[:]

    while queue:
        #comments is the current index of the queue
        #(we removed as we iterate)
        comments = queue.pop(0)
        #if we get the correct id, we ad the value to it
        if comments['_id'] == _id:
            comments[key] += value
            return
        #if we have children we add it to the end of the queue
        if comments['children']:
            queue.extend(comments['children'])


if __name__ == '__main__':
    app.run(debug=True)
