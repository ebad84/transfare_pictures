import os
import shutil
import hashlib
import json
from pathlib import Path
from datetime import datetime

# ==================== CONFIG ====================
SOURCE_DIRS = [
    r"E:\CAMERA SHITS\1404 06 09",
    r"E:\CAMERA SHITS\1404 06 26",
    r"E:\CAMERA SHITS\1404 06 29",
]
DEST_DIR = r"D:\all_camera_shits"
PROGRESS_FILE = r"D:\all_camera_shits\_progress.json"
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.raw', '.cr2', '.cr3',
    '.nef', '.arw', '.dng', '.heic', '.heif', '.tiff',
    '.tif', '.bmp', '.mp4', '.mov', '.avi', '.mkv'
}
# ================================================

def get_file_hash(filepath, chunk_size=65536):
    """SHA256 hash of file content"""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"copied_hashes": {}, "processed_files": [], "skipped_duplicates": 0, "copied_count": 0}

def save_progress(progress):
    os.makedirs(DEST_DIR, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def collect_all_files():
    all_files = []
    for src_dir in SOURCE_DIRS:
        if not os.path.exists(src_dir):
            print(f"⚠️  فولدر پیدا نشد: {src_dir}")
            continue
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    all_files.append(os.path.join(root, fname))
    return all_files

def get_unique_dest_name(dest_dir, filename):
    """اگه اسم فایل تکراری بود (ولی محتوا فرق داشت) یه اسم جدید بده"""
    dest_path = os.path.join(dest_dir, filename)
    if not os.path.exists(dest_path):
        return dest_path
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        new_name = f"{stem}_({counter}){suffix}"
        new_path = os.path.join(dest_dir, new_name)
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def main():
    print("=" * 60)
    print("📷  شروع انتقال تصاویر")
    print(f"📁  مقصد: {DEST_DIR}")
    print("=" * 60)

    os.makedirs(DEST_DIR, exist_ok=True)
    progress = load_progress()
    
    already_processed = set(progress["processed_files"])
    copied_hashes = progress["copied_hashes"]  # hash -> dest_filename

    print("🔍 در حال جمع‌آوری لیست فایل‌ها...")
    all_files = collect_all_files()
    total = len(all_files)
    print(f"✅ {total} فایل پیدا شد\n")

    for i, src_path in enumerate(all_files, 1):
        # نشون بده چند درصد کل کار پیش رفته
        pct = (i / total) * 100
        print(f"[{pct:5.1f}%] ({i}/{total})  {os.path.basename(src_path)}", end=" ... ")

        # اگه قبلاً پردازش شده skip کن
        if src_path in already_processed:
            print("⏭️  قبلاً پردازش شده")
            continue

        try:
            file_hash = get_file_hash(src_path)

            if file_hash in copied_hashes:
                print(f"🔁 تکراری (= {copied_hashes[file_hash]})")
                progress["skipped_duplicates"] += 1
            else:
                dest_path = get_unique_dest_name(DEST_DIR, os.path.basename(src_path))
                # copy2 متادیتا و تاریخ رو حفظ می‌کنه
                shutil.copy2(src_path, dest_path)
                copied_hashes[file_hash] = os.path.basename(dest_path)
                progress["copied_count"] += 1
                print(f"✅ کپی شد → {os.path.basename(dest_path)}")

            progress["processed_files"].append(src_path)
            progress["copied_hashes"] = copied_hashes

            # هر 10 فایل progress رو ذخیره کن
            if i % 10 == 0:
                save_progress(progress)

        except Exception as e:
            print(f"❌ خطا: {e}")
            save_progress(progress)
            continue

    save_progress(progress)

    print("\n" + "=" * 60)
    print("🎉 تموم شد!")
    print(f"   ✅ کپی شد:       {progress['copied_count']} فایل")
    print(f"   🔁 تکراری skip:  {progress['skipped_duplicates']} فایل")
    print(f"   📁 مقصد:         {DEST_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()