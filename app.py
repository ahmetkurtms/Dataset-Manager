"""
Dataset Browser — tez_dataset
==============================
Browses the flat_dataset with metadata parsed from filenames.

Filename format: {original_stem}__{modality}__{class}__{obj_size}.ext
Dataset layout:  flat_dataset/{train,test,val}/{images,labels}/

Usage:
  python app.py                    # serve on port 5000
  python app.py --port 8080        # custom port
  python app.py --dataset ~/path   # custom dataset path
"""

import os
import sys
import re
import argparse
from flask import Flask, render_template_string, jsonify, send_from_directory, request

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

app = Flask(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

DEFAULT_DATASET = os.path.expanduser("~/Downloads/tez_dataset/flat_dataset")

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
SPLITS             = ['train', 'test', 'val']
MODALITIES         = ['rgb', 'thermal']
CLASSES            = ['airplane', 'bird', 'drone', 'helicopter']
OBJ_SIZES          = ['small', 'large']

DATASET_ROOT = DEFAULT_DATASET  # will be set by argparse

# ── Filename parsing ─────────────────────────────────────────────────────────
# Pattern: {stem}__{modality}__{class}__{obj_size}.ext

METADATA_PATTERN = re.compile(
    r'^(.+)__(' + '|'.join(MODALITIES) + r')__(' + '|'.join(CLASSES) + r')__(' + '|'.join(OBJ_SIZES) + r')$'
)

def parse_filename(filename: str) -> dict | None:
    """Parse modality, class, and obj_size from filename."""
    base = os.path.splitext(filename)[0]
    m = METADATA_PATTERN.match(base)
    if m:
        return {
            'original_stem': m.group(1),
            'modality':      m.group(2),
            'class':         m.group(3),
            'obj_size':      m.group(4),
        }
    return None


# ── Image scanning ───────────────────────────────────────────────────────────

def scan_split(split: str) -> list[dict]:
    """Scan a single split (train/test/val) and return image metadata."""
    img_dir = os.path.join(DATASET_ROOT, split, 'images')
    lbl_dir = os.path.join(DATASET_ROOT, split, 'labels')
    results = []

    if not os.path.isdir(img_dir):
        return results

    for fname in sorted(os.listdir(img_dir)):
        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        full_path = os.path.join(img_dir, fname)
        meta = parse_filename(fname)

        # Label file
        base = os.path.splitext(fname)[0]
        lbl_path = os.path.join(lbl_dir, base + '.txt') if os.path.isdir(lbl_dir) else None
        has_label = lbl_path and os.path.exists(lbl_path)

        results.append({
            'path':      os.path.join(split, 'images', fname),
            'name':      fname,
            'split':     split,
            'modality':  meta['modality']  if meta else 'unknown',
            'class':     meta['class']     if meta else 'unknown',
            'obj_size':  meta['obj_size']  if meta else 'unknown',
            'has_label': has_label,
        })

    return results


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/images')
def api_images():
    split    = request.args.get('split', '')
    modality = request.args.get('modality', '')
    cls      = request.args.get('class', '')
    obj_size = request.args.get('obj_size', '')

    splits_to_scan = [split] if split and split in SPLITS else SPLITS
    all_imgs = []
    for s in splits_to_scan:
        all_imgs.extend(scan_split(s))

    if modality:
        all_imgs = [i for i in all_imgs if i['modality'] == modality]
    if cls:
        all_imgs = [i for i in all_imgs if i['class'] == cls]
    if obj_size:
        all_imgs = [i for i in all_imgs if i['obj_size'] == obj_size]

    return jsonify(all_imgs)

@app.route('/api/stats')
def api_stats():
    all_imgs = []
    for s in SPLITS:
        all_imgs.extend(scan_split(s))

    stats = {
        'total': len(all_imgs),
        'by_split':    {},
        'by_modality': {},
        'by_class':    {},
        'by_obj_size': {},
        'combos':      {},
    }
    # Init all 16 combos
    for mod in MODALITIES:
        for cls in CLASSES:
            for obj in OBJ_SIZES:
                stats['combos'][f"{mod}__{cls}__{obj}"] = 0

    for img in all_imgs:
        for dim, key in [('by_split', 'split'), ('by_modality', 'modality'),
                         ('by_class', 'class'), ('by_obj_size', 'obj_size')]:
            val = img[key]
            stats[dim][val] = stats[dim].get(val, 0) + 1
        combo_key = f"{img['modality']}__{img['class']}__{img['obj_size']}"
        if combo_key in stats['combos']:
            stats['combos'][combo_key] += 1
    return jsonify(stats)

@app.route('/image/<path:filepath>')
def serve_image(filepath):
    directory = os.path.dirname(filepath)
    filename  = os.path.basename(filepath)
    return send_from_directory(os.path.join(DATASET_ROOT, directory), filename)

@app.route('/api/labels/<path:filepath>')
def api_labels(filepath):
    # images/ → labels/
    label_path = os.path.join(DATASET_ROOT, filepath.replace('/images/', '/labels/'))
    label_path = os.path.splitext(label_path)[0] + '.txt'

    labels = []
    if os.path.exists(label_path):
        try:
            with open(label_path) as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) >= 5:
                        labels.append({
                            'class': int(p[0]),
                            'x': float(p[1]), 'y': float(p[2]),
                            'w': float(p[3]), 'h': float(p[4]),
                        })
        except Exception:
            pass
    return jsonify(labels)

@app.route('/api/delete/<path:filepath>', methods=['DELETE'])
def api_delete(filepath):
    full = os.path.join(DATASET_ROOT, filepath)
    if not os.path.exists(full):
        return jsonify({'error': 'Not found'}), 404
    try:
        os.remove(full)
        # Remove label too
        lbl = os.path.join(DATASET_ROOT, filepath.replace('/images/', '/labels/'))
        lbl = os.path.splitext(lbl)[0] + '.txt'
        if os.path.exists(lbl):
            os.remove(lbl)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═════════════════════════════════════════════════════════════════════════════
#  HTML TEMPLATE
# ═════════════════════════════════════════════════════════════════════════════

HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dataset Browser</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f1117; color: #e0e0e0; display: flex; flex-direction: column; height: 100vh; }

/* ── Top bar ───────────────────────────────────── */
.top-bar { background: #161822; border-bottom: 1px solid #2a2d3a;
           padding: 12px 20px; display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.top-bar h1 { font-size: 18px; color: #7cacf8; margin-right: 12px; }

/* Filter pills */
.filter-group { display: flex; align-items: center; gap: 6px; }
.filter-label { font-size: 11px; color: #666; text-transform: uppercase; }
.filter-btn { font-size: 12px; padding: 4px 12px; border-radius: 16px; border: 1px solid #2a2d3a;
              background: #1a1d2b; color: #a0a8c8; cursor: pointer; transition: all 0.15s; }
.filter-btn:hover { border-color: #4a5070; }
.filter-btn.active { background: #263154; border-color: #4a6bb8; color: #7cacf8; }

/* Stats pills */
.stat-pill { font-size: 11px; padding: 3px 10px; border-radius: 10px;
             background: #1e2233; color: #a0a8c8; }
.stat-pill.total { background: #263154; color: #7cacf8; font-weight: 600; }

/* ── Gallery ───────────────────────────────────── */
.gallery-header { padding: 10px 20px; border-bottom: 1px solid #1a1d2b;
                  display: flex; align-items: center; gap: 12px; }
.gallery-header h3 { font-size: 14px; color: #888; }
.img-count { font-size: 12px; color: #555; }

.gallery { flex: 1; overflow-y: auto; padding: 16px;
           display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
           gap: 12px; align-content: start; }
.gallery-empty { grid-column: 1/-1; text-align: center; color: #444; padding: 60px; font-size: 14px; }

.image-card { background: #1a1d2b; border-radius: 10px;
              cursor: pointer; transition: transform 0.15s, box-shadow 0.15s;
              border: 1px solid #2a2d3a; display: flex; flex-direction: column; }
.image-card:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
.image-card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block;
                  min-height: 150px; background: #222; border-radius: 10px 10px 0 0; }
.card-info { padding: 8px 10px; }
.card-name { font-size: 10px; color: #555; white-space: nowrap; overflow: hidden;
             text-overflow: ellipsis; margin-bottom: 5px; }
.card-badges { display: flex; flex-wrap: wrap; gap: 3px; }
.badge { font-size: 10px; padding: 2px 7px; border-radius: 3px;
         font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px; }
.badge.mod-rgb      { background: #1565c0; color: #fff; }
.badge.mod-thermal  { background: #e65100; color: #fff; }
.badge.cls-airplane { background: #6a1b9a; color: #fff; }
.badge.cls-bird     { background: #00796b; color: #fff; }
.badge.cls-drone    { background: #c62828; color: #fff; }
.badge.cls-helicopter { background: #ef6c00; color: #fff; }
.badge.obj-small    { background: #4e342e; color: #fff; }
.badge.obj-large    { background: #283593; color: #fff; }
.card-dims { font-size: 10px; color: #444; margin-top: 3px; }

/* ── Combo Grid ────────────────────────────────── */
.combo-section { background: #161822; border-bottom: 1px solid #2a2d3a; padding: 10px 20px; }
.combo-section h3 { font-size: 13px; color: #888; margin-bottom: 8px; cursor: pointer; user-select: none; }
.combo-grid { display: grid; grid-template-columns: 140px repeat(4, 1fr); gap: 2px; }
.combo-header { font-size: 11px; color: #7cacf8; text-align: center; padding: 4px; font-weight: 600;
                text-transform: uppercase; }
.combo-row-label { font-size: 11px; color: #a0a8c8; padding: 6px 8px; display: flex;
                   align-items: center; gap: 4px; }
.combo-cell { text-align: center; padding: 6px 4px; border-radius: 4px; font-size: 12px;
              font-weight: 600; cursor: pointer; transition: all 0.15s; position: relative; }
.combo-cell:hover { transform: scale(1.05); }
.combo-cell.has-data { background: #1e2233; color: #e0e0e0; }
.combo-cell.zero { background: #1a1a22; color: #444; }

/* ── Modal ─────────────────────────────────────── */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.88);
                 z-index:100; justify-content:center; align-items:center; }
.modal-overlay.active { display:flex; }
.modal-box { max-width:92vw; max-height:92vh; display:flex; flex-direction:column;
             position:relative; }
.modal-info-bar { display:flex; gap:10px; align-items:center; padding:8px 0; flex-wrap:wrap; }
.modal-info-bar span { font-size:12px; color:#aaa; }
.modal-info-bar .badge { font-size:11px; }
.modal-canvas-wrap { position:relative; display:inline-block; }
.modal-canvas-wrap img { max-width:90vw; max-height:72vh; object-fit:contain; border-radius:6px; display:block; }
.modal-canvas-wrap canvas { position:absolute; top:0; left:0; pointer-events:none; }
.modal-controls { display:flex; gap:10px; padding:10px 0; justify-content:center; }
.modal-controls button { padding:8px 20px; border:none; border-radius:6px; cursor:pointer;
                          font-size:13px; font-weight:600; transition:all 0.15s; }
.btn-nav { background:#2a2d3a; color:#e0e0e0; }
.btn-nav:hover { background:#3a3d4a; }
.btn-delete { background:#b71c1c; color:#fff; }
.btn-delete:hover { background:#e53935; }
.close-btn { position:absolute; top:-30px; right:0; background:none; border:none;
             color:#888; font-size:26px; cursor:pointer; }
.close-btn:hover { color:#fff; }
.img-counter { font-size:13px; color:#666; padding:0 12px; line-height:36px; }
</style>
</head>
<body>

<!-- Top bar: filters + stats -->
<div class="top-bar">
    <h1>📁 Dataset Browser</h1>
    <div id="statsArea" style="display:flex;gap:8px;flex-wrap:wrap;"></div>
    <div style="flex:1;"></div>
</div>

<div class="top-bar" style="border-top:none;padding-top:0;">
    <!-- Split filter -->
    <div class="filter-group">
        <span class="filter-label">Split</span>
        <button class="filter-btn active" data-filter="split" data-value="" onclick="setFilter(this)">All</button>
        <button class="filter-btn" data-filter="split" data-value="train" onclick="setFilter(this)">Train</button>
        <button class="filter-btn" data-filter="split" data-value="test" onclick="setFilter(this)">Test</button>
        <button class="filter-btn" data-filter="split" data-value="val" onclick="setFilter(this)">Val</button>
    </div>
    <!-- Modality filter -->
    <div class="filter-group">
        <span class="filter-label">Modality</span>
        <button class="filter-btn active" data-filter="modality" data-value="" onclick="setFilter(this)">All</button>
        <button class="filter-btn" data-filter="modality" data-value="rgb" onclick="setFilter(this)">RGB</button>
        <button class="filter-btn" data-filter="modality" data-value="thermal" onclick="setFilter(this)">Thermal</button>
    </div>
    <!-- Class filter -->
    <div class="filter-group">
        <span class="filter-label">Class</span>
        <button class="filter-btn active" data-filter="class" data-value="" onclick="setFilter(this)">All</button>
        <button class="filter-btn" data-filter="class" data-value="airplane" onclick="setFilter(this)">Airplane</button>
        <button class="filter-btn" data-filter="class" data-value="bird" onclick="setFilter(this)">Bird</button>
        <button class="filter-btn" data-filter="class" data-value="drone" onclick="setFilter(this)">Drone</button>
        <button class="filter-btn" data-filter="class" data-value="helicopter" onclick="setFilter(this)">Helicopter</button>
    </div>
    <!-- Object Size filter -->
    <div class="filter-group">
        <span class="filter-label">Obj Size</span>
        <button class="filter-btn active" data-filter="obj_size" data-value="" onclick="setFilter(this)">All</button>
        <button class="filter-btn" data-filter="obj_size" data-value="small" onclick="setFilter(this)">Small</button>
        <button class="filter-btn" data-filter="obj_size" data-value="large" onclick="setFilter(this)">Large</button>
    </div>
</div>

<!-- 16 Combo Grid -->
<div class="combo-section">
    <h3 onclick="document.getElementById('comboGrid').style.display = document.getElementById('comboGrid').style.display === 'none' ? 'grid' : 'none'">
        📊 16 Combinations (click to toggle)
    </h3>
    <div class="combo-grid" id="comboGrid"></div>
</div>

<!-- Gallery -->
<div class="gallery-header">
    <h3 id="filterDesc">All Images</h3>
    <span class="img-count" id="imgCount"></span>
</div>
<div class="gallery" id="gallery">
    <div class="gallery-empty">Loading…</div>
</div>

<!-- Modal -->
<div class="modal-overlay" id="modal">
    <button class="close-btn" onclick="closeModal()">&times;</button>
    <div class="modal-box">
        <div class="modal-info-bar" id="modalInfo"></div>
        <div class="modal-canvas-wrap">
            <img id="modalImg" src="" alt="">
            <canvas id="modalCanvas"></canvas>
        </div>
        <div class="modal-controls">
            <button class="btn-nav" onclick="navImage(-1)">← Prev</button>
            <span class="img-counter" id="modalCounter"></span>
            <button class="btn-delete" onclick="deleteImage()">🗑 Delete</button>
            <span class="img-counter"></span>
            <button class="btn-nav" onclick="navImage(1)">Next →</button>
        </div>
    </div>
</div>

<script>
let allImages = [];
let currentIdx = -1;
let filters = { split: '', modality: '', 'class': '', obj_size: '' };

const CLS_COLORS = { airplane:'#6a1b9a', bird:'#00796b', drone:'#c62828', helicopter:'#ef6c00' };
const CLS_NAMES  = ['airplane','bird','drone','helicopter'];

// ── Filters ───────────────────────────────────────────
function setFilter(btn) {
    const group = btn.dataset.filter;
    const value = btn.dataset.value;
    filters[group] = value;

    // Update active state
    btn.closest('.filter-group').querySelectorAll('.filter-btn')
        .forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // Update description
    const parts = [];
    if (filters.split) parts.push(filters.split);
    if (filters.modality) parts.push(filters.modality);
    if (filters['class']) parts.push(filters['class']);
    if (filters.obj_size) parts.push(filters.obj_size + ' obj');
    document.getElementById('filterDesc').textContent = parts.length ? parts.join(' · ') : 'All Images';

    loadImages();
}

// ── Stats ─────────────────────────────────────────────
async function loadStats() {
    const r = await fetch('/api/stats');
    const s = await r.json();
    const area = document.getElementById('statsArea');
    let html = `<span class="stat-pill total">${s.total} total</span>`;
    for (const [title, data] of [['split', s.by_split], ['mod', s.by_modality],
                                  ['class', s.by_class], ['obj', s.by_obj_size]]) {
        for (const [k, v] of Object.entries(data).sort()) {
            html += `<span class="stat-pill">${k}: ${v}</span>`;
        }
    }
    area.innerHTML = html;
    renderComboGrid(s.combos);
}

function renderComboGrid(combos) {
    const grid = document.getElementById('comboGrid');
    const classes  = ['airplane', 'bird', 'drone', 'helicopter'];
    const mods     = ['rgb', 'thermal'];
    const objs     = ['small', 'large'];

    let html = '<div class="combo-header"></div>';
    classes.forEach(c => { html += `<div class="combo-header">${c}</div>`; });

    for (const mod of mods) {
        for (const obj of objs) {
            html += `<div class="combo-row-label">
                <span class="badge mod-${mod}" style="font-size:9px;padding:1px 4px">${mod}</span>
                <span class="badge obj-${obj}" style="font-size:9px;padding:1px 4px">${obj}</span>
            </div>`;
            for (const cls of classes) {
                const key = `${mod}__${cls}__${obj}`;
                const val = combos[key] || 0;
                const cellClass = val > 0 ? 'has-data' : 'zero';
                html += `<div class="combo-cell ${cellClass}" onclick="filterCombo('${mod}','${cls}','${obj}')" title="${mod} · ${cls} · ${obj}">${val}</div>`;
            }
        }
    }
    grid.innerHTML = html;
}

function filterCombo(mod, cls, obj) {
    filters.modality = mod;
    filters['class'] = cls;
    filters.obj_size = obj;
    // Update filter button states
    document.querySelectorAll('.filter-btn').forEach(btn => {
        const f = btn.dataset.filter;
        const v = btn.dataset.value;
        btn.classList.toggle('active', filters[f] === v);
    });
    document.getElementById('filterDesc').textContent = `${mod} · ${cls} · ${obj} obj`;
    loadImages();
}

// ── Gallery ───────────────────────────────────────────
async function loadImages() {
    document.getElementById('gallery').innerHTML = '<div class="gallery-empty">Loading…</div>';

    const params = new URLSearchParams();
    if (filters.split) params.set('split', filters.split);
    if (filters.modality) params.set('modality', filters.modality);
    if (filters['class']) params.set('class', filters['class']);
    if (filters.obj_size) params.set('obj_size', filters.obj_size);

    try {
        const r = await fetch(`/api/images?${params}`);
        allImages = await r.json();
        document.getElementById('imgCount').textContent = `${allImages.length} images`;
        renderGallery();
    } catch(e) {
        console.error('Load error', e);
    }
}

function renderGallery() {
    const gallery = document.getElementById('gallery');
    if (allImages.length === 0) {
        gallery.innerHTML = '<div class="gallery-empty">No images match the current filters</div>';
        return;
    }
    gallery.innerHTML = '';
    allImages.forEach((img, i) => {
        const card = document.createElement('div');
        card.className = 'image-card';
        card.onclick = () => openModal(i);

        card.innerHTML = `
            <img src="/image/${img.path}" loading="lazy" alt="">
            <div class="card-info">
                <div class="card-name" title="${img.name}">${img.name}</div>
                <div class="card-badges">
                    <span class="badge mod-${img.modality}">${img.modality}</span>
                    <span class="badge cls-${img.class}">${img.class}</span>
                    <span class="badge obj-${img.obj_size}">${img.obj_size} obj</span>
                </div>
            </div>`;
        gallery.appendChild(card);
    });
}

// ── Modal ─────────────────────────────────────────────
function openModal(idx) {
    if (idx < 0 || idx >= allImages.length) return;
    currentIdx = idx;
    const img = allImages[idx];
    const modal = document.getElementById('modal');
    const modalImg = document.getElementById('modalImg');
    const canvas = document.getElementById('modalCanvas');
    const ctx = canvas.getContext('2d');

    // Info bar
    let info = `<span>${img.name}</span>`;
    info += `<span class="badge mod-${img.modality}">${img.modality}</span>`;
    info += `<span class="badge cls-${img.class}">${img.class}</span>`;
    info += `<span class="badge obj-${img.obj_size}">${img.obj_size} obj</span>`;
    info += `<span style="color:#555">${img.split}</span>`;
    document.getElementById('modalInfo').innerHTML = info;
    document.getElementById('modalCounter').textContent = `${idx+1} / ${allImages.length}`;

    modalImg.src = `/image/${img.path}`;
    modal.classList.add('active');

    modalImg.onload = async () => {
        canvas.width = modalImg.width;
        canvas.height = modalImg.height;
        canvas.style.width = modalImg.width + 'px';
        canvas.style.height = modalImg.height + 'px';
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        try {
            const lr = await fetch(`/api/labels/${img.path}`);
            const labels = await lr.json();
            if (Array.isArray(labels)) drawLabels(ctx, labels, modalImg.width, modalImg.height);
        } catch(e) {}
    };
}

function drawLabels(ctx, labels, W, H) {
    ctx.lineWidth = 2;
    ctx.font = '13px Arial';
    labels.forEach(l => {
        const x=(l.x-l.w/2)*W, y=(l.y-l.h/2)*H, w=l.w*W, h=l.h*H;
        const name  = CLS_NAMES[l.class] || `cls ${l.class}`;
        const color = CLS_COLORS[name] || '#00ff00';
        ctx.strokeStyle = color;
        ctx.strokeRect(x, y, w, h);
        const txt = `${name} ${(l.w*l.h*100).toFixed(1)}%`;
        const tw = ctx.measureText(txt).width;
        ctx.fillStyle = color; ctx.fillRect(x, y-18, tw+6, 18);
        ctx.fillStyle = '#fff'; ctx.fillText(txt, x+3, y-4);
    });
}

function closeModal() { document.getElementById('modal').classList.remove('active'); currentIdx = -1; }
function navImage(d) { openModal(currentIdx + d); }

async function deleteImage() {
    if (currentIdx === -1) return;
    if (!confirm('Delete this image and its label?')) return;
    const img = allImages[currentIdx];
    const r = await fetch(`/api/delete/${img.path}`, { method: 'DELETE' });
    const res = await r.json();
    if (res.success) {
        allImages.splice(currentIdx, 1);
        renderGallery();
        loadStats();
        if (allImages.length === 0) closeModal();
        else if (currentIdx >= allImages.length) openModal(currentIdx - 1);
        else openModal(currentIdx);
    } else alert('Error: ' + res.error);
}

// ── Keyboard ──────────────────────────────────────────
document.addEventListener('keydown', e => {
    if (!document.getElementById('modal').classList.contains('active')) return;
    if (e.key === 'Escape') closeModal();
    if (e.key === 'ArrowRight') navImage(1);
    if (e.key === 'ArrowLeft') navImage(-1);
    if (e.key === 'Delete') deleteImage();
});

// ── Init ──────────────────────────────────────────────
loadImages();
loadStats();
</script>
</body>
</html>
"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    global DATASET_ROOT

    parser = argparse.ArgumentParser(description="Dataset Browser — tez_dataset")
    parser.add_argument('--dataset', default=DEFAULT_DATASET, help=f'Dataset root (default: {DEFAULT_DATASET})')
    parser.add_argument('--port', type=int, default=5000, help='Server port (default: 5000)')

    args = parser.parse_args()
    DATASET_ROOT = os.path.expanduser(args.dataset)

    if not os.path.isdir(DATASET_ROOT):
        print(f"❌ Dataset not found: {DATASET_ROOT}")
        sys.exit(1)

    # Count images
    total = 0
    for s in SPLITS:
        img_dir = os.path.join(DATASET_ROOT, s, 'images')
        if os.path.isdir(img_dir):
            total += sum(1 for f in os.listdir(img_dir)
                        if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS)

    print(f"📁 Dataset: {DATASET_ROOT}")
    print(f"🖼  Images:  {total}")
    print(f"🌐 http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=True, threaded=True)


if __name__ == '__main__':
    main()
