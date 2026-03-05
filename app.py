import os
import re
import sys
import shutil
import threading
from flask import Flask, render_template, jsonify, send_from_directory, request

app = Flask(__name__)

DATASET_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
SUBDIRS = ['train', 'test', 'valid', 'selected']

# ── Label taxonomy ───────────────────────────────────────────────────────────
MODALITIES   = ['rgb', 'thermal']
RESOLUTIONS  = ['small', 'large']
OBJECT_SIZES = ['small', 'large']
CLASSES      = ['airplane', 'bird', 'drone', 'helicopter']

# ── Targets (1000 total, balanced) ───────────────────────────────────────────
TOTAL_TARGET       = 1000
CLASS_TARGET       = TOTAL_TARGET // len(CLASSES)                                       # 250
MODALITY_TARGET    = TOTAL_TARGET // len(MODALITIES)                                    # 500
RESOLUTION_TARGET  = TOTAL_TARGET // len(RESOLUTIONS)                                   # 500
OBJ_SIZE_TARGET    = TOTAL_TARGET // len(OBJECT_SIZES)                                  # 500
COMBO_TARGET       = TOTAL_TARGET // (len(MODALITIES) * len(RESOLUTIONS) *
                                      len(OBJECT_SIZES) * len(CLASSES))                 # 31

# ── Thread-safe counter ──────────────────────────────────────────────────────
_counter_lock = threading.Lock()

os.makedirs(os.path.join(DATASET_ROOT, 'selected'), exist_ok=True)

# ── Filename helpers ─────────────────────────────────────────────────────────
# Format: img_{counter:04d}_{modality}_{resolution}res_{objsize}obj_{class}.ext
# Example: img_0023_rgb_smallres_largeobj_airplane.jpg
LABEL_PATTERN = re.compile(
    r'img_(\d+)_(rgb|thermal)_(small|large)res_(small|large)obj_(airplane|bird|drone|helicopter)\.'
)

def build_labeled_name(counter: int, modality: str, resolution: str,
                        obj_size: str, label_class: str, ext: str) -> str:
    return f"img_{counter:04d}_{modality}_{resolution}res_{obj_size}obj_{label_class}{ext}"

def parse_label_from_filename(filename: str):
    m = LABEL_PATTERN.search(filename)
    if m:
        return {
            'counter':    int(m.group(1)),
            'modality':   m.group(2),
            'resolution': m.group(3),
            'obj_size':   m.group(4),
            'class':      m.group(5),
        }
    return None

def get_next_counter() -> int:
    """Return the next unique counter, thread-safe."""
    with _counter_lock:
        selected_dir = os.path.join(DATASET_ROOT, 'selected')
        max_val = 0
        if os.path.exists(selected_dir):
            for f in os.listdir(selected_dir):
                m = re.match(r'img_(\d+)_', f)
                if m:
                    max_val = max(max_val, int(m.group(1)))
        return max_val + 1

def is_image_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def find_image_dir(folder: str) -> str:
    """train/images/ varsa onu, yoksa train/ klasörünün kendisini döndür."""
    sub = os.path.join(DATASET_ROOT, folder, 'images')
    if os.path.isdir(sub):
        return sub
    return os.path.join(DATASET_ROOT, folder)

def find_label_file(folder: str, base_name: str):
    """Önce train/labels/, sonra diğer klasikleri dene."""
    txt = base_name + '.txt'
    candidates = [
        os.path.join(DATASET_ROOT, folder, 'labels', txt),                       # train/labels/
        os.path.join(DATASET_ROOT, 'Labels', f'{folder}-labels', 'labels', txt), # Labels/train-labels/labels/
        os.path.join(DATASET_ROOT, 'Labels', f'{folder}-labels', txt),           # Labels/train-labels/
        os.path.join(DATASET_ROOT, folder, txt),                                  # düz train/
    ]
    return next((p for p in candidates if os.path.exists(p)), None)

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def list_images():
    folder = request.args.get('folder', 'train')
    if folder not in SUBDIRS:
        return jsonify({'error': 'Invalid folder'}), 400

    images = []
    img_dir = find_image_dir(folder)
    if os.path.exists(img_dir):
        try:
            files = sorted(f for f in os.listdir(img_dir) if is_image_file(f))
            for filename in files:
                full_path = os.path.join(img_dir, filename)
                # DATASET_ROOT'a göre göreli yol → /image/ ve /delete/ endpoint'leri için
                rel_path  = os.path.relpath(full_path, DATASET_ROOT)
                label     = parse_label_from_filename(filename)
                images.append({
                    'path':   rel_path,   # örn. train/images/foo.jpg  veya  train/foo.jpg
                    'name':   filename,
                    'folder': folder,
                    'size':   os.path.getsize(full_path),
                    'label':  label,
                })
        except OSError as e:
            print(f"Error accessing {img_dir}: {e}")

    return jsonify(images)

@app.route('/image/<path:filepath>')
def serve_image(filepath):
    directory = os.path.dirname(filepath)
    filename  = os.path.basename(filepath)
    return send_from_directory(os.path.join(DATASET_ROOT, directory), filename)

@app.route('/delete/<path:filepath>', methods=['DELETE'])
def delete_image(filepath):
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    full_path = os.path.join(DATASET_ROOT, filepath)
    if not os.path.exists(full_path):
        return jsonify({'error': 'File not found'}), 404

    folder    = parts[0]
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    try:
        os.remove(full_path)
        txt_path = find_label_file(folder, base_name)
        if txt_path:
            os.remove(txt_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/select/<path:filepath>', methods=['POST'])
def select_image(filepath):
    """Move an image to selected/ with a label-encoded filename."""
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    # Validate label payload
    data       = request.get_json(silent=True) or {}
    modality   = data.get('modality')
    resolution = data.get('resolution')
    obj_size   = data.get('obj_size')
    cls        = data.get('class')

    if modality not in MODALITIES:
        return jsonify({'error': f'Invalid modality: {modality}'}), 400
    if resolution not in RESOLUTIONS:
        return jsonify({'error': f'Invalid resolution: {resolution}'}), 400
    if obj_size not in OBJECT_SIZES:
        return jsonify({'error': f'Invalid obj_size: {obj_size}'}), 400
    if cls not in CLASSES:
        return jsonify({'error': f'Invalid class: {cls}'}), 400

    src_path = os.path.join(DATASET_ROOT, filepath)
    if not os.path.exists(src_path):
        return jsonify({'error': 'File not found'}), 404

    folder    = parts[0]
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    ext       = os.path.splitext(filepath)[1].lower()
    counter   = get_next_counter()
    new_name  = build_labeled_name(counter, modality, resolution, obj_size, cls, ext)
    dst_path  = os.path.join(DATASET_ROOT, 'selected', new_name)

    try:
        shutil.move(src_path, dst_path)
        src_txt = find_label_file(folder, base_name)
        if src_txt:
            shutil.move(src_txt, os.path.splitext(dst_path)[0] + '.txt')
        return jsonify({'success': True, 'new_name': new_name})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Return dataset collection progress for all 4 dimensions + 32 combos."""
    selected_dir = os.path.join(DATASET_ROOT, 'selected')

    stats = {
        'total':         0,
        'by_class':      {c: 0 for c in CLASSES},
        'by_modality':   {m: 0 for m in MODALITIES},
        'by_resolution': {r: 0 for r in RESOLUTIONS},
        'by_obj_size':   {s: 0 for s in OBJECT_SIZES},
        'combos':        {},
        'targets': {
            'total':      TOTAL_TARGET,
            'class':      CLASS_TARGET,
            'modality':   MODALITY_TARGET,
            'resolution': RESOLUTION_TARGET,
            'obj_size':   OBJ_SIZE_TARGET,
            'combo':      COMBO_TARGET,
        }
    }

    for mod in MODALITIES:
        for res in RESOLUTIONS:
            for obj in OBJECT_SIZES:
                for cls in CLASSES:
                    stats['combos'][f"{mod}_{res}_{obj}_{cls}"] = 0

    if os.path.exists(selected_dir):
        for fname in os.listdir(selected_dir):
            label = parse_label_from_filename(fname)
            if label:
                stats['total']                              += 1
                stats['by_class'][label['class']]           += 1
                stats['by_modality'][label['modality']]     += 1
                stats['by_resolution'][label['resolution']] += 1
                stats['by_obj_size'][label['obj_size']]     += 1
                key = (f"{label['modality']}_{label['resolution']}_"
                       f"{label['obj_size']}_{label['class']}")
                stats['combos'][key] += 1

    return jsonify(stats)

@app.route('/api/labels/<path:filepath>')
def get_labels(filepath):
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    folder    = parts[0]
    filename  = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]

    final_path = find_label_file(folder, base_name)

    labels = []
    if final_path:
        try:
            with open(final_path, 'r') as f:
                for line in f:
                    p = line.strip().split()
                    if len(p) >= 5:
                        labels.append({
                            'class': int(p[0]),
                            'x': float(p[1]), 'y': float(p[2]),
                            'w': float(p[3]), 'h': float(p[4]),
                        })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify(labels)

@app.route('/api/config')
def get_config():
    """Expose label taxonomy to the frontend."""
    return jsonify({
        'modalities':   MODALITIES,
        'resolutions':  RESOLUTIONS,
        'object_sizes': OBJECT_SIZES,
        'classes':      CLASSES,
    })

if __name__ == '__main__':
    port = 5000
    if '--port' in sys.argv:
        idx = sys.argv.index('--port')
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    print(f"Serving dataset from: {DATASET_ROOT}")
    print(f"Arayüz: http://localhost:{port}")
    print(f"LAN   : http://0.0.0.0:{port}  (ekip arkadaşları için)")
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
