from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask import Flask, render_template, redirect, url_for, flash, abort, request
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask_sqlalchemy import SQLAlchemy
from email.message import EmailMessage
from flask_caching import Cache
from flask_bcrypt import Bcrypt
from datetime import datetime
from bs4 import BeautifulSoup
from flask import jsonify
import smtplib
import hashlib
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


# --- CONFIGURAÇÕES DE E-MAIL ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASS')

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
    email = db.Column(db.String(120), unique=True, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    password_hash = db.Column(db.String(60), nullable=False)
    favorites = db.relationship('Favorite', backref='author', lazy=True)

    def avatar(self, size):
        email_hash = hashlib.md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{email_hash}?d=identicon&s={size}'

    def __repr__(self):
        return f"User('{self.username}')"
    
    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})
    
    @staticmethod
    def verify_reset_token(token, expires_sec=1800): # Token válido por 30 minutos
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

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
    return db.session.get(User, int(user_id))

JIKAN_API_URL = "https://api.jikan.moe/v4/seasons/upcoming"

@cache.memoize(timeout=43200)
def get_weekly_schedule():
    """Busca a grade de animes da semana na API Jikan."""
    logging.info("Fazendo chamada na API Jikan para buscar a grade da semana.")
    SCHEDULE_URL = "https://api.jikan.moe/v4/schedules"
    try:
        response = requests.get(SCHEDULE_URL)
        response.raise_for_status()
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao buscar a grade da semana: {e}")
        return []

@cache.memoize() 
def get_upcoming_animes(page=1):
    """Busca uma página específica de animes da próxima temporada na API."""
    logging.info(f"Fazendo chamada na API Jikan para buscar a PÁGINA {page} de animes.")

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

@cache.memoize(timeout=86400) # Cache de 24 horas ATIVADO
def get_anime_episodes(anime_id):
    """Busca a lista COMPLETA de episódios de um anime, navegando por todas as páginas da API."""
    logging.info(f"Buscando TODAS as páginas de episódios para o anime ID {anime_id}")
    
    all_episodes = []
    page = 1
    
    while True:
        try:
            EPISODES_URL = f"https://api.jikan.moe/v4/anime/{anime_id}/episodes?page={page}"
            response = requests.get(EPISODES_URL, timeout=10) # Manter o timeout é uma boa prática
            
            if response.status_code != 200:
                logging.warning(f"Recebido status {response.status_code} ao buscar episódios. Parando a busca.")
                break

            json_data = response.json()
            page_data = json_data.get('data', [])
            
            if not page_data:
                break 
            
            all_episodes.extend(page_data)
            
            if not json_data.get('pagination', {}).get('has_next_page'):
                break
            
            page += 1

        except requests.exceptions.RequestException as e:
            logging.error(f"Falha ao buscar página {page} de episódios para o anime ID {anime_id}: {e}")
            break

    logging.info(f"Encontrados {len(all_episodes)} episódios no total para o anime ID {anime_id}.")
    return all_episodes

@app.route('/get_episode_synopsis')
def get_episode_synopsis():
    # Pega a URL do episódio que o nosso JavaScript vai enviar
    episode_url = request.args.get('url')
    if not episode_url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        logging.info(f"Fazendo scraping da URL: {episode_url}")
        response = requests.get(episode_url, timeout=10)
        response.raise_for_status()

        # Usamos a BeautifulSoup para parsear o HTML da página
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Encontramos a sinopse dentro da tag <p> com o atributo itemprop="description"
        # Esta é a parte "frágil": se o MyAnimeList mudar seu HTML, isso pode quebrar.
        synopsis_tag = soup.find('p', itemprop='description')
        
        synopsis_text = synopsis_tag.text.strip() if synopsis_tag else "Sinopse não encontrada."

        return jsonify({'synopsis': synopsis_text})

    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de scraping para {episode_url}: {e}")
        return jsonify({'error': 'Falha ao buscar a página do episódio'}), 500

def send_reset_email(user):
    token = user.get_reset_token()
    remetente = os.environ.get('EMAIL_USER')
    senha = os.environ.get('EMAIL_PASS')

    assunto = "Solicitação de Redefinição de Senha - Valhalla Animes"
    corpo = f'''Para redefinir sua senha, visite o seguinte link:
{url_for('reset_token', token=token, _external=True)}

Este link expirará em 30 minutos.

Se você não fez esta solicitação, simplesmente ignore este e-mail.
'''

    msg = EmailMessage()
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = user.email
    msg.set_content(corpo)

    try:
        logging.info(f"Tentando enviar e-mail para {user.email}...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.send_message(msg)
        server.quit()
        logging.info("E-mail de redefinição enviado com sucesso.")
    except Exception as e:
        logging.error(f"[FALHA NO ENVIO DE E-MAIL] Erro: {e}")

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user:
            send_reset_email(user)
        # Mostramos a mesma mensagem mesmo se o e-mail não existir, por segurança.
        flash('Um e-mail foi enviado com as instruções para redefinir sua senha, caso o e-mail exista em nosso sistema.', 'info')
        return redirect(url_for('login'))
    return render_template('request_reset.html', year=datetime.now().year)

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('O token é inválido ou expirou. Por favor, tente novamente.', 'warning')
        return redirect(url_for('reset_request'))
    if request.method == 'POST':
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user.password_hash = hashed_password
        db.session.commit()
        logging.info(f"Senha do usuário {user.username} foi redefinida com sucesso.")
        flash('Sua senha foi atualizada! Você já pode fazer o login.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', year=datetime.now().year)

@app.route('/anime/<int:anime_id>')
def anime_detail(anime_id):
    logging.info(f"Buscando detalhes para o anime ID {anime_id}")
    
    ANIME_API_URL = f"https://api.jikan.moe/v4/anime/{anime_id}"
    
    try:
        response = requests.get(ANIME_API_URL)
        response.raise_for_status()
        anime_data = response.json().get('data')

        if not anime_data:
            logging.error(f"Nenhum dado encontrado para o anime ID {anime_id}")
            flash('Anime não encontrado.', 'danger')
            return redirect(url_for('index'))

        # --- NOVA PARTE: BUSCAR EPISÓDIOS ---
        episodes_list = get_anime_episodes(anime_id)
        # --- FIM DA NOVA PARTE ---

        logging.info(f"Detalhes de '{anime_data.get('title')}' carregados com sucesso.")
        
        # Adicionamos 'episodes' ao render_template
        return render_template('anime_detail.html', 
                               anime=anime_data, 
                               episodes=episodes_list, 
                               year=datetime.now().year)

    except requests.exceptions.RequestException as e:
        logging.error(f"Falha ao buscar detalhes da API para o anime ID {anime_id}: {e}")
        flash('Erro ao carregar os detalhes do anime. Tente novamente mais tarde.', 'danger')
        return redirect(url_for('index'))


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

@app.route('/semana')
def semana():
    logging.info("Acessando a página da agenda da semana.")
    
    weekly_animes = get_weekly_schedule()
    
    animes_por_dia = {
        "Segunda-feira": [],
        "Terça-feira": [],
        "Quarta-feira": [],
        "Quinta-feira": [],
        "Sexta-feira": [],
        "Sábado": [],
        "Domingo": [],
        "Indefinido": []
    }
    
    # Dicionário para traduzir os dias da semana
    dias_en_pt = {
        "Mondays": "Segunda-feira",
        "Tuesdays": "Terça-feira",
        "Wednesdays": "Quarta-feira",
        "Thursdays": "Quinta-feira",
        "Fridays": "Sexta-feira",
        "Saturdays": "Sábado",
        "Sundays": "Domingo"
    }

    for anime in weekly_animes:
        dia_en = anime.get('broadcast', {}).get('day')
        # Pega o nome do dia em português, ou 'Indefinido' se não houver
        dia_pt = dias_en_pt.get(dia_en, "Indefinido")
        animes_por_dia[dia_pt].append(anime)

    return render_template('semana.html', animes_por_dia=animes_por_dia, year=datetime.now().year)

# --- ROTAS DE LOGIN/LOGOUT ---


@app.route('/profile/<string:username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    
    logging.info(f"Usuário '{current_user.username}' está vendo o perfil de '{user.username}'.")
    
    # Lógica para buscar os detalhes dos animes favoritos (reutilizada da página /favorites)
    favorite_animes_details = []
    for fav in user.favorites:
        res = requests.get(f'https://api.jikan.moe/v4/anime/{fav.anime_id}')
        if res.status_code == 200:
            detail = res.json()['data']
            favorite_animes_details.append(detail)
            
    return render_template('profile.html', user=user, favorite_animes=favorite_animes_details, year=datetime.now().year)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')

        # Verifica se username ou email já existem
        user_by_username = User.query.filter_by(username=username).first()
        user_by_email = User.query.filter_by(email=email).first()

        if user_by_username:
            flash('Este nome de usuário já está em uso. Por favor, escolha outro.', 'danger')
            return render_template('register.html')
        
        if user_by_email:
            flash('Este e-mail já está cadastrado. Por favor, utilize outro.', 'danger')
            return render_template('register.html')
        
        hashed_password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        # Adicionamos o email ao criar o novo usuário
        user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        
        logging.info(f"Usuário '{username}' criado com sucesso.")
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
    app.run(host='0.0.0.0', port=5051 ,debug=True, use_reloader=False)