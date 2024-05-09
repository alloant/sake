# SAKE

This Flask project integrates Synology Drive, SQLAlchemy, HTMX and user authentication to create a robust and secure document management system.

## Key Features:

* Synology Drive Integration: Leverages the synology-drive-api library to interact with your Synology Drive.
* SQLAlchemy ORM: Streamlines database interactions for a smooth development experience:
    * Handles database operations effortlessly
    * Ensures data consistency and integrity
* User Authentication and Access Control: Enforces granular control over user access to documents, ensuring:
    * Secure document management
    * Restriction of sensitive information to authorized users
    * Workflow Support.

## Getting Started:


1. Clone the repository: `git clone https://github.com/alloant/sake`

2. Install dependencies: `pip install -r requirements.txt` or `poetry install`

3. Configure credentials SECRET_KEY (to encrypt the user passwords) and DATABASE_URI (to connect to the databse, otherwise it will default to SQlite)

4. Run the application: `python flask_app/app.py` or `waitress-serve -call 'app:create_app'`

### With docker

1. Clone the repository: `git clone https://github.com/alloant/sake`

2. Build image: `docker build -t sake .`

3. Run docker: `docker run --env SECRET_KEY="secret" DATABASE_URI="mariadb+pymysql://user:password@host/database?charset=utf8mb4"`

