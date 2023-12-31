from fastapi import FastAPI, Query, HTTPException
from typing import List, Optional
import httpx 
from pydantic import BaseModel 
from dotenv import load_dotenv
import os

#load the api key stored in .env
load_dotenv()  

#model to be used as a structure of the dictionary expected to be received by the post endpoint. 
class Movie(BaseModel):
    title: str
    year: int
    genre: str
    overview: str
    vote_average: float 

# fast api instance 
app = FastAPI()

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'

# Function to fetch and cache genre name-ID mappings since tmdb stores each genre as a numerical id. 
async def get_genre_id_mapping() -> dict:
    url = f"{TMDB_BASE_URL}/genre/movie/list"
    params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        genres = data.get('genres', [])
        return {genre['name'].lower(): genre['id'] for genre in genres}

# Cache for genre IDs to minimize API calls
GENRE_ID_CACHE = None

#helper function handling api call movie fetching
async def fetch_movies_from_tmdb(genre: Optional[str], year: Optional[int]) -> List[dict]:
    global GENRE_ID_CACHE
    if GENRE_ID_CACHE is None:
        GENRE_ID_CACHE = await get_genre_id_mapping()

    query_params = {
        'api_key': TMDB_API_KEY,
        'language': 'en-US',
        'sort_by': 'popularity.desc',
        'include_adult': 'false',
        'include_video': 'false',
        'page': 1,
    }
    if genre:
        genre = genre.lower()
        genre_id = GENRE_ID_CACHE.get(genre)
        if not genre_id:
            raise ValueError(f"Genre '{genre}' not found.")
        query_params['with_genres'] = genre_id
    if year:
        query_params['year'] = year

    #receive up to 5 movies and their data based on the given optional query params
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TMDB_BASE_URL}/discover/movie", params=query_params)
        response.raise_for_status()
        data = response.json()
        movies = data.get('results', [])[:5] 

        #return only the respective movie data fields specified below
        filtered_movies = []
        for movie in movies:
            filtered_movie = {
                'title': movie['title'],
                'release_date': movie['release_date'],
                'vote_average': movie['vote_average'],
                'overview': movie['overview'],
              
            }
            filtered_movies.append(filtered_movie)

        return filtered_movies

#get endpoint expecting to respond with a list of movie dictionaries 
@app.get("/movies/", response_model=List[dict])
async def read_movies(
    genre: Optional[str] = Query(None, min_length=3, max_length=50, description="The genre to filter for."),
    year: Optional[int] = Query(None, description="The year to filter for.")
) -> List[dict]:
    try:
        return await fetch_movies_from_tmdb(genre, year)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

#put endpoint expecting to recieve a movie dictionary from the client based on the local movie model. This is not the Movie response from the api call.  
@app.post("/movies/", response_model=Movie)
def create_movie(movie: Movie):
    return movie

# Run the server with: uvicorn myapi:app --reload
