from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache
from flask_bcrypt import Bcrypt
from datetime import datetime
import logging
import requests
import os


# --- Logs ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# Função para carregar o usuário da sessão
@login_manager.user_loader
def load_user(user_id):
    logging.info(f"Carregando usuário da sessão: ID {user_id}")
    return User.query.get(int(user_id))

JIKAN_API_URL = "https://api.jikan.moe/v4/seasons/upcoming"

@cache.memoize() 
def get_upcoming_animes(page=1):
    """Busca uma página específica de animes da próxima temporada na API."""
    logging.info(f"Fazendo chamada na API Jikan para buscar a PÁGINA {page} de animes.")
    
    # Adicionamos o parâmetro de página na URL
    PAGED_JIKAN_URL = f"https://api.jikan.moe/v4/seasons/upcoming?page={page}"
    
    try:
        response = requests.get(PAGED_JIKAN_URL)
        response.raise_for_status()
        # Retornamos o JSON completo para ter acesso aos dados de paginação
        return response.json() 
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao buscar dados da API para a página {page}: {e}")
        return None
    
@app.route('/')
def index():
    # Pega o número da página da URL, o padrão é 1
    page = request.args.get('page', 1, type=int)
    logging.info(f"Acessando a página inicial, página {page}.")

    # Chama a função com o número da página
    api_response = get_upcoming_animes(page=page)
    
    animes_formatados = []
    pagination_data = None

    if api_response:
        # Pega os dados dos animes e as informações de paginação
        animes = api_response.get('data', [])
        pagination_data = api_response.get('pagination')

        for anime in animes:
            # A lógica de formatação continua a mesma
            release_date = "Data a ser anunciada"
            if anime['aired']['from']:
                try:
                    date_obj = datetime.fromisoformat(anime['aired']['from'])
                    release_date = date_obj.strftime('%d de %B de %Y')
                except (ValueError, TypeError):
                    release_date = anime.get('broadcast', {}).get('string', 'Data a ser anunciada')

            animes_formatados.append({
                'id': anime['mal_id'],
                'title': anime['title'],
                'image_url': anime['images']['jpg']['large_image_url'],
                'synopsis': anime.get('synopsis', 'Sinopse não disponível.')[:150] + '...' if anime.get('synopsis') else 'Sinopse não disponível.',
                'release_date': release_date,
            })

    current_year = datetime.now().year
    # Enviamos os animes E os dados de paginação para o template
    return render_template('index.html', 
                           animes=animes_formatados, 
                           pagination=pagination_data,
                           year=current_year)

@app.route('/anime/<int:anime_id>')
def anime_detail(anime_id):
    logging.info(f"Buscando detalhes para o anime ID {anime_id}")
    
    # URL da API para um anime específico
    ANIME_API_URL = f"https://api.jikan.moe/v4/anime/{anime_id}"
    
    try:
        response = requests.get(ANIME_API_URL)
        response.raise_for_status() # Lança um erro se a requisição falhar
        anime_data = response.json().get('data')

        if not anime_data:
            logging.info(f"[LOG][ERRO]: Nenhum dado encontrado para o anime ID {anime_id}")
            flash('Anime não encontrado.', 'danger')
            return redirect(url_for('index'))

        logging.info(f"Detalhes de '{anime_data.get('title')}' carregados com sucesso.")
        return render_template('anime_detail.html', anime=anime_data, year=datetime.now().year)

    except requests.exceptions.RequestException as e:
        logging.info(f"Falha ao buscar detalhes da API para o anime ID {anime_id}: {e}")
        flash('Erro ao carregar os detalhes do anime. Tente novamente mais tarde.', 'danger')
        return redirect(url_for('index'))

@app.route('/search')
@app.route('/search')
def search():
    query = request.args.get('q')
    
    if not query:
        return redirect(url_for('index'))

    logging.info(f"Usuário pesquisou por: '{query}'")
    SEARCH_API_URL = f"https://api.jikan.moe/v4/anime?q={query}&limit=24"
    
    try:
        response = requests.get(SEARCH_API_URL)
        response.raise_for_status()
        search_results = response.json().get('data', [])
        
        # Reutilizamos a lógica de formatação da página inicial
        animes_formatados = []
        for anime in search_results:
            animes_formatados.append({
                'id': anime['mal_id'],
                'title': anime['title'],
                'image_url': anime['images']['jpg']['large_image_url'],
                'synopsis': anime.get('synopsis', 'Sinopse não disponível.')[:150] + '...' if anime.get('synopsis') else 'Sinopse não disponível.',
                'release_date': anime.get('year', 'N/A')
            })

        return render_template('search_results.html', 
                               animes=animes_formatados, 
                               query=query,
                               year=datetime.now().year)

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar na API para a query '{query}': {e}")
        flash('Erro ao realizar a busca. Tente novamente.', 'danger')
        return redirect(url_for('index'))

@app.route('/favorite/<int:anime_id>')
@login_required
def add_favorite(anime_id):
    logging.info(f"Usuário '{current_user.username}' tentando favoritar anime ID {anime_id}")
    response = requests.get(f'https://api.jikan.moe/v4/anime/{anime_id}')
    if response.status_code == 200:
        anime_data = response.json()['data']
        anime_title = anime_data['title']
        existing_favorite = Favorite.query.filter_by(user_id=current_user.id, anime_id=anime_id).first()
        if existing_favorite:
            logging.info(f"Anime {anime_id} já era um favorito.\n")
            flash('Este anime já está nos seus favoritos!', 'info')
        else:
            new_favorite = Favorite(anime_id=anime_id, anime_title=anime_title, author=current_user)
            db.session.add(new_favorite)
            db.session.commit()
            logging.info(f"Anime {anime_id} adicionado aos favoritos com sucesso.\n")
            flash('Anime adicionado aos favoritos!', 'success')
    else:
        flash('Erro ao encontrar o anime.', 'danger')
    
    return redirect(request.referrer or url_for('index'))

@app.route("/favorites")
@login_required
def favorites():
    logging.info(f"Usuário '{current_user.username}' acessando a página de favoritos.\n")
    user_favorites_ids = [fav.anime_id for fav in current_user.favorites]
    favorite_animes_details = []
    for fav in current_user.favorites:
        res = requests.get(f'https://api.jikan.moe/v4/anime/{fav.anime_id}')
        if res.status_code == 200:
            detail = res.json()['data']
            detail['favorite_id'] = fav.id
            favorite_animes_details.append(detail)
    
    return render_template('favorites.html', animes=favorite_animes_details)

@app.route('/unfavorite/<int:favorite_id>')
@login_required
def remove_favorite(favorite_id):
    logging.info(f"Usuário '{current_user.username}' tentando remover o favorito de ID {favorite_id}")
    favorite_to_remove = Favorite.query.get_or_404(favorite_id)
    if favorite_to_remove.author != current_user:
        logging.error(f"[LOG][ERRO]: Tentativa de acesso não autorizado para remover favorito.\n")
        abort(403)
    db.session.delete(favorite_to_remove)
    db.session.commit()
    logging.info(f"Favorito {favorite_id} removido com sucesso.\n")
    flash('Anime removido dos favoritos.', 'success')
    return redirect(url_for('favorites'))

# --- ROTAS DE LOGIN/LOGOUT ---


@app.route('/profile/<string:username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    logging.info(f"Usuário '{current_user.username}' está vendo o perfil de '{user.username}'.")

    return render_template('profile.html', user=user, year=datetime.now().year)

@app.route("/register", methods=['GET', 'POST'])
def register():
    logging.info("Acessando a página 'register'.\n")
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        logging.info(f"Tentativa de registro para o usuário: '{username}'")
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            logging.error(f"Falha no registro: usuário '{username}' já existe.\n")
            flash('Este nome de usuário já está em uso. Por favor, escolha outro.', 'danger')
            return render_template('register.html')
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(username=username, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        logging.info(f"Usuário '{username}' criado com sucesso.\n")
        flash('Sua conta foi criada! Você já pode fazer o login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    logging.info("Acessando a página 'login'.\n")
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        print(f"Tentativa de login para o usuário: '{username}'")
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user, remember=True)
            print(f"Usuário '{username}' logado com sucesso.\n")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            logging.error(f"Falha no login para o usuário: '{username}'\n")
            flash('Login falhou. Por favor, verifique o usuário e a senha.', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    logging.info(f"Usuário '{current_user.username}' fazendo logout.\n")
    logout_user()
    return redirect(url_for('index'))

@app.route('/sobre')
def sobre():
    logging.info("Acessando a página 'Sobre'.\n")
    current_year = datetime.now().year
    return render_template('sobre.html', year=current_year)

if __name__ == '__main__':
    logging.info("Iniciando a aplicação Valhalla Animes...")
    logging.info("Servidor em execução\n")
    app.run(host='0.0.0.0', port=5051 ,debug=True)