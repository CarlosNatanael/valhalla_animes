# Valhalla Animes ⛩️

> Uma aplicação web dinâmica para descobrir, favoritar e acompanhar animes. O que começou como uma simples lista pessoal de animes para assistir se transformou em uma plataforma completa construída com Python e Flask.

## Visão Geral

 ![image](https://github.com/user-attachments/assets/b76fcf1f-798a-46f6-98bb-5b98e596d605)


Valhalla Animes é um site interativo que consome dados da [Jikan API](https://jikan.moe/) (um wrapper não oficial da API do MyAnimeList) para fornecer informações atualizadas sobre animes. Os usuários podem se registrar, fazer login, pesquisar por animes, ver detalhes, trailers, listas de episódios e criar sua própria lista de favoritos.

## ✨ Funcionalidades

- **Página Inicial Dinâmica:** Exibe os próximos lançamentos de animes com sistema de **paginação**.
- **Busca Completa:** Barra de busca para encontrar qualquer anime no catálogo do MyAnimeList.
- **Página de Detalhes Rica:** Informações completas sobre cada anime, incluindo sinopse, score, status, gêneros, trailer incorporado e **lista de episódios interativa**.
- **Sistema de Usuários:**
    - Registro de novas contas com e-mail e senha segura (hash).
    - Login e logout com gerenciamento de sessão.
    - Perfis de usuário com avatar (via Gravatar) e estatísticas.
- **Sistema de Favoritos:** Usuários logados podem adicionar e remover animes de sua lista de favoritos.
- **Agenda da Semana:** Página dedicada mostrando a grade de animes exibidos em cada dia da semana.
- **Design Moderno e Responsivo:** Interface com efeitos de "Glassmorphism", adaptável a desktop e dispositivos móveis.

## 🛠️ Tecnologias Utilizadas

- **Backend:**
    - [Python](https://www.python.org/)
    - [Flask](https://flask.palletsprojects.com/)
    - [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
    - [Flask-Login](https://flask-login.readthedocs.io/)
    - [Flask-Bcrypt](https://flask-bcrypt.readthedocs.io/)
    - [Jikan API](https://jikan.moe/)
    - [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- **Frontend:**
    - HTML5
    - CSS3 (Flexbox e Grid)
    - JavaScript
- **Banco de Dados:**
    - SQLite

## 🚀 Como Rodar Localmente

### 1. Pré-requisitos

- Python 3.x instalado
- `git` (opcional)

### 2. Clone o Repositório

```bash
git clone [https://github.com/CarlosNatanael/valhalla_animes]
cd valhalla_animes
```

### 3. Crie e Ative um Ambiente Virtual

No Windows:

```bash
python -m venv venv
.\venv\Scripts\activate
```

No macOS/Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Instale as Dependências

```bash
pip install -r requirements.txt
```

### 5. Configure as Variáveis de Ambiente

Para a funcionalidade de "Esqueci a senha", defina as variáveis de ambiente:

No PowerShell (Windows):

```powershell
$env:EMAIL_USER="seu-email@gmail.com"
$env:EMAIL_PASS="sua-senha-de-app-do-google"
```

No Bash (Linux/macOS):

```bash
export EMAIL_USER="seu-email@gmail.com"
export EMAIL_PASS="sua-senha-de-app-do-google"
```

### 6. Crie o Banco de Dados

```bash
flask shell
```

No shell do Flask:

```python
from app import db
db.create_all()
exit()
```

### 7. Rode a Aplicação

```bash
flask run
```
Ou:

```bash
python app.py
```

Acesse em: [Valhalla Animes](https://vn75t0lq-5051.brs.devtunnels.ms/)

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 👨‍💻 Contato

**Carlos Natanael**  
GitHub: [@CarlosNatanael](https://github.com/CarlosNatanael)  
LinkedIn: [@CarlosNatanael](https://www.linkedin.com/in/carlos-natanael-608628243/)
