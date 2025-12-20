import os
import shutil
import time
from flask import Flask, render_template, jsonify, send_from_directory, request, abort

app = Flask(__name__)

DATASET_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
SUBDIRS = ['train', 'test', 'valid', 'selected']

os.makedirs(os.path.join(DATASET_ROOT, 'selected'), exist_ok=True)

def is_image_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/images')
def list_images():
    folder = request.args.get('folder', 'train')
    if folder not in SUBDIRS:
        return jsonify({'error': 'Invalid folder'}), 400

    images = []
    dir_path = os.path.join(DATASET_ROOT, folder)

    if os.path.exists(dir_path):
        try:
            files = [f for f in os.listdir(dir_path) if is_image_file(f)]
            files.sort()

            for filename in files:
                full_path = os.path.join(dir_path, filename)
                size_bytes = os.path.getsize(full_path)
                images.append({
                    'path': os.path.join(folder, filename),
                    'name': filename,
                    'folder': folder,
                    'size': size_bytes
                })
        except OSError as e:
            print(f"Error accessing {dir_path}: {e}")

    return jsonify(images)

@app.route('/image/<path:filepath>')
def serve_image(filepath):
    directory = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    abs_dir = os.path.join(DATASET_ROOT, directory)
    return send_from_directory(abs_dir, filename)

@app.route('/delete/<path:filepath>', methods=['DELETE'])
def delete_image(filepath):
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    full_path = os.path.join(DATASET_ROOT, filepath)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            base_name = os.path.splitext(full_path)[0]
            txt_path = base_name + '.txt'
            if os.path.exists(txt_path):
                os.remove(txt_path)

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/select/<path:filepath>', methods=['POST'])
def select_image(filepath):
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    src_path = os.path.join(DATASET_ROOT, filepath)
    filename = os.path.basename(filepath)
    dst_folder = os.path.join(DATASET_ROOT, 'selected')
    dst_path = os.path.join(dst_folder, filename)

    if os.path.exists(src_path):
        try:
            if os.path.exists(dst_path):
                name, ext = os.path.splitext(filename)
                timestamp = int(time.time())
                new_filename = f"{name}_{timestamp}{ext}"
                dst_path = os.path.join(dst_folder, new_filename)

            shutil.move(src_path, dst_path)

            src_base = os.path.splitext(src_path)[0]
            src_txt = src_base + '.txt'
            if os.path.exists(src_txt):
                dst_base = os.path.splitext(dst_path)[0]
                dst_txt = dst_base + '.txt'
                shutil.move(src_txt, dst_txt)

            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'File not found'}), 404

@app.route('/api/labels/<path:filepath>')
def get_labels(filepath):
    parts = filepath.split('/')
    if not parts or parts[0] not in SUBDIRS:
        return jsonify({'error': 'Invalid path'}), 400

    folder = parts[0]
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]
    txt_name = base_name + '.txt'

    label_paths = [
        os.path.join(DATASET_ROOT, 'Labels', f'{folder}-labels', 'labels', txt_name),
        os.path.join(DATASET_ROOT, 'Labels', f'{folder}-labels', txt_name),
        os.path.join(DATASET_ROOT, folder, txt_name)
    ]

    final_path = None
    for path in label_paths:
        if os.path.exists(path):
            final_path = path
            break

    labels = []
    if final_path:
        try:
            with open(final_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        labels.append({
                            'class': int(parts[0]),
                            'x': float(parts[1]),
                            'y': float(parts[2]),
                            'w': float(parts[3]),
                            'h': float(parts[4])
                        })
        except Exception as e:
            print(f"Error reading label file {final_path}: {e}")
            return jsonify({'error': str(e)}), 500

    return jsonify(labels)

if __name__ == '__main__':
    print(f"Serving dataset from: {DATASET_ROOT}")
    app.run(host='0.0.0.0', port=5000, debug=True)
