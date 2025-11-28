# munis

The municipal bond dashboard.

## setup

Create a virtual environment and install required packages:

```sh
python -m venv env
source env/bin/activate
(env) pip install -r requirements.txt
```

Create `secrets.toml` file in a new `.streamlit` directory:

```toml
[connections.postgresql]
dialect = "postgresql"
host = "localhost"
port = "5432"
database = "munis"
username = "(username)"
password = "(password)"
```

Supply the *username* and *password* to your local copy of the municipal bond 
database. Ensure that the postgres server for this database is running, and that
the database has been initialized.

Finally, run the following to open the dashboard in your default browser:

```sh
streamlit run munis.py
```
