from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_bootstrap import Bootstrap
from flask_gravatar import Gravatar
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from functools import wraps
import flask_login
import smtplib
import datetime
import os
from form import Comment_form

# ENV Variables
my_email = os.getenv("EMAIL")
password = os.getenv("EMAIL_PASS")
to_email = os.getenv("EMAIL_TO")

# Configuring Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)


# Connect to DB
# if os.getenv("DATABASE_URL") == None:
#
#     # Local Database
#     app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///BlogDB.db'
# else:
# Connecting to PostgreSQL Heroku DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuring flask_login

# The login manager contains the code that lets your application and Flask-Login work together,
# such as how to load a user from an ID, where to send users when they need to log in, and the like.
login_manager = flask_login.LoginManager()

# Once the actual application object has been created, you can configure it for login with:
login_manager.init_app(app)

# Initialize Flask Gravatar
# This is small and simple integration gravatar into flask
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


# Configure User Table
class User(flask_login.UserMixin, db.Model):
    # UserMixin is a helper provided by the Flask-Login library
    # to provide boilerplate methods necessary for managing users.
    # __tablename__: Set the name of the resulting table.
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    user_pass = db.Column(db.String(25), nullable=False)

    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = db.relationship('BlogPost', back_populates='author')

    # creating relationship ship between Comment table and User table
    # The "text" refers to the author property in the Comment class.
    comments = db.relationship('Comment', back_populates='comment_author')


# CONFIGURE TABLE
class BlogPost(db.Model):
    __tablename__ = "blog_posts"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    # author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # creating one-many relationship between the two table
    # this will allow locate the BlogPosts a User has written and also the User of any BlogPost object.
    # https: // docs.sqlalchemy.org / en / 13 / orm / basic_relationships.html  # one-to-many
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = db.relationship('User', back_populates='posts')

    # ***************Parent Relationship*************#
    # creating relationship between Comment table and BlogPost table
    comments = db.relationship('Comment', back_populates='parent_post')


# Creating Comment Table
class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = db.relationship("User", back_populates='comments')

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))
    parent_post = db.relationship("BlogPost", back_populates='comments')
    text = db.Column(db.Text, nullable=False)

# db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


###
# from functools import wraps
# Since the original function is replaced, you need to remember to copy the original function’s information
# to the new function. Use functools.wraps() to handle this for you.
# Flask abort:
# Flask comes with a handy abort() function that aborts a request with an HTTP error code early.
# It will also provide a plain black and white error page for you with a basic description, but nothing fancy.
###
# creating admin_only decorator
# Only admin should be able to access the /edit-post or /new-post or /delete routes
def admin_only(func):
    @wraps(func)
    def page_not_found(*args, **kwargs):
        # is the user is not logged or the user id != 1 deny access to this route
        if not flask_login.current_user.is_authenticated or flask_login.current_user.id != 1:
            return abort(403)
        # else continue with the route function
        return func(*args, **kwargs)

    return page_not_found


# WTForm
class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    # Removing author, b/c this is no longer needed. B/c of the the relationship between users and blogpost table
    # Name will be automatically filled by the name user of the registered user
    # author = StringField("Your Name", validators=[DataRequired()])
    img_url = StringField("Blog Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


# Register Form
class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    name = StringField("Full Name", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Submit")


# Login Form
class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    user_pass = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log In")


@app.route('/')
def home():
    blog_posts = db.session.query(BlogPost).all()
    # print(flask_login.current_user.id)
    return render_template("index.html", posts=blog_posts)


@app.route('/post/<int:index>', methods=["GET", "POST"])
# index is = post['id']. This is coming from the post API in index.html
# This is going to create a url for each page post
def get_post(index):
    all_posts = db.session.query(BlogPost).all()
    requested_post = None
    for blog_post in all_posts:
        if blog_post.id == index:
            requested_post = blog_post

        if request.method == "POST":
            if flask_login.current_user.is_authenticated:
                new_comment = Comment(
                    author_id=flask_login.current_user.id,
                    post_id=index,
                    text=request.form.get("body"),
                )
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for("get_post", index=index))
            else:
                flash("You need to login or register to comment.")
                return redirect(url_for("user_login"))

    return render_template("post.html", post=requested_post, comment_form=Comment_form())


@app.route('/new-post', methods=["GET", "POST"])
@admin_only
def new_post():
    if request.method == "POST":
        # getting hold of each field in the form and passing to the Blogpost DB to add a new row using the data
        post = BlogPost(
            title=request.form.get("title"),
            subtitle=request.form.get("subtitle"),
            date=datetime.datetime.now().strftime("%B %d, %Y"),
            body=request.form.get("body"),
            author_id=flask_login.current_user.id,
            img_url=request.form.get("img_url"),
        )
        db.session.add(post)
        db.session.commit()

        return redirect(url_for("home"))

    return render_template("make-post.html", form=CreatePostForm())


@app.route('/edit-post/<int:post_id>', methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    # getting hold of the post user clicked on using the post_id pass in from post.html
    post = BlogPost.query.get(post_id)
    # getting hold of the all the post data and passing into the form
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author.name,
        body=post.body
    )

    # After the user updates a post and click on submit.
    # The following will update the  database

    if request.method == "POST":
        post.title = request.form.get("title")
        post.subtitle = request.form.get("subtitle")
        post.body = request.form.get("body")
        # Removing author, b/c this is no longer needed. B/c of the the relationship between users and blogpost table
        # Name will be automatically filled by the name user of the registered user
        # post.author = request.form.get("author")
        post.img_url = request.form.get("img_url")
        db.session.commit()

        # redirect to the post that was getting edited
        return redirect(url_for("get_post", index=post_id))

    return render_template("make-post.html", form=edit_form)


@app.route('/delete/<int:post_id>')
@admin_only
def delete_post(post_id):
    post = BlogPost.query.get(post_id)
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for("home"))


@app.route('/register', methods=["GET", "POST"])
def register_user():
    form = RegisterForm()

    # getting hold of all the users in the User DB
    exiting_user = db.session.query(User).all()
    if form.validate_on_submit():

        for user in exiting_user:
            if request.form.get("email") == user.email:
                flash("You've already signed up with that email. Login.", "error")
                return redirect(url_for("user_login"))
        else:
            new_user = User(
                email=request.form.get("email"),
                name=request.form.get("name"),
                user_pass=request.form.get("password")
            )
            db.session.add(new_user)
            db.session.commit()

            # logging in the new user after they complete registration
            flask_login.login_user(new_user)
            return redirect(url_for("home"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def user_login():
    form = LoginForm()
    if form.validate_on_submit():
        user_email = request.form.get("email")
        user_password = request.form.get("user_pass")
        user = User.query.filter_by(email=user_email).first()
        try:
            if user.email == user_email and user.user_pass == user_password:
                flask_login.login_user(user)
                return redirect(url_for("home"))
        except AttributeError:
            flash("The email does not exit or incorrect, please try again.")
            return redirect(url_for("user_login"))
        else:
            if user.email != user_email:
                flash("The email does not exit or incorrect, please try again.")
                return redirect(url_for("user_login"))
            elif user.user_pass != user_password:
                flash("The password is incorrect, please try again.")
                return redirect(url_for("user_login"))

    return render_template("login.html", form=form)


@app.route('/logout')
@flask_login.login_required
def logout():
    # They will be logged out, and any cookies for their session will be cleaned up.
    flask_login.logout_user()
    return redirect(url_for("home"))


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/contact', methods=["GET", "POST"])
def contact():
    
    # getting hold of all the data user typing into the contact form in contact.html 
    contact_form = request.form

    # if the method is post it will return the if block, else it use GET method and return the webpage
    if request.method == "POST":
        name = contact_form['username']
        email = contact_form['Email']
        phone = contact_form['phone_number']
        message = contact_form['msg']
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as connection:
                connection.starttls()
                connection.login(user=my_email, password=password)
                connection.sendmail(from_addr=my_email,
                                    to_addrs=to_email,
                                    msg=f"Subject: New Message \n\nName: {name}\n Email: {email}\n Phone#:{phone}\n Message: {message}"
                                    )

        except smtplib.SMTPAuthenticationError:
            flash("Bad Credentials")
            return redirect(url_for("contact"))
        except smtplib.SMTPResponseException:
            flash("Bad Credentials")
            return redirect(url_for("contact"))

        return render_template("contact.html")
    else:
        return render_template("contact.html")


# port = int(os.getenv('POST', 5000))

if __name__ == "__main__":
    app.run(debug=True)
    # app.run(host='0.0.0.0', port=port)