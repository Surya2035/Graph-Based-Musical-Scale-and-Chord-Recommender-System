from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()
URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

app = FastAPI(title="Music Scale & Chord Recommender")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev; tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecommendRequest(BaseModel):
    genre: str
    mood: Optional[str] = None
    partial_chords: Optional[List[str]] = None  # e.g., ["Am","F"]

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/recommend")
def recommend(req: RecommendRequest):
    with driver.session() as ses:
        if req.mood:
            q = """
            MATCH (g:Genre {name:$genre})-[:HAS_MOOD]->(m:Mood {name:$mood})
            MATCH (m)-[:SUGGESTS_SCALE]->(s:Scale)
            OPTIONAL MATCH (s)-[:HAS_CHORD]->(c:Chord)
            OPTIONAL MATCH (p:Progression)-[:FOR_GENRE]->(g),
                           (p)-[:FOR_SCALE]->(s)
            OPTIONAL MATCH (p)-[st:STEP]->(pc:Chord)
            WITH s, collect(DISTINCT c.name) AS scale_chords, p, st, pc
            ORDER BY coalesce(st.pos, 9999)
            WITH s, scale_chords, p, collect(pc.name) AS progression_chords
            RETURN s.name AS scale, scale_chords, p.id AS progression_id, progression_chords
            """
            res = ses.run(q, genre=req.genre, mood=req.mood).data()
        else:
            q = """
            MATCH (g:Genre {name:$genre})-[:HAS_MOOD]->(m)
            MATCH (m)-[:SUGGESTS_SCALE]->(s:Scale)
            OPTIONAL MATCH (s)-[:HAS_CHORD]->(c:Chord)
            OPTIONAL MATCH (p:Progression)-[:FOR_GENRE]->(g),
                           (p)-[:FOR_SCALE]->(s)
            OPTIONAL MATCH (p)-[st:STEP]->(pc:Chord)
            WITH s, collect(DISTINCT c.name) AS scale_chords, p, st, pc
            ORDER BY coalesce(st.pos, 9999)
            WITH s, scale_chords, p, collect(pc.name) AS progression_chords
            RETURN s.name AS scale, scale_chords, p.id AS progression_id, progression_chords
            """
            res = ses.run(q, genre=req.genre).data()

        # Simple scoring via partial chords
        scored = []
        partial = set(req.partial_chords or [])
        for row in res:
            chords = set([c for c in row.get("scale_chords", []) if c])
            progression = row.get("progression_chords") or []
            match_score = len(partial.intersection(chords)) if partial else 0
            scored.append({
                "scale": row["scale"],
                "scale_chords": sorted(chords),
                "progression_id": row.get("progression_id"),
                "progression_chords": progression,
                "match_score": match_score
            })

        scored.sort(key=lambda x: (x["match_score"], len(x.get("progression_chords") or [])), reverse=True)
        return {"genre": req.genre, "mood": req.mood, "results": scored[:5]}
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
