from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_bcrypt import Bcrypt
from datetime import datetime
import requests
import os

config = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 3600
}

app = Flask(__name__)
app.config.from_mapping(config)

# --- CONFIGURAÇÕES ---
app.config['SECRET_KEY'] = 'U%As%yuy"F&T'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- INICIALIZAÇÃO DO DB ---
cache = Cache(app)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- MODELS BD ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    favorites = db.relationship('Favorite', backref='author', lazy=True)

    def __repr__(self):
        return f"User('{self.username}')"

class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    anime_id = db.Column(db.Integer, nullable=False) # ID do anime vindo da API Jikan
    anime_title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Favorite('{self.anime_title}')"

# Função para carregar o usuário da sessão (o "callback" que o erro menciona)
@login_manager.user_loader
def load_user(user_id):
    # Flask-Login nos dá o user_id. Nós usamos para buscar o usuário no banco.
    return User.query.get(int(user_id))

JIKAN_API_URL = "https://api.jikan.moe/v4/seasons/upcoming"

def get_upcoming_animes():
    """Busca os animes da próxima temporada na API"""
    print("\nFAZENDO CHAMADA REAL PARA API\n")
    try:
        response = requests.get(JIKAN_API_URL)
        response.raise_for_status()
        data = response.json()
        return data.get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar dados da API: {e}")
        return []
    
@app.route('/')
def index():
    """Rota principal que renderiza a página inicial"""
    animes = get_upcoming_animes()

    animes_formatados = []
    for anime in animes:
        release_date = "Data a ser anunciada"
        if anime['aired']['from']:
            try:
                date_obj = datetime.fromisoformat(anime['aired']['from'])
                release_date = date_obj.strftime('%d de %B de %Y')
            except (ValueError, TypeError):
                release_date = anime.get('broadcast', {}).get('string', 'Data a ser anunciada')

        animes_formatados.append({
            'title': anime['title'],
            'image_url': anime['images']['jpg']['large_image_url'],
            'synopsis': anime.get('synopsis', 'Sinopse não disponível.')[:250] + '...' if anime.get('synopsis') else 'Sinopse não disponível.',
            'release_date': release_date,
            'url': anime['url']
        })

    current_year = datetime.now().year
    return render_template('index.html', animes=animes_formatados, year=current_year)

@app.route('/favorite/<int:anime_id>')
@login_required
def add_favorite(anime_id):
    response = requests.get(f'https://api.jikan.moe/v4/anime/{anime_id}')
    if response.status_code == 200:
        anime_data = response.json()['data']
        anime_title = anime_data['title']
        existing_favorite = Favorite.query.filter_by(user_id=current_user.id, anime_id=anime_id).first()
        if existing_favorite:
            flash('Este anime já está nos seus favoritos!', 'info')
        else:
            new_favorite = Favorite(anime_id=anime_id, anime_title=anime_title, author=current_user)
            db.session.add(new_favorite)
            db.session.commit()
            flash('Anime adicionado aos favoritos!', 'success')
    else:
        flash('Erro ao encontrar o anime.', 'danger')
    
    return redirect(request.referrer or url_for('index'))

@app.route("/favorites")
@login_required
def favorites():
    user_favorites_ids = [fav.anime_id for fav in current_user.favorites]
    
    favorite_animes_details = []
    for fav in current_user.favorites:
        # Para cada favorito, buscamos os detalhes na API Jikan
        # NOTA: Isso pode ser lento se o usuário tiver muitos favoritos.
        # Uma otimização futura seria fazer chamadas em paralelo ou cachear os resultados.
        res = requests.get(f'https://api.jikan.moe/v4/anime/{fav.anime_id}')
        if res.status_code == 200:
            detail = res.json()['data']
            detail['favorite_id'] = fav.id # Adicionamos o ID do nosso BD para o botão de remover
            favorite_animes_details.append(detail)
    
    return render_template('favorites.html', animes=favorite_animes_details)

@app.route('/unfavorite/<int:favorite_id>')
@login_required
def remove_favorite(favorite_id):
    favorite_to_remove = Favorite.query.get_or_404(favorite_id)
    # Garante que o usuário só pode remover seus próprios favoritos
    if favorite_to_remove.author != current_user:
        abort(403) # Erro de "proibido"
    db.session.delete(favorite_to_remove)
    db.session.commit()
    flash('Anime removido dos favoritos.', 'success')
    return redirect(url_for('favorites'))

# --- ROTAS DE LOGIN/LOGOUT ---

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(username=request.form.get('username'), password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada! Você pode fazer o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login falhou. Por favor, verifique o usuário e a senha.', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/sobre')
def sobre():
    current_year = datetime.now().year
    return render_template('sobre.html', year=current_year)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5051 ,debug=True)