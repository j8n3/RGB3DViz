import sqlite3
import io
import numpy as np
from PIL import Image, UnidentifiedImageError
from pathlib import Path
import os # Still needed for cpu_count for webp saving efficiency

# --- Configuration ---
SOURCE_FOLDER = Path("/home/dome/Pictures/Screenshots/")  # CHANGE to your image folder path
DATABASE_FILE = Path("./image_ss_database.db")
TARGET_RESOLUTION = (1290, 720)
IMAGE_FORMAT = "WEBP"
# List common image extensions Pillow can usually handle
SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

# --- Ensure source folder exists ---
if not SOURCE_FOLDER.is_dir():
    print(f"Error: Source folder '{SOURCE_FOLDER}' not found.")
    print("Please create it and add images.")
    exit()

# --- Database Setup ---
print(f"Connecting to database: {DATABASE_FILE}")
try:
    # Using 'with' ensures connection is closed automatically
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_filename TEXT NOT NULL,
                webp_blob BLOB NOT NULL,
                avg_r INTEGER,
                avg_g INTEGER,
                avg_b INTEGER
            )
        ''')
        print("Database table 'images' ensured.")

        # --- Process Images ---
        print(f"Processing images from: {SOURCE_FOLDER}")
        processed_count = 0
        skipped_count = 0

        for file_path in SOURCE_FOLDER.glob('*'):
            # Check if it's a file and has a supported extension
            if not file_path.is_file() or file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue # Skip directories or unsupported file types

            print(f"Processing: {file_path.name}...", end="")
            try:
                with Image.open(file_path) as img:
                    # Resize (LANCZOS is high quality)
                    img_resized = img.resize(TARGET_RESOLUTION, Image.Resampling.LANCZOS)

                    # Calculate average RGB
                    # Convert to RGB first to handle formats like RGBA, P, L
                    img_rgb = img_resized.convert('RGB')
                    avg_color = np.array(img_rgb).mean(axis=(0, 1)).astype(int) # Avg over height, width

                    # Convert to WEBP in memory
                    with io.BytesIO() as buffer:
                        # Use multiple threads if available for potentially faster saving
                        img_resized.save(
                            buffer,
                            format=IMAGE_FORMAT,
                            quality=85, # Adjust quality vs size as needed (0-100)
                            method=6, # Preset for balancing quality and speed (0=fastest, 6=slowest/best)
                            # Use lossless=True if desired, but often larger file size
                        )
                        webp_data = buffer.getvalue()

                    # Insert into database
                    cursor.execute(
                        "INSERT INTO images (original_filename, webp_blob, avg_r, avg_g, avg_b) VALUES (?, ?, ?, ?, ?)",
                        (file_path.name, webp_data, int(avg_color[0]), int(avg_color[1]), int(avg_color[2]))
                    )
                    print(f" Done. Avg RGB: {tuple(avg_color)}")
                    processed_count += 1

            except UnidentifiedImageError:
                print(f" Skipped (not a valid image file).")
                skipped_count += 1
            except Exception as e:
                print(f" Error: {e}")
                skipped_count += 1

        # Commit changes (though 'with' context manager often handles this on successful exit)
        conn.commit()
        print("-" * 20)
        print(f"Processing complete.")
        print(f"Successfully processed and added: {processed_count} images.")
        print(f"Skipped due to errors or format: {skipped_count} files.")

except sqlite3.Error as e:
    print(f"Database error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
