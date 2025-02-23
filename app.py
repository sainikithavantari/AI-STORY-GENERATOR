from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import sqlite3
from transformers import pipeline
import random
from datetime import datetime
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

app = Flask(__name__)
CORS(app)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# Load AI model
story_generator = pipeline("text-generation", model="gpt2")

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    
    # Drop the existing table if it exists
    c.execute("DROP TABLE IF EXISTS stories")
    
    # Create the table with the updated schema
    c.execute('''CREATE TABLE IF NOT EXISTS stories
                 (id INTEGER PRIMARY KEY, 
                  theme TEXT, 
                  character TEXT, 
                  story TEXT, 
                  category TEXT, 
                  length TEXT,
                  views INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

# Serve the index.html file directly
@app.route("/")
def index():
    return send_file("index.html")

@app.route("/generate-story", methods=["POST"])
@limiter.limit("5 per minute")  # Rate limit story generation
def generate_story():
    data = request.json
    theme = data.get("theme", "fantasy")
    character = data.get("character", "Alex")
    length = data.get("length", "medium")
    category = data.get("category", "General")
    prompt = f"A {theme} story about {character}: "

    # Adjust max_length based on the selected length
    if length == "short":
        max_length = 200
    elif length == "medium":
        max_length = 500
    else:
        max_length = 1000

    # Generate AI story
    response = story_generator(prompt, max_length=max_length, num_return_sequences=1)
    story = response[0]["generated_text"]

    # Save to database
    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    c.execute("INSERT INTO stories (theme, character, story, category, length) VALUES (?, ?, ?, ?, ?)", 
              (theme, character, story, category, length))
    conn.commit()
    conn.close()

    return jsonify({"story": story})

@app.route("/get-stories", methods=["GET"])
def get_stories():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    length = request.args.get('length', '')

    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    query = "SELECT * FROM stories WHERE (theme LIKE ? OR character LIKE ?) AND (category LIKE ?) AND (length LIKE ?) ORDER BY id DESC LIMIT ? OFFSET ?"
    c.execute(query, (f'%{search}%', f'%{search}%', f'%{category}%', f'%{length}%', per_page, (page - 1) * per_page))
    stories = c.fetchall()
    conn.close()

    return jsonify({"stories": stories})

@app.route("/update-story/<int:story_id>", methods=["PUT"])
def update_story(story_id):
    data = request.json
    new_story = data.get("story")

    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    c.execute("UPDATE stories SET story = ? WHERE id = ?", (new_story, story_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Story updated successfully"})

@app.route("/delete-story/<int:story_id>", methods=["DELETE"])
def delete_story(story_id):
    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    c.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Story deleted successfully"})

@app.route("/export-story/<int:story_id>", methods=["GET"])
def export_story(story_id):
    conn = sqlite3.connect('stories.db')
    c = conn.cursor()
    c.execute("SELECT story FROM stories WHERE id = ?", (story_id,))
    story = c.fetchone()
    conn.close()

    if story:
        with open(f"story_{story_id}.txt", "w") as file:
            file.write(story[0])
        return send_file(f"story_{story_id}.txt", as_attachment=True)
    else:
        return jsonify({"message": "Story not found"}), 404

@app.route("/random-story", methods=["GET"])
def random_story():
    themes = ["fantasy", "sci-fi", "mystery", "romance", "adventure"]
    characters = ["Alex", "Jordan", "Taylor", "Morgan", "Casey"]
    theme = random.choice(themes)
    character = random.choice(characters)
    prompt = f"A {theme} story about {character}: "

    response = story_generator(prompt, max_length=500, num_return_sequences=1)
    story = response[0]["generated_text"]

    return jsonify({"story": story})

if __name__ == "__main__":
    init_db()  # Reinitialize the database with the updated schema
    app.run(debug=True)
