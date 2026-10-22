import os
import shutil
import hashlib
import json
from pathlib import Path
import time
import signal
import sys

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
CHUNK = 524_288      # 512KB برای hash
COPY_BUF = 8 * 1024 * 1024  # 8MB buffer برای copy
# ================================================

# ---- برای Ctrl+C ----
interrupted = False

def handle_interrupt(sig, frame):
    global interrupted
    print("\n\n⚠️  Ctrl+C دریافت شد - در حال ذخیره و خروج...")
    interrupted = True

signal.signal(signal.SIGINT, handle_interrupt)
# ---------------------

def partial_hash(filepath):
    size = os.path.getsize(filepath)
    h = hashlib.md5(usedforsecurity=False)
    h.update(str(size).encode())
    with open(filepath, 'rb') as f:
        h.update(f.read(CHUNK))
        if size > CHUNK * 2:
            f.seek(-CHUNK, 2)
            h.update(f.read(CHUNK))
    return h.hexdigest()

def fast_copy(src, dst):
    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
        while buf := fsrc.read(COPY_BUF):
            fdst.write(buf)
    shutil.copystat(src, dst)

def load_progress():
    """با هر ساختاری که progress داشت کار میکنه"""
    if not os.path.exists(PROGRESS_FILE):
        return {"hashes": {}, "done": [], "copied": 0, "dupes": 0, "errors": []}
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            old = json.load(f)
        # normalize - هر کلیدی که نبود رو با default پر کن
        return {
            "hashes":  old.get("hashes")  or old.get("copied_hashes") or {},
            "done":    old.get("done")    or old.get("processed_files") or [],
            "copied":  old.get("copied")  or old.get("copied_count") or 0,
            "dupes":   old.get("dupes")   or old.get("skipped_duplicates") or 0,
            "errors":  old.get("errors")  or [],
        }
    except Exception as e:
        print(f"⚠️  فایل progress خراب بود، از صفر شروع میکنیم: {e}")
        return {"hashes": {}, "done": [], "copied": 0, "dupes": 0, "errors": []}

def save_progress(p):
    os.makedirs(DEST_DIR, exist_ok=True)
    tmp = PROGRESS_FILE + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False)
    os.replace(tmp, PROGRESS_FILE)

def collect_files():
    files = []
    for src_dir in SOURCE_DIRS:
        if not os.path.exists(src_dir):
            print(f"⚠️  پیدا نشد: {src_dir}")
            continue
        for root, _, filenames in os.walk(src_dir):
            for fn in filenames:
                if Path(fn).suffix.lower() in IMAGE_EXTENSIONS:
                    files.append(os.path.join(root, fn))
    return files

def get_dest_path(dest_dir, filename):
    p = os.path.join(dest_dir, filename)
    if not os.path.exists(p):
        return p
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while True:
        p = os.path.join(dest_dir, f"{stem}_({i}){suffix}")
        if not os.path.exists(p):
            return p
        i += 1

def fmt_size(b):
    for u in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}TB"

def fmt_time(s):
    s = int(s)
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}m {s%60}s"
    return f"{s//3600}h {(s%3600)//60}m"

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    p = load_progress()
    done_set = set(p["done"])

    print("🔍 جمع‌آوری فایل‌ها...")
    all_files = collect_files()
    total = len(all_files)
    remaining = [f for f in all_files if f not in done_set]
    total_size = sum(os.path.getsize(f) for f in remaining)

    print(f"{'='*60}")
    print(f"📦 کل فایل:       {total}")
    print(f"⏳ باقیمانده:     {len(remaining)}")
    print(f"💾 حجم باقیمانده: {fmt_size(total_size)}")
    print(f"{'='*60}\n")

    start_time = time.time()
    processed_size = 0

    for i, src in enumerate(remaining, 1):
        if interrupted:
            break

        fname = os.path.basename(src)
        fsize = os.path.getsize(src)
        pct = ((len(done_set) + i) / total * 100)

        elapsed = time.time() - start_time
        if processed_size > 0 and elapsed > 2:
            speed = processed_size / elapsed
            eta = fmt_time((total_size - processed_size) / speed)
            speed_str = f"{fmt_size(speed)}/s"
        else:
            eta = "..."
            speed_str = "..."

        print(f"[{pct:5.1f}%] [{i}/{len(remaining)}]  {fname}  ({fmt_size(fsize)})  🚀{speed_str}  ⏱{eta}")

        try:
            h = partial_hash(src)

            if h in p["hashes"]:
                print(f"         🔁 تکراری = {p['hashes'][h]}")
                p["dupes"] += 1
            else:
                dst = get_dest_path(DEST_DIR, fname)
                fast_copy(src, dst)
                p["hashes"][h] = os.path.basename(dst)
                p["copied"] += 1

            p["done"].append(src)
            done_set.add(src)
            processed_size += fsize

            if i % 25 == 0:
                save_progress(p)

        except Exception as e:
            print(f"         ❌ خطا: {e}")
            p["errors"].append({"file": src, "error": str(e)})

    # همیشه آخر ذخیره کن - چه تموم شه چه Ctrl+C
    save_progress(p)

    if interrupted:
        print(f"\n⏸️  متوقف شد - progress ذخیره شد")
        print(f"   ✅ این دفعه کپی شد: {p['copied']} فایل")
        print(f"   برای ادامه دوباره اجرا کن: python transfare.py")
    else:
        total_time = fmt_time(time.time() - start_time)
        print(f"\n{'='*60}")
        print(f"🎉 تموم شد!  ({total_time})")
        print(f"   ✅ کپی شد:   {p['copied']} فایل")
        print(f"   🔁 تکراری:   {p['dupes']} فایل")
        print(f"   ❌ خطا:      {len(p['errors'])} فایل")
        if p['errors']:
            print(f"\n   فایل‌های خطادار:")
            for e in p['errors']:
                print(f"   - {e['file']}: {e['error']}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()