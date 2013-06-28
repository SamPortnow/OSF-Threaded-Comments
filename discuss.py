__author__ = 'samportnow'

from flask import Flask, request, url_for, render_template, redirect
from flask.ext.pymongo import PyMongo
import datetime
from bson.objectid import ObjectId
import markdown2

app = Flask(__name__)
mongo = PyMongo(app)

# 
app.jinja_env.filters['markdownify'] = markdown2.markdown

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
    print comments
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

if __name__ == '__main__':
    app.run(debug=True)
