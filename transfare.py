import os
import shutil
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
MAX_WORKERS = 6  # تعداد thread همزمان - میتونی بیشتر کنی
# ================================================

lock = threading.Lock()

def get_partial_hash(filepath, bytes_to_read=1_048_576):  # فقط 1MB اول و آخر
    """خیلی سریع‌تر از hash کامل - برای 99.9% کافیه"""
    h = hashlib.xxhash.xxh64() if hasattr(hashlib, 'xxhash') else hashlib.md5()
    size = os.path.getsize(filepath)
    with open(filepath, 'rb') as f:
        # 1MB اول
        h.update(f.read(bytes_to_read))
        # 1MB آخر (اگه فایل بزرگه)
        if size > bytes_to_read * 2:
            f.seek(-bytes_to_read, 2)
            h.update(f.read(bytes_to_read))
        # size رو هم اضافه کن
        h.update(str(size).encode())
    return h.hexdigest()

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "copied_hashes": {},
        "processed_files": [],
        "skipped_duplicates": 0,
        "copied_count": 0
    }

def save_progress(progress):
    os.makedirs(DEST_DIR, exist_ok=True)
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROGRESS_FILE)  # atomic write

def collect_all_files():
    all_files = []
    for src_dir in SOURCE_DIRS:
        if not os.path.exists(src_dir):
            print(f"⚠️  فولدر پیدا نشد: {src_dir}")
            continue
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                if Path(fname).suffix.lower() in IMAGE_EXTENSIONS:
                    all_files.append(os.path.join(root, fname))
    return all_files

def get_unique_dest_name(dest_dir, filename):
    dest_path = os.path.join(dest_dir, filename)
    if not os.path.exists(dest_path):
        return dest_path
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        new_path = os.path.join(dest_dir, f"{stem}_({counter}){suffix}")
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def process_file(src_path, progress, already_processed):
    """پردازش یک فایل - برای thread pool"""
    if src_path in already_processed:
        return "skip_already", src_path, None

    try:
        file_hash = get_partial_hash(src_path)
        return "hash_done", src_path, file_hash
    except Exception as e:
        return "error", src_path, str(e)

def main():
    print("=" * 60)
    print("📷  شروع انتقال تصاویر (حالت سریع)")
    print(f"📁  مقصد: {DEST_DIR}")
    print(f"⚡  threads: {MAX_WORKERS}")
    print("=" * 60)

    os.makedirs(DEST_DIR, exist_ok=True)
    progress = load_progress()
    already_processed = set(progress["processed_files"])
    copied_hashes = progress["copied_hashes"]

    print("🔍 جمع‌آوری فایل‌ها...")
    all_files = collect_all_files()
    total = len(all_files)
    remaining = [f for f in all_files if f not in already_processed]
    print(f"✅ {total} فایل کل | {len(remaining)} باقیمانده\n")

    completed = len(already_processed)
    save_counter = 0

    # hash کردن موازی
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(get_partial_hash, fp): fp
            for fp in remaining
        }

        for future in as_completed(futures):
            src_path = futures[future]
            completed += 1
            pct = (completed / total) * 100
            fname = os.path.basename(src_path)

            try:
                file_hash = future.result()

                with lock:
                    if file_hash in copied_hashes:
                        print(f"[{pct:5.1f}%] 🔁 تکراری  {fname}")
                        progress["skipped_duplicates"] += 1
                    else:
                        dest_path = get_unique_dest_name(DEST_DIR, fname)
                        shutil.copy2(src_path, dest_path)
                        copied_hashes[file_hash] = os.path.basename(dest_path)
                        progress["copied_count"] += 1
                        print(f"[{pct:5.1f}%] ✅ کپی      {fname}")

                    progress["processed_files"].append(src_path)
                    save_counter += 1
                    if save_counter % 20 == 0:
                        save_progress(progress)

            except Exception as e:
                print(f"[{pct:5.1f}%] ❌ خطا  {fname}: {e}")

    save_progress(progress)

    print("\n" + "=" * 60)
    print("🎉 تموم شد!")
    print(f"   ✅ کپی شد:       {progress['copied_count']} فایل")
    print(f"   🔁 تکراری skip:  {progress['skipped_duplicates']} فایل")
    print(f"   📁 مقصد:         {DEST_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()