from app import app
from config import get_config
import routes

if __name__ == "__main__":
    config = get_config()
    host = getattr(config, 'HOST', '0.0.0.0')
    port = getattr(config, 'PORT', 5000)
    debug = getattr(config, 'DEBUG', True)
    app.run(host=host, port=port, debug=debug)
