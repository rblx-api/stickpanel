from flask import Flask, render_template, request, jsonify, Response
from github import Github
import json
import secrets
import string
from datetime import datetime
import os

# ============================================================
# 🔥 CONFIGURACIÓN - USA VARIABLES DE ENTORNO
# ============================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = "rblx-api/stick-bot-sistema-de-keys"
PASSWORD_WEB = os.getenv("PASSWORD_WEB", "stick123")
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://stickpanel.up.railway.app")
# ============================================================

if not GITHUB_TOKEN:
    print("❌ Error: Falta GITHUB_TOKEN. Asegúrate de configurarlo en las variables de entorno.")
    exit(1)

app = Flask(__name__)

try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    print("✅ Conexión con GitHub exitosa")
except Exception as e:
    print("❌ Error conectando a GitHub:", e)

def leer_data():
    try:
        contenido = repo.get_contents("keys.json")
        data = json.loads(contenido.decoded_content)
        if "script_template" not in data:
            data["script_template"] = "-- 💜 Script personalizado de Stick\nprint('¡Hola! Este es tu script personalizado.')"
        if "keys" not in data:
            data["keys"] = {}
        return data
    except Exception as e:
        print(f"⚠️ Error al leer keys.json: {e}")
        return {"script_template": "-- 💜 Script personalizado de Stick\nprint('¡Hola Mundo!')", "keys": {}}

def guardar_data(data):
    try:
        contenido = repo.get_contents("keys.json")
        repo.update_file(contenido.path, "Actualizado desde Web", json.dumps(data, indent=2), contenido.sha)
        print("✅ Datos guardados en GitHub")
    except Exception as e:
        print(f"⚠️ No se encontró keys.json, creándolo: {e}")
        repo.create_file("keys.json", "Creado desde Web", json.dumps(data, indent=2))
        print("✅ keys.json creado")

def key_from_user_code(data, user_code):
    for key, info in data.get("keys", {}).items():
        if info.get("user_code") == user_code:
            return key
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    return jsonify(leer_data())

@app.route('/api/generate', methods=['POST'])
def generate_key():
    try:
        req = request.json
        script_name = req.get('script', 'default')
        duration = req.get('duration', '30 días')
        note = req.get('note', '')
        
        alphabet = string.ascii_uppercase + string.digits
        key = ''.join(secrets.choice(alphabet) for _ in range(16))
        key = '-'.join(key[i:i+4] for i in range(0, 16, 4))
        
        data = leer_data()
        data["keys"][key] = {
            "script": script_name,
            "activa": True,
            "redeemed_by": None,
            "user_code": None,
            "hwid": None,
            "duration": duration,
            "note": note,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        guardar_data(data)
        print(f"🔑 Clave generada: {key} para {script_name}")
        return jsonify({"success": True, "key": key})
    except Exception as e:
        print("❌ Error generando clave:", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/delete/<key>', methods=['DELETE'])
def delete_key(key):
    try:
        data = leer_data()
        if key in data["keys"]:
            del data["keys"][key]
            guardar_data(data)
            return jsonify({"success": True})
        return jsonify({"success": False}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/script', methods=['PUT'])
def update_script():
    try:
        req = request.json
        new_script = req.get('script', '')
        data = leer_data()
        data["script_template"] = new_script
        guardar_data(data)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# 🔥 RUTA /raw/<user_code> - UNIVERSAL
# ============================================================
@app.route('/raw/<user_code>')
def raw_script(user_code):
    data = leer_data()
    key = key_from_user_code(data, user_code)
    if not key:
        return Response("print('❌ Código inválido.')", mimetype='text/plain')
    
    bootstrap = f'''-- 💜 Stick Panel - Loader Universal
local url = "{WEB_BASE_URL}/raw/{user_code}"

local function get_script()
    local methods = {{
        function() return game:HttpGet(url) end,
        function() return syn.request({{Url = url, Method = "GET"}}).Body end,
        function() return http_request({{Url = url, Method = "GET"}}).Body end,
        function() return request({{Url = url, Method = "GET"}}).Body end,
    }}
    
    for _, method in ipairs(methods) do
        local success, result = pcall(method)
        if success and result then
            return result
        end
    end
    return nil
end

local script_content = get_script()
if script_content then
    local fn, err = loadstring(script_content)
    if fn then
        fn()
    else
        warn("❌ Error al cargar el script: " .. tostring(err))
        print("❌ Error: " .. tostring(err))
    end
else
    warn("❌ No se pudo descargar el script.")
    print("❌ Error: No se pudo descargar el script.")
end
'''
    return Response(bootstrap, mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)