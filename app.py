import os
from flask import Flask, jsonify, request
from blockchain.store import ChainStore
from routes.wallet import wallet_bp
from routes.issuer import issuer_bp
from routes.verifier import verifier_bp
from routes.p2p import p2p_bp
from utils.auth_db import init_db, seed_admin


def create_app(
    chain_path: str = "chain.json",
    peers_path: str = "peers.json",
    auth_db_path: str = "auth.db",
    node_url: str = "http://localhost:5000",
) -> Flask:
    # Resolve relative paths against the directory app.py lives in,
    # not the shell's cwd — so the app works regardless of where it's launched from.
    _base = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(chain_path):   chain_path   = os.path.join(_base, chain_path)
    if not os.path.isabs(peers_path):   peers_path   = os.path.join(_base, peers_path)
    if not os.path.isabs(auth_db_path): auth_db_path = os.path.join(_base, auth_db_path)
    app = Flask(__name__, template_folder="templates", static_folder="static")

    app.secret_key                        = os.environ.get("SECRET_KEY", os.urandom(32))
    app.config["NODE_URL"]                = node_url
    app.config["AUTH_DB"]                 = auth_db_path
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"]   = False

    init_db(auth_db_path)
    seed_admin(
        db_path  = auth_db_path,
        username = os.environ.get("ADMIN_USER", "admin"),
        password = os.environ.get("ADMIN_PASS", "admin123"),
    )

    store = ChainStore(
        chain_path = chain_path,
        peers_path = peers_path,
        node_url   = node_url,
    )
    app.config["STORE"] = store

    @app.before_request
    def _inject_store():
        app.config["BLOCKCHAIN"] = store

    app.register_blueprint(wallet_bp)
    app.register_blueprint(issuer_bp)
    app.register_blueprint(verifier_bp)
    app.register_blueprint(p2p_bp)

    from routes.verifier import public_verify

    @app.route("/verify", methods=["GET"])
    def verify_redirect():
        return public_verify()

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status":       "ok",
            "node_url":     node_url,
            "chain_length": store.chain_length(),
            "chain_valid":  store.is_chain_valid(),
            "peers":        store.get_peers(),
        }), 200

    from flask import render_template

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Route not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DID node")
    parser.add_argument("--port",    type=int, default=5000)
    parser.add_argument("--chain",   default="chain.json")
    parser.add_argument("--peers",   default="peers.json")
    parser.add_argument("--auth-db", default="auth.db")
    args = parser.parse_args()

    node_url  = f"http://localhost:{args.port}"
    flask_app = create_app(
        chain_path   = args.chain,
        peers_path   = args.peers,
        auth_db_path = args.auth_db,
        node_url     = node_url,
    )
    flask_app.run(debug=False, host="0.0.0.0", port=args.port)