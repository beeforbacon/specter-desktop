import json, os, random, requests
from flask import Blueprint, Flask, jsonify, render_template, request
from flask import current_app as app
from flask_cors import CORS
from .hwi_rpc import HWIBridge
from .helpers import deep_update, hwi_get_config, save_hwi_bridge_config


hwi_server = Blueprint('hwi_server', __name__)
CORS(hwi_server)
rand = random.randint(0, 1e32) # to force style refresh
hwi = HWIBridge()

@hwi_server.route("/api/", methods=["POST"])
def api():
    """JSON-RPC for HWI Bridge"""
    whitelisted_domains = hwi_get_config(app.specter)['whitelisted_domains'].split()
    for i, url in enumerate(whitelisted_domains):
        whitelisted_domains[i] = url.replace('http://localhost:', 'http://127.0.0.1:')
    if '*' not in whitelisted_domains and 'HTTP_ORIGIN' in request.environ:
        origin_url = request.environ['HTTP_ORIGIN'].replace('http://localhost:', 'http://127.0.0.1:')
        if not origin_url.endswith("/"):
                # make sure the url end with a "/"
                origin_url += "/"
        if not(origin_url in whitelisted_domains):
            return jsonify({
                "jsonrpc": "2.0",
                "error": { "code": -32001, "message": "Unauthorized request origin.<br>You must first whitelist this website URL in HWIBridge settings to grant it access." },
                "id": None
            }), 500
    try:
        data = json.loads(request.data)
    except:
        return jsonify({
            "jsonrpc": "2.0",
            "error": { "code": -32700, "message": "Parse error" },
            "id": None
        }), 500
    if ('forwarded_request' not in data or not data['forwarded_request']) and (app.specter.hwi_bridge_url.startswith('http://') or app.specter.hwi_bridge_url.startswith('https://')):
            if ('HTTP_ORIGIN' not in request.environ):
                return jsonify({
                    "jsonrpc": "2.0",
                    "error": { "code": -32600, "message": "Request must specify its origin or set `forwarded_request` to `true`." },
                    "id": None
                }), 500
            data['forwarded_request'] = True
            requests_session = requests.Session()
            requests_session.headers.update({'origin': request.environ['HTTP_ORIGIN']})
            if '.onion/' in app.specter.hwi_bridge_url:
                requests_session.proxies = {}
                requests_session.proxies['http'] = 'socks5h://localhost:9050'
                requests_session.proxies['https'] = 'socks5h://localhost:9050'
            forwarded_request = requests_session.post(app.specter.hwi_bridge_url, data=json.dumps(data))
            response = json.loads(forwarded_request.content)
            return jsonify(response)

    return jsonify(hwi.jsonrpc(data))

@hwi_server.route('/settings/', methods=["GET", "POST"])
def hwi_bridge_settings():
    config = hwi_get_config(app.specter)
    if request.method == 'POST':
        action = request.form['action']
        if action == "update":
            config['whitelisted_domains'] = request.form['whitelisted_domains']
            save_hwi_bridge_config(app.specter, config)
    return render_template("hwi_bridge.jinja", specter=app.specter, whitelisted_domains=config['whitelisted_domains'], rand=rand)
