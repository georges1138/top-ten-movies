from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField
from wtforms.validators import DataRequired
import requests
import os

MOVIE_API_KEY = os.environ["TMDB_API_KEY"]
MOVIE_SITE_URL = "https://api.themoviedb.org/3/search/movie"
MOVIE_DETAIL_SITE_URL = "https://api.themoviedb.org/3/movie"
MOVIE_POSTER_SITE_URL = "https://image.tmdb.org/t/p/w500"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///top-ten-movies.db'
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
Bootstrap(app)

db = SQLAlchemy(app)


class RateMovieForm(FlaskForm):
    new_rating = FloatField(label='Your Rating Out of 10 e.g. 7.5', validators=[DataRequired()])
    new_review = StringField(label='Your Review', validators=[DataRequired()])
    submit = SubmitField(label='Done')


class AddMovieForm(FlaskForm):
    new_movie = StringField(label='Movie Title', validators=[DataRequired()])
    submit = SubmitField(label='Add Movie')


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), unique=True, nullable=False)
    year = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(250), nullable=False)
    rating = db.Column(db.Float)
    ranking = db.Column(db.Integer)
    review = db.Column(db.String(250))
    img_url = db.Column(db.String(80))

    def __repr__(self):
        return '<Movie %r>' % self.title


with app.app_context():
    db.create_all()


all_movies = []


@app.route("/")
def home():
    global all_movies
    all_movies = retrieve_all_rows()
    return render_template("index.html", mList=all_movies)


@app.route("/delete")
def delete():
    movie_id = request.args.get('id')
    movie_to_update = Movie.query.get(movie_id)
    print(movie_to_update.title)
    db.session.delete(movie_to_update)
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/edit", methods=['GET', 'POST'])
def edit():
    form = RateMovieForm()
    if form.validate_on_submit():
        print('True')
        nrate = float(form.new_rating.data)
        nreview = form.new_review.data
        print(f"New Rating: {nrate}, New Review: {nreview}")
        movie_id = request.args.get('id')
        movie_to_update = Movie.query.get(movie_id)
        movie_to_update.rating = nrate
        movie_to_update.review = nreview
        db.session.commit()
        return redirect(url_for('home'))
    return render_template("edit.html", form=form)


@app.route("/add", methods=['GET', 'POST'])
def add():
    form = AddMovieForm()
    if form.validate_on_submit():
        mname = form.new_movie.data
        print("Let's Add a Movie: ", mname)
        movie_list = movie_search_request(mname)
        print(type(movie_list))
        print(movie_list)
        return render_template("select.html", mList=movie_list)
    return render_template("add.html", form=form)


@app.route("/select")
def select():
    movie_id = request.args.get('id')
    print(f"Pulling movie details for id: {movie_id}")
    m_dict = movie_detail_request(movie_id)
    # I have my movie info to add a new entry
    add_movie = Movie(title=m_dict['original_title'],
                      year=str(m_dict['release_date'])[0:4],
                      description=m_dict['overview'],
                      rating=m_dict['vote_average'],
                      ranking=10,
                      review=m_dict['tagline'],
                      img_url=f"{MOVIE_POSTER_SITE_URL}/{m_dict['poster_path']}",
                      )
    db.session.add(add_movie)
    db.session.commit()
    # Movie.query.filter_by(title=)
    print(add_movie)
    print(add_movie.id)
    return redirect(url_for('edit', id=add_movie.id))


def retrieve_all_rows() -> list:
    movie_return_list = []
    movie_db_list = Movie.query.order_by(Movie.rating).all()
    print(len(movie_db_list))
    m_rank_num = len(movie_db_list)
    for movie in movie_db_list:
        movie_dict_hold = {}
        movie_dict_hold['id'] = movie.id
        movie_dict_hold['title'] = movie.title
        movie_dict_hold['year'] = movie.year
        movie_dict_hold['description'] = movie.description
        movie_dict_hold['rating'] = movie.rating
        # movie_dict_hold['ranking'] = movie.ranking
        movie_dict_hold['ranking'] = m_rank_num
        movie_dict_hold['review'] = movie.review
        movie_dict_hold['img_url'] = movie.img_url
        movie_return_list.append(movie_dict_hold)
        m_rank_num -= 1
    return movie_return_list


def movie_search_request(mname) -> list:
    payload = {
        'api_key': MOVIE_API_KEY,
        'query': mname,
    }
    response = requests.get(url=MOVIE_SITE_URL, params=payload)
    response.raise_for_status()
    result = response.json()
    print(result['total_results'])
    return result['results']


def movie_detail_request(m_id):
    payload = {
        'api_key': MOVIE_API_KEY,
        'language': 'en-US',
    }
    MOVIE_URL = f"{MOVIE_DETAIL_SITE_URL}/{m_id}"
    print(MOVIE_URL)
    response = requests.get(url=MOVIE_URL, params=payload)
    response.raise_for_status()
    result = response.json()
    print(type(result))
    print(result)
    return result


if __name__ == '__main__':
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
