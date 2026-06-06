import argparse
import secrets
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import (Flask, jsonify, redirect, render_template_string,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

SHARED = Path(__file__).parent / "shared"

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
SHARED.mkdir(exist_ok=True)

PASSWORD_HASH = None  # set at startup when --password is given


def login_required(json_api=False):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if PASSWORD_HASH and not session.get("authenticated"):
                if json_api:
                    return jsonify(error="Not authenticated"), 401
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


LOGIN_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MiniCloud — Login</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
</head>
<body class="bg-light d-flex align-items-center" style="min-height:100vh">
<div class="container" style="max-width:360px">
  <h2 class="mb-4 fw-bold text-center">&#x2601; MiniCloud</h2>
  {% if error %}
  <div class="alert alert-danger py-2">{{ error }}</div>
  {% endif %}
  <div class="card shadow-sm">
    <div class="card-body p-4">
      <form method="post">
        <div class="mb-3">
          <label class="form-label fw-semibold">Password</label>
          <input type="password" name="password" class="form-control" autofocus required>
        </div>
        <button type="submit" class="btn btn-primary w-100">Sign in</button>
      </form>
    </div>
  </div>
</div>
</body>
</html>"""


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MiniCloud</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
  <style>
    #drop-zone {
      border: 2px dashed #adb5bd;
      border-radius: .5rem;
      padding: 2.5rem 1rem;
      text-align: center;
      cursor: pointer;
      transition: background .15s, border-color .15s;
      user-select: none;
    }
    #drop-zone.over { background: #eef3ff; border-color: #0d6efd; }
  </style>
</head>
<body class="bg-light">
<div class="container py-5" style="max-width:860px">
  <div class="d-flex justify-content-between align-items-center mb-4">
    <h2 class="fw-bold mb-0">&#x2601; MiniCloud</h2>
    {% if authenticated %}
    <form method="post" action="/logout" class="mb-0">
      <button class="btn btn-outline-secondary btn-sm">Sign out</button>
    </form>
    {% endif %}
  </div>

  <div id="drop-zone" class="mb-3">
    <div class="fs-5 mb-1">Drop a file here</div>
    <div class="text-muted small mb-2">or click to browse</div>
    <input id="file-input" type="file" class="d-none">
    <button class="btn btn-outline-secondary btn-sm"
            onclick="event.stopPropagation();document.getElementById('file-input').click()">
      Browse&hellip;
    </button>
  </div>

  <div id="prog-wrap" class="mb-3 d-none">
    <div class="progress mb-1" style="height:20px">
      <div id="prog-bar" class="progress-bar progress-bar-striped progress-bar-animated"
           role="progressbar" style="width:0%"></div>
    </div>
    <small id="prog-label" class="text-muted"></small>
  </div>

  <div id="msg-box" class="mb-3"></div>

  <div class="card shadow-sm">
    <div class="card-header d-flex align-items-center gap-2">
      <strong>shared/</strong>
      <span id="file-count" class="badge bg-secondary">{{ files|length }}</span>
    </div>
    <table class="table table-hover mb-0">
      <thead class="table-light">
        <tr>
          <th>Name</th><th>Size</th><th>Modified</th><th></th>
        </tr>
      </thead>
      <tbody id="file-tbody">
        {% if not files %}
        <tr id="empty-row">
          <td colspan="4" class="text-muted py-3 text-center">No files yet</td>
        </tr>
        {% endif %}
        {% for f in files %}
        <tr data-name="{{ f.name }}">
          <td class="align-middle">{{ f.name }}</td>
          <td class="align-middle text-muted">{{ f.size }}</td>
          <td class="align-middle text-muted">{{ f.modified }}</td>
          <td class="text-end align-middle">
            <a href="/download/{{ f.name }}"
               class="btn btn-sm btn-outline-primary me-1">Download</a>
            <button class="btn btn-sm btn-outline-danger"
                    data-name="{{ f.name }}"
                    onclick="del(this.dataset.name, this)">Delete</button>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<script>
const zone  = document.getElementById('drop-zone');
const input = document.getElementById('file-input');

zone.addEventListener('click', () => input.click());
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
zone.addEventListener('dragleave', () => zone.classList.remove('over'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('over');
  const f = e.dataTransfer.files[0];
  if (f) upload(f);
});
input.addEventListener('change', () => { if (input.files[0]) upload(input.files[0]); });

function showMsg(html, type) {
  document.getElementById('msg-box').innerHTML =
    `<div class="alert alert-${type} alert-dismissible fade show py-2" role="alert">
       ${html}
       <button type="button" class="btn-close py-2" data-bs-dismiss="alert"></button>
     </div>`;
}

function upload(file) {
  const wrap = document.getElementById('prog-wrap');
  const bar  = document.getElementById('prog-bar');
  const lbl  = document.getElementById('prog-label');
  wrap.classList.remove('d-none');
  bar.style.width = '0%';
  lbl.textContent = 'Uploading ' + file.name + '…';

  const fd = new FormData();
  fd.append('file', file);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/upload');
  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const pct = Math.round(e.loaded / e.total * 100);
      bar.style.width = pct + '%';
      lbl.textContent = file.name + ' — ' + pct + '%';
    }
  };
  xhr.onload = () => {
    wrap.classList.add('d-none');
    input.value = '';
    const data = JSON.parse(xhr.responseText);
    if (xhr.status === 200) {
      addRow(data.name, data.size, data.modified);
      showMsg('<strong>' + esc(data.name) + '</strong> uploaded successfully.', 'success');
    } else {
      showMsg(esc(data.error || 'Upload failed.'), 'danger');
    }
  };
  xhr.onerror = () => { wrap.classList.add('d-none'); showMsg('Upload failed.', 'danger'); };
  xhr.send(fd);
}

function addRow(name, size, modified) {
  const tbody = document.getElementById('file-tbody');
  const empty = document.getElementById('empty-row');
  if (empty) empty.remove();
  const existing = tbody.querySelector('tr[data-name="' + CSS.escape(name) + '"]');
  if (existing) existing.remove();
  const tr = document.createElement('tr');
  tr.dataset.name = name;
  tr.innerHTML =
    '<td class="align-middle">' + esc(name) + '</td>' +
    '<td class="align-middle text-muted">' + esc(size) + '</td>' +
    '<td class="align-middle text-muted">' + esc(modified) + '</td>' +
    '<td class="text-end align-middle">' +
      '<a href="/download/' + encodeURIComponent(name) +
         '" class="btn btn-sm btn-outline-primary me-1">Download</a>' +
      '<button class="btn btn-sm btn-outline-danger"' +
              ' data-name="' + esc(name) + '"' +
              ' onclick="del(this.dataset.name, this)">Delete</button>' +
    '</td>';
  tbody.appendChild(tr);
  updateCount();
}

function del(name, btn) {
  if (!confirm('Delete "' + name + '"?')) return;
  btn.disabled = true;
  fetch('/delete/' + encodeURIComponent(name), { method: 'POST' })
    .then(r => {
      if (r.ok) {
        btn.closest('tr').remove();
        updateCount();
        const tbody = document.getElementById('file-tbody');
        if (!tbody.querySelector('tr')) {
          tbody.innerHTML =
            '<tr id="empty-row"><td colspan="4" class="text-muted py-3 text-center">No files yet</td></tr>';
        }
      } else {
        btn.disabled = false;
      }
    })
    .catch(() => { btn.disabled = false; });
}

function updateCount() {
  const n = document.getElementById('file-tbody')
              .querySelectorAll('tr:not(#empty-row)').length;
  document.getElementById('file-count').textContent = n;
}

function esc(s) {
  return s.replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;');
}
</script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PASSWORD_HASH:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        if check_password_hash(PASSWORD_HASH, request.form.get("password", "")):
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = "Incorrect password."
    return render_template_string(LOGIN_TEMPLATE, error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required()
def index():
    files = []
    for p in sorted(SHARED.iterdir()):
        if p.is_file():
            st = p.stat()
            files.append({
                "name": p.name,
                "size": fmt_size(st.st_size),
                "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
    return render_template_string(TEMPLATE, files=files, authenticated=bool(PASSWORD_HASH))


@app.route("/upload", methods=["POST"])
@login_required(json_api=True)
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="No file provided"), 400
    filename = secure_filename(f.filename)
    if not filename:
        return jsonify(error="Invalid filename"), 400
    dest = SHARED / filename
    f.save(dest)
    st = dest.stat()
    return jsonify(
        ok=True,
        name=filename,
        size=fmt_size(st.st_size),
        modified=datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/download/<path:filename>")
@login_required()
def download(filename):
    return send_from_directory(SHARED, secure_filename(filename), as_attachment=True)


@app.route("/delete/<path:filename>", methods=["POST"])
@login_required(json_api=True)
def delete(filename):
    target = SHARED / secure_filename(filename)
    if target.is_file():
        target.unlink()
    return ("", 204)


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser(description="MiniCloud — local network file server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--password", default=os.environ.get("MINICLOUD_PASSWORD"),
                        help="Password to protect the site (or set MINICLOUD_PASSWORD env var)")
    args = parser.parse_args()
    if args.password:
        PASSWORD_HASH = generate_password_hash(args.password)
        print("MiniCloud: password protection enabled")
    else:
        print("MiniCloud: running without password protection")
    print(f"MiniCloud running on http://0.0.0.0:{args.port}  (serving from {SHARED})")
    app.run(host="0.0.0.0", port=args.port, debug=False)
