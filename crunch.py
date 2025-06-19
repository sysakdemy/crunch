#!/usr/bin/env python3
"""
Crunch Web - Application web pour tester l'autoscaling Kubernetes
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import threading
import multiprocessing
import time
import psutil
import json
from datetime import datetime
import os
import signal
import sys

app = Flask(__name__)

# État global de l'application
class CrunchState:
    def __init__(self):
        self.is_running = False
        self.processes = []
        self.start_time = None
        self.duration = 0
        self.intensity = 0
        self.cores = 0
        self.stats = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'running_time': 0
        }

crunch_state = CrunchState()

def cpu_worker(worker_id, intensity, stop_event):
    """Worker qui consomme du CPU selon l'intensité définie"""
    print(f"Worker {worker_id} démarré avec intensité {intensity}%")
    
    intensity_ratio = intensity / 100.0
    
    while not stop_event.is_set():
        # Période d'activité
        start_time = time.time()
        work_duration = 0.1 * intensity_ratio
        
        while time.time() - start_time < work_duration and not stop_event.is_set():
            # Calculs intensifs pour charger le CPU
            for _ in range(10000):
                x = 3.14159 * 2.71828
                y = x ** 0.5
        
        # Période de repos
        if intensity_ratio < 1.0 and not stop_event.is_set():
            rest_duration = 0.1 * (1.0 - intensity_ratio)
            time.sleep(rest_duration)

def start_cpu_load(duration, intensity, cores):
    """Démarre le test de charge CPU"""
    global crunch_state
    
    if crunch_state.is_running:
        return False
    
    crunch_state.is_running = True
    crunch_state.start_time = datetime.now()
    crunch_state.duration = duration
    crunch_state.intensity = intensity
    crunch_state.cores = cores
    crunch_state.processes = []
    
    # Créer l'événement d'arrêt
    stop_event = threading.Event()
    
    # Créer et démarrer les processus workers
    for i in range(cores):
        process = multiprocessing.Process(
            target=cpu_worker, 
            args=(i+1, intensity, stop_event)
        )
        process.start()
        crunch_state.processes.append((process, stop_event))
    
    # Thread pour arrêter automatiquement après la durée
    def auto_stop():
        time.sleep(duration)
        stop_cpu_load()
    
    timer_thread = threading.Thread(target=auto_stop)
    timer_thread.daemon = True
    timer_thread.start()
    
    return True

def stop_cpu_load():
    """Arrête le test de charge CPU"""
    global crunch_state
    
    if not crunch_state.is_running:
        return
    
    crunch_state.is_running = False
    
    # Arrêter tous les processus
    for process, stop_event in crunch_state.processes:
        stop_event.set()
        if process.is_alive():
            process.terminate()
    
    # Attendre que les processus se terminent
    for process, _ in crunch_state.processes:
        process.join(timeout=5)
        if process.is_alive():
            process.kill()
    
    crunch_state.processes = []
    crunch_state.start_time = None

def update_stats():
    """Met à jour les statistiques système"""
    global crunch_state
    
    try:
        crunch_state.stats['cpu_percent'] = psutil.cpu_percent(interval=1)
        crunch_state.stats['memory_percent'] = psutil.virtual_memory().percent
        
        if crunch_state.is_running and crunch_state.start_time:
            elapsed = datetime.now() - crunch_state.start_time
            crunch_state.stats['running_time'] = elapsed.total_seconds()
        else:
            crunch_state.stats['running_time'] = 0
            
    except Exception as e:
        print(f"Erreur lors de la mise à jour des stats: {e}")

@app.route('/')
def index():
    """Page principale"""
    update_stats()
    return render_template('index.html', 
                         state=crunch_state, 
                         max_cores=multiprocessing.cpu_count())

@app.route('/start', methods=['POST'])
def start_load():
    """Démarre le test de charge"""
    try:
        duration = int(request.form.get('duration', 300))
        intensity = int(request.form.get('intensity', 80))
        cores = int(request.form.get('cores', multiprocessing.cpu_count()))
        
        # Validation
        if not (1 <= duration <= 3600):
            raise ValueError("Durée doit être entre 1 et 3600 secondes")
        if not (1 <= intensity <= 100):
            raise ValueError("Intensité doit être entre 1 et 100%")
        if not (1 <= cores <= multiprocessing.cpu_count()):
            raise ValueError(f"Nombre de cœurs doit être entre 1 et {multiprocessing.cpu_count()}")
        
        success = start_cpu_load(duration, intensity, cores)
        
        if success:
            return redirect(url_for('index'))
        else:
            return "Un test est déjà en cours", 400
            
    except Exception as e:
        return f"Erreur: {str(e)}", 400

@app.route('/stop', methods=['POST'])
def stop_load():
    """Arrête le test de charge"""
    stop_cpu_load()
    return redirect(url_for('index'))

@app.route('/api/stats')
def api_stats():
    """API pour récupérer les statistiques en temps réel"""
    update_stats()
    return jsonify({
        'is_running': crunch_state.is_running,
        'cpu_percent': crunch_state.stats['cpu_percent'],
        'memory_percent': crunch_state.stats['memory_percent'],
        'running_time': crunch_state.stats['running_time'],
        'config': {
            'duration': crunch_state.duration,
            'intensity': crunch_state.intensity,
            'cores': crunch_state.cores
        } if crunch_state.is_running else None
    })

@app.route('/health')
def health():
    """Endpoint de santé pour Kubernetes"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

def signal_handler(signum, frame):
    """Gestionnaire de signaux pour arrêt propre"""
    print("Signal reçu, arrêt de l'application...")
    stop_cpu_load()
    sys.exit(0)

# Template HTML intégré
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crunch - Test d'Autoscaling</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #333;
        }
        .container {
            background: white;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 600px;
            width: 90%;
        }
        h1 { color: #5a67d8; text-align: center; margin-bottom: 2rem; }
        .status {
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            text-align: center;
            font-weight: bold;
        }
        .status.running { background: #fed7d7; color: #c53030; }
        .status.stopped { background: #c6f6d5; color: #2d7d32; }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat {
            background: #f7fafc;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value { font-size: 1.5rem; font-weight: bold; color: #5a67d8; }
        .stat-label { font-size: 0.9rem; color: #666; margin-top: 0.5rem; }
        .form-group {
            margin-bottom: 1rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }
        input, select {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 1rem;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #5a67d8;
        }
        .button-group {
            display: flex;
            gap: 1rem;
            margin-top: 2rem;
        }
        button {
            flex: 1;
            padding: 1rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-start { background: #48bb78; color: white; }
        .btn-start:hover { background: #38a169; }
        .btn-stop { background: #f56565; color: white; }
        .btn-stop:hover { background: #e53e3e; }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 1rem;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #48bb78, #38a169);
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Crunch - Test d'Autoscaling</h1>
        
        <div class="status {{ 'running' if state.is_running else 'stopped' }}">
            {% if state.is_running %}
                ⚡ Test en cours - {{ state.intensity }}% sur {{ state.cores }} cœurs
            {% else %}
                ✅ Prêt pour un nouveau test
            {% endif %}
        </div>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{{ "%.1f"|format(state.stats.cpu_percent) }}%</div>
                <div class="stat-label">CPU</div>
            </div>
            <div class="stat">
                <div class="stat-value">{{ "%.1f"|format(state.stats.memory_percent) }}%</div>
                <div class="stat-label">Mémoire</div>
            </div>
            <div class="stat">
                <div class="stat-value">{{ max_cores }}</div>
                <div class="stat-label">Cœurs disponibles</div>
            </div>
            {% if state.is_running %}
            <div class="stat">
                <div class="stat-value">{{ "%.0f"|format(state.stats.running_time) }}s</div>
                <div class="stat-label">Temps écoulé</div>
            </div>
            {% endif %}
        </div>
        
        {% if state.is_running %}
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{ (state.stats.running_time / state.duration * 100) if state.duration > 0 else 0 }}%"></div>
            </div>
        {% endif %}
        
        <form method="POST" action="{{ url_for('start_load') if not state.is_running else url_for('stop_load') }}">
            {% if not state.is_running %}
            <div class="form-group">
                <label for="duration">Durée (secondes):</label>
                <input type="number" id="duration" name="duration" value="300" min="10" max="3600" required>
            </div>
            
            <div class="form-group">
                <label for="intensity">Intensité CPU (%):</label>
                <input type="range" id="intensity" name="intensity" value="80" min="1" max="100" 
                       oninput="document.getElementById('intensity-value').textContent = this.value + '%'">
                <div style="text-align: center; margin-top: 0.5rem;">
                    <span id="intensity-value">80%</span>
                </div>
            </div>
            
            <div class="form-group">
                <label for="cores">Nombre de cœurs:</label>
                <select id="cores" name="cores">
                    {% for i in range(1, max_cores + 1) %}
                    <option value="{{ i }}" {{ 'selected' if i == max_cores else '' }}>{{ i }} cœur{{ 's' if i > 1 else '' }}</option>
                    {% endfor %}
                </select>
            </div>
            {% endif %}
            
            <div class="button-group">
                {% if state.is_running %}
                <button type="submit" class="btn-stop">🛑 Arrêter le test</button>
                {% else %}
                <button type="submit" class="btn-start">🚀 Lancer le test</button>
                {% endif %}
            </div>
        </form>
    </div>
    
    <script>
        // Mise à jour automatique des statistiques
        if ({{ 'true' if state.is_running else 'false' }}) {
            setInterval(() => {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        if (!data.is_running) {
                            location.reload();
                        }
                    })
                    .catch(error => console.error('Erreur:', error));
            }, 2000);
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Créer le template
    os.makedirs('templates', exist_ok=True)
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(HTML_TEMPLATE)
    
    # Gestionnaire de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Lancer l'application
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"🚀 Crunch Web démarré sur http://{host}:{port}")
    print("Utilisez Ctrl+C pour arrêter")
    
    app.run(host=host, port=port, debug=False)