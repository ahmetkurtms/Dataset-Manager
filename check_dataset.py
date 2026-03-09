"""Quick script to analyze the unified_dataset2 structure."""
import os, glob

DATASET = os.path.expanduser("~/Downloads/unified_dataset2/unified_dataset2")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Count files per split/modality/class
print("=== Dataset Structure ===")
total = 0
for split in sorted(os.listdir(DATASET)):
    split_path = os.path.join(DATASET, split)
    if not os.path.isdir(split_path) or split.startswith('.'):
        continue
    for mod in sorted(os.listdir(split_path)):
        mod_path = os.path.join(split_path, mod)
        if not os.path.isdir(mod_path) or mod.startswith('.'):
            continue
        for cls in sorted(os.listdir(mod_path)):
            cls_path = os.path.join(mod_path, cls)
            if not os.path.isdir(cls_path) or cls.startswith('.'):
                continue
            img_dir = os.path.join(cls_path, 'images')
            lbl_dir = os.path.join(cls_path, 'labels')
            imgs = len(glob.glob(os.path.join(img_dir, '*'))) if os.path.isdir(img_dir) else 0
            lbls = len(glob.glob(os.path.join(lbl_dir, '*.txt'))) if os.path.isdir(lbl_dir) else 0
            total += imgs
            print(f"  {split}/{mod}/{cls}: {imgs} images, {lbls} labels")

            # Check image resolution (first 3 images)
            if HAS_PIL and os.path.isdir(img_dir):
                for f in sorted(os.listdir(img_dir))[:3]:
                    if f.lower().endswith(('.jpg','.jpeg','.png')):
                        try:
                            img = Image.open(os.path.join(img_dir, f))
                            print(f"    -> {f}: {img.size[0]}x{img.size[1]}")
                        except:
                            pass

            # Check label content (first label)
            if os.path.isdir(lbl_dir):
                for f in sorted(os.listdir(lbl_dir))[:1]:
                    lbl_path = os.path.join(lbl_dir, f)
                    with open(lbl_path) as lf:
                        lines = lf.readlines()
                        for line in lines:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                w, h = float(parts[3]), float(parts[4])
                                pct = w * h * 100
                                print(f"    -> label sample: class={parts[0]}, bbox_w={w:.4f}, bbox_h={h:.4f}, obj_area={pct:.2f}%")

print(f"\nTotal images: {total}")
