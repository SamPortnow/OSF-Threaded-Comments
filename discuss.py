__author__ = 'samportnow'

from flask import Flask, request, url_for, render_template, redirect
from flask.ext.pymongo import PyMongo
import datetime
from bson.objectid import ObjectId

app = Flask(__name__)
mongo = PyMongo(app)

@app.route('/clear/')
def clear():
    
    mongo.db.comments.remove()
    return redirect(url_for('home'))

@app.route('/', methods=['GET', 'POST'])
def home():
    #if there's a post, we add the comment
    if request.method == 'POST':
        add_comment()
    #in order to render the comments, we first get a cursor that
    #is the all of the comments without parent. these are
    #our first level comments
    cursor = mongo.db.comments.find({'parent': None})
    #once we have this cursor, we look up all the comments
    comments = get_all_comments(cursor=cursor)
    return render_template('commenting.html', comments=comments)


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
    indent = request.form.get('indent', 0)
    if indent:
        try:
            indent = int(indent)
        except ValueError:
            raise Exception('Indent must be int-convertible.')
    #we want to know when the comments were posted
    posted = datetime.datetime.utcnow()
    #we want to know the text
    text = request.form['comment']
    if parent_id:
        mongo.db.comments.update(
            {'_id':parent_id},
            {'$set':{'last':False}})
        cursor = mongo.db.comments.find_one({'parent': parent_id, 'indentation': indent})
    new_id = mongo.db.comments.insert({
        'posted': posted,
        'text': text,
        'parent': parent_id,
        'indentation': indent,
        'children': [],
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
    return redirect(url_for('home'))


def get_all_comments(cursor=None):
    """
     we recursively go through the db. we go
     through all of the first level comments,
     but if they have children, hit those directly
     after so we get the children before we get the
     rest of the first level comments.
     each time we add to our list of comments

    """
    comments = []
    for i in range(0, cursor.count()):
        comments.append(cursor[i])
        for child in cursor[i]['children']:
            comments.extend(get_all_comments(
                mongo.db.comments.find({
                    '_id' : ObjectId(child['ref_id'])
                })
            ))
    if comments:
        comments[0]['open'] = 1
        comments[-1]['close'] = comments[-1]['close'] + 1 \
            if 'close' in comments[-1] \
            else 1
    return comments


### if that indent level does not exist yet, then that one is the first
### also make that one the last by default, and as you add to that indent,
### update that id so its no longer the last, and make the current one the
### last


if __name__ == '__main__':
    app.run(debug=True)
