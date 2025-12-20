# Dataset Manager

A simple web-based tool for managing and visualizing YOLO dataset images. Built for our graduation project to make dataset cleanup easier.

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)

## Features

- Browse images across train/test/valid folders
- View YOLO bounding box annotations
- Delete bad images or move them to a "selected" folder
- Keyboard shortcuts for quick navigation
- Team collaboration using VS Code Live Share

## Setup

```bash
# Clone into your dataset root directory
cd /path/to/your-dataset-root
git clone https://github.com/yourusername/Dataset-Manager.git
cd Dataset-Manager

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

Open `http://localhost:5000` in your browser.

## Directory Structure

```
dataset-root/
├── Dataset-Manager/    # This repo
├── train/              # Training images
├── test/               # Test images
├── valid/              # Validation images
└── Labels/             # YOLO label files
    ├── train-labels/labels/
    ├── test-labels/labels/
    └── valid-labels/labels/
```

## Usage

- Click any image to view it with annotations
- Use arrow keys to navigate between images
- Press `Del` to delete, `Enter` to select/move to selected folder
- Press `Esc` to close the viewer

## Team Collaboration

We used VS Code's Live Share extension during development. One person runs the app, shares their VS Code session, and everyone can access it together. Makes dataset curation much faster when working as a team.

## Notes

- Supports `.jpg`, `.png`, `.webp` images
- YOLO labels should be in standard format: `class_id x_center y_center width height`
- The app creates a `selected/` folder automatically for curated images
