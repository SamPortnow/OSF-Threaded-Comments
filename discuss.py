__author__ = 'samportnow'

from flask import Flask, request, session, url_for, render_template, redirect
from flask.ext.pymongo import PyMongo
import datetime
import pymongo
from bson.objectid import ObjectId

app = Flask(__name__)
mongo = PyMongo(app)

@app.route('/', methods=['GET','POST'])
def home():
    if request.method == 'POST':
        add_comment()
    cursor = mongo.db.comments.find({'parent': None})
    comments = get_all_comments(cursor=cursor)
    return render_template('commenting.html', comments=comments)

def add_comment():
    """ Add a comment or reply. """

    # Validate parent ID
    parent_id = request.form.get('parent', None)
    if parent_id:
        parent_id = ObjectId(parent_id)
        if not mongo.db.comments.find({'_id' : parent_id}).count():
            raise Exception('Parent ID doesn\'t exist.')

    # Validate indent
    indent = request.form.get('indent', 0)
    if indent:
        try:
            indent = int(indent)
        except ValueError:
            raise Exception('Indent must be int-convertible.')

    posted = datetime.datetime.utcnow()
    text = request.form['comment']
    new_id = mongo.db.comments.insert({
        'posted':posted,
        'text': text,
        'parent' : parent_id,
        'indentation' : indent,
        'children' : [],
    })

    if parent_id:
        mongo.db.comments.update(
            {'_id' : parent_id},
            {'$push': {'children': {
                'ref_id' : str(new_id),
                }}})

    # Refresh home page
    return redirect(url_for('home'))

def get_all_comments(cursor=None):
    comments = []
    for comment in cursor:
        comments.append(comment)
        for child in comment['children']:
            comments += get_all_comments(
                mongo.db.comments.find({'_id':ObjectId(child['ref_id'])})
            )
    return comments

if __name__ == '__main__':
    app.run(debug=True)