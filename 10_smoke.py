import os
from google import genai
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
r = client.models.embed_content(model="gemini-embedding-001", contents=["hippurate reference limit"])
print("dimensi embedding:", len(r.embeddings[0].values))
