import weaviate

# ----------------------------
# Configuration
# ----------------------------
WEAVIATE_URL = "http://localhost:8081"
API_KEY = "adminkey"
CLASS_NAME = "MYDATA"

# ----------------------------
# Connect to Weaviate
# ----------------------------
client = weaviate.Client(
    url=WEAVIATE_URL,
    auth_client_secret=weaviate.AuthApiKey(API_KEY)
)

if not client.is_ready():
    print("Weaviate is not ready. Check the server.")
    exit(1)

print("✅ Connected to Weaviate")

# ----------------------------
# Query all objects (optional)
# ----------------------------
all_objects = client.data_object.get(class_name=CLASS_NAME)
print("\n--- All objects in the class ---")
for obj in all_objects["objects"]:
    print("Properties:", obj.get("properties"))
    print("ID:", obj.get("id"))
    print("---")

# ----------------------------
# Semantic search query
# ----------------------------
query_text = "How do I create an account?"

results = (
    client.query
    .get("MYDATA", ["title", "text"])
    .with_near_text({"concepts": [query_text]})
    .with_limit(5)
    .do()
)

for obj in results["data"]["Get"]["MYDATA"]:
    print(obj["title"])
    print(obj["text"])
    print("---")
