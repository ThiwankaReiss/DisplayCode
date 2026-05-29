"""
download_server.py  —  CAN Log File Download / Delete Server
Port  : 5001
Usage : python download_server.py
Open  : http://<PI_IP>:5001/logs  on your phone browser
"""

import glob
import os
import re
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

LOG_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_valid_log_filename(filename):
    """Accept only csv_log.csv / csv_log1.csv / csv_log2.csv … (no path traversal)."""
    return bool(re.match(r'^csv_log\d*\.csv$', filename))


_DOWNLOAD_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Download Logs</title>
  <style>
    body     { font-family:sans-serif; background:#0a0f1e; color:#fff;
               max-width:520px; margin:40px auto; padding:0 16px; }
    h2       { color:#00d4ff; }
    .row     { display:flex; align-items:center; gap:8px; margin:10px 0 2px; }
    a.dl     { flex:1; background:#00d4ff; color:#000; text-decoration:none;
               padding:12px 14px; border-radius:8px;
               font-weight:bold; font-size:.95em; }
    button.del{ background:#c0392b; color:#fff; border:none; border-radius:8px;
               padding:12px 14px; font-size:.95em; cursor:pointer; }
    button.del:active { background:#922b21; }
    .meta    { font-size:.78em; color:#aaa; margin-bottom:8px; padding-left:2px; }
  </style>
</head>
<body>
  <h2>CAN Log Files</h2>
  {% for f in files %}
    <div class="row">
      <a class="dl" href="/download/{{ f.filename }}">&#8659; {{ f.filename }}</a>
      <button class="del" onclick="delFile('{{ f.filename }}')" title="Delete">&#128465;</button>
    </div>
    <div class="meta">{{ f.size_kb }} KB &nbsp;|&nbsp; {{ f.modified }}</div>
  {% endfor %}
  {% if not files %}<p>No log files found.</p>{% endif %}
  <script>
  function delFile(fn) {
    if (!confirm('Delete ' + fn + '?')) return;
    fetch('/delete-log', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filename: fn})
    })
    .then(r => r.json())
    .then(d => { if (d.deleted) location.reload(); else alert('Error: ' + (d.error || 'unknown')); })
    .catch(() => alert('Network error'));
  }
  </script>
</body>
</html>
"""


@app.route('/logs', methods=['GET'])
def download_page():
    files = glob.glob(os.path.join(LOG_DIR, "csv_log*.csv"))
    files.sort(key=os.path.getmtime, reverse=True)
    entries = [
        {
            "filename": os.path.basename(p),
            "size_kb":  round(os.path.getsize(p) / 1024.0, 1),
            "modified": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M"),
        }
        for p in files
    ]
    return render_template_string(_DOWNLOAD_PAGE, files=entries)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    if not _is_valid_log_filename(filename):
        return jsonify({"error": "invalid filename"}), 400
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404
    return send_file(path, as_attachment=True,
                     download_name=filename,
                     mimetype="text/csv")


@app.route('/delete-log', methods=['POST'])
def delete_log():
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    if not _is_valid_log_filename(filename):
        return jsonify({"error": "invalid filename"}), 400
    path = os.path.join(LOG_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404
    try:
        os.remove(path)
        print(f"[LOG] Deleted: {filename}")
        return jsonify({"deleted": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
